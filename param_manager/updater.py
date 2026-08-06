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
  {저장폴더의 부모}/
    ├─ {저장폴더}/            예: docs — 참고자료·양식·취합 등 데이터
    └─ 프로그램/              **저장폴더 안이 아니라 옆**(형제 폴더)
        ├─ 버전정보.json                          버전·해시·크기·변경내용·게시자
        ├─ Camtek_AOI_Parameter_manage_v3.1.0.exe  최신(매니페스트가 가리키는 것)
        └─ Camtek_AOI_Parameter_manage_v3.0.0.exe  **직전 버전 — 롤백용으로 남긴다**

배포 폴더를 저장폴더 '옆'에 두는 이유: 저장폴더를 `…\docs` 같은 문서용 하위
폴더로 지정해 쓰는 경우가 있어, 안쪽에 만들면 배포 exe 가 문서 폴더에 묻힌다
(2026-08 사용자 지정). 부모 폴더를 못 쓰거나 이미 저장폴더 안에 게시본이 있으면
예전처럼 저장폴더 안을 쓴다 — `resolve_program_dir` 참고.

파일명에 버전이 들어가므로 게시할 때마다 새 파일이 생긴다. 무한정 쌓이면 안 되지만
새 버전에 문제가 생겼을 때 되돌릴 수 있어야 하므로, `publish()` 가 **최신 2개
(신버전 + 직전 구버전)만 남기고** 그보다 오래된 것을 지운다(`KEEP_VERSIONS`).
되돌릴 때는 `프로그램/` 폴더의 구버전 exe 를 그대로 실행하면 된다.

실행 파일 교체 (로컬, 각 사용자 PC)
------------------------------------
실행 중인 exe 는 자기 자신을 덮어쓸 수 없다. 그래서:
  1) 새 exe 를 로컬 임시폴더(localdirs Temp)로 복사 + 해시 검증
     (OneDrive 동기화가 덜 끝난 파일을 그대로 쓰면 깨진 실행파일이 되므로 필수)
  2) 교체용 배치스크립트(.bat)를 로컬에 생성 — 현재 프로세스 종료 대기 → 기존 exe
     백업(1개만, 누적 안 됨) → 새 exe 로 교체 → 재실행 → 자기 자신 삭제
  3) 그 스크립트를 detached 로 실행하고 앱은 스스로 종료
사용자는 "업데이트할까요?" 확인 한 번만 하면 되고, 재시작은 자동이다.

배치스크립트 작성 시 주의 (실제로 문제가 됐던 것들)
---------------------------------------------------
  · **한글 경로 + 인코딩**: cmd.exe 는 .bat 을 UTF-8 이 아니라 시스템 ANSI(한국어
    Windows = cp949)로 읽는다. UTF-8 로 쓰면 한글 경로가 깨져 엉뚱한 파일을 만진다.
    → `_write_bat()` 이 mbcs/cp949 로 쓰고, **우리가 만드는 이름은 전부 ASCII**로 둔다.
  · **`timeout` 금지**: detached(콘솔 없음)로 실행하면 `timeout` 은 입력 핸들이 없어
    "Input redirection is not supported" 로 즉시 실패한다. → `ping` 으로 대기한다.
  · **PID 문자열 매칭 금지**: `tasklist | find "1234"` 는 메모리 사용량 열(예 "1,234 K")
    에도 걸려 영원히 대기할 수 있다. → **파일 잠금**으로 종료를 판정한다.
  · **종료 판정은 반드시 '구 exe 삭제'로**(2026-08 실사고): 파일명에 버전이 들어가
    새 이름은 아무도 잠그고 있지 않으므로 `copy → 새이름` 은 앱이 켜져 있어도 즉시
    성공한다. 그걸 종료 판정으로 쓰면 **앱이 살아 있는 채로 새 프로그램이 떠서
    2개가 동시에 실행**되고, 실행 중이라 지워지지 않은 구 exe 가 남아 다음 실행 때
    또 업데이트 알림이 뜬다. 실행 중인 exe 는 삭제가 불가능하므로
    `del /q "%OLD%"` 성공 = 종료 완료다.
  · **실패 시 원상복구**: 교체가 끝내 실패하면 **기존 exe 를 다시 실행**해 준다.
    그러지 않으면 사용자는 아무것도 실행되지 않은 채 남는다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime

PROGRAM_DIRNAME = "프로그램"
MANIFEST_NAME = "버전정보.json"

