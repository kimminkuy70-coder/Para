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

from . import __version__, atomicfile, engine, localdirs, refdata
from .desktop_batch import DesktopBatch, read_json

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
        extra = cfg.get("batch_extra_paths")
        return dict(save_dir=cfg.get("save_dir") or "",
                    local_dir=cfg.get("local_dir") or "",
                    report_paths=report if isinstance(report, dict) else {},
                    scanresult_roots=roots if isinstance(roots, dict) else {},
                    extra_paths={m: [p for p in v if isinstance(p, str)] for m, v in extra.items()
                                 if isinstance(v, list)} if isinstance(extra, dict) else {},
                    batch_auto=bool(cfg.get("batch_auto")))

    # ---- local work folder (tkinter '로컬 작업 폴더') ---------------------
    def local_state(self):
        root = DesktopBatch(self.config_path).configuration()[2]
        return dict(root=str(root), summary=localdirs.describe(str(root)),
                    onedrive=localdirs.is_under_onedrive(str(root)), default=localdirs.default_root())

    def set_local_dir(self, params):
        """Local temp/log/cache/result root. Must stay off OneDrive and network
        shares (the 2026-08 mass-sync incident); like tkinter, a `CamtekAOI`
        folder is created inside the chosen folder."""
        if set(params) != {"path"}:
            raise ValueError("로컬 작업 폴더 경로를 확인하세요")
        picked = self._valid_dir(params["path"], "로컬 작업 폴더")
        if picked.startswith(("\\\\", "//")) or localdirs.is_under_onedrive(picked):
            raise ValueError("로컬 작업 폴더는 OneDrive/네트워크 공유가 아닌 이 PC의 폴더여야 합니다")
        root = picked if Path(picked).name == localdirs.APP_DIRNAME else str(Path(picked) / localdirs.APP_DIRNAME)
        from .desktop_appupdate import inside_install
        if inside_install(root):
            raise ValueError("로컬 작업 폴더를 앱 설치 폴더 안에 둘 수 없습니다(업데이트 때 교체됩니다)")
        cfg = self._read()
        # Refuse output next to/inside registered equipment sources (same rule as batch output).
        from . import batchreport_store
        batchreport_store.local_root(root, (cfg.get("wph_report_paths") or {}).values())
        localdirs.ensure(root)
        cfg["local_dir"] = root
        self._write(cfg)
        return self.local_state()

    def purge_temp(self, params):
        if params:
            raise ValueError("정리 요청을 확인하세요")
        root = self.local_state()["root"]
        removed = localdirs.cleanup_temp(root, keep_hours=localdirs.TEMP_KEEP_HOURS)
        return dict(self.local_state(), removed=removed)

    def about(self, params):
        if params:
            raise ValueError("정보 요청을 확인하세요")
        try:
            root = self.local_state()["root"]
            logs = localdirs.logs_dir(root)
        except (OSError, ValueError):
            root, logs = "", ""
        return dict(version=__version__, user=engine.current_user(), config=str(self.config_path),
                    local_root=root, logs=logs)

    def set_hide_kla(self, params):
        if set(params) != {"enabled"} or type(params["enabled"]) is not bool:
            raise ValueError("KLA 숨김 설정을 확인하세요")
        cfg = self._read()
        cfg["hide_kla"] = params["enabled"]
        self._write(cfg)
        return self.state()

    def set_batch_auto(self, params):
        if set(params) != {"enabled"} or type(params["enabled"]) is not bool:
            raise ValueError("자동 조사 설정을 확인하세요")
        cfg = self._read()
        cfg["batch_auto"] = params["enabled"]
        self._write(cfg)
        return self.state()

    def set_extra_paths(self, params):
        """Additional Report folders scanned together with a machine's main folder
        (tkinter `batch_extra_paths`, e.g. an archive/backup folder)."""
        if set(params) != {"machine", "paths"} or not isinstance(params["paths"], list) or len(params["paths"]) > 20:
            raise ValueError("추가 폴더 목록을 확인하세요")
        machine = self._valid_machine(params["machine"])
        cfg = self._read()
        main = (cfg.get("wph_report_paths") or {}).get(machine)
        if not main:
            raise ValueError("먼저 이 호기의 Report 폴더를 등록하세요")
        paths = []
        for raw in params["paths"]:
            path = self._valid_dir(raw, "추가 Report 폴더")
            if Path(path) == Path(main).absolute():
                raise ValueError("기본 Report 폴더와 같은 폴더입니다")
            if path not in paths:
                paths.append(path)
        extra = cfg.get("batch_extra_paths") if isinstance(cfg.get("batch_extra_paths"), dict) else {}
        if paths:
            extra[machine] = paths
        else:
            extra.pop(machine, None)
        cfg["batch_extra_paths"] = extra
        self._write(cfg)
        return self.state()

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
