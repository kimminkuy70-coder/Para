"""New Commonality investigation (web): plan → Lot/slot choice → safe copy →
per device/recipe form (coefficients, parameter editor) → Lot values → result.

Port of the tkinter `_cm_*` flow (`_cm_upload_plan` … `_cm_collate`) as
protocol steps. The equipment Scanresult tree is only read (safe copy of the
target files into the local Commonality run folder, verified). Results are
written where the existing compare screen already looks, so a finished run
shows up in [저장 결과 비교] right away.

A run is split into *units* — one per (device, recipe) — exactly like the
tkinter device → recipe queues. Each unit goes: detect variants/coefficients →
parse Lots → edit the form (same editor model as 양식 만들기) → confirm form →
confirm variant names → collate and write `조사_*.xlsx`.
"""
from pathlib import Path

from . import (coef_detector, coefstore, collate, commonality as cm, engine, editor_model,
               extract_io, formbuilder, ini_parser, localdirs, namestore, workdirs)
from .desktop_batch import DesktopBatch, read_json
from .desktop_cmsurvey import DesktopCmSurvey
from .desktop_form import DesktopForm

MAX_LOTS = 500


class DesktopCmRun:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.survey = DesktopCmSurvey(self.config_path)
        self.form = DesktopForm(self.config_path)   # page/edit reused for the unit form
        self.state = None

    # ---- helpers -----------------------------------------------------------
    def _save_dir(self):
        cfg = read_json(self.config_path)
        return cfg.get("save_dir") or ""

    def _cm_root(self):
        root = str(DesktopBatch(self.config_path).configuration()[2])
        return localdirs.commonality_dir(localdirs.ensure(root))

    def _coef_rows(self):
        save = self._save_dir()
        path = coefstore.coef_path(save) if save else ""
        return coefstore.load(path) if path and Path(path).is_file() else []

    def _need(self, *keys):
        if not self.state or any(k not in self.state for k in keys):
            raise ValueError("Commonality 조사를 처음부터 다시 진행하세요")
        return self.state

    def _unit(self, params):
        state = self._need("units")
        idx = params.get("unit")
        if type(idx) is not int or not 0 <= idx < len(state["units"]):
            raise ValueError("조사 단위를 확인하세요")
        return state["units"][idx]

    # ---- 1. plan → Lot folders ----------------------------------------------
    def plan(self, params):
        """Resolve the Lot plan on the machine's Scanresult roots (read-only)."""
        if set(params) - {"machine", "plan"}:
            raise ValueError("호기와 계획을 확인하세요")
        machine = params.get("machine")
        roots = self.survey._roots()
        if not isinstance(machine, str) or machine not in roots:
            raise ValueError("Scanresult 루트가 설정된 호기를 선택하세요")
        mine = cm.filter_plan_for_machine(self.survey._validate_plan(params.get("plan")), machine)
        if not mine:
            raise ValueError("이 호기에 해당하는 계획 행이 없습니다. AOI호기를 확인하세요.")
        scan_roots = cm.scanresult_roots(roots[machine], machine)
        lots = cm.resolve_plan(scan_roots, mine)
        if len(lots) > MAX_LOTS:
            raise ValueError("S/M 폴더가 너무 많습니다. 계획을 나눠 진행하세요.")
        self.state = dict(machine=machine, lots=lots)
        return dict(machine=machine, roots=[str(r) for r in scan_roots], lots=[
            dict(id=i, label=l.label, device=l.device, lot=l.lot, sm=l.sm, exists=bool(l.exists),
                 fail=bool(l.fail), scan_time=l.scan_time, created=l.created, reason=l.reason,
                 wafers=[p.name for p in l.wafer_choices],
                 wafer=l.wafer_dir.name if l.wafer_dir is not None else "")
            for i, l in enumerate(lots)])

    # ---- 2. safe copy -----------------------------------------------------------
    def copy(self, params):
        """Copy the chosen S/M folders (and chosen slots) into a new local run."""
        if set(params) != {"picks"} or not isinstance(params["picks"], list) or not params["picks"]:
            raise ValueError("복사할 S/M 폴더를 하나 이상 고르세요")
        state = self._need("lots", "machine")
        lots, selected = state["lots"], []
        for pick in params["picks"]:
            if not isinstance(pick, dict) or set(pick) - {"id", "wafers"}:
                raise ValueError("S/M 선택을 확인하세요")
            idx, wafers = pick.get("id"), pick.get("wafers") or []
            if type(idx) is not int or not 0 <= idx < len(lots) or not lots[idx].exists:
                raise ValueError("찾은 S/M 폴더만 고를 수 있습니다")
            lot = lots[idx]
            if not isinstance(wafers, list) or any(not isinstance(w, str) for w in wafers):
                raise ValueError("슬롯 선택을 확인하세요")
            if wafers:
                by_name = {p.name: p for p in lot.wafer_choices}
                if set(wafers) - set(by_name):
                    raise ValueError("목록에 있는 슬롯만 고를 수 있습니다")
                lot.wafer_picks = [by_name[w] for w in wafers]
                cm.set_wafer(lot, lot.wafer_picks[0])
            selected.append(lot)
        selected = cm.expand_all(selected)      # several slots of one Lot → one column each
        machine, st = state["machine"], workdirs.stamp()
        run_dir = workdirs.commonality_run_dir(self._cm_root(), machine, st)
        staging = workdirs.commonality_staging(run_dir)
        lot_dirs, fails = [], []
        for lot in selected:
            res = cm.copy_lot(lot, staging, verify=True)
            lot_dirs.append((lot.label, res["dest"]))
            if lot.fail:
                fails.append(lot.label)
        state.update(selected=selected, run_dir=run_dir, st=st, staging=staging, lot_dirs=lot_dirs,
                     fail_labels=fails, lot_devices={l.label: l.device for l in selected})
        state["units"] = self._units(lot_dirs, state["lot_devices"])
        return dict(copied=len(lot_dirs), fails=len(fails), staging=staging, units=self._units_view())

    def _units(self, lot_dirs, devices):
        """Device → recipe queue (tkinter `_cm_make_form` / `_cm_process_device`)."""
        groups = cm.group_lot_dirs_by_device(lot_dirs, devices)
        units = []
        for dev, pairs in groups:
            dirs = [(lbl, Path(d)) for lbl, d in pairs]
            pre = cm.form_preflight(dirs)
            recipes = cm.detect_recipes(dirs) or [{"name": "", "prefix": ""}]
            files = pre.get("files") or {}
            for rec in recipes:
                name = engine._s(rec.get("name")).strip()
                info = files.get(name, {})
                units.append(dict(device=dev if len(groups) > 1 else "", recipe=name,
                                  prefix=rec.get("prefix", ""), lot_dirs=dirs,
                                  files=dict(global_=bool(info.get("global")), optic=bool(info.get("optic")),
                                             zones=int(info.get("zones", 0) or 0)),
                                  thin=bool(info.get("thin")), config_dir=str(pre.get("config_dir") or ""),
                                  done=None))
        return units

    def _units_view(self):
        return [dict(unit=i, device=u["device"], recipe=u["recipe"], lots=len(u["lot_dirs"]),
                     files=u["files"], thin=u["thin"], config_dir=u["config_dir"],
                     title=u.get("title", ""), result=u["done"] or "")
                for i, u in enumerate(self.state["units"])]

    def units(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        self._need("units")
        return dict(units=self._units_view(), machine=self.state["machine"])

    # ---- 3. per unit: variants + coefficients ---------------------------------------
    def detect(self, params):
        if set(params) != {"unit", "base"} or not isinstance(params["base"], str) or not params["base"].strip():
            raise ValueError("조사 제목을 입력하세요")
        unit = self._unit(params)
        base = params["base"].strip()
        if len(base) > 80 or any(c in base for c in '<>:"/\\|?*'):
            raise ValueError("조사 제목에 파일 이름으로 쓸 수 없는 문자가 있습니다")
        # '조사제목[_디바이스][_레시피]' so branches of one investigation stay recognisable.
        unit["title"] = "_".join(p for p in (base, unit["device"], unit["recipe"]) if p)
        variants, dirs = [], {}
        for _lbl, d in unit["lot_dirs"]:
            for c in ini_parser.scan_tree(d, default_level=unit["title"], recipe_prefix=unit["prefix"]):
                v = c.mag or ""
                if v not in variants:
                    variants.append(v)
                    dirs[v] = c.config_dir
        variants = variants or [""]
        rows, machine = self._coef_rows(), self.state["machine"]
        out = []
        for v in variants:
            try:
                reco = coef_detector.detect_from_dir(dirs[v]) if dirs.get(v) else None
            except Exception:  # noqa: BLE001 - a recommendation is optional
                reco = None
            stored = coefstore.lookup(rows, machine, v) if rows else None
            recommended = (reco or {}).get("Coefficient")
            value = stored if stored is not None else recommended if recommended is not None else ini_parser.DEFAULT_SCALE
            out.append(dict(variant=v, coef=value,
                            source="변환계수.xlsx" if stored is not None else "RTP 추정" if recommended is not None else "기본값",
                            confidence=(reco or {}).get("Confidence", ""), reason=(reco or {}).get("Reason", "")))
        unit["variants"] = [x["variant"] for x in out]
        return dict(unit=params["unit"], title=unit["title"], scales=out,
                    known=[float(f"{s:.16g}") for s in ini_parser.KNOWN_SCALES])

    # ---- 4. parse Lots → editable form ---------------------------------------------
    def parse(self, params):
        if set(params) != {"unit", "scales", "base_form"}:
            raise ValueError("변환계수를 확인하세요")
        unit = self._unit(params)
        if "title" not in unit:
            raise ValueError("먼저 조사 제목과 변환계수를 확인하세요")
        scales = params["scales"]
        if not isinstance(scales, dict) or any(
                k not in unit.get("variants", []) or type(v) not in (int, float) or not 0 < v <= 1e6
                for k, v in scales.items()):
            raise ValueError("변환계수는 0보다 큰 숫자여야 합니다")
        machine, rows = self.state["machine"], self._coef_rows()
        unit["scales"] = {k: float(v) for k, v in scales.items()}

        def lookup(_equipment, variant=""):
            return coefstore.lookup(rows, machine, variant)   # Commonality: fixed machine
        pivot, labels = cm.parse_lots(unit["lot_dirs"], level=unit["title"], scales=unit["scales"],
                                      coef_lookup=lookup, recipe_prefix=unit["prefix"])
        if not pivot:
            raise ValueError("읽힌 파라미터가 없습니다. 복사된 설정 파일을 확인하세요.")
        unit["pivot"], unit["labels"] = pivot, labels
        save = self._save_dir()
        from .formcache import similar_forms
        from .desktop_batch import DesktopBatch
        # Cached per form file (local): unchanged forms are not re-opened on OneDrive.
        forms = similar_forms(save, str(DesktopBatch(self.config_path).configuration()[2]), exclude=None) if save else {}
        ranked = formbuilder.rank_similar_forms(formbuilder.pivot_param_keys(pivot), forms)
        base_form = params["base_form"]
        if not isinstance(base_form, str) or (base_form and base_form not in forms):
            raise ValueError("기준 양식을 확인하세요")
        base_keys = forms[base_form] if base_form else None
        name_rows = []
        if save:
            try:
                name_rows = namestore.load(namestore.name_path(save))
            except (OSError, ValueError):
                name_rows = []
        entries = editor_model.build_entries(pivot, base_keys=base_keys,
                                             name_lookup=namestore.make_lookup(name_rows),
                                             use_lookup=namestore.make_use_lookup(name_rows))
        opened = self.form.load_entries(entries, level=unit["title"], recipe=unit["title"], source=f"commonality {machine}")
        return dict(unit=params["unit"], form=opened, labels=labels,
                    similar=[dict(recipe=r, match=n, total=t) for r, n, t in ranked[:8]], base_form=base_form)

    # ---- 5. confirm the unit form ---------------------------------------------
    def confirm(self, params):
        if set(params) != {"unit", "snapshot"}:
            raise ValueError("양식을 확인하세요")
        unit = self._unit(params)
        if "pivot" not in unit or params["snapshot"] != self.form.version:
            raise ValueError("양식 편집 화면을 새로고침하세요")
        entries = self.form.entries
        scales = unit.get("scales", {})
        selected = [dict(use=e["use"], name=e["name"], reco=e["reco"], variant=e["variant"], zone=e["zone"],
                         alg=e["alg"], ext=e["ext"], method=e["label"],
                         coef=scales.get(e["variant"], ini_parser.DEFAULT_SCALE)) for e in entries]
        records, extracts, used = editor_model.build_records(selected, unit["title"])
        if not records:
            raise ValueError("사용할 항목이 없습니다. 한 개 이상 체크하세요.")
        state = self.state
        form_path = workdirs.commonality_form_path(state["run_dir"], unit["title"], state["machine"], state["st"])
        sheet = "RDL_ALL" if unit["title"].upper().startswith("RDL") else "PI_ALL"
        extract_io.write_snapshot(form_path, records, machines=[], sheet_name=sheet, extracts=extracts,
                                  stage="final", level=unit["title"], aoi=state["machine"],
                                  source=f"commonality {unit['title']}", user=engine.current_user(), scales=used)
        unit["form_path"] = form_path
        table = collate.variant_match_table(collate.form_variants(form_path), collate.parsed_variants(unit["pivot"]))
        needed = any(engine._s(f).strip() for f, _ in table["rows"]) or any(engine._s(p).strip() for p in table["parsed"])
        return dict(unit=params["unit"], form=form_path, kept=len(records),
                    variants=dict(rows=[list(r) for r in table["rows"]], parsed=table["parsed"],
                                  unmatched=table["unmatched_parsed"]) if needed else None)

    # ---- 6. Lot values → result workbook -------------------------------------------
    def collate(self, params):
        if set(params) != {"unit", "mapping"} or not isinstance(params["mapping"], dict):
            raise ValueError("하위 레시피 매칭을 확인하세요")
        unit = self._unit(params)
        if "form_path" not in unit:
            raise ValueError("먼저 양식을 확정하세요")
        mapping = {k: v for k, v in params["mapping"].items()
                   if isinstance(k, str) and isinstance(v, str) and k.strip() != v.strip()}
        pivot = collate.apply_variant_map(unit["pivot"], mapping) if mapping else unit["pivot"]
        state, rows = self.state, self._coef_rows()
        machine = state["machine"]
        result = workdirs.commonality_result_path(state["run_dir"], unit["title"], machine, state["st"])
        res = cm.collate_lots(unit["title"], unit["form_path"], pivot, unit["labels"],
                              coef_lookup=lambda _lot, var: coefstore.lookup(rows, machine, var),
                              variant_orig=collate.invert_variant_map(mapping))
        sel = state.get("selected") or []
        coefs = [f"{r.get('변형') or '(기본)'}: {r.get('계수')}{' / MAG ' + str(r.get('MAG')) if r.get('MAG') else ''}"
                 for r in coefstore.machine_coefs(rows, machine)]
        cm.write_lot_result(result, unit["title"], machine, res, unit["labels"], state.get("fail_labels") or [],
                            coef_note=coefs, scan_times={l.label: l.scan_time for l in sel},
                            created={l.label: l.created for l in sel if engine._s(l.created).strip()})
        unit["done"] = result
        return dict(unit=params["unit"], result=result, matched_rows=res.matched_rows,
                    filled_cells=res.filled_cells, mismatches=len(res.mismatches), units=self._units_view())

    def reset(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        self.state = None
        return dict(reset=True)