# 게시 파일명 — 버전이 올라가면 파일명도 같이 바뀐다(사용자 지정 2026-08).
EXE_STEM = "Camtek_AOI_Parameter_manage"
EXE_PREFIX = f"{EXE_STEM}_v"                    # + 버전 + ".exe"
# 구버전(고정 파일명) 매니페스트 호환용 — 예전 게시본을 계속 읽을 수 있게.
LEGACY_EXE_NAME = "PI_Param_Manager.exe"

# 로컬 롤백 백업 접미사. **ASCII 만** — 배치스크립트에 들어가므로(위 주의 참고).
BACKUP_SUFFIX = "_prev"
# 로컬 임시 폴더 접두사도 ASCII.
TEMP_PREFIX = "update"

# 저장폴더에 남겨 둘 게시본 개수 — **신버전 + 직전 구버전 1개**(사용자 지정 2026-08).
# 새 버전에 문제가 생기면 직전 버전으로 되돌려야 하므로 1개는 반드시 남긴다.
KEEP_VERSIONS = 2


def exe_filename(version: str) -> str:
    """버전 → 게시 파일명. 파일명에 못 쓰는 문자는 제거한다.

    사용자가 'v3.1.0' 처럼 v 를 붙여 입력해도 접두사와 겹쳐 '_vv3.1.0' 이 되지
    않도록 앞의 v 를 떼어낸다.
    예: '3.1.0' / 'v3.1.0' → 'Camtek_AOI_Parameter_manage_v3.1.0.exe'
    """
    safe = re.sub(r'[<>:"/\\|?*\s]+', "", str(version or "").strip())
    safe = re.sub(r"^[vV]+", "", safe)
    return f"{EXE_PREFIX}{safe}.exe"


def is_published_exe(name: str) -> bool:
    """`프로그램/` 폴더에서 우리가 게시한 exe 인가(구버전 고정 파일명 포함)."""
    low = str(name or "").lower()
    return low.endswith(".exe") and (
        low.startswith(EXE_PREFIX.lower()) or low == LEGACY_EXE_NAME.lower())


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
                           # 파일명이 없는 구 매니페스트는 그 시절 고정 이름으로 해석
                           filename=str(d.get("filename") or LEGACY_EXE_NAME),
                           sha256=sha256, size=size,
                           changelog=str(d.get("changelog") or ""),
                           published_at=str(d.get("published_at") or ""),
                           published_by=str(d.get("published_by") or ""))


# --------------------------------------------------------------------------
# 경로
# --------------------------------------------------------------------------
def _has_published_content(d: str) -> bool:
    """이미 게시본(매니페스트나 우리 exe)이 들어 있는 폴더인가."""
    try:
        names = os.listdir(d)
    except OSError:
        return False
    return MANIFEST_NAME in names or any(is_published_exe(n) for n in names)


def legacy_program_dir(save_dir: str) -> str:
    """구 위치 — 저장폴더 **안**. 예전에 게시한 것을 계속 읽기 위해서만 쓴다."""
    return os.path.join(os.path.abspath(str(save_dir or ".")), PROGRAM_DIRNAME)


def resolve_program_dir(save_dir: str) -> str:
    """게시 폴더(정식 위치) 경로 — **만들지는 않는다**(읽기에서 빈 폴더 방지).

    배포용 exe 는 저장폴더 '안'이 아니라 **'옆'(형제 폴더)** 에 둔다. 저장폴더를
    `…\\docs` 처럼 문서용 하위 폴더로 지정해 쓰기 때문에, 안쪽에 만들면 배포
    폴더가 문서 폴더에 묻힌다(2026-08 사용자 지정 — "프로그램 폴더가 docs 안에
    있는데 docs 와 같은 위치에 있도록").

    형제 폴더를 쓸 수 없을 때(저장폴더가 드라이브 루트 / 부모 폴더가 실재하지
    않음)만 예전처럼 저장폴더 안을 쓴다.
    """
    base = os.path.abspath(str(save_dir or "."))
    parent = os.path.dirname(base)
    if not parent or parent == base or not os.path.isdir(parent):
        return os.path.join(base, PROGRAM_DIRNAME)
    return os.path.join(parent, PROGRAM_DIRNAME)


def active_program_dir(save_dir: str) -> str:
    """**읽을** 게시 폴더 — 정식 위치(형제) 우선, 없으면 구 위치(저장폴더 안).

    새 위치로 바꾸기 전에 게시된 버전이 갑자기 안 보이면 안 되므로, 아직
    다시 게시하지 않은 동안에는 구 위치의 게시본을 그대로 읽는다.
    """
    canon = resolve_program_dir(save_dir)
    legacy = legacy_program_dir(save_dir)
    if canon != legacy and not _has_published_content(canon) \
            and _has_published_content(legacy):
        return legacy
    return canon


