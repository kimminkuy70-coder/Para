"""tkinter 판 자동 업데이트의 실행 파일 교체 스크립트(.bat) — **tkinter 판 전용**.

`updater.py` 에서 분리함(Para #58, 2026-11). 웹 앱 엔진(sidecar, `tools/desktop_engine_entry.py`)
은 이 모듈을 import 하면 안 된다: PyInstaller 가 이 pyc 를 배포 zip 에 넣으면 자기 삭제 .bat
문구 때문에 Windows Defender 클라우드 ML 이 zip 을 `Trojan:Script/Wacatac.F!ml` 로 막는다.
`tests/test_sidecar_no_scripts.py` 가 고정한다. 웹 앱의 교체는 `desktop_swap.py`(스크립트 없음).

교체 절차 (로컬, 각 사용자 PC)
------------------------------
실행 중인 exe 는 자기 자신을 덮어쓸 수 없다. 그래서:
  1) 새 exe 를 로컬 임시폴더(localdirs Temp)로 복사 + 해시 검증
     (OneDrive 동기화가 덜 끝난 파일을 그대로 쓰면 깨진 실행파일이 되므로 필수)
  2) 교체용 배치스크립트(.bat)를 로컬에 생성 — 현재 프로세스 종료 대기 → 기존 exe
     백업(1개만, 누적 안 됨) → 새 exe 로 교체 → 재실행 → 자기 자신 삭제
  3) 그 스크립트를 detached 로 실행하고 앱은 스스로 종료

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

import os

from .updater import BACKUP_SUFFIX, EXE_STEM, ReleaseInfo


def _write_bat(path: str, content: str) -> str:
    """배치스크립트 기록 — cmd.exe 가 읽는 **시스템 ANSI(한국어=cp949)** 로 쓴다.

    UTF-8 로 쓰면 경로에 한글이 있을 때(사용자 폴더·저장폴더 등) 깨져서 엉뚱한
    파일을 건드린다. 개발환경(Linux)에는 'mbcs' 가 없으므로 cp949 로 검사한다.
    표현 불가능한 경로는 파일 교체 전에 중단한다.
    """
    # Never silently change encoding for a destructive Windows script.
    import codecs
    try:
        codecs.lookup("mbcs")
        enc = "mbcs"
    except LookupError:
        enc = "cp949"  # non-Windows test environment only
    normalized = content.replace("\r\n", "\n").replace("\n", "\r\n")
    data = normalized.encode(enc)  # fail BEFORE creating a partial script
    with open(path, "wb") as fh:
        fh.write(data)
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
    def batch_path(value):
        if any(c in value for c in '\r\n"'):
            raise ValueError("실행파일 경로에 배치 파일에서 사용할 수 없는 문자가 있습니다")
        return value.replace('%', '%%')

    current_exe, new_exe, backup_path, target = map(
        batch_path, (current_exe, new_exe, backup_path, target))
    header = (f'@echo off\r\n'
              f'setlocal DisableDelayedExpansion\r\n'
              f'set "PID={pid}"\r\n'
              f'set "OLD={current_exe}"\r\n'
              f'set "NEW={new_exe}"\r\n'
              f'set "BACKUP={backup_path}"\r\n'
              f'set "TARGET={target}"\r\n')
    body = '''
rem Give the app a moment to close. ping is used instead of timeout because
rem timeout needs a console and this script runs detached.
ping -n 3 127.0.0.1 >nul 2>&1

rem Do not delete the installed program unless a fresh backup succeeded.
if not exist "%OLD%" goto done
copy /y "%OLD%" "%BACKUP%" >nul 2>&1
if errorlevel 1 goto backup_failed
if not exist "%BACKUP%" goto backup_failed
fc /b "%OLD%" "%BACKUP%" >nul 2>&1
if errorlevel 1 goto backup_failed

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
goto done

:backup_failed
rem Leave the installed exe untouched when backup is unavailable.
start "" "%OLD%"

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
