"""Desktop batch adapter. UI supplies machine IDs, never filesystem paths."""
import json
import math
from pathlib import Path

from . import atomicfile, batchreport, batchreport_service, batchreport_store, localdirs, wph


def read_json(path):
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("설정 파일 크기 또는 연결 경로를 확인하세요")
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("설정 형식을 확인하세요")
    return data


def options(raw):
    if not isinstance(raw, dict) or set(raw) - {"metrics", "valid_wafers", "min_baseline", "yield_drop", "by_recipe"}:
        raise ValueError("분석 설정을 확인하세요")
    result = dict(metrics=list(batchreport.METRICS), valid_wafers=25, min_baseline=20, yield_drop=5.0, by_recipe=True)
    result.update(raw)
    metrics = result["metrics"]
    if not isinstance(metrics, list) or len(metrics) > 64 or any(not isinstance(m, str) for m in metrics):
        raise ValueError("지표를 하나 이상 선택하세요")
    # Saved settings from older versions may still list retired metrics (M07).
    # Drop unknown keys like batchreport.compute does instead of rejecting the run.
    metrics = list(dict.fromkeys(m for m in metrics if m in batchreport.METRICS))
    if not metrics:
        raise ValueError("지표를 하나 이상 선택하세요")
    result["metrics"] = metrics
    for key, low in (("valid_wafers", 1), ("min_baseline", 2)):
        if type(result[key]) is not int or not low <= result[key] <= 100000:
            raise ValueError("매수/표본 수를 확인하세요")
    drop = result["yield_drop"]
    if type(drop) not in (int, float) or not math.isfinite(drop) or not 0 <= drop <= 100:
        raise ValueError("Yield 하락 기준은 0~100입니다")
    if type(result["by_recipe"]) is not bool:
        raise ValueError("Recipe 설정을 확인하세요")
    return result


class DesktopBatch:
    def __init__(self, config_path=None):
        # Only tests inject config_path; IPC never accepts it.
        self.config_path = config_path or Path.home() / ".pi_param_manager.json"

    def configuration(self):
        cfg = read_json(self.config_path)
        paths = cfg.get("wph_report_paths") or {}
        if not isinstance(paths, dict):
            raise ValueError("기존 Report 폴더 설정을 확인하세요")
        requested_root = Path(cfg.get("local_dir") or localdirs.default_root()).absolute()
        for part in (requested_root, *requested_root.parents):
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("로컬 결과 폴더의 연결 경로는 사용할 수 없습니다")
        root = batchreport_store.local_root(requested_root, paths.values())
        # Reject redirected output trees, including cache/output directory junctions.
        for path in (root, root / "Cache", root / "배치분석", root / "배치분석" / "누적", root / "배치분석" / "대시보드"):
            for part in (path, *path.parents):
                if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                    raise ValueError("로컬 결과 폴더의 연결 경로는 사용할 수 없습니다")
        latest = read_json(root / "Cache" / "rev1_batch_last.json")
        if latest and latest.get("schema_version") != 1:
            raise ValueError("최근 조사 설정 버전을 확인하세요")
        last = latest.get("last", cfg.get("batch_last", {}))
        if not isinstance(last, dict):
            raise ValueError("최근 조사 설정 형식을 확인하세요")
        return cfg, paths, root, last

    def describe(self):
        _, paths, root, last = self.configuration()
        saved = last.get("options") if isinstance(last.get("options"), dict) else None
        if saved and isinstance(saved.get("metrics"), list):
            # Hide retired metric keys (e.g. M07) from the UI's restored selection.
            last = dict(last, options=dict(saved, metrics=[
                m for m in saved["metrics"] if isinstance(m, str) and m in batchreport.METRICS]))
        return dict(machines=[dict(id=name, folder=folder) for name, folder in sorted(paths.items())],
                    local_root=str(root), last=last)

    def reports(self, params):
        # List report file names for one machine, read-only, names only.
        if set(params) - {"machine", "query", "start", "end"}:
            raise ValueError("검색 조건을 확인하세요")
        cfg, paths, _root, _ = self.configuration()
        machine = params.get("machine")
        if not isinstance(machine, str) or machine not in paths:
            raise ValueError("등록된 호기를 선택하세요")
        target = {}
        for key in ("query", "start", "end"):
            value = params.get(key, "")
            if not isinstance(value, str) or len(value) > 256:
                raise ValueError("검색어/기간을 확인하세요")
            target[key] = value.strip()
        start, end = batchreport_store.dates(target)
        names, seen = [], set()
        for folder in dict.fromkeys([paths[machine], *cfg.get("batch_extra_paths", {}).get(machine, [])]):
            if not isinstance(folder, str) or not Path(folder).is_absolute():
                continue
            for name in wph.list_reports(folder, target["query"], start, end):
                if name not in seen:
                    seen.add(name)
                    names.append(name)
                    if len(names) > 5000:
                        raise ValueError("검색 결과가 너무 많습니다. 검색어/기간을 좁히세요.")
        return dict(machine=machine, total=len(names), names=sorted(names, key=str.lower))

    def prepare(self, params):
        if set(params) != {"targets", "options"} or not isinstance(params["targets"], list) or not 1 <= len(params["targets"]) <= 200:
            raise ValueError("조사할 호기를 선택하세요")
        cfg, paths, root, _ = self.configuration()
        targets, seen = [], set()
        for item in params["targets"]:
            if not isinstance(item, dict) or set(item) - {"machine", "query", "start", "end", "names"}:
                raise ValueError("폴더 경로 대신 등록된 호기를 선택하세요")
            machine = item.get("machine")
            if not isinstance(machine, str) or machine not in paths or machine in seen:
                raise ValueError("등록된 호기를 중복 없이 선택하세요")
            seen.add(machine)
            names = item.get("names")
            if names is not None:
                # Selected report file names (from batch_reports); collect() re-validates each.
                if not isinstance(names, list) or len(names) > 20000 or any(
                        not isinstance(n, str) or len(n) > 1024 for n in names):
                    raise ValueError("선택 Report 목록을 확인하세요")
            target = dict(machine=machine, names=names)
            for key in ("query", "start", "end"):
                value = item.get(key, "")
                if not isinstance(value, str) or len(value) > 256:
                    raise ValueError("검색어/기간을 확인하세요")
                target[key] = value.strip()
            batchreport_store.dates(target)
            for folder in dict.fromkeys([paths[machine], *cfg.get("batch_extra_paths", {}).get(machine, [])]):
                if not isinstance(folder, str) or not Path(folder).is_absolute():
                    raise ValueError("기존 Report 폴더의 절대 경로를 확인하세요")
                targets.append(dict(target, folder=folder))
        batchreport_store.local_root(root, [t["folder"] for t in targets])
        return root, targets, options(params["options"])

    def run(self, prepared, progress, cancel):
        root, targets, opts = prepared
        cache = root / "Cache"
        cache.mkdir(parents=True, exist_ok=True)
        # Separate migration state: never overwrite unrelated legacy configuration.
        atomicfile.write_json(cache / "rev1_batch_last.json", {
            "schema_version": 1, "last": {"targets": targets, "options": opts}})
        return batchreport_service.run(root, targets, opts, progress=progress, cancel=cancel)