def program_dir(save_dir: str) -> str:
    """게시 폴더(없으면 생성). 만들 수 없으면 저장폴더 안으로 물러난다 —
    부모 폴더에 쓰기 권한이 없어 게시 자체가 실패하는 일은 없어야 한다."""
    d = resolve_program_dir(save_dir)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = legacy_program_dir(save_dir)
        os.makedirs(d, exist_ok=True)
    return d


def migrate_legacy_program_dir(save_dir: str) -> list[str]:
    """구 위치(저장폴더 안)의 게시물을 정식 위치(형제)로 옮긴다. 반환: 옮긴 파일명.

    게시할 때 한 번 부르면 배포물이 두 곳에 나뉘어 남지 않는다. 실패해도 게시
    자체는 계속돼야 하므로 예외를 밖으로 내보내지 않는다(옮기지 못한 건 그대로 둠).
    """
    legacy = legacy_program_dir(save_dir)
    dest = resolve_program_dir(save_dir)
    if legacy == dest or not _has_published_content(legacy):
        return []
    moved: list[str] = []
    try:
        os.makedirs(dest, exist_ok=True)
        names = [n for n in os.listdir(legacy)
                 if n == MANIFEST_NAME or is_published_exe(n)]
    except OSError:
        return []
    for name in names:
        try:
            shutil.move(os.path.join(legacy, name), os.path.join(dest, name))
            moved.append(name)
        except (OSError, shutil.Error):
            continue                       # 남의 파일이 잠겨 있어도 게시는 계속
    try:
        os.rmdir(legacy)                   # 비었을 때만 지워진다(남의 파일 보존)
    except OSError:
        pass
    return moved


def manifest_path(save_dir: str) -> str:
    return os.path.join(active_program_dir(save_dir), MANIFEST_NAME)


def published_exe_path(save_dir: str, release: ReleaseInfo) -> str:
    """게시된 exe 의 경로. 파일명이 버전마다 다르므로 release 가 반드시 필요하다."""
    return os.path.join(active_program_dir(save_dir), release.filename)


def list_published_exes(save_dir: str) -> list[str]:
    """`프로그램/` 폴더에 있는 우리 exe 파일명 목록(정리 대상 확인용)."""
    d = active_program_dir(save_dir)
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d) if is_published_exe(n))


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


def looks_like_onedir_build(exe_path: str) -> bool:
    """'한 폴더(onedir)' 빌드의 exe 인가 — **혼자서는 실행되지 않는다**.

    build_exe.bat 은 문제 진단용으로 onedir 빌드도 만들 수 있는데, 그 exe 를
    실수로 게시하면 받은 사람 전원이 실행조차 못 한다(옆에 있어야 할
    `_internal/`·python3xx.dll 이 함께 오지 않으므로). 게시 전에 막는다.
    """
    try:
        d = os.path.dirname(os.path.abspath(exe_path))
        if os.path.isdir(os.path.join(d, "_internal")):      # PyInstaller 6 배치
            return True
        return any(n.lower().startswith("python") and n.lower().endswith(".dll")
                   for n in os.listdir(d))                   # 구 배치(exe 옆 DLL)
    except OSError:
        return False


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
    """새 exe 를 저장폴더(OneDrive)에 게시 — **파일명에 버전 포함** + 매니페스트 갱신.

    파일명이 버전마다 달라지므로 게시할 때마다 새 파일이 생긴다. 무한정 쌓이면
    안 되지만 **직전 버전 1개는 남긴다** — 새 버전에 문제가 생기면 되돌려야 하기
    때문이다(항상 신버전 + 직전 구버전 = 2개 유지, `KEEP_VERSIONS`).
    매니페스트는 exe 를 다 쓴 뒤 마지막에 기록한다(중간에 실패하면 이전 매니페스트가
    그대로 남아, 사용자가 존재하지 않는 파일을 받으려다 실패하는 일이 없다).
    """
    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"exe 파일을 찾을 수 없습니다: {exe_path}")
    if parse_version(version) == (0,):
        raise ValueError(f"버전 번호를 알아볼 수 없습니다: {version!r}")

    version = str(version).strip()
    filename = exe_filename(version)
    # 구 위치(저장폴더 안)에 남아 있던 게시물은 정식 위치로 옮겨 한 곳에 모은다
    migrate_legacy_program_dir(save_dir)
    dest = os.path.join(program_dir(save_dir), filename)
    tmp = dest + ".tmp"
    shutil.copy2(exe_path, tmp)
    os.replace(tmp, dest)                    # 같은 폴더 내 원자적 교체

    release = ReleaseInfo(version=version, filename=filename,
                          sha256=file_sha256(dest), size=os.path.getsize(dest),
                          changelog=changelog or "",
                          published_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                          published_by=user or "")
    with open(manifest_path(save_dir), "w", encoding="utf-8") as fh:
        json.dump(release.to_dict(), fh, ensure_ascii=False, indent=2)

    # 새 매니페스트가 자리잡은 뒤 구버전 정리(누적 방지). 실패해도 게시는 유효하다.
    prune_old_exes(save_dir, keep=filename)
    return release


