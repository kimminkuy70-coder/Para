"""Build the first-install zip (CI, stdlib only).

    python tools/build_install.py --python-dir <unpacked python.org embeddable> --out <folder>

Result: <out>/AOI_Manager_v<ver>_install.zip, laid out as the install folder
(%LOCALAPPDATA%\\CamtekAOI\\app):

    python/                      python.org Windows embeddable package, unchanged (PSF-signed exe/dll)
    AOI_Manager.pyw              start file (the repository's Camtek_AOI_manager.pyw, renamed in the zip)
    AOI_Manager.bat              double-click starter of AOI Manager (one line: pythonw.exe + the start file)
    AOI_Manager_Mini.bat         double-click starter of AOI Manager Mini (the same line + --mini)
    app/                         the program = param_manager.deploy.files() (source text only)
    설치_안내.txt

v14.4 (owner 2026-11-23): the program is called AOI Manager (Camtek AOI Manager before) and the
same install also starts AOI Manager Mini (`param_manager/edition.py`). The owner deletes
AOI_Manager.bat and zips the folder again for people who should only have Mini.

The only scripts are the one-line starters at the zip root (owner decision 2026-11-11, Para #64,
second starter owner 2026-11-23). They are written here, not kept in the repository, and they are
not part of `param_manager.deploy.files()`, so updates never ship or replace them. CI checks the
signature of python.exe before calling this, and scans the zip with Windows Defender after.

The start file keeps its repository name Camtek_AOI_manager.pyw (also in app/): updaters of
installs before v14.4 refuse a tree without that file.
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

START_SOURCE = "Camtek_AOI_manager.pyw"     # name in the repository (and app/)
START_NAME = "AOI_Manager.pyw"              # name at the install root
# ASCII only (cmd.exe reads .bat files in the ANSI code page). %~dp0 = the folder of this file,
# so the install works in any local folder. One command each — never add more.
_LINE = '@echo off\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0' + START_NAME + '"{extra}\r\n'
STARTERS = {"AOI_Manager.bat": _LINE.format(extra=""),
            "AOI_Manager_Mini.bat": _LINE.format(extra=" --mini")}

GUIDE = """AOI Manager v{ver} 설치 (처음 한 번)

1. 이 zip 을 다음 폴더에 푸십시오(폴더가 없으면 만드십시오):
   %LOCALAPPDATA%\\CamtekAOI\\app   (권장)
   그 폴더 바로 아래에 python 폴더, app 폴더, AOI_Manager.pyw, 실행 파일(.bat)이 있어야 합니다.
   OneDrive 폴더(OneDrive 로 옮겨진 바탕화면 · 문서 포함)에는 풀지 마십시오(프로그램이 실행을 거부합니다).

2. 그 폴더의 실행 파일(AOI_Manager.bat 또는 AOI_Manager_Mini.bat — 받은 zip 에 들어 있는 것)을 더블클릭하십시오.

3. 프로그램 창이 열리고 바탕화면에 'AOI Manager'(또는 'AOI Manager Mini') 바로가기가 생깁니다.
   다음부터는 그 바로가기나 같은 .bat 으로 실행하십시오.

업데이트: 새 버전이 나오면 프로그램을 켤 때 알림 창이 뜹니다. [지금 업데이트]를 누르면 됩니다.
AOI Manager 와 AOI Manager Mini 는 같은 프로그램 파일을 쓰므로 한 번 업데이트하면 둘 다 새 버전이 됩니다.
설정 · 캐시 · OneDrive 공유 자료는 v12 와 같은 것을 그대로 씁니다.
"""


def version() -> str:
    text = (ROOT / "param_manager" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M).group(1)


LABEL_FILE = "build_label.txt"   # app/ 안 — 시험판 표시(설정 > 정보). 정식 업데이트가 app/ 를 바꾸면 사라진다.
LABEL_RE = re.compile(r"^[0-9A-Za-z가-힣_]{1,40}$")


def build(python_dir: Path, out: Path, label: str = "") -> Path:
    """label = 시험판 표시(소유자 2026-11-27 — 디자인 브랜치 zip 이 정식판과 이름이 같아 헷갈림).
    있으면 zip 이름 = AOI_Manager_v{ver}_{label}_install.zip, app/build_label.txt = 화면 글('디자인 시험판 · 11-27').
    버전 번호는 그대로(번호를 올리면 다른 사람 프로그램이 업데이트로 받는다). 정식 판(version_v14)은 label 없이 만든다."""
    ver = version()
    if label and not LABEL_RE.match(label):
        raise SystemExit(f"label must be letters/digits/_ only: {label!r}")
    if not (python_dir / "pythonw.exe").is_file() or not (python_dir / "python.exe").is_file():
        raise SystemExit(f"python.org embeddable package not found in {python_dir}")
    files = deploy.files(ROOT)
    bad = deploy.forbidden(files)
    if bad:
        raise SystemExit(f"executable/script files in the program: {bad}")
    out.mkdir(parents=True, exist_ok=True)
    target = out / (f"AOI_Manager_v{ver}_{label}_install.zip" if label else f"AOI_Manager_v{ver}_install.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(python_dir.rglob("*")):
            if f.is_file():
                z.write(f, "python/" + f.relative_to(python_dir).as_posix())
        z.write(ROOT / START_SOURCE, START_NAME)
        for name, text in STARTERS.items():
            z.writestr(name, text.encode("ascii"))
        for rel in files:
            z.write(ROOT / rel, "app/" + rel)
        guide = GUIDE.format(ver=ver)
        if label:
            shown = label_text(label)
            z.writestr("app/" + LABEL_FILE, (shown + "\n").encode("utf-8"))
            guide = f"※ {shown} — 정식 판이 아닙니다(시험용). 지금 쓰는 판과 다른 폴더에 푸십시오.\n\n" + guide
        z.writestr("설치_안내.txt", guide.replace("\n", "\r\n").encode("utf-8-sig"))
    return target


def label_text(label: str) -> str:
    """'디자인시험판_1127' → '디자인 시험판 · 11-27'(끝 4자리 = 월일). 그 밖의 꼴은 '_' 만 공백으로."""
    m = re.match(r"^(.*?)_?(\d{2})(\d{2})$", label)
    head = (m.group(1) if m else label).replace("_", " ").replace("시험판", " 시험판").replace("  ", " ").strip()
    return f"{head} · {m.group(2)}-{m.group(3)}" if m else head


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--label", default="", help="시험판 표시(예: 디자인시험판_1127) — 정식 판은 비움")
    a = ap.parse_args(argv)
    path = build(a.python_dir, a.out, a.label)
    print(path, path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
