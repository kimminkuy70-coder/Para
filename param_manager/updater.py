"""프로그램 자동 업데이트 — **OneDrive 저장폴더만 사용**(순수 A안, 인터넷 미사용).

배경 (2026-08 결정)
--------------------
GitHub 직접 폴링/다운로드 방식도 검토했으나 기각했다:
  · CLAUDE.md 확정 제약 '런타임 외부 네트워크 금지' 위반 — 별도 방화벽 예외 승인 필요
  · exe 를 인터넷에서 직접 받으면 Mark-of-the-Web 이 매번 새로 찍혀 Windows Defender/
    SmartScreen 경고가 오히려 **더** 자주 뜬다(이미 겪은 사고와 같은 유형).
그래서 이미 전원이 공유 중인 **OneDrive 저장폴더**를 배포 통로로 쓴다. 개발자가
새 exe 를 빌드해 '새 버전 배포' 메뉴로 게시하면, 각 사용자 프로그램이 시작할 때
버전정보.json 을 읽어 새 버전이면 물어보고 업데이트한다.

폴더 구조 (저장폴더 = OneDrive, 공유)
--------------------------------------
  {저장폴더}/프로그램/
    ├─ 버전정보.json         버전·해시·크기·변경내용·게시자
    └─ PI_Param_Manager.exe  항상 고정 파일명(버전마다 새로 만들지 않음 — 누적 방지)

실행 파일 교체 (로컬, 각 사용자 PC)
------------------------------------
실행 중인 exe 는 자기 자신을 덮어쓸 수 없다. 그래서:
  1) 새 exe 를 로컬 임시폴더(localdirs Temp)로 복사 + 해시 검증
     (OneDrive 동기화가 덜 끝난 파일을 그대로 쓰면 깨진 실행파일이 되므로 필수)
  2) 교체용 배치스크립트(.bat)를 로컬에 생성 — 현재 프로세스 종료 대기 → 기존 exe
     백업(1개만, 누적 안 됨) → 새 exe 로 교체 → 재실행 → 자기 자신 삭제
  3) 그 스크립트를 detached 로 실행하고 앱은 스스로 종료
사용자는 "업데이트할까요?" 확인 한 번만 하면 되고, 재시작은 자동이다.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime

PROGRAM_DIRNAME = "프로그램"
MANIFEST_NAME = "버전정보.json"
PUBLISHED_EXE_NAME = "PI_Param_Manager.exe"     # OneDrive 쪽 고정 파일명(누적 방지)
BACKUP_EXE_NAME = "PI_Param_Manager_이전버전.exe"  # 로컬 롤백용, 항상 1개만


@dataclass
class ReleaseInfo:
    version: str
    filename: str
    sha256: str
    size: int
    changelog: str = ""
    published_at: str = ""
    published_by: str = ""

    def to_dict(self) -> dict:
        return {"version": self.version, "filename": self.filename,
                "sha256": self.sha256, "size": self.size,
                "changelog": self.changelog, "published_at": self.published_at,
                "published_by": self.published_by}

    @staticmethod
    def from_dict(d: dict) -> "ReleaseInfo | None":
        try:
            version = str(d.get("version") or "").strip()
            sha256 = str(d.get("sha256") or "").strip()
            size = int(d.get("size") or 0)
        except (TypeError, ValueError):
            return None
        if not version or not sha256 or size <= 0:
            return None
        return ReleaseInfo(version=version,
                           filename=str(d.get("filename") or PUBLISHED_EXE_NAME),
                           sha256=sha256, size=size,
                           changelog=str(d.get("changelog") or ""),
                           published_at=str(d.get("published_at") or ""),
                           published_by=str(d.get("published_by") or ""))


# --------------------------------------------------------------------------
# 경로
# --------------------------------------------------------------------------
def program_dir(save_dir: str) -> str:
    d = os.path.join(save_dir, PROGRAM_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return d


def manifest_path(save_dir: str) -> str:
    return os.path.join(program_dir(save_dir), MANIFEST_NAME)


def published_exe_path(save_dir: str, release: ReleaseInfo | None = None) -> str:
    name = release.filename if release else PUBLISHED_EXE_NAME
    return os.path.join(program_dir(save_dir), name)


# --------------------------------------------------------------------------
# 버전 비교
# --------------------------------------------------------------------------
def parse_version(text: str) -> tuple[int, ...]:
    """'v3.1.0' / '3.1' / '3.1.0-beta' 등에서 숫자만 뽑아 튜플로. 못 뽑으면 (0,)."""
    import re
    nums = re.findall(r"\d+", str(text or ""))
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums)


def is_newer(remote: str, local: str) -> bool:
    """remote 버전이 local 보다 높은가. 길이가 달라도(예: '3.1' vs '3.1.0')
    올바르게 비교되도록 짧은 쪽을 0으로 채운다."""
    r, l = parse_version(remote), parse_version(local)
    n = max(len(r), len(l))
    r = r + (0,) * (n - len(r))
    l = l + (0,) * (n - len(l))
    return r > l


# --------------------------------------------------------------------------
# 해시/검증
# --------------------------------------------------------------------------
def file_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_download(path: str, release: ReleaseInfo) -> tuple[bool, str]:
    """다운로드(복사)한 파일이 매니페스트와 일치하는가.

    OneDrive 동기화가 덜 끝난 상태에서 복사하면 크기·해시가 어긋나므로, 여기서
    걸러내지 못하면 깨진 exe 로 교체해 프로그램이 실행조차 안 되는 사고가 난다.
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"파일을 읽을 수 없습니다: {e}"
    if size != release.size:
        return False, ("파일 크기가 다릅니다(OneDrive 동기화가 아직 끝나지 않은 "
                       "것 같습니다). 잠시 후 다시 시도하세요.")
    got = file_sha256(path)
    if got.lower() != release.sha256.lower():
        return False, ("파일 내용이 일치하지 않습니다(다운로드가 손상됐을 수 "
                       "있습니다). 잠시 후 다시 시도하세요.")
    return True, ""


