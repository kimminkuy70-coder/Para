"""Desktop batch adapter. UI supplies machine IDs, never filesystem paths."""
import json
from datetime import datetime
from pathlib import Path

from . import atomicfile, batchreport, batchreport_service, batchreport_store, localdirs, lotreport, watcher, wph


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
    if not isinstance(raw, dict) or set(raw) - {"metrics", "valid_wafers", "min_baseline", "yield_drop", "by_recipe", "reuse"}:
        raise ValueError("분석 설정을 확인하세요")
    # reuse = '이미 읽은 Batch Report는 다시 읽지 않기'(기본 켜짐). 끄면 고른 범위를 전부 다시 연다.
    result = dict(metrics=list(batchreport.METRICS), valid_wafers=25, by_recipe=True, reuse=True)
    # M09 was retired; its thresholds may still arrive from older saved settings. Ignore them.
    result.update({k: v for k, v in raw.items() if k not in ("min_baseline", "yield_drop")})
    metrics = result["metrics"]
    if not isinstance(metrics, list) or len(metrics) > 64 or any(not isinstance(m, str) for m in metrics):
        raise ValueError("지표를 하나 이상 선택하세요")
    # Saved settings from older versions may still list retired metrics (M07, M09).
    # Drop unknown keys like batchreport.compute does instead of rejecting the run.
    metrics = list(dict.fromkeys(m for m in metrics if m in batchreport.METRICS))
    if not metrics:
        raise ValueError("지표를 하나 이상 선택하세요")
    result["metrics"] = metrics
    if type(result["valid_wafers"]) is not int or not 1 <= result["valid_wafers"] <= 100000:
        raise ValueError("WPH 유효 매수를 확인하세요")
    if type(result["by_recipe"]) is not bool:
        raise ValueError("Recipe 설정을 확인하세요")
    if type(result["reuse"]) is not bool:
        raise ValueError("캐시 사용 설정을 확인하세요")
    return result


# Web-only analysis period (the tkinter program always uses 24 h; it ignores this key).
# Kept to a few long periods: every run reads the equipment Report folders.
BATCH_INTERVALS = (6, 12, 24, 48, 168)


def batch_interval(cfg):
    value = cfg.get("batch_interval_hours", 24)
    return value if type(value) in (int, float) and value in BATCH_INTERVALS else 24


def _name_key(text):
    from .desktop_config import name_key
    return name_key(text)


# ---------------------------------------------------------------------------
#  새 Batch Report 화면(가동률 조사 및 분석 · 찾기 · 취합) — batchview 결과를 화면에 나눠 보낸다
# ---------------------------------------------------------------------------
VIEW_CHUNK = 1_000_000            # 글자 수(ASCII JSON). 따옴표 이스케이프까지 넣어도 IPC 4MB 프레임 안
CHOICES_FILE = "batch_lot_choices.json"
VIEWS = ("scope", "find")
MAX_FIND_MACHINES = 200
NEIGHBOR_H = 24                   # 찾기: 고른 Batch Report 앞뒤로 같은 호기에서 이어서 스캔한 것까지(이슈 #19: 13 → 24시간)
MAX_FIND_HITS = 20000             # 찾기 1단계 목록(파일 이름만)
MAX_FIND_PICK = 2000              # 찾기 2단계에서 한 번에 읽을 수 있는 고른 Batch Report


def _choice_key(bunch_key, wafer_key):
    return f"{bunch_key}\t{wafer_key}"


def _scope_of(targets, opts):
    machines = list(dict.fromkeys(t["machine"] for t in targets))
    first = targets[0] if targets else {}
    return dict(machines=machines, start=first.get("start", ""), end=first.get("end", ""),
                reuse=bool((opts or {}).get("reuse", True)), at=datetime.now().strftime("%Y-%m-%d %H:%M"))