def version_of_filename(name: str) -> tuple[int, ...]:
    """게시 파일명에서 버전 튜플을 뽑는다. 구 고정 파일명은 가장 낮은 (0,).

    정리할 때 '어느 것이 더 최신인가'를 파일 시각이 아니라 **버전 번호**로 판단한다
    (OneDrive 동기화로 파일 시각은 뒤바뀔 수 있어 신뢰할 수 없다).
    """
    base = os.path.basename(str(name or ""))
    stem = os.path.splitext(base)[0]
    if stem.lower().startswith(EXE_PREFIX.lower()):
        return parse_version(stem[len(EXE_PREFIX):])
    return (0,)


def _version_key(name: str) -> tuple:
    """버전 내림차순 정렬용 키(길이 다른 버전도 안전하게 비교)."""
    v = version_of_filename(name)
    return v + (0,) * (8 - len(v)) if len(v) < 8 else v[:8]


def prune_old_exes(save_dir: str, keep: str,
                   keep_count: int = KEEP_VERSIONS) -> list[str]:
    """구버전 exe 정리 — **최신 keep_count 개만 남긴다**(기본 2 = 신버전 + 직전).

    keep(방금 게시한 파일)은 버전 번호와 무관하게 **항상** 남긴다. 나머지는 버전이
    높은 순으로 남기고 그 아래를 지운다. 반환: 지운 파일명 목록.
    """
    d = active_program_dir(save_dir)
    keep_lower = str(keep).lower()
    others = [n for n in list_published_exes(save_dir) if n.lower() != keep_lower]
    others.sort(key=_version_key, reverse=True)     # 최신 버전이 앞으로
    survivors = others[: max(0, int(keep_count) - 1)]
    survive_lower = {n.lower() for n in survivors}

    removed = []
    for name in others:
        if name.lower() in survive_lower:
            continue
        try:
            os.remove(os.path.join(d, name))
            removed.append(name)
        except OSError:
            continue                        # 누가 실행 중이면 다음 게시 때 정리됨
    return removed


# --------------------------------------------------------------------------
# 로컬로 받기 + 교체
# --------------------------------------------------------------------------
def download_to_local(save_dir: str, release: ReleaseInfo, local_root: str) -> str:
    """게시된 exe 를 **로컬 임시폴더**로 복사(OneDrive 에 쓰지 않음). 반환: 로컬 경로."""
    from . import localdirs
    src = published_exe_path(save_dir, release)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"게시된 exe 를 찾을 수 없습니다: {src}")
    # 접두사는 ASCII — 이 경로가 배치스크립트에 그대로 들어간다(인코딩 주의 참고).
    run_dir = localdirs.new_temp_run(local_root, TEMP_PREFIX)
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


def _write_bat(path: str, content: str) -> str:
    """배치스크립트 기록 — cmd.exe 가 읽는 **시스템 ANSI(한국어=cp949)** 로 쓴다.

    UTF-8 로 쓰면 경로에 한글이 있을 때(사용자 폴더·저장폴더 등) 깨져서 엉뚱한
    파일을 건드린다. 개발환경(Linux)에는 'mbcs' 가 없으므로 cp949 → utf-8 순으로
    물러난다. 되돌릴 수 없는 파일 조작을 하는 스크립트라 인코딩은 중요하다.
    """
    for enc in ("mbcs", "cp949", "utf-8"):
        try:
            with open(path, "w", encoding=enc, newline="\r\n") as fh:
                fh.write(content)
            return path
        except (LookupError, UnicodeEncodeError):
            continue
    with open(path, "w", encoding="utf-8", errors="replace",
              newline="\r\n") as fh:                       # 최후 수단
        fh.write(content)
    return path


def local_target_path(current_exe: str, release: ReleaseInfo) -> str:
    """업데이트 후 로컬 exe 경로 — **같은 폴더, 새 버전 파일명**.

    파일명에 버전이 들어가므로 업데이트하면 이름도 바뀐다(사용자 지정). 즉
    `..._v3.0.0.exe` → `..._v3.1.0.exe` 가 되고 구파일은 교체 스크립트가 지운다.
    """
    return os.path.join(os.path.dirname(os.path.abspath(current_exe)),
                        release.filename)