# --------------------------------------------------------------------------
# 읽기/게시
# --------------------------------------------------------------------------
def read_manifest(save_dir: str) -> ReleaseInfo | None:
    """버전정보.json 읽기. 없거나 깨졌으면 None(예외 없음 — 업데이트 확인은
    실패해도 프로그램 사용에 지장이 없어야 한다)."""
    try:
        with open(manifest_path(save_dir), encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:  # noqa: BLE001
        return None
    return ReleaseInfo.from_dict(d)


def publish(save_dir: str, exe_path: str, version: str, changelog: str = "",
           user: str | None = None) -> ReleaseInfo:
    """새 exe 를 저장폴더(OneDrive)에 게시 — 고정 파일명으로 덮어쓰고 매니페스트 갱신.

    버전별 파일이 쌓이지 않도록 항상 PUBLISHED_EXE_NAME 하나만 유지한다.
    """
    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"exe 파일을 찾을 수 없습니다: {exe_path}")
    v = parse_version(version)
    if v == (0,):
        raise ValueError(f"버전 번호를 알아볼 수 없습니다: {version!r}")
    dest = published_exe_path(save_dir)
    tmp = dest + ".tmp"
    shutil.copy2(exe_path, tmp)
    os.replace(tmp, dest)                    # 같은 폴더 내 원자적 교체
    release = ReleaseInfo(version=str(version).strip(), filename=PUBLISHED_EXE_NAME,
                          sha256=file_sha256(dest), size=os.path.getsize(dest),
                          changelog=changelog or "",
                          published_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                          published_by=user or "")
    with open(manifest_path(save_dir), "w", encoding="utf-8") as fh:
        json.dump(release.to_dict(), fh, ensure_ascii=False, indent=2)
    return release


# --------------------------------------------------------------------------
# 로컬로 받기 + 교체
# --------------------------------------------------------------------------
def download_to_local(save_dir: str, release: ReleaseInfo, local_root: str) -> str:
    """게시된 exe 를 **로컬 임시폴더**로 복사(OneDrive 에 쓰지 않음). 반환: 로컬 경로."""
    from . import localdirs
    src = published_exe_path(save_dir, release)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"게시된 exe 를 찾을 수 없습니다: {src}")
    run_dir = localdirs.new_temp_run(local_root, "업데이트")
    dest = os.path.join(run_dir, release.filename)
    shutil.copy2(src, dest)
    return dest


def is_frozen() -> bool:
    """PyInstaller 등으로 묶은 실행파일로 돌고 있는가. 소스 실행이면 자동
    업데이트 자체가 의미 없다(교체할 exe 가 없음)."""
    return bool(getattr(sys, "frozen", False))


def current_exe_path() -> str:
    """현재 실행 중인 exe 경로. is_frozen() 이 False 면 무의미."""
    return os.path.abspath(sys.executable)


def build_swap_script(local_dir: str, pid: int, current_exe: str, new_exe: str,
                      backup_path: str) -> str:
    r"""현재 프로세스 종료를 기다렸다가 exe 를 교체하고 재실행하는 .bat 생성.

    실행 중인 exe 는 자기 자신을 못 지우므로 별도 프로세스(cmd)가 필요하다.
    Windows 전용 문법이라 이 환경(Linux)에서는 **실행 검증이 불가** — 내용만 만든다.
    """
    from . import localdirs
    d = localdirs.temp_dir(local_dir)
    script = os.path.join(d, "para_update.bat")
    content = f'''@echo off
setlocal
set "PID={pid}"
set "OLD={current_exe}"
set "NEW={new_exe}"
set "BACKUP={backup_path}"

:wait
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto wait
)
timeout /t 1 /nobreak >NUL

if exist "%OLD%" (
    copy /y "%OLD%" "%BACKUP%" >NUL
)

set RETRY=0
:copyloop
copy /y "%NEW%" "%OLD%" >NUL
if errorlevel 1 (
    set /a RETRY+=1
    if %RETRY% LSS 10 (
        timeout /t 1 /nobreak >NUL
        goto copyloop
    )
)

start "" "%OLD%"

(goto) 2>nul & del "%~f0"
'''
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(content)
    return script


def backup_path_for(local_dir: str, current_exe: str) -> str:
    from . import localdirs
    name = os.path.basename(current_exe) or BACKUP_EXE_NAME
    stem, ext = os.path.splitext(name)
    return os.path.join(localdirs.ensure(local_dir), f"{stem}_이전버전{ext}")