def _scanresult_paths(cfg, records, progress=None, cancel=None, limit=300):
    """{호기|Job|Setup|S/M: {paths: 실제 있는 폴더, pattern: 찾는 모양}} — 폴더 이름만 확인한다."""
    from . import lotmodel
    from .desktop_config import scanresult_roots_for
    aoi = cfg.get("aoi_roots") if isinstance(cfg.get("aoi_roots"), dict) else {}
    roots, out = {}, {}
    for record in records:
        a = lotmodel.attempt(record)
        key = "|".join((a["machine"], a["job"], a["setup"], a["sm"]))
        if key in out or not a["job"] or not a["sm"]:
            continue
        if len(out) >= limit:
            break
        batchreport_store.checkpoint(cancel)
        base = aoi.get(a["machine"]) or str(Path(record.get("source_folder", "")).parent)
        pattern = str(Path(base) / "Scanresult*" / a["job"] / a["setup"] / a["sm"])
        if a["machine"] not in roots:
            if progress:
                progress(f"{a['machine']}: Scanresult 폴더 확인 중…")
            try:
                roots[a["machine"]] = scanresult_roots_for(cfg, a["machine"])
            except OSError:
                roots[a["machine"]] = []
        found = []
        for r in roots[a["machine"]]:
            p = Path(r) / a["job"] / a["setup"] / a["sm"]
            try:
                if p.is_dir():
                    found.append(str(p))
            except OSError:
                pass
        out[key] = dict(paths=found, pattern=pattern)
    return out


def _cached_names(root, folders):
    """{(호기, 폴더): {파일 이름}} — 로컬 조사 캐시(배치분석/누적)에 이미 읽어 둔 Batch Report 이름(이슈 #19).

    장비에 묻지 않는다. 캐시 파일 이름은 원본 폴더를 resolve 한 해시라 그 경로를 다시 풀면 장비 공유에 접속하게
    되므로, `load_cached` 처럼 캐시 안에 적어 둔 (호기, 폴더) 문자열로 짝을 찾는다. 같은 실행 중에는 메모리에 둔
    캐시(`_load_state`)를 다시 쓴다."""
    import os
    base = batchreport_store.local_root(root, [f for _, f in folders]) / "배치분석" / "누적"
    want = {(m, os.path.normcase(str(Path(f)))): (m, f) for m, f in folders}
    out = {}
    if not base.is_dir():
        return out
    for cachefile in sorted(base.glob("*.json")):
        if cachefile.is_symlink():
            continue
        try:
            state = batchreport_store._load_state(cachefile)
        except (OSError, ValueError):
            continue
        pair = want.get((state.get("machine"), os.path.normcase(str(state.get("folder", "")))))
        if pair:
            out.setdefault(pair, set()).update(state["entries"])
    return out


