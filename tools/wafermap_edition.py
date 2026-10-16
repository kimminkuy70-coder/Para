"""Wafer Map 전용판(특수 버전) 빌드 도우미 — stdlib 만.

전용판 패키지에는 Wafer Map 변환에 필요한 프로그램 모듈만 들어가야 한다(다른 기능은 배포하지
않는다는 사용자 결정). PyInstaller 는 import 되는 모듈만 묶지만, 일부 공용 모듈이 함수 안에서
다른 모듈을 늦게 import 하므로(예: `desktop_progress` → `localdirs` → `workdirs`) 허용 목록 밖의
`param_manager` 모듈은 빌드 때 `--exclude-module` 로 **명시적으로 뺀다**(늦은 import 는 모두
try/except 안이라 빠져도 동작은 같다 — `tests/test_wafermap_edition.py` 가 고정).

사용:
  python tools/wafermap_edition.py excludes      # PyInstaller 인자(한 줄에 하나) 출력
  python tools/wafermap_edition.py check <dist>  # 빌드 결과에 허용 밖 모듈이 없는지 확인
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "param_manager")

# 전용판이 쓰는 프로그램 모듈(이것만 패키지에 들어간다).
ALLOWED = {
    "__init__", "wafermap_ipc", "wafermap", "desktop_wafermap",
    "desktop_progress", "desktop_diag", "desktop_boot", "singleinst",
}
# 전용판에서 쓰지 않는 외부 패키지(본 앱 tkinter 화면 · 표 라이브러리, openpyxl 의 선택 의존성).
EXTERNAL_EXCLUDES = ("tkinter", "_tkinter", "tksheet", "numpy", "pandas", "PIL")

APP_NAME = "Camtek_AOI_WaferMap"
ENGINE_NAME = "Camtek_AOI_WaferMap_engine"


def program_modules() -> list[str]:
    return sorted(name[:-3] for name in os.listdir(PACKAGE)
                  if name.endswith(".py") and not name.startswith("."))


def excluded_modules() -> list[str]:
    return [f"param_manager.{m}" for m in program_modules() if m not in ALLOWED]


def exclude_args() -> list[str]:
    out = []
    for name in [*excluded_modules(), *EXTERNAL_EXCLUDES]:
        out += ["--exclude-module", name]
    return out


def bundled_program_modules(dist: str) -> list[str]:
    """빌드 결과(onedir, --debug noarchive)에 들어간 param_manager 모듈 이름."""
    found = set()
    for base, _dirs, files in os.walk(dist):
        if os.path.basename(base) != "param_manager":
            continue
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext in (".pyc", ".py"):
                found.add(stem.split(".")[0])
    return sorted(found)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "excludes"
    if cmd == "excludes":
        print("\n".join(exclude_args()))
        return 0
    if cmd == "check" and len(argv) == 2:
        extra = [m for m in bundled_program_modules(argv[1]) if m not in ALLOWED]
        missing = [m for m in ALLOWED if m not in bundled_program_modules(argv[1])]
        if extra:
            print("[ERROR] modules that must not be in the Wafer Map edition: " + ", ".join(extra))
            return 1
        if missing:
            print("[ERROR] Wafer Map edition modules missing from the build: " + ", ".join(sorted(missing)))
            return 1
        print("[OK] Wafer Map edition modules: " + ", ".join(sorted(ALLOWED)))
        return 0
    print("usage: wafermap_edition.py excludes | check <dist folder>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
