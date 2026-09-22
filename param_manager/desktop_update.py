"""Recipe value update (값 업데이트): collect from equipment or a local folder,
parse, confirm variant names, then write a new collation.

This is the tkinter `_update_values_dialog` → `_collect_dialog`/
`_local_pick_sources` → `_parse_sources_busy` → `_update_collate_flow` →
`_update_write_results` flow, split into protocol steps because the web UI
cannot block inside a callback:

1. `collect`  — copies equipment files read-only into a local temp run and
   parses them. When the collector needs a human choice (which Job folders
   belong to each recipe, or which Setup when a Job has several) the step
   returns a `question`; the UI asks and calls `collect` again with the
   answer. Questions happen before any copy, and machines already collected in
   the same run are not copied again.
2. `preview`  — applies the confirmed variant-name mapping and builds the
   collation in memory (reports mismatches per recipe).
3. `commit`   — writes the new collation with the recipes the user kept.

Equipment access is read-only and only through sessions the user already
opened in Explorer (no credentials, like the tkinter program). The UI never
supplies paths: machines come from the 장비 IP document, the local source
folder from the shared config.
"""
import os
import re
from pathlib import Path

from . import (coefstore, collate, collector, engine, extract_io, ini_parser, localdirs,
               locking, refdata, watcher, workdirs)
from .desktop_batch import DesktopBatch, read_json

MAX_ITEMS = 500


class Question(Exception):
    def __init__(self, payload):
        super().__init__(payload.get("kind", "question"))
        self.payload = payload


def _sanitize_name(s):
    return re.sub(r'[<>:"/\\|?*]+', "_", str(s)).strip().strip(".") or "item"


def resolve_local_machine_dir(root, machine):
    """{root}/{호기} exactly, else a sub-folder whose name contains the machine key
    (tkinter `_resolve_local_machine_dir`)."""
    cand = os.path.join(root, _sanitize_name(machine))
    if os.path.isdir(cand):
        return cand
    key = re.sub(r"[^0-9a-z]", "", machine.lower())
    try:
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if os.path.isdir(path) and key and key in re.sub(r"[^0-9a-z]", "", name.lower()):
                return path
    except OSError:
        pass
    return None


