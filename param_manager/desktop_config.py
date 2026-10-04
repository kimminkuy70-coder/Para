"""Save-folder and folder-registration setup, written to the shared config.

The web UI cannot invent paths, but the user can choose a folder through the
native OS folder chooser (Tauri `pick_folder`) — the same trust model as the
tkinter program, where the person picks a folder in Explorer. The chosen path
is sent here, validated, and persisted to `~/.pi_param_manager.json`, which the
existing tkinter program shares. Setting the save folder also creates the three
initial reference files if they are missing, like the tkinter first run.
"""
import os
import re
from pathlib import Path

from . import __version__, atomicfile, engine, localdirs, refdata
from .desktop_batch import DesktopBatch, read_json

MAX_PATH = 4096
MAX_MACHINE = 64
MAX_EXTRA = 20
EXTRA_KINDS = ("report", "scanresult")


def name_key(text):
    """이름 순 정렬 키 — 숫자는 크기로(AOI-9 < AOI-10), 대소문자 무시."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", str(text)) if t]


def _is_report_name(name):
    return re.sub(r"[\s_\-]+", "", name).lower() in ("report", "reports")


def find_report_dir(root):
    """호기 루트 바로 아래의 Batch Report 폴더(`Reports`/`Report`, 대소문자 무시).
    사람이 호기 루트를 등록·수정할 때 한 번만 본다(요청마다 장비 폴더를 열지 않는다)."""
    try:
        names = sorted((e.name for e in os.scandir(root) if e.is_dir()), key=name_key)
    except OSError:
        return ""
    exact = [n for n in names if n.lower() == "reports"]
    hits = exact or [n for n in names if _is_report_name(n)]
    return str(Path(root) / hits[0]) if hits else ""


def aoi_view(cfg):
    """설정 파일 → 'AOI 장비 호기 루트' 목록(이름 순). 구 설정(`wph_report_paths`·
    `commonality_roots` 를 따로 등록)도 한 호기로 묶어 보여 준다 — 파일은 건드리지
    않고 경로 문자열만 본다(장비 폴더 접근 없음)."""
    def table(key):
        v = cfg.get(key)
        return {m: p for m, p in v.items() if isinstance(m, str) and isinstance(p, str) and p.strip()} \
            if isinstance(v, dict) else {}
    roots, reports, scans = table("aoi_roots"), table("wph_report_paths"), table("commonality_roots")
    extra = cfg.get("batch_extra_paths") if isinstance(cfg.get("batch_extra_paths"), dict) else {}
    aoi_extra = cfg.get("aoi_extra") if isinstance(cfg.get("aoi_extra"), dict) else {}
    out = []
    for m in sorted(set(roots) | set(reports) | set(scans), key=name_key):
        report = reports.get(m, "")
        root = roots.get(m) or scans.get(m) or (
            str(Path(report).parent) if report and _is_report_name(Path(report).name) else report)
        mine = aoi_extra.get(m) if isinstance(aoi_extra.get(m), dict) else {}
        out.append(dict(
            machine=m, root=root, report=report, scanresult=scans.get(m, ""), legacy=m not in roots,
            extra=dict(report=sorted((p for p in extra.get(m, []) if isinstance(p, str)), key=name_key),
                       scanresult=sorted((p for p in mine.get("scanresult", []) if isinstance(p, str)), key=name_key))))
    return out


def scanresult_roots_for(cfg, machine):
    """Commonality 가 그 호기에서 뒤질 Scanresult 폴더 전부 = 호기 루트 아래 Scanresult*
    (백업본 자동) + 사람이 추가한 Scanresult 보관 폴더(각각 아래 Scanresult* 도 인식)."""
    from . import commonality as cm
    roots = cfg.get("commonality_roots") if isinstance(cfg.get("commonality_roots"), dict) else {}
    out = []
    if roots.get(machine):
        out += cm.scanresult_roots(roots[machine], machine)
    extra = (cfg.get("aoi_extra") or {}).get(machine) if isinstance(cfg.get("aoi_extra"), dict) else None
    for p in (extra or {}).get("scanresult", []) if isinstance(extra, dict) else []:
        if isinstance(p, str) and p.strip():
            out += cm.scanresult_roots(p, machine)
    return list(dict.fromkeys(out))


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
        from .desktop_batch import BATCH_INTERVALS
        return dict(save_dir=cfg.get("save_dir") or "", aoi=aoi_view(cfg),
                    local_dir=cfg.get("local_dir") or "",
                    report_paths=report if isinstance(report, dict) else {},
                    scanresult_roots=roots if isinstance(roots, dict) else {},
                    extra_paths={m: [p for p in v if isinstance(p, str)] for m, v in extra.items()
                                 if isinstance(v, list)} if isinstance(extra, dict) else {},
                    batch_auto=bool(cfg.get("batch_auto")),
                    batch=DesktopBatch(self.config_path).auto_state(cfg), batch_intervals=list(BATCH_INTERVALS),
                    # Effective local folder (config or default) + the config file itself, for the
                    # "현재 설정" summary. Pure path computation, no folder access.
                    local_root=self._local_root_text(), config_file=str(self.config_path))

    def _local_root_text(self):
        try:
            return str(DesktopBatch(self.config_path).configuration()[2])
        except (OSError, ValueError) as exc:
            return f"(확인 필요: {exc})"

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
        from . import desktop_diag
        return dict(version=__version__, user=engine.current_user(), config=str(self.config_path),
                    local_root=root, logs=logs, diag_log=desktop_diag.path())

    def set_hide_kla(self, params):
        if set(params) != {"enabled"} or type(params["enabled"]) is not bool:
            raise ValueError("KLA 숨김 설정을 확인하세요")
        cfg = self._read()
        cfg["hide_kla"] = params["enabled"]
        self._write(cfg)
        return self.state()

    def set_batch_auto(self, params):
        from .desktop_batch import BATCH_INTERVALS
        if set(params) - {"enabled", "interval_hours"} or type(params.get("enabled")) is not bool:
            raise ValueError("자동 조사 설정을 확인하세요")
        cfg = self._read()
        if "interval_hours" in params:
            if type(params["interval_hours"]) not in (int, float) or params["interval_hours"] not in BATCH_INTERVALS:
                raise ValueError("분석 주기를 목록에서 고르세요")
            cfg["batch_interval_hours"] = params["interval_hours"]
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

    # ---- AOI 장비 호기 루트 (Batch Report + Scanresult 일원화, 2026-09) --------------
    # 호기 폴더(예: W:\\AOI-9) 하나만 등록하면 그 아래 Reports 는 Batch Report 분석이,
    # Scanresult*(백업본 포함)는 Commonality 가 쓴다. 기존 프로그램과 설정 파일을 공유하므로
    # 구 키(wph_report_paths·commonality_roots·batch_extra_paths)도 같은 값으로 맞춰 둔다.
    def _aoi_write(self, cfg, machine, root):
        report = find_report_dir(root)
        for key in ("aoi_roots", "commonality_roots", "wph_report_paths"):
            if not isinstance(cfg.get(key), dict):
                cfg[key] = {}
        cfg["aoi_roots"][machine] = root
        cfg["commonality_roots"][machine] = root
        if report:
            cfg["wph_report_paths"][machine] = report
        else:
            cfg["wph_report_paths"].pop(machine, None)
        return report

    def _aoi_result(self, machine, root, report):
        from . import commonality as cm
        scans = [p.name for p in cm._find_scanresult_dirs(Path(root))]
        notes = []
        notes.append(f"Batch Report: {Path(report).name}" if report else
                     "Reports 폴더를 찾지 못했습니다 — Batch Report 분석 목록에는 나오지 않습니다")
        notes.append(f"Scanresult: {', '.join(scans)}" if scans else
                     "Scanresult 폴더를 찾지 못했습니다 — Commonality 조사 전에 폴더를 확인하세요")
        return dict(self.state(), notice=f"{machine}: " + " · ".join(notes))

    def set_aoi_root(self, params):
        if set(params) != {"machine", "path"}:
            raise ValueError("호기와 폴더를 확인하세요")
        machine = self._valid_machine(params["machine"])
        root = self._valid_dir(params["path"], "AOI 장비 호기 루트")
        cfg = self._read()
        if any(v["machine"] == machine for v in aoi_view(cfg)):
            raise ValueError(f"{machine} 은(는) 이미 등록되어 있습니다. 목록에서 [수정]을 쓰세요")
        report = self._aoi_write(cfg, machine, root)
        self._write(cfg)
        return self._aoi_result(machine, root, report)

    def edit_aoi_root(self, params):
        if set(params) != {"machine", "new_machine", "path"}:
            raise ValueError("수정할 항목을 확인하세요")
        old = self._valid_machine(params["machine"])
        new = self._valid_machine(params["new_machine"])
        root = self._valid_dir(params["path"], "AOI 장비 호기 루트")
        cfg = self._read()
        known = {v["machine"] for v in aoi_view(cfg)}
        if old not in known:
            raise ValueError("등록되지 않은 호기입니다. 새로고침하세요")
        if new != old and new in known:
            raise ValueError(f"{new} 은(는) 이미 등록되어 있습니다")
        if new != old:
            for key in ("aoi_roots", "commonality_roots", "wph_report_paths", "batch_extra_paths", "aoi_extra"):
                table = cfg.get(key)
                if isinstance(table, dict) and old in table:
                    table[new] = table.pop(old)
        report = self._aoi_write(cfg, new, root)
        self._write(cfg)
        return self._aoi_result(new, root, report)

    def remove_aoi(self, params):
        if set(params) != {"machine"}:
            raise ValueError("삭제 대상을 확인하세요")
        machine = self._valid_machine(params["machine"])
        cfg = self._read()
        for key in ("aoi_roots", "commonality_roots", "wph_report_paths", "batch_extra_paths", "aoi_extra"):
            table = cfg.get(key)
            if isinstance(table, dict):
                table.pop(machine, None)
        self._write(cfg)
        return self.state()

    def set_aoi_extra(self, params):
        """호기별 추가 폴더(백업·보관본). kind=report → Batch Report 분석이 함께 읽고
        (구 `batch_extra_paths`), kind=scanresult → Commonality 가 함께 뒤진다."""
        if set(params) != {"machine", "kind", "paths"} or params.get("kind") not in EXTRA_KINDS \
                or not isinstance(params["paths"], list) or len(params["paths"]) > MAX_EXTRA:
            raise ValueError(f"추가 폴더 목록을 확인하세요(호기당 종류별 최대 {MAX_EXTRA}개)")
        machine = self._valid_machine(params["machine"])
        kind = params["kind"]
        cfg = self._read()
        view = next((v for v in aoi_view(cfg) if v["machine"] == machine), None)
        if view is None:
            raise ValueError("먼저 이 호기의 AOI 장비 호기 루트를 등록하세요")
        label = "추가 Report 폴더" if kind == "report" else "추가 Scanresult 폴더"
        main = view["report"] if kind == "report" else view["scanresult"] or view["root"]
        paths = []
        for raw in params["paths"]:
            path = self._valid_dir(raw, label)
            if main and Path(path) == Path(main).absolute():
                raise ValueError("기본 폴더와 같은 폴더입니다")
            if path not in paths:
                paths.append(path)
        paths.sort(key=name_key)
        if kind == "report":
            table = cfg.get("batch_extra_paths") if isinstance(cfg.get("batch_extra_paths"), dict) else {}
            if paths:
                table[machine] = paths
            else:
                table.pop(machine, None)
            cfg["batch_extra_paths"] = table
        else:
            table = cfg.get("aoi_extra") if isinstance(cfg.get("aoi_extra"), dict) else {}
            mine = table.get(machine) if isinstance(table.get(machine), dict) else {}
            if paths:
                mine["scanresult"] = paths
            else:
                mine.pop("scanresult", None)
            if mine:
                table[machine] = mine
            else:
                table.pop(machine, None)
            cfg["aoi_extra"] = table
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
        return self.state()

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
        return self.state()

    def edit_root(self, params):
        """'수정' for a registered root: change its folder and/or its machine name.
        A renamed Batch Report root keeps its extra (backup) folders."""
        if set(params) != {"kind", "machine", "new_machine", "path"}:
            raise ValueError("수정할 항목을 확인하세요")
        key = {"report": "wph_report_paths", "scanresult": "commonality_roots"}.get(params.get("kind"))
        if not key:
            raise ValueError("수정 종류를 확인하세요")
        old = self._valid_machine(params["machine"])
        new = self._valid_machine(params["new_machine"])
        label = "Report 폴더" if key == "wph_report_paths" else "Scanresult 루트"
        path = self._valid_dir(params["path"], label)
        cfg = self._read()
        table = cfg.get(key) if isinstance(cfg.get(key), dict) else {}
        if old not in table:
            raise ValueError("등록되지 않은 호기입니다. 새로고침하세요")
        if new != old and new in table:
            raise ValueError(f"{new} 은(는) 이미 등록되어 있습니다")
        # Keep the original order; rename in place.
        cfg[key] = {(new if m == old else m): (path if m == old else p) for m, p in table.items()}
        if key == "wph_report_paths" and new != old:
            extra = cfg.get("batch_extra_paths") if isinstance(cfg.get("batch_extra_paths"), dict) else {}
            if old in extra:
                extra[new] = extra.pop(old)
                cfg["batch_extra_paths"] = extra
        self._write(cfg)
        return self.state()

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