def build_swap_script(local_dir: str, pid: int, current_exe: str, new_exe: str,
                      backup_path: str, target_exe: str | None = None) -> str:
    r"""현재 프로세스 종료를 기다렸다가 exe 를 교체하고 재실행하는 .bat 생성.

    실행 중인 exe 는 자기 자신을 못 지우므로 별도 프로세스(cmd)가 필요하다.

    설계 포인트(모듈 상단 '주의' 참고):
      · 종료 판정을 PID 문자열 매칭이 아니라 **복사 성공 여부**로 한다 — 파일 잠금이
        풀렸다는 건 곧 프로세스가 끝났다는 뜻이고, 로케일/PID 오탐이 없다.
      · 대기는 `timeout` 이 아니라 `ping` — detached 실행에는 콘솔이 없어 `timeout`
        이 즉시 실패한다.
      · 끝내 실패하면 **기존 exe 를 다시 실행**한다(사용자가 빈손으로 남지 않게).
    Windows 전용 문법이라 이 환경(Linux)에서는 실행 검증이 불가 — 내용만 만든다.
    """
    from . import localdirs
    d = localdirs.temp_dir(local_dir)
    script = os.path.join(d, "para_update.bat")
    target = target_exe or current_exe
    # 주석은 **영문(ASCII)만** — 한글을 넣으면 cp949 에 없는 문자 하나(예: em-dash)
    # 때문에 파일 전체가 UTF-8 로 물러나 경로의 한글이 깨진다. 설명은 이 docstring 에.
    # (기존 build_exe.bat 도 같은 이유로 All-ASCII 를 지킨다.)
    # 경로(사용자 폴더에 한글이 있을 수 있음)와 로직 문구를 분리해서, **문구만**
    # ASCII 인지 검사한다. 경로는 cp949 로 기록되므로 한글이어도 안전하다.
    header = (f'@echo off\r\n'
              f'setlocal\r\n'
              f'set "PID={pid}"\r\n'
              f'set "OLD={current_exe}"\r\n'
              f'set "NEW={new_exe}"\r\n'
              f'set "BACKUP={backup_path}"\r\n'
              f'set "TARGET={target}"\r\n')
    body = '''
rem Give the app a moment to close. ping is used instead of timeout because
rem timeout needs a console and this script runs detached.
ping -n 3 127.0.0.1 >nul 2>&1

rem Keep exactly one rollback backup (never accumulates).
if exist "%OLD%" copy /y "%OLD%" "%BACKUP%" >nul 2>&1

rem Wait until the old program has REALLY exited. Windows cannot delete a
rem running exe, so a successful delete is the exit check (locale safe, no PID
rem string matching). We must test the OLD file: the new file name contains the
rem version, so copying to the new name would succeed even while the app runs -
rem that used to start a second copy and leave the old exe behind.
set RETRY=0
:waitloop
if not exist "%OLD%" goto gone
del /q "%OLD%" >nul 2>&1
if not exist "%OLD%" goto gone
set /a RETRY+=1
if %RETRY% LSS 60 (
    ping -n 2 127.0.0.1 >nul 2>&1
    goto waitloop
)

rem Still running after about two minutes: leave everything as it was.
start "" "%OLD%"
goto done

:gone
copy /y "%NEW%" "%TARGET%" >nul 2>&1
if errorlevel 1 goto failed
start "" "%TARGET%"
goto done

:failed
rem The old exe is already gone, so put it back from the backup - the user must
rem never be left without a working program.
if exist "%BACKUP%" copy /y "%BACKUP%" "%OLD%" >nul 2>&1
if exist "%OLD%" start "" "%OLD%"

:done
(goto) 2>nul & del "%~f0"
'''
    if not body.isascii():        # 로직 문구는 반드시 ASCII(cp949 폴백 사고 방지)
        raise ValueError("배치스크립트 문구에 ASCII 가 아닌 문자가 있습니다"
                         "(경로를 뺀 나머지는 영문만 사용).")
    return _write_bat(script, header + body)


def backup_path_for(local_dir: str, current_exe: str) -> str:
    """로컬 롤백용 백업 경로. 배치스크립트에 들어가므로 **ASCII 이름**을 쓴다."""
    from . import localdirs
    name = os.path.basename(current_exe) or f"{EXE_STEM}.exe"
    stem, ext = os.path.splitext(name)
    return os.path.join(localdirs.ensure(local_dir), f"{stem}{BACKUP_SUFFIX}{ext}")