class BatchViews:
    """새 Batch Report 화면용 결과 보관(엔진 메모리). 화면은 `view_chunk` 로 조각을 받아 간다."""

    def _view_items(self):
        if not hasattr(self, "_views"):
            self._views, self.version = {}, 0
        return self._views

    def _load_choices(self):
        _, _, root, _ = self.configuration()
        path = root / "Cache" / CHOICES_FILE
        data = read_json(path)
        raw = data.get("choices") if data.get("schema") == 1 and isinstance(data.get("choices"), dict) else {}
        out = {}
        for key, value in raw.items():
            if isinstance(key, str) and "\t" in key and isinstance(value, str):
                bunch, wafer = key.split("\t", 1)
                out[(bunch, wafer)] = value
        return out

    def set_view(self, name, records, extra=None, hits=None, view=None):
        """records → View. 저장된 사람 선택(로컬 Cache)을 늘 적용한다(개발자 기능 토글과 무관).
        view = 이미 같은 records · 선택으로 만든 View(조사 서비스가 저장 파일용으로 만든 것 — 다시 계산하지 않음)."""
        from . import batchview
        items = self._view_items()
        if view is None:
            view = batchview.View(records, overrides=self._load_choices(), hits=hits)
        payload = dict(view.payload(), **(extra or {}))
        self.version += 1
        blob = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str)
        items[name] = dict(view=view, blob=blob, version=self.version, extra=extra or {}, records=records, hits=hits)
        return self.view_meta(name)

    def view_meta(self, name):
        item = self._view_items().get(name)
        if not item:
            return dict(view=name, version=0, size=0)
        return dict(view=name, version=item["version"], size=len(item["blob"]), saved=item["view"].payload()["saved"],
                    lots=len(item["view"].model["lots"]), reports=len(item["records"]))

    def _item(self, params, keys=()):
        if not isinstance(params, dict) or set(params) - {"view", *keys}:
            raise ValueError("요청을 확인하세요")
        name = params.get("view")
        if name not in VIEWS:
            raise ValueError("요청을 확인하세요")
        item = self._view_items().get(name)
        if not item:
            raise ValueError("조사 결과가 없습니다. [조사 시작]을 눌러 주세요.")
        return item

    def view_chunk(self, params):
        item = self._item(params, ("version", "offset"))
        offset = params.get("offset", 0)
        if type(offset) is not int or not 0 <= offset <= len(item["blob"]):
            raise ValueError("요청을 확인하세요")
        if params.get("version") != item["version"]:
            raise ValueError("결과가 새로 바뀌었습니다. 다시 불러옵니다.")
        return dict(view=params["view"], version=item["version"], size=len(item["blob"]), offset=offset,
                    data=item["blob"][offset:offset + VIEW_CHUNK])

    def view_lot(self, params):
        item = self._item(params, ("lot",))
        return item["view"].lot(params.get("lot"))

    def view_raw(self, params):
        item = self._item(params, ("report",))
        raw = item["view"].raw(params.get("report"))
        raw["path"] = str(Path(raw["folder"]) / raw["f"]) if raw["folder"] else ""
        return raw

    def save_choices(self, params):
        """개발자 기능 [선택 저장]: changes = [[lot, 줄, wafer key, 위치]]. 추천과 같으면 저장에서 지운다.
        저장 뒤 조사·찾기 결과를 같은 선택으로 다시 계산한다(가동률·WPH·Dice 합계 모두)."""
        item = self._item(params, ("changes",))
        changes = params.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 5000:
            raise ValueError("저장할 선택이 없습니다")
        _, _, root, _ = self.configuration()
        path = root / "Cache" / CHOICES_FILE
        data = read_json(path)
        choices = dict(data.get("choices") or {}) if data.get("schema") == 1 else {}
        view = item["view"]
        for change in changes:
            if not isinstance(change, list) or len(change) != 4 or not isinstance(change[2], str) \
                    or type(change[0]) is not int or type(change[1]) is not int or type(change[3]) is not int:
                raise ValueError("저장할 선택을 확인하세요")
            li, bi, wk, pos = change
            bunch, wafer = view.choice_key(li, bi, wk)
            cell = next((c for c in wafer["cells"] if c["attempt"] == pos and c["pass"]), None)
            if cell is None:
                raise ValueError("Pass 한 Batch Report 만 고를 수 있습니다")
            recommended = max(c["attempt"] for c in wafer["cells"] if c["pass"])
            key = _choice_key(bunch["key"], wafer["key"])
            if pos == recommended:
                choices.pop(key, None)
            else:
                choices[key] = bunch["attempts"][pos]["id"]
        path.parent.mkdir(parents=True, exist_ok=True)
        atomicfile.write_json(path, {"schema": 1, "choices": choices})
        out = {}
        for name, old in list(self._view_items().items()):
            out[name] = self.set_view(name, old["records"], old["extra"], old["hits"])
        return dict(saved=len(choices), views=out)

    def restore(self):
        """화면을 열 때: 지난 조사 범위를 로컬 캐시만으로 다시 보여 준다(장비 접근 없음)."""
        cfg, paths, root, last = self.configuration()
        targets = []
        for item in last.get("targets") or []:
            if not isinstance(item, dict) or item.get("machine") not in paths or not isinstance(item.get("folder"), str):
                continue
            try:
                batchreport_store.dates(item)
            except (ValueError, TypeError):
                continue
            targets.append(item)
        if not targets:
            return dict(meta=self.view_meta("scope"), restored=False)
        collection = batchreport_store.load_cached(root, targets)
        self.set_view("scope", collection["records"], extra=dict(
            scope=_scope_of(targets, last.get("options")), restored=True,
            mstat={m: dict(v, cached=True) for m, v in collection["by_machine"].items()},
            collection=dict(parsed=0, reused=len(collection["records"]), errors=0, cached_only=len(collection["records"])),
            artifacts={}))
        return dict(meta=self.view_meta("scope"), restored=True)

    def scope_extra(self, prepared, output):
        _root, targets, opts = prepared
        collection = output["collection"]
        return dict(scope=_scope_of(targets, opts), restored=False, mstat=collection.get("by_machine", {}),
                    collection={"parsed": collection["parsed"], "reused": collection["reused"],
                                "errors": len(collection["errors"]), "cached_only": collection["cached_only"]},
                    errors=[[e["machine"], e["source_file"], e["error"]] for e in collection["errors"][:200]],
                    artifacts={k: output[k] for k in ("outdir", "html", "lots", "xlsx", "dashboard")})

    def prepare_find(self, params):
        if not isinstance(params, dict) or set(params) - {"machines", "query", "start", "end"}:
            raise ValueError("검색 조건을 확인하세요")
        cfg, paths, root, _ = self.configuration()
        machines = params.get("machines")
        if not isinstance(machines, list) or not 1 <= len(machines) <= MAX_FIND_MACHINES or any(
                not isinstance(m, str) or m not in paths for m in machines):
            raise ValueError("찾을 호기를 하나 이상 고르세요")
        target = {}
        for key in ("query", "start", "end"):
            value = params.get(key, "")
            if not isinstance(value, str) or len(value) > 256:
                raise ValueError("키워드/기간을 확인하세요")
            target[key] = value.strip()
        if not target["query"]:
            raise ValueError("Batch Report 키워드를 입력하세요")
        batchreport_store.dates(target)
        folders = []
        for m in dict.fromkeys(machines):
            for folder in dict.fromkeys([paths[m], *cfg.get("batch_extra_paths", {}).get(m, [])]):
                if isinstance(folder, str) and Path(folder).is_absolute():
                    folders.append((m, folder))
        batchreport_store.local_root(root, [f for _, f in folders])
        return root, folders, target, cfg

    def find(self, prepared, stage="equipment", progress=None, cancel=None, host_gap=2.0):
        """찾기 1단계(이슈 #19): **파일 이름만** 본다 — Batch Report 원문은 열지 않는다.

        ① 로컬 조사 캐시(배치분석/누적 — [조사 시작]으로 이미 읽어 둔 것)에서 먼저 찾는다(장비 접근 없음, 즉시).
        ② stage='equipment' 면 고른 호기 Reports 폴더 이름 목록도 본다(캐시에 없는 새 Batch Report 를 더함).
        결과 = 찾은 파일 이름 목록. 원문 읽기 · Lot 묶기 · Scanresult 확인은 사람이 고른 것만(`find_load`)."""
        import time as _time
        if stage not in ("cache", "equipment"):
            raise ValueError("검색 조건을 확인하세요")
        root, folders, target, cfg = prepared
        start, end = batchreport_store.dates(target)
        cached = _cached_names(root, folders)
        names = {pair: dict.fromkeys(cached.get(pair, ()), True) for pair in folders}
        listed, offline, prev = 0, [], None
        if stage == "equipment":
            for machine, folder in folders:
                batchreport_store.checkpoint(cancel)
                if prev is not None and prev != machine and host_gap:
                    _time.sleep(host_gap)             # 장비 사이 간격(접속 매너) — 같은 호기 추가 폴더 사이는 없음
                prev = machine
                if progress:
                    progress(f"{machine}: Reports 폴더 이름 확인 중…")
                try:
                    if not Path(folder).is_dir():
                        raise OSError(folder)
                    found = wph.list_reports(folder, "", None, None)
                except OSError:
                    offline.append(machine)
                    continue
                listed += len(found)
                pool = names[(machine, folder)]
                for x in found:
                    pool.setdefault(x, False)
        hits = []
        for (machine, folder), pool in names.items():
            for x, in_cache in pool.items():
                if wph._matches(x, target["query"], start, end):
                    t = wph.parse_filename_datetime(x)
                    hits.append(dict(m=machine, folder=folder, f=x, c=in_cache,
                                     t=t.strftime("%Y-%m-%d %H:%M:%S") if t else ""))
        if len(hits) > MAX_FIND_HITS:
            raise ValueError(f"찾은 Batch Report 가 {len(hits):,}개로 너무 많습니다. 키워드/기간을 좁히세요.")
        hits.sort(key=lambda h: (h["t"], h["m"], h["f"].lower()), reverse=True)
        self._find = dict(prepared=prepared, names=names, hits=hits, stage=stage)
        return dict(stage=stage, query=target["query"], start=target["start"], end=target["end"],
                    hits=[dict(i=i, m=h["m"], f=h["f"], t=h["t"], c=h["c"]) for i, h in enumerate(hits)],
                    total=len(hits), cached=sum(1 for h in hits if h["c"]), listed=listed,
                    offline=list(dict.fromkeys(offline)), neighbor_h=NEIGHBOR_H)

    def find_load(self, params, progress=None, cancel=None, host_gap=2.0):
        """찾기 2단계(이슈 #19): 사람이 고른 Batch Report 와, 같은 호기에서 그 앞뒤 NEIGHBOR_H(24)시간 안에
        스캔한 Batch Report 만 읽어(캐시에 있으면 장비 접근 없음) Lot 으로 모으고 Scanresult 경로를 확인한다
        — 키워드에 안 걸린 이어서 스캔도 놓치지 않게."""
        import os
        from datetime import timedelta
        state = getattr(self, "_find", None)
        if not isinstance(params, dict) or set(params) - {"hits"}:
            raise ValueError("요청을 확인하세요")
        if not state:
            raise ValueError("먼저 [검색]을 눌러 주세요")
        picks = params.get("hits")
        if not isinstance(picks, list) or not 1 <= len(picks) <= MAX_FIND_PICK or any(
                type(i) is not int or not 0 <= i < len(state["hits"]) for i in picks):
            raise ValueError(f"읽을 Batch Report 를 1~{MAX_FIND_PICK}개 고르세요")
        root, folders, target, cfg = state["prepared"]
        chosen = {}
        for i in dict.fromkeys(picks):
            h = state["hits"][i]
            chosen.setdefault((h["m"], h["folder"]), set()).add(h["f"])
        gap = timedelta(hours=NEIGHBOR_H)
        targets, live = [], set()
        for pair in folders:
            sel = chosen.get(pair)
            if not sel:
                continue
            stamps = [w for w in (wph.parse_filename_datetime(x) for x in sel) if w]
            pool = state["names"][pair]
            keep = set(sel)
            for x in pool:
                t = wph.parse_filename_datetime(x)
                if t and any(abs(t - w) <= gap for w in stamps):
                    keep.add(x)
            if len(keep) > 20000:
                raise ValueError("읽을 Batch Report 가 너무 많습니다. 고른 것을 줄이세요.")
            if any(not pool.get(x, False) for x in keep):
                live.add(pair[0])                 # 캐시에 없는 것이 있으면 그 호기는 장비에서 읽는다
            targets.append(dict(machine=pair[0], folder=pair[1], query="", start="", end="", names=sorted(keep)))
        records, errors = [], []
        cached_targets = [t for t in targets if t["machine"] not in live]
        live_targets = [t for t in targets if t["machine"] in live]
        if cached_targets:
            if progress:
                progress("로컬 캐시에서 읽는 중…")
            records += batchreport_store.load_cached(root, cached_targets)["records"]
        if live_targets:
            collection = batchreport_store.collect(root, live_targets, (lambda *a: progress(str(a[-1]))) if progress else None,
                                                   host_gap=host_gap, cancel=cancel)
            records += collection["records"]
            errors = collection["errors"]

        def norm(folder):
            return os.path.normcase(str(Path(folder)))
        wanted = {(m, norm(f), x) for (m, f), sel in chosen.items() for x in sel}
        hit_ids = {r["id"] for r in records
                   if (r["machine"], norm(r["source_folder"]), r["report"].get("file_name")) in wanted}
        scan = _scanresult_paths(cfg, [r for r in records if r["id"] in hit_ids] + [r for r in records if r["id"] not in hit_ids],
                                 progress, cancel)
        from .desktop_config import scan_backup
        self.set_view("find", records, hits=hit_ids, extra=dict(
            find=dict(target, total=len(hit_ids), picked=len(set(picks)), reports=len(records), neighbor_h=NEIGHBOR_H,
                      cached_only=not live_targets),
            scan=scan, scan_backup=scan_backup(cfg),
            errors=[[e["machine"], e["source_file"], e["error"]] for e in errors[:200]]))
        return self.view_meta("find")

    def aggregate(self, params):
        item = self._item(params, ("reports",))
        return dict(groups=item["view"].aggregate(params.get("reports")))

    def export(self, params):
        """찾기·취합 결과 / Lot 창 취합을 Excel 로(로컬 결과 폴더). 1행 = 선택 기준."""
        from . import batchview
        item = self._item(params, ("kind", "reports", "choices", "lot", "drafts", "stamp"))
        view, payload = item["view"], item["view"].payload()
        R, lots = payload["R"], payload["lots"]
        stamp_text = params.get("stamp")
        if not isinstance(stamp_text, str) or len(stamp_text) > 300:
            raise ValueError("선택 기준 문구를 확인하세요")
        _, _, root, _ = self.configuration()
        folder = root / "배치분석" / "취합"
        folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")

        def yld(sc, good):
            return round(good / sc * 100, 2) if sc else None

        def source(g):
            raw = view.records[g]
            return str(Path(raw.get("source_folder", "")) / R[g]["f"]) if raw.get("source_folder") else R[g]["f"]
        lot_rows, wafer_rows = [], []
        if params.get("kind") == "agg":
            choices = params.get("choices") or {}
            if not isinstance(choices, dict) or len(choices) > 50000:
                raise ValueError("선택을 확인하세요")
            for gi, grp in enumerate(view.aggregate(params.get("reports"))):
                lot, b = lots[grp["li"]], lots[grp["li"]]["bunches"][grp["bi"]]
                t = dict(sc=0, bad=0, good=0, ok=0, no=0)
                for k in grp["keys"]:
                    w = grp["w"][k]
                    j = choices.get(f"{gi}|{k}", w["rec"])
                    if type(j) is not int or not 0 <= j < len(w["cells"]):
                        raise ValueError("선택을 확인하세요")
                    x = w["cells"][j]
                    if x["ok"]:
                        t["ok"] += 1
                        if x["sc"] is not None:
                            t["sc"] += x["sc"]; t["bad"] += x["bad"] or 0; t["good"] += x["good"] or 0
                    else:
                        t["no"] += 1
                    real = next((c["id"] for c in w["cells"] if batchview.lm.is_real_id(c["id"])), x["id"])
                    wafer_rows.append([lot["label"], batchview.step_label(b["step"], b.get("k")), k.replace("ID:", ""), real, x["status"],
                                       "Pass" if x["ok"] else "Pass 없음", R[x["g"]]["f"], R[x["g"]]["m"], R[x["g"]]["s"],
                                       x["sc"], x["bad"], x["good"], yld(x["sc"], x["good"]), source(x["g"])])
                lot_rows.append([lot["label"], batchview.step_label(b["step"], b.get("k")), f"{b['s']} ~ {b['e']}", " → ".join(b["machines"]), len(grp["att"]),
                                 len(grp["keys"]), t["ok"], t["no"], t["sc"], t["bad"], t["good"], yld(t["sc"], t["good"])])
            name, title = f"BatchReport_취합_{now}.xlsx", "Batch Report 찾기 · 취합"
        elif params.get("kind") == "lot":
            detail = view.lot(params.get("lot"))
            drafts = params.get("drafts") or {}
            if not isinstance(drafts, dict) or len(drafts) > 5000:
                raise ValueError("선택을 확인하세요")
            lot = lots[detail["li"]]
            for bi, (b, d) in enumerate(zip(lot["bunches"], detail["bunches"])):
                t = dict(sc=0, bad=0, good=0, ok=0, no=0)
                for w in d["wafers"]:
                    p = drafts.get(f"{bi}|{w['k']}", w["pick"])
                    cell = next((c for c in w["cells"] if c[0] == p), None) if p is not None else None
                    if cell and cell[2]:
                        t["ok"] += 1
                        if cell[4] is not None:
                            t["sc"] += cell[4]; t["bad"] += cell[5] or 0; t["good"] += cell[6] or 0
                    else:
                        t["no"] += 1
                    last = cell or w["cells"][-1]
                    g = b["att"][last[0]]
                    wafer_rows.append([lot["label"], batchview.step_label(b["step"], b.get("k")), w["slot"] if w["slot"] is not None else w["id"], w["id"],
                                       last[1], w["v"], R[g]["f"] if cell else "", R[g]["m"] if cell else "", R[g]["s"] if cell else "",
                                       cell[4] if cell else None, cell[5] if cell else None, cell[6] if cell else None,
                                       yld(cell[4], cell[6]) if cell and cell[4] is not None else None, source(g) if cell else ""])
                lot_rows.append([lot["label"], batchview.step_label(b["step"], b.get("k")), f"{b['s']} ~ {b['e']}", " → ".join(b["machines"]), len(b["att"]),
                                 len(d["wafers"]), t["ok"], t["no"], t["sc"], t["bad"], t["good"], yld(t["sc"], t["good"])])
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in lot["label"])[:60]
            name, title = f"Lot_{safe}_취합_{now}.xlsx", f"Lot {lot['label']} 취합"
        else:
            raise ValueError("요청을 확인하세요")
        path = folder / name
        batchview.write_excel(path, title, stamp_text, lot_rows, wafer_rows)
        return dict(path=str(path))


    # ---- 레시피 비교 모드(이슈 #14) — 지금 조사 결과(View) 위에서 계산(장비 접근 없음)
    def compare_recipes(self, params):
        from . import recipecompare
        item = self._item(params)
        return dict(recipes=recipecompare.recipes(item["view"]))

    def compare(self, params):
        from . import recipecompare
        item = self._item(params, ("spec",))
        return recipecompare.compare(item["view"], params.get("spec"))

    def compare_export(self, params):
        """비교 결과 HTML(앱 디자인 · 원문 포함)을 로컬 배치분석/비교 폴더에 저장."""
        from . import batchreport_output as output, recipecompare
        item = self._item(params, ("spec",))
        result = recipecompare.compare(item["view"], params.get("spec"))
        _, _, root, _ = self.configuration()
        folder = root / "배치분석" / "비교"
        folder.mkdir(parents=True, exist_ok=True)
        safe = lambda t: "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in t)[:30]
        g = result["groups"]
        path = folder / f"레시피비교_{safe(g['a']['name'])}_vs_{safe(g['b']['name'])}_{datetime.now():%Y%m%d_%H%M%S}.html"
        output.atomic_text(path, recipecompare.build_html(result, item["view"]))
        return dict(path=str(path))

    def cache_export(self, params):
        """조사로 취합한 Batch Report 캐시(배치분석/누적/*.json — 호기·폴더별 원문 전부)를 zip 1개로 내보낸다(이슈 #16).
        장비 접근 없음. 캐시는 한 파일씩 읽어 개수만 세고 그대로 압축한다(전체를 메모리에 모으지 않음).
        manifest.json = 내보낸 시각 · 버전 · 파일별 호기 · 원본 폴더 · Batch Report 수. 사람 선택(Cache)도 있으면 함께."""
        import zipfile
        from . import __version__
        if params:
            raise ValueError("요청을 확인하세요")
        _, _, root, _ = self.configuration()
        source = root / "배치분석" / "누적"
        caches = []
        if source.is_dir():
            for path in sorted(source.glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    with path.open(encoding="utf-8") as stream:
                        state = json.load(stream)
                except (OSError, ValueError):
                    continue
                if state.get("schema") != batchreport_store.SCHEMA or not isinstance(state.get("entries"), dict):
                    continue
                caches.append((path, str(state.get("machine") or ""), str(state.get("folder") or ""), len(state["entries"])))
                del state
        if not caches:
            raise ValueError("내보낼 Batch Report 캐시가 없습니다. 먼저 [조사 시작]으로 조사하세요.")
        folder = root / "배치분석" / "내보내기"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now()
        target = folder / f"BatchReport_캐시_{stamp:%Y%m%d_%H%M%S}.zip"
        safe = lambda t: "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in t)[:40] or "호기"
        files = []
        temporary = target.with_name("." + target.name + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for path, machine, src, count in caches:
                    name = f"누적/{safe(machine)}_{path.stem[:8]}.json"
                    zf.write(path, name)
                    files.append(dict(file=name, machine=machine, folder=src, reports=count))
                choices = root / "Cache" / CHOICES_FILE
                if choices.is_file() and not choices.is_symlink():
                    zf.write(choices, "사람선택/" + CHOICES_FILE)
                manifest = dict(schema=1, exported_at=stamp.strftime("%Y-%m-%d %H:%M:%S"), app_version=__version__,
                                cache_schema=batchreport_store.SCHEMA, machines=len({f["machine"] for f in files}),
                                reports=sum(f["reports"] for f in files), files=files)
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
        # 최근 3개만 남긴다(캐시가 크면 zip 도 크다).
        for old in sorted(folder.glob("BatchReport_캐시_*.zip"))[:-3]:
            try:
                old.unlink()
            except OSError:
                pass
        return dict(path=str(target), folder=str(folder), files=len(files), machines=manifest["machines"],
                    reports=manifest["reports"], size=target.stat().st_size)


class DesktopBatch(BatchViews):
    def __init__(self, config_path=None):
        # Only tests inject config_path; IPC never accepts it.
        self.config_path = config_path or Path.home() / ".pi_param_manager.json"

    def configuration(self):
        from . import desktop_diag
        with desktop_diag.timed(f"설정 파일 읽기 {self.config_path}", 200):
            cfg = read_json(self.config_path)
        paths = cfg.get("wph_report_paths") or {}
        if not isinstance(paths, dict):
            raise ValueError("기존 Report 폴더 설정을 확인하세요")
        from .desktop_appupdate import default_local_root
        # Packaged web app: never default into the install folder (an update replaces it).
        requested_root = Path(cfg.get("local_dir") or default_local_root()).absolute()
        for part in (requested_root, *requested_root.parents):
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("로컬 결과 폴더의 연결 경로는 사용할 수 없습니다")
        with desktop_diag.timed(f"로컬 결과 폴더 확인 {requested_root}", 200):
            root = batchreport_store.local_root(requested_root, paths.values())
        # Reject redirected output trees, including cache/output directory junctions.
        with desktop_diag.timed("로컬 결과 폴더 연결경로 검사", 200):
            for path in (root, root / "Cache", root / "배치분석", root / "배치분석" / "누적", root / "배치분석" / "대시보드",
                         root / "배치분석" / "내보내기"):
                for part in (path, *path.parents):
                    if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                        raise ValueError("로컬 결과 폴더의 연결 경로는 사용할 수 없습니다")
        with desktop_diag.timed("최근 조사 설정 읽기(Cache/rev1_batch_last.json)", 200):
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
            # Hide retired metric keys (e.g. M07, M09) from the UI's restored selection.
            last = dict(last, options=dict(saved, metrics=[
                m for m in saved["metrics"] if isinstance(m, str) and m in batchreport.METRICS]))
        cfg = read_json(self.config_path)
        extra = cfg.get("batch_extra_paths") if isinstance(cfg.get("batch_extra_paths"), dict) else {}
        return dict(machines=[dict(id=name, folder=folder, extra=[p for p in extra.get(name, []) if isinstance(p, str)])
                              for name, folder in sorted(paths.items(), key=lambda kv: _name_key(kv[0]))],
                    local_root=str(root), last=last, auto=self.auto_state(cfg),
                    # Engine titles so the UI labels never drift from the analysis (A10).
                    metrics=[dict(id=k, title=v) for k, v in batchreport.METRICS.items()],
                    # Lot 판정 기준 — 화면 ? 버튼과 Lot 추적 HTML 이 같은 문구(엔진 한 곳)를 쓴다.
                    lot_criteria=[dict(title=t, text=d, example=e) for t, d, e in lotreport.CRITERIA])

    def auto_state(self, cfg=None):
        """Daily automatic re-run (tkinter `batch_auto`/`batch_schedule`, shared keys so
        the two programs never both run the same day)."""
        cfg = read_json(self.config_path) if cfg is None else cfg
        schedule = cfg.get("batch_schedule") if isinstance(cfg.get("batch_schedule"), dict) else {}
        settings = watcher.WatchSettings(enabled=bool(cfg.get("batch_auto")), interval_hours=batch_interval(cfg))
        state = watcher.WatchState.from_dict(schedule)
        nxt = watcher.next_run_at(settings, state) if settings.enabled and state.last_run else None
        return dict(enabled=settings.enabled, interval_hours=settings.interval_hours, last_run=state.last_run,
                    last_result=state.last_result, next_run=nxt.strftime("%Y-%m-%d %H:%M") if nxt else "",
                    due=bool(watcher.should_run(datetime.now(), settings, state)))

    def record_run(self, ok, partial=False, error=""):
        """Record the run in `batch_schedule` with the watcher's `%Y-%m-%d %H:%M:%S`
        format (an ISO 'T' timestamp would make the watcher re-run every minute)."""
        cfg = read_json(self.config_path)
        old = cfg.get("batch_schedule") if isinstance(cfg.get("batch_schedule"), dict) else {}
        try:
            fails = int(old.get("fail_count", 0))
        except (TypeError, ValueError):
            fails = 0
        cfg["batch_schedule"] = {"last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 "fail_count": 0 if ok and not partial else min(fails + 1, 4),
                                 "last_result": "완료" if ok and not partial else "일부 오류" if ok else error or "실패"}
        atomicfile.write_json(str(self.config_path), cfg)

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
        return batchreport_service.run(root, targets, opts, progress=progress, cancel=cancel, overrides=self._load_choices())
