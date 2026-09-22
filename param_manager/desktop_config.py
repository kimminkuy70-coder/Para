"""Save-folder and folder-registration setup, written to the shared config.

The web UI cannot invent paths, but the user can choose a folder through the
native OS folder chooser (Tauri `pick_folder`) — the same trust model as the
tkinter program, where the person picks a folder in Explorer. The chosen path
is sent here, validated, and persisted to `~/.pi_param_manager.json`, which the
existing tkinter program shares. Setting the save folder also creates the three
initial reference files if they are missing, like the tkinter first run.
"""
import os
from pathlib import Path

from . import atomicfile, refdata
from .desktop_batch import read_json

MAX_PATH = 4096
MAX_MACHINE = 64


class DesktopConfig:
    def __init__(self, config_path=None):
        # Only tests inject config_path; IPC never accepts it.
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    def _read(self):
        return read_json(self.config_path)

    def _write(self, cfg):
        atomicfile.write_json(str(self.config_path), cfg)

    def _valid_dir(self, path, label):
        if not isinstance(path, str) or not path.strip() or len(path) > MAX_PATH:
            raise ValueError(f"{label} 경로를 확인하세요")
        p = Path(path).absolute()
        if p.is_symlink():
            raise ValueError(f"{label} 연결 경로는 사용할 수 없습니다")
        if not p.is_dir():
            raise ValueError(f"{label} 폴더가 존재하지 않습니다")
        return str(p)

    def _valid_machine(self, name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_MACHINE:
            raise ValueError("호기 이름을 확인하세요")
        return name.strip()

    def state(self):
        cfg = self._read()
        report = cfg.get("wph_report_paths")
        roots = cfg.get("commonality_roots")
        return dict(save_dir=cfg.get("save_dir") or "",
                    local_dir=cfg.get("local_dir") or "",
                    report_paths=report if isinstance(report, dict) else {},
                    scanresult_roots=roots if isinstance(roots, dict) else {})

    def set_save_dir(self, params):
        if set(params) != {"path"}:
            raise ValueError("저장폴더 경로를 확인하세요")
        path = self._valid_dir(params["path"], "저장폴더")
        # Create the initial reference files if missing (matches tkinter first run).
        created = []
        for getter, maker in ((refdata.ip_path, refdata.create_blank_ip),
                              (refdata.ref_path, refdata.create_blank_reference),
                              (refdata.special_path, refdata.create_blank_special)):
            fp = getter(path)
            if not os.path.exists(fp):
                maker(fp)
                created.append(os.path.basename(fp))
        cfg = self._read()
        cfg["save_dir"] = path
        self._write(cfg)
        return dict(save_dir=path, created=created)

    def set_report_path(self, params):
        if set(params) != {"machine", "path"}:
            raise ValueError("호기와 폴더를 확인하세요")
        machine = self._valid_machine(params["machine"])
        path = self._valid_dir(params["path"], "Report 폴더")
        cfg = self._read()
        paths = cfg.get("wph_report_paths")
        if not isinstance(paths, dict):
            paths = {}
        paths[machine] = path
        cfg["wph_report_paths"] = paths
        self._write(cfg)
        return dict(report_paths=paths)

    def set_scanresult_root(self, params):
        if set(params) != {"machine", "path"}:
            raise ValueError("호기와 폴더를 확인하세요")
        machine = self._valid_machine(params["machine"])
        path = self._valid_dir(params["path"], "Scanresult 루트")
        cfg = self._read()
        roots = cfg.get("commonality_roots")
        if not isinstance(roots, dict):
            roots = {}
        roots[machine] = path
        cfg["commonality_roots"] = roots
        self._write(cfg)
        return dict(scanresult_roots=roots)

    def remove(self, params):
        if set(params) != {"kind", "machine"}:
            raise ValueError("삭제 대상을 확인하세요")
        machine = self._valid_machine(params["machine"])
        key = {"report": "wph_report_paths", "scanresult": "commonality_roots"}.get(params.get("kind"))
        if not key:
            raise ValueError("삭제 종류를 확인하세요")
        cfg = self._read()
        table = cfg.get(key)
        if isinstance(table, dict) and machine in table:
            del table[machine]
            cfg[key] = table
            self._write(cfg)
        return self.state()
