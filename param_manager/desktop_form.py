"""Desktop form-building adapter: open an existing form candidate, edit which
parameters are used / their display names / transforms, and confirm to a new
form version under the configured save_dir.

The UI supplies recipe and version identifiers plus in-memory edits, never
filesystem paths. Equipment/SMB collection of a brand-new recipe is a separate
concern; here the source is an existing candidate (원본/수정본) already under
save_dir, so the whole flow is offline and headless-testable. Confirmation
reuses the tested build_records → extract_io.write_snapshot pipeline and, like
the tkinter finalize, always preserves an editable original alongside the
confirmed workbook.
"""
from pathlib import Path
from uuid import uuid4

import math

from . import (coefstore, collate, editor_model, engine, extract_io, formbuilder,
               ini_parser, locking, namestore, refdata, workdirs)
from .desktop_batch import read_json

MAX_ENTRIES = 40000
KINDS = {"use", "name", "transform"}
METHOD_LABELS = {"RAW", "LINEAR", "AREA"}
SCALED = {"LINEAR", "AREA"}
MAX_SCALE = 1e6


class DesktopForm:
    def __init__(self, config_path=None):
        # Only tests inject config_path; IPC never accepts it.
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.version = None
        self.entries = []
        self.root = None

    # ---- helpers -------------------------------------------------------
    def _load_root(self):
        cfg = read_json(self.config_path)
        if not cfg.get("save_dir"):
            return None
        root = Path(cfg["save_dir"]).absolute()
        for part in (root, *root.parents):
            if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
                raise ValueError("저장폴더의 연결 경로는 사용할 수 없습니다")
        return root

    def _safe(self, path):
        value = Path(path).absolute()
        if value.is_symlink() or not value.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("양식 경로를 확인하세요")
        return str(value)

    def _check(self, params, allowed):
        if set(params) - allowed or not self.version or params.get("snapshot") != self.version:
            raise ValueError("양식 편집 화면을 새로고침하세요")

    # ---- catalog -------------------------------------------------------
    def catalog(self):
        self.version, self.entries = None, []
        root = self._load_root()
        if root is None:
            return dict(save_dir=False, recipes=[])
        self.root = root
        recipes = []
        for recipe in workdirs.list_recipes(str(root)):
            versions = [dict(stamp=v["stamp"], has_candidate=v["has_candidate"], kind=v["kind"])
                        for v in workdirs.form_version_status(str(root), recipe)]
            recipes.append(dict(recipe=recipe, versions=versions,
                                can_edit=any(v["has_candidate"] for v in versions)))
        return dict(save_dir=True, recipes=recipes, machines=self._machines())

    def _machines(self):
        # Registered machines = the shared '장비 IP' workbook, like the tkinter app.
        try:
            path = self._safe(refdata.ip_path(str(self.root)))
            return refdata.machines(refdata.load_ip(path)) if Path(path).is_file() else []
        except (OSError, ValueError, KeyError):
            return []

    # ---- open ----------------------------------------------------------
    def open(self, params):
        if set(params) - {"recipe", "stamp"}:
            raise ValueError("레시피/버전을 선택하세요")
        self.version, self.entries = None, []
        root = self._load_root()
        if root is None:
            raise ValueError("먼저 저장폴더를 지정하세요")
        self.root = root
        recipe = params.get("recipe")
        if not isinstance(recipe, str) or recipe not in workdirs.list_recipes(str(root)):
            raise ValueError("등록된 레시피를 선택하세요")
        stamp = params.get("stamp", "")
        if not isinstance(stamp, str) or len(stamp) > 64:
            raise ValueError("버전을 확인하세요")
        candidate = None
        for v in workdirs.form_version_status(str(root), recipe):
            if (not stamp or v["stamp"] == stamp) and v["candidate"]:
                candidate = v["candidate"]
                break
        if candidate is None:
            candidate = workdirs.any_candidate_for(str(root), recipe)
        if candidate is None:
            raise ValueError("항목을 추가할 수 있는 원본이 없습니다. 기존 프로그램에서 원본을 만든 버전을 선택하세요.")
        path = self._safe(candidate)
        before = locking.file_stamp(path)
        pivot, _used, _names = formbuilder.initial_to_pivot(path)
        if before != locking.file_stamp(path):
            raise ValueError("조회 중 원본 파일이 변경되었습니다. 다시 열어 주세요.")
        if len(pivot) > MAX_ENTRIES:
            raise ValueError("원본 항목이 너무 많습니다. 기존 프로그램에서 편집하세요.")
        self.recipe = recipe
        self.level = next((engine._s(r.get("recipe")).strip() for r in pivot
                           if engine._s(r.get("recipe")).strip()), recipe)
        self.entries = editor_model.build_entries(pivot)
        self.multi = len(editor_model.variants_of(self.entries)) > 1
        self.version = uuid4().hex
        return dict(version=self.version, recipe=recipe, level=self.level,
                    variants=editor_model.variants_of(self.entries),
                    total=len(self.entries),
                    used=sum(1 for e in self.entries if e["use"]),
                    source=Path(candidate).name)

    # ---- page ----------------------------------------------------------
    def page(self, params):
        self._check(params, {"snapshot", "variant", "query", "used_only", "offset", "limit"})
        variant = params.get("variant", "")
        query = params.get("query", "")
        used_only = params.get("used_only", False)
        if not isinstance(variant, str) or not isinstance(query, str) or len(query) > 256:
            raise ValueError("검색 조건을 확인하세요")
        if type(used_only) is not bool:
            raise ValueError("표시 조건을 확인하세요")
        offset, limit = params.get("offset", 0), params.get("limit", 100)
        for value, low, high in ((offset, 0, 10000000), (limit, 1, 100)):
            if type(value) is not int or not low <= value <= high:
                raise ValueError("표 조회 범위를 확인하세요")
        q = query.casefold()
        matches = []
        for i, e in enumerate(self.entries):
            if variant and e["variant"] != variant:
                continue
            if used_only and not e["use"]:
                continue
            if q and q not in (e["orig"] + " " + e["name"] + " " + e["zone"] + " " + e["alg"]).casefold():
                continue
            matches.append((i, e))
        rows = []
        for i, e in matches[offset:offset + limit]:
            method = editor_model.method_of(e["label"])
            rows.append(dict(id=i, use=e["use"], variant=e["variant"], zone=e["zone"],
                             alg=e["alg"], orig=e["orig"], name=e["name"],
                             transform=method, raw=engine._s(e["raw"]),
                             display=editor_model.safe_display(e["raw"], method, None)))
        return dict(rows=rows, total=len(matches),
                    used=sum(1 for e in self.entries if e["use"]),
                    grand_total=len(self.entries), offset=offset)

    # ---- edit ----------------------------------------------------------
    def edit(self, params):
        self._check(params, {"snapshot", "row", "kind", "value"})
        index, kind, value = params.get("row"), params.get("kind"), params.get("value")
        if type(index) is not int or not 0 <= index < len(self.entries) or kind not in KINDS:
            raise ValueError("사용/이름/변환만 수정할 수 있습니다")
        entry = self.entries[index]
        if kind == "use":
            if type(value) is not bool:
                raise ValueError("사용 여부는 참/거짓입니다")
            entry["use"] = value
        elif kind == "name":
            if not isinstance(value, str) or len(value) > 200:
                raise ValueError("표시 이름을 확인하세요")
            entry["name"] = value.strip()
        else:
            if value not in METHOD_LABELS:
                raise ValueError("변환은 RAW/LINEAR/AREA 중 하나입니다")
            entry["label"] = editor_model.label_of(value)
        return dict(ok=True, used=sum(1 for e in self.entries if e["use"]))

    # ---- scales ----------------------------------------------------------
    def _scale_table(self, machine, coef_rows):
        """Per variant: coefficient to use and where it came from.

        Order matches the tkinter form: human-managed 변환계수.xlsx first, then the
        coefficient embedded in the candidate's transform label, else the default.
        `needed` marks variants that have a used LINEAR/AREA item (only those change values).
        """
        out = {}
        for e in self.entries:
            v = e["variant"]
            item = out.get(v)
            if item is None:
                coef, source = (coefstore.lookup(coef_rows, machine, v) if coef_rows and machine else None), "변환계수.xlsx"
                if coef is None:
                    coef, source = ini_parser.scale_from_label(engine._s((e["ext"] or {}).get("transform"))), "원본 라벨"
                if coef is None:
                    coef, source = ini_parser.DEFAULT_SCALE, "기본값"
                item = out[v] = dict(variant=v, coef=coef, source=source, needed=False)
            if e["use"] and editor_model.method_of(e["label"]) in SCALED:
                item["needed"] = True
        return out

    def scales(self, params):
        self._check(params, {"snapshot", "machine"})
        machine = params.get("machine", "")
        if not isinstance(machine, str) or len(machine) > 64:
            raise ValueError("호기를 선택하세요")
        rows = self._coef_rows()
        return dict(machine=machine, scales=list(self._scale_table(machine.strip(), rows).values()))

    # ---- confirm -------------------------------------------------------
    def confirm(self, params):
        self._check(params, {"snapshot", "machine", "scales"})
        machine = params.get("machine")
        if not isinstance(machine, str) or not 1 <= len(machine.strip()) <= 64:
            raise ValueError("호기를 선택하세요")
        machine = machine.strip()
        given = params.get("scales", {})
        if not isinstance(given, dict) or len(given) > 1000:
            raise ValueError("변환계수를 확인하세요")
        for key, value in given.items():
            if (not isinstance(key, str) or type(value) not in (int, float)
                    or not math.isfinite(value) or not 0 < value <= MAX_SCALE):
                raise ValueError("변환계수는 0보다 큰 숫자여야 합니다")
        if not any(e["use"] and engine._s(e["name"]).strip() for e in self.entries):
            raise ValueError("사용할 항목이 없습니다. 한 개 이상 체크하고 이름을 확인하세요.")
        coef_rows = self._coef_rows()
        table = self._scale_table(machine, coef_rows)
        for variant, value in given.items():
            if variant in table:
                table[variant].update(coef=float(value), source="직접 입력")
        selected = []
        for e in self.entries:
            selected.append(dict(use=e["use"], name=e["name"], reco=e["reco"],
                                 variant=e["variant"], zone=e["zone"], alg=e["alg"],
                                 ext=e["ext"], method=e["label"], coef=table[e["variant"]]["coef"]))
        records, extracts, used_scales = editor_model.build_records(selected, self.level)
        if not records:
            raise ValueError("사용할 항목이 없습니다. 한 개 이상 체크하고 이름을 확인하세요.")

        user = engine.current_user()
        acquired = locking.acquire_global(str(self.root), f"양식_{self.recipe}", user)
        if not acquired.editable:
            raise ValueError(locking.holder_message(acquired, "양식 만들기"))
        try:
            # An existing confirmed form means this confirmation edits it: inherit values after.
            prev_form = workdirs.latest_form(str(self.root), self.recipe)
            st = workdirs.stamp()
            run = workdirs.form_run_dir(str(self.root), self.recipe, st)
            related = workdirs.related_dir(run)
            final_path = workdirs.form_final_path(run, self.recipe, machine, st)
            original_path = workdirs.form_original_path(related, self.recipe, machine, st)
            sheet = formbuilder._detect_sheet(records)
            extract_io.write_snapshot(final_path, records, machines=[], sheet_name=sheet,
                                      extracts=extracts, stage="final", level=self.level,
                                      aoi=machine, source=f"편집: {self.recipe}", user=user,
                                      scales=used_scales)
            # Always keep an editable full candidate (original) so items can be re-added later.
            pivot = [dict(layer=self.level, recipe=self.level, mag=e["variant"], zone=e["zone"],
                          alg=e["alg"], param=engine._s(e["name"]).strip() or e["reco"],
                          values={}, unit="", raws={"양식": e["raw"]},
                          use=e["use"], extract=dict(e["ext"] or {})) for e in self.entries]
            formbuilder.build_initial_workbook(pivot, original_path, level=self.level,
                                               source=f"편집 원본: {self.recipe}")
            # Remember display names + checkbox states for future forms (best effort).
            name_note = ""
            try:
                name_selected = [dict(alg=e["alg"], ext={"key": e["orig"]}, name=e["name"],
                                      use=e["use"]) for e in self.entries]
                npath = self._safe(namestore.name_path(str(self.root)))
                namestore.save_selected(npath, name_selected, user)
            except (OSError, ValueError) as exc:
                name_note = str(exc)
        finally:
            locking.release_global(str(self.root), f"양식_{self.recipe}", user)
        needed = [t for t in table.values() if t["needed"]]
        coef = self._apply_coefs(machine, coef_rows, needed)
        merge = self._inherit_values(final_path, prev_form) if prev_form else None
        return dict(final=final_path, original=original_path, kept=len(records),
                    total=len(self.entries), sheet=sheet, name_note=name_note,
                    scales=needed, coef=coef, merge=merge)

    def _apply_coefs(self, machine, coef_rows, needed):
        """Record the confirmed per-variant coefficients in 변환계수.xlsx (tkinter
        `_coef_from_form`). A new variant row needs the optic MAG, which an existing
        candidate does not carry, so such variants are reported instead of guessed."""
        chosen = {t["variant"]: t["coef"] for t in needed if t["source"] != "기본값"}
        defaulted = [t["variant"] for t in needed if t["source"] == "기본값"]
        result = dict(saved=0, defaulted=defaulted, unregistered=[], error="")
        if not chosen:
            return result
        result["unregistered"] = [v for v in chosen if coefstore.lookup(coef_rows, machine, v) is None]
        try:
            n = coefstore.apply_form_scales(coef_rows, machine, chosen, {}, note=f"{self.level} 양식 확정")
            if n:
                coefstore.save(self._safe(coefstore.coef_path(str(self.root))), coef_rows)
            result["saved"] = n
        except (OSError, ValueError) as exc:
            # Coefficient bookkeeping never blocks the confirmation (tkinter E145).
            result["error"] = str(exc) if isinstance(exc, ValueError) else "변환계수.xlsx 를 저장하지 못했습니다"
        return result

    def _inherit_values(self, final_path, prev_form):
        """After editing an existing form, carry the previous collation values into a
        new collation built on the new form (tkinter `_post_finalize_merge`). New
        parameters stay blank until the next value update."""
        result = dict(collate="", added=0, error="")
        try:
            added = formbuilder.form_params(final_path) - formbuilder.form_params(prev_form)
        except Exception:  # noqa: BLE001 - informational count only
            added = set()
        result["added"] = len(added)
        prev = workdirs.latest_collate(str(self.root))
        if not prev:
            return result
        user = engine.current_user()
        acquired = locking.acquire_global(str(self.root), locking.GLOBAL_COLLATE, user)
        if not acquired.editable:
            result["error"] = locking.holder_message(acquired, "값 이어받기")
            return result
        try:
            prev = self._safe(prev)
            machines = self._machines() or collate.load_collation(prev)[1]
            rows = self._coef_rows()
            out = collate.build_collation(str(self.root), [self.recipe], [], machines,
                                          prev_collate_path=prev,
                                          coef_lookup=coefstore.make_lookup(rows))
            made = {r: v for r, v in out.items() if not v.missing_form}
            dest = self._safe(workdirs.collate_path(str(self.root), workdirs.stamp()))
            collate.write_collation(dest, made, machines)
            result["collate"] = dest
        except (OSError, ValueError, KeyError) as exc:
            result["error"] = str(exc) if isinstance(exc, ValueError) else "이전 값을 이어받지 못했습니다"
        finally:
            locking.release_global(str(self.root), locking.GLOBAL_COLLATE, user)
        return result

    def _coef_rows(self):
        try:
            path = self._safe(coefstore.coef_path(str(self.root)))
        except ValueError:
            return []
        try:
            return coefstore.load(path)
        except (OSError, ValueError):
            return []