class DesktopUpdate:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"
        self.job_root_override = None     # tests only (fake equipment tree); never from IPC
        self.state = None
        self.lock_root = None

    # ---- helpers ---------------------------------------------------------
    def _cfg(self):
        cfg = read_json(self.config_path)
        if not cfg.get("save_dir"):
            raise ValueError("먼저 [설정]에서 저장폴더를 지정하세요")
        return cfg

    def _ip_rows(self, save):
        path = refdata.ip_path(save)
        return refdata.load_ip(path) if os.path.isfile(path) else []

    def _local_root(self):
        return Path(DesktopBatch(self.config_path).configuration()[2])

    def _release(self):
        if self.lock_root:
            locking.release_global(self.lock_root, locking.GLOBAL_COLLATE, engine.current_user())
            self.lock_root = None

    def _hold(self, save):
        """Several PCs collecting at once would hit the equipment twice and race on the
        collation file, so the whole flow holds the global collate lock (tkinter)."""
        if self.lock_root == save:
            return
        self._release()
        state = locking.acquire_global(save, locking.GLOBAL_COLLATE, engine.current_user())
        if not state.editable:
            raise ValueError(locking.holder_message(state, "파라미터 값 업데이트"))
        self.lock_root = save

    # ---- step 0: what can be updated -------------------------------------
    def prepare(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        cfg = self._cfg()
        save = cfg["save_dir"]
        rows = self._ip_rows(save)
        source = cfg.get("local_root") or ""
        machines = []
        for m in refdata.machines(rows):
            local = resolve_local_machine_dir(source, m) if source and os.path.isdir(source) else None
            machines.append(dict(id=m, ip=refdata.ip_for(rows, m), type=refdata.device_type_for(rows, m),
                                 local=local or ""))
        recipes = [r for r in workdirs.list_recipes(save) if workdirs.latest_form(save, r)]
        return dict(recipes=recipes, machines=machines, local_source=source,
                    local_source_ok=bool(source and os.path.isdir(source)))

    def set_local_source(self, params):
        """Parent folder holding per-machine copies (tkinter `local_root`)."""
        if set(params) != {"path"} or not isinstance(params["path"], str) or not params["path"].strip():
            raise ValueError("로컬 상위 폴더를 확인하세요")
        path = Path(params["path"].strip()).absolute()
        if path.is_symlink() or not path.is_dir():
            raise ValueError("로컬 상위 폴더가 존재하지 않습니다")
        cfg = read_json(self.config_path)
        cfg["local_root"] = str(path)
        from . import atomicfile
        atomicfile.write_json(str(self.config_path), cfg)
        return self.prepare({})

    # ---- step 1: collect + parse -----------------------------------------
    def gather(self, params, allow_new=False, hold=True):
        """Validate the request and copy/locate the sources. Returns a `question`
        payload, or the sources to parse. `allow_new` lets 양식 만들기 name a recipe
        that has no form yet; `hold` takes the global collate lock (value update only)."""
        if set(params) - {"recipes", "machines", "source", "answers"}:
            raise ValueError("수집 요청을 확인하세요")
        cfg = self._cfg()
        save = cfg["save_dir"]
        recipes, machines, source = params.get("recipes"), params.get("machines"), params.get("source")
        answers = params.get("answers") or {}
        if source not in ("equipment", "local") or not isinstance(answers, dict):
            raise ValueError("수집 방식을 확인하세요")
        known = set(workdirs.list_recipes(save))
        if (not isinstance(recipes, list) or not recipes or len(recipes) > MAX_ITEMS
                or any(not isinstance(r, str) or not r.strip() or (r not in known and not allow_new) for r in recipes)):
            raise ValueError("양식이 있는 레시피를 하나 이상 고르세요")
        rows = self._ip_rows(save)
        registered = refdata.machines(rows)
        if (not isinstance(machines, list) or not machines or len(machines) > MAX_ITEMS
                or any(not isinstance(m, str) or m not in registered for m in machines)):
            raise ValueError("[장비 IP]에 등록된 호기를 하나 이상 고르세요")
        recipes = list(dict.fromkeys(recipes))
        machines = list(dict.fromkeys(machines))
        if hold:
            self._hold(save)
        key = (tuple(recipes), tuple(machines), source)
        if not self.state or self.state.get("key") != key:
            self.state = dict(key=key, sources={}, errors={}, plan=None, staging=None)
        state = self.state
        state.pop("pivot", None)
        state.pop("results", None)
        dlevel = recipes[0] if len(recipes) == 1 else ""
        try:
            if source == "local":
                root = cfg.get("local_root") or ""
                if not root or not os.path.isdir(root):
                    raise ValueError("먼저 로컬 상위 폴더를 지정하세요")
                for m in machines:
                    found = resolve_local_machine_dir(root, m)
                    if found:
                        state["sources"][m] = [(found, dlevel)]
                    else:
                        state["errors"][m] = "로컬 상위 폴더 아래에 이 호기 폴더가 없습니다"
            else:
                self._collect_equipment(save, rows, recipes, machines, answers, state)
            sources = [(d, lvl, m) for m in machines for d, lvl in state["sources"].get(m, [])]
            if not sources:
                raise ValueError("수집된 호기가 없습니다. " + "; ".join(f"{m}: {e}" for m, e in state["errors"].items()))
        except Question as q:
            return dict(stage="question", question=q.payload,
                        collected=[m for m in machines if m in state["sources"]])
        except Exception:
            # Keep nothing half-done: a failed run must not hold the collate lock.
            self.cancel({})
            raise
        return dict(stage="sources", save=save, recipes=recipes, machines=machines, sources=sources, dlevel=dlevel)

    def collect(self, params):
        out = self.gather(params)
        if out.get("stage") == "question":
            return out
        state, save, recipes, machines = self.state, out["save"], out["recipes"], out["machines"]
        try:
            pivot, missing = self._parse(save, recipes, out["sources"], out["dlevel"])
        except Exception:
            self.cancel({})
            raise
        if not pivot:
            self.cancel({})
            raise ValueError("인식된 설정(config) 폴더가 없습니다. GlobalRTP.ini/OpticPreset.ini/Zones 구조를 확인하세요.")
        state["pivot"] = pivot
        tables = {}
        for recipe in recipes:
            form = workdirs.latest_form(save, recipe)
            if not form:
                continue
            try:
                table = collate.variant_match_table(collate.form_variants(form), collate.parsed_variants(pivot))
            except Exception:  # noqa: BLE001 - matching help never blocks the collation (tkinter E146)
                continue
            if any(engine._s(f).strip() for f, _ in table["rows"]) or any(engine._s(p).strip() for p in table["parsed"]):
                tables[recipe] = dict(rows=[list(r) for r in table["rows"]], parsed=table["parsed"],
                                      unmatched=table["unmatched_parsed"])
        return dict(stage="variants", collected=[m for m in machines if m in state["sources"]],
                    errors=[dict(machine=m, error=e) for m, e in state["errors"].items()],
                    tables=tables, coef_missing=[dict(machine=m, variant=v) for m, v in missing],
                    rows=len(pivot))

    def _collect_equipment(self, save, rows, recipes, machines, answers, state):
        match_answers = answers.get("match") if isinstance(answers.get("match"), dict) else {}
        setup_answers = answers.get("setup") if isinstance(answers.get("setup"), dict) else {}
        if state["staging"] is None:
            state["staging"] = localdirs.new_temp_run(str(self._local_root()), "수집")
        for m in machines:
            if m in state["sources"] or m in state["errors"]:
                continue
            ip = refdata.ip_for(rows, m)
            if not ip:
                state["errors"][m] = "[장비 IP]에 IP가 없습니다"
                continue

            def staging_for(_kw, m=m):
                d = os.path.join(state["staging"], _sanitize_name(m))
                os.makedirs(d, exist_ok=True)
                return d

            def match_recipes(job_dirs, levels, m=m):
                chosen = match_answers.get(m)
                if isinstance(chosen, dict):
                    by_name = {p.name: p for p in job_dirs}
                    mapping = {}
                    for lvl in levels:
                        names = chosen.get(lvl) or []
                        picked = [by_name[n] for n in names if isinstance(n, str) and n in by_name]
                        if picked:
                            mapping[lvl] = picked
                    if mapping:
                        return mapping
                    raise ValueError(f"{m}: 레시피별 Job 폴더를 하나 이상 고르세요")
                raise Question(dict(kind="match", machine=m, levels=list(levels),
                                    jobs=[p.name for p in job_dirs],
                                    suggested={lvl: [p.name for p in job_dirs if collector.level_folder_match(p.name, lvl)]
                                               for lvl in levels}))

            def chooser(kind, title, items, multi, m=m):
                if kind != "setup" or not items:
                    raise ValueError(f"{m}: 이 수집 단계는 기존 프로그램에서 진행하세요 ({title})")
                job = Path(items[0]).parent.name
                picked = (setup_answers.get(m) or {}).get(job) if isinstance(setup_answers.get(m), dict) else None
                for item in items:
                    if Path(item).name == picked:
                        return [item]
                raise Question(dict(kind="setup", machine=m, job=job, title=title,
                                    options=[Path(i).name for i in items]))

            try:
                _, plan, srcs = collector.collect_equipment(
                    ip, staging_for, chooser, plan=state["plan"], confirm=lambda planned: True,
                    target_levels=list(recipes), match_recipes=match_recipes,
                    **({"job_root_override": self.job_root_override(m)} if self.job_root_override else {}))
                state["plan"] = plan
                state["sources"][m] = [(d, lvl) for d, lvl in srcs]
            except Question:
                raise
            except collector.UserCancelled as exc:
                state["errors"][m] = f"취소: {exc}"
            except (OSError, RuntimeError, ValueError) as exc:
                state["errors"][m] = str(exc)
        if state["plan"] is not None:
            # Keep the confirmed Job/Setup choice for unattended watch cycles (tkinter E161).
            try:
                ws, wst = watcher.load_settings(save)
                ws.plan = watcher.plan_to_dict(state["plan"])
                watcher.save_settings(save, ws, wst)
            except Exception:  # noqa: BLE001
                pass

    def _parse(self, save, recipes, sources, dlevel):
        scales = {}
        for r in recipes:
            form = workdirs.latest_form(save, r)
            if form:
                scales.update(extract_io.read_scales(form))
        coef_rows = coefstore.load(coefstore.coef_path(save)) if os.path.isfile(coefstore.coef_path(save)) else []
        missing, cache = [], {}

        def lookup(equipment, variant=""):
            key = (equipment, variant)
            if key not in cache:
                cache[key] = coefstore.lookup(coef_rows, equipment, variant)
            if cache[key] is None:
                item = (engine._s(equipment).strip(), engine._s(variant).strip())
                if item[0] and item not in missing:
                    missing.append(item)
            return cache[key]
        configs = []
        for root, kw, machine in sources:
            configs += ini_parser.scan_tree(root, default_level=dlevel or kw, default_equipment=machine,
                                            scales=scales, coef_lookup=lookup)
        valid = [c for c in configs if ini_parser.config_valid(c)]
        pivot, _ = ini_parser.build_pivot(valid)
        return pivot, missing

    # ---- step 2: variant mapping + in-memory collation --------------------
    def preview(self, params):
        if set(params) != {"mapping"} or not isinstance(params["mapping"], dict):
            raise ValueError("하위 레시피 매칭을 확인하세요")
        state = self.state
        if not state or "pivot" not in state:
            raise ValueError("먼저 값을 수집하세요")
        mapping = {}
        for copied, form in params["mapping"].items():
            if not isinstance(copied, str) or not isinstance(form, str) or len(copied) > 256 or len(form) > 256:
                raise ValueError("하위 레시피 매칭을 확인하세요")
            if copied.strip() != form.strip():
                mapping[copied] = form
        save = self._cfg()["save_dir"]
        recipes = list(state["key"][0])
        rows = collate.apply_variant_map(state["pivot"], mapping)
        machines_all = refdata.machines(self._ip_rows(save))
        coef_rows = coefstore.load(coefstore.coef_path(save)) if os.path.isfile(coefstore.coef_path(save)) else []
        results = collate.build_collation(save, recipes, rows, machines_all,
                                          prev_collate_path=workdirs.latest_collate(save),
                                          coef_lookup=coefstore.make_lookup(coef_rows),
                                          variant_orig=collate.invert_variant_map(mapping))
        state["results"], state["machines_all"] = results, machines_all
        out = []
        for recipe, res in results.items():
            names = sorted({engine._s(m.get("param")) for m in res.mismatches})
            out.append(dict(recipe=recipe, missing_form=res.missing_form, carried=bool(getattr(res, "carried", False)),
                            matched_rows=res.matched_rows, filled_cells=res.filled_cells,
                            mismatches=len(res.mismatches), mismatch_names=names[:50]))
        return dict(stage="preview", recipes=out)

    # ---- step 3: write -----------------------------------------------------
    def commit(self, params):
        if set(params) != {"include"} or not isinstance(params["include"], list):
            raise ValueError("포함할 레시피를 확인하세요")
        state = self.state
        if not state or "results" not in state:
            raise ValueError("먼저 취합 미리보기를 확인하세요")
        include = {r for r in params["include"] if isinstance(r, str)}
        made, notes = {}, []
        for recipe, res in state["results"].items():
            if res.missing_form:
                notes.append(f"{recipe}: 양식 없음(건너뜀)")
            elif getattr(res, "carried", False) or not res.mismatches or recipe in include:
                made[recipe] = res
            else:
                notes.append(f"{recipe}: 불일치로 제외")
        if not [r for r, v in made.items() if not getattr(v, "carried", False)]:
            raise ValueError("취합할 레시피가 없습니다. " + "; ".join(notes))
        save = self._cfg()["save_dir"]
        dest = workdirs.collate_path(save, workdirs.stamp())
        collate.write_collation(dest, made, state["machines_all"])
        summary = [dict(recipe=r, matched_rows=v.matched_rows, filled_cells=v.filled_cells,
                        carried=bool(getattr(v, "carried", False))) for r, v in made.items()]
        self.cancel({})
        return dict(stage="done", path=dest, recipes=summary, notes=notes)

    def cancel(self, params):
        if params:
            raise ValueError("요청을 확인하세요")
        staging = (self.state or {}).get("staging")
        self.state = None
        self._release()
        if staging:
            localdirs.drop(staging)      # temp copies live only in the local temp folder
        return dict(stage="cancelled")
