"""Open a produced file or its folder with the OS (tkinter `_open_path` /
`_open_in_excel`).

The web UI only shows paths the engine itself returned, but it could send any
string, so this adapter never trusts it: the path must already exist, be a
known document type or a folder, contain no link/junction, and sit under the
configured save folder or the local result folder. Nothing is executed except
the OS default handler (`os.startfile`) or Explorer's select switch.
"""
import os
from pathlib import Path
import shutil
import subprocess

from .desktop_batch import DesktopBatch, read_json

OPENABLE = {".xlsx", ".xlsm", ".xls", ".html", ".htm", ".csv", ".txt", ".png", ".pdf"}
MAX_PATH = 4096


class DesktopOpen:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    def _roots(self):
        roots = []
        cfg = read_json(self.config_path)
        if cfg.get("save_dir"):
            roots.append(Path(cfg["save_dir"]).absolute())
        try:
            roots.append(Path(DesktopBatch(self.config_path).configuration()[2]).absolute())
        except ValueError:
            pass
        return roots

    def resolve(self, raw):
        if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_PATH or "\0" in raw:
            raise ValueError("열 파일 경로를 확인하세요")
        path = Path(raw).absolute()
        if not path.exists():
            raise ValueError("파일이 없습니다. 이동되었거나 삭제되었을 수 있습니다.")
        if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
            raise ValueError("연결 경로는 열 수 없습니다")
        if path.is_file() and path.suffix.lower() not in OPENABLE:
            raise ValueError("이 종류의 파일은 열 수 없습니다")
        if not path.is_file() and not path.is_dir():
            raise ValueError("파일 또는 폴더만 열 수 있습니다")
        real = path.resolve()
        if not any(real == root.resolve() or real.is_relative_to(root.resolve()) for root in self._roots()):
            raise ValueError("저장폴더 또는 로컬 결과 폴더 안의 파일만 열 수 있습니다")
        return path

    def open(self, params):
        if set(params) - {"path", "reveal"} or type(params.get("reveal", False)) is not bool:
            raise ValueError("열기 요청을 확인하세요")
        path = self.resolve(params.get("path"))
        reveal = params.get("reveal", False)
        if os.name == "nt":
            if reveal and path.is_file():
                # Fixed program + fixed switch; the path is a single argument, no shell.
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            else:
                os.startfile(str(path.parent if reveal else path))  # noqa: S606 - Windows only
        else:
            opener = shutil.which("xdg-open") or shutil.which("open")
            if not opener:
                raise ValueError("이 환경에서는 파일을 열 수 없습니다")
            subprocess.Popen([opener, str(path.parent if reveal and path.is_file() else path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dict(opened=str(path))
