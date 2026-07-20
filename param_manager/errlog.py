"""오류 코드·로그 유틸(GUI 비의존).

에러 발생 지점마다 고유 코드(E###)를 부여하고, 전체 traceback 을 로그 파일에 남긴다.
사용자에게는 코드가 포함된 메시지를 보여 준다 → 사용자가 코드를 알려주면 개발자가
소스에서 그 코드를 grep 해 발생 지점을 즉시 찾고, 로그의 traceback 으로 원인을 본다.

equip_app 의 _err/_logerr/_write_log 가 이 함수들을 호출한다(그래서 헤드리스 테스트 가능).
"""
from __future__ import annotations

import datetime
import os
import traceback

LOG_NAME = "오류_로그.txt"
_SEP = "-" * 60


def log_path(save_dir=None) -> str:
    """오류 로그 파일 경로. 저장폴더가 있으면 그 안, 없으면 홈 폴더."""
    base = save_dir if save_dir else os.path.expanduser("~")
    return os.path.join(base, LOG_NAME)


def _tb_text(exc) -> str:
    if exc is None:
        return ""
    if isinstance(exc, BaseException):
        return "".join(traceback.format_exception(
            type(exc), exc, exc.__traceback__)).rstrip()
    return str(exc)


def write_log(save_dir, code, title, exc=None) -> bool:
    """오류 1건을 로그 파일에 추가(시각·코드·제목·traceback). 실패해도 앱을 막지 않게 bool."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [f"[{ts}] [{code}] {title}"]
        tb = _tb_text(exc)
        if tb:
            parts.append(tb)
        parts.append(_SEP)
        with open(log_path(save_dir), "a", encoding="utf-8") as f:
            f.write("\n".join(parts) + "\n")
        return True
    except Exception:  # noqa: BLE001  (로깅 실패가 앱을 막지 않게)
        return False


def detail_of(exc) -> str:
    """사용자 화면에 보일 짧은 기술 요약(예: 'ValueError: ...')."""
    if isinstance(exc, BaseException):
        return f"{type(exc).__name__}: {exc}"
    return str(exc) if exc else ""


def user_message(code, title, exc=None, extra=None, path=None) -> str:
    """사용자에게 보여 줄 메시지(코드 강조 + 요약 + 코드 안내 + 로그 경로)."""
    msg = f"[오류 코드 {code}] {title}"
    if extra:
        msg += f"\n\n{extra}"
    d = detail_of(exc)
    if d:
        msg += f"\n\n기술 정보: {d}"
    msg += f"\n\n이 문제를 알릴 때 위 오류 코드({code})를 함께 알려주세요."
    if path:
        msg += f"\n자세한 기록: {path}"
    return msg
