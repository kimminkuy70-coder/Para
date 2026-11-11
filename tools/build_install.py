"""Build the v13 first-install zip (CI, stdlib only).

    python tools/build_install.py --python-dir <unpacked python.org embeddable> --out <folder>

Result: <out>/Camtek_AOI_manager_v<ver>_install.zip, laid out as the install folder
(%LOCALAPPDATA%\\CamtekAOI\\app):

    python/                      python.org Windows embeddable package, unchanged (PSF-signed exe/dll)
    Camtek_AOI_manager.pyw       start file
    Camtek_AOI_manager.bat       double-click starter (one line: pythonw.exe + the start file, Para #64)
    app/                         the program = param_manager.deploy.files() (source text only)
    설치_안내.txt

The only script is the one-line starter .bat at the zip root (owner decision 2026-11-11, Para #64 —
the same way the company's AOI Recipe Verification starts). It is written here, not kept in the
repository, and it is not part of `param_manager.deploy.files()`, so updates never ship or replace
it. CI checks the signature of python.exe before calling this, and scans the zip with Windows
Defender after.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from param_manager import deploy  # noqa: E402

BAT_NAME = "Camtek_AOI_manager.bat"
# ASCII only (cmd.exe reads .bat files in the ANSI code page). %~dp0 = the folder of this file,
# so the install works in any local folder.
BAT = '@echo off\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0Camtek_AOI_manager.pyw"\r\n'

GUIDE = """Camtek AOI Manager v{ver} 설치 (처음 한 번)

1. 이 zip 을 다음 폴더에 푸십시오(폴더가 없으면 만드십시오):
   %LOCALAPPDATA%\\CamtekAOI\\app   (권장)
   그 폴더 바로 아래에 python 폴더, app 폴더, Camtek_AOI_manager.pyw, Camtek_AOI_manager.bat 이 있어야 합니다.
   OneDrive 폴더(OneDrive 로 옮겨진 바탕화면 · 문서 포함)에는 풀지 마십시오(프로그램이 실행을 거부합니다).

2. 그 폴더의 Camtek_AOI_manager.bat 을 더블클릭하십시오.

3. 프로그램 창이 열리고 바탕화면에 'Camtek AOI Manager' 바로가기가 생깁니다.
   다음부터는 그 바로가기나 Camtek_AOI_manager.bat 으로 실행하십시오.

업데이트: 새 버전이 나오면 프로그램을 켤 때 알림 창이 뜹니다. [지금 업데이트]를 누르면 됩니다.
설정 · 캐시 · OneDrive 공유 자료는 v12 와 같은 것을 그대로 씁니다.
"""


def version() -> str:
    text = (ROOT / "param_manager" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M).group(1)


def build(python_dir: Path, out: Path) -> Path:
    ver = version()
    if not (python_dir / "pythonw.exe").is_file() or not (python_dir / "python.exe").is_file():
        raise SystemExit(f"python.org embeddable package not found in {python_dir}")
    files = deploy.files(ROOT)
    bad = deploy.forbidden(files)
    if bad:
        raise SystemExit(f"executable/script files in the program: {bad}")
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"Camtek_AOI_manager_v{ver}_install.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(python_dir.rglob("*")):
            if f.is_file():
                z.write(f, "python/" + f.relative_to(python_dir).as_posix())
        z.write(ROOT / "Camtek_AOI_manager.pyw", "Camtek_AOI_manager.pyw")
        z.writestr(BAT_NAME, BAT.encode("ascii"))
        for rel in files:
            z.write(ROOT / rel, "app/" + rel)
        z.writestr("설치_안내.txt", GUIDE.format(ver=ver).replace("\n", "\r\n").encode("utf-8-sig"))
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    path = build(a.python_dir, a.out)
    print(path, path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
