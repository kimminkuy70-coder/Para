"""Automatic watches for the web app: parameter watch and Commonality watch.

Headless ports of the tkinter `_watch_*` (parameter) and `_cmw_*` (Commonality)
features. The engine's scheduler thread (desktop_ipc) ticks them; the UI only
edits settings and shows notices. All the existing safety rules are kept:

* Equipment is read-only, only through Explorer sessions the user opened
  (no credentials), one machine at a time with HOST_GAP_SEC between machines
  (no lateral-movement-like bursts), files that changed while copying are
  dropped for that cycle (no torn reads), failures back off (watcher.should_run).
* Only one PC runs the parameter watch: global lock `자동감시` in the shared
  folder, refreshed only near expiry.
* OneDrive: the cycle's collation is written locally first and copied to the
  save folder only when something changed (or for the very first baseline);
  the change report is written only when there is a change. Other PCs learn
  about a finished cycle by reading the one small settings file — here every
  SHARED_POLL_SEC (5 min) instead of every minute.
* Commonality watch output stays local (cmwatcher), like the tkinter app.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import (cmwatcher, coefstore, collate, collector, commonality as cm, downloader as dl, engine,
               extract_io, ini_parser, localdirs, locking, refdata, watcher, workdirs)
from .desktop_batch import DesktopBatch, read_json

HOST_GAP_SEC = 2.0          # between machines (same as the tkinter unattended collector)
SHARED_POLL_SEC = 300       # how often other PCs read the shared watch state
_SEGMENT = re.compile(r'^[^<>:"/\\|?*\x00-\x1f]+$')


def _sanitize(s):
    return re.sub(r'[<>:"/\\|?*]+', "_", str(s)).strip().strip(".") or "item"


def valid_rel(rel: str) -> str:
    """A Job-relative folder path (`PI3_MAIN\\Setup1\\Recipes\\PI3`): plain segments only."""
    if not isinstance(rel, str) or len(rel) > 400:
        raise ValueError("폴더 경로를 확인하세요")
    parts = [p for p in rel.replace("/", "\\").split("\\") if p]
    if any(p in (".", "..") or not _SEGMENT.match(p) for p in parts):
        raise ValueError("Job 폴더 아래의 폴더만 지정할 수 있습니다")
    return "\\".join(parts)


class _Base:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else Path.home() / ".pi_param_manager.json"

    def _cfg(self):
        return read_json(self.config_path)

    def _save_dir(self):
        save = self._cfg().get("save_dir") or ""
        if not save:
            raise ValueError("먼저 [설정]에서 저장폴더를 지정하세요")
        return save

    def _local_root(self):
        return str(DesktopBatch(self.config_path).configuration()[2])

    def _ip_rows(self, save):
        path = refdata.ip_path(save)
        return refdata.load_ip(path) if os.path.isfile(path) else []

    def _coef_rows(self, save):
        path = coefstore.coef_path(save)
        return coefstore.load(path) if os.path.isfile(path) else []

    @staticmethod
    def _interval(value):
        allowed = [h for h, _ in watcher.INTERVAL_CHOICES]
        if type(value) not in (int, float) or float(value) not in allowed:
            raise ValueError("감시 주기를 목록에서 고르세요")
        return float(value)

    @staticmethod
    def _hour(value):
        if type(value) is not int or not 0 <= value <= 23:
            raise ValueError("시간대는 0~23시입니다")
        return value


# =============================================================================
#  Parameter watch (감시설정.json in the shared save folder)
# =============================================================================
class ParamWatch(_Base):
    def __init__(self, config_path=None):
        super().__init__(config_path)
        self.owned = None           # save_dir whose watch lock this engine holds
        self.job_root_override = None   # tests only: machine -> fake Job root
        self._shared = (0.0, None)  # (read time, (settings, state)) cache for the scheduler
        self.sleep = time.sleep

    # ---- lock ------------------------------------------------------------------
    def _acquire(self, save, silent=False):
        if self.owned == save:
            return True
        st = locking.acquire_global(save, locking.GLOBAL_WATCHER, engine.current_user())
        if st.editable:
            self.owned = save
            return True
        if silent:
            return False
        raise ValueError(locking.holder_message(st, "자동 감시"))

    def release(self):
        if self.owned:
            try:
                locking.release_global(self.owned, locking.GLOBAL_WATCHER, engine.current_user())
            except OSError:
                pass
        self.owned = None

    def refresh_lock(self):
        if self.owned:
            locking.refresh(locking.global_lock_path(self.owned, locking.GLOBAL_WATCHER), engine.current_user())

    # ---- settings/state for the UI ---------------------------------------------
    def state(self, params=None):
        save = self._save_dir()
        s, st = watcher.load_settings(save)
        self._shared = (time.monotonic(), (s, st))
        holder = locking.global_status(save, locking.GLOBAL_WATCHER, engine.current_user())
        info = getattr(holder, "info", None)
        targets = [dict(machine=m, recipe=r, path=watcher.path_for(s.recipe_paths, m, r))
                   for m, names in watcher.machine_recipes(s).items() for r in names]
        nxt = watcher.next_run_at(s, st) if st.last_run else None
        return dict(enabled=s.enabled, interval_hours=s.interval_hours,
                    intervals=[dict(hours=h, label=l) for h, l in watcher.INTERVAL_CHOICES],
                    window_start=s.window_start, window_end=s.window_end,
                    notify_on_change_only=s.notify_on_change_only, targets=targets,
                    paths={m: dict(v) for m, v in s.recipe_paths.items() if m != watcher.ANY_MACHINE},
                    machines=refdata.machines(self._ip_rows(save)), recipes=workdirs.list_recipes(save),
                    last_run=st.last_run, last_result=st.last_result, fail_count=st.fail_count,
                    next_run=nxt.strftime("%Y-%m-%d %H:%M") if nxt else "",
                    owned=self.owned == save,
                    holder=(getattr(info, "user", "") or "") if holder.status == "other" else "",
                    reports=[dict(name=os.path.basename(p), path=p) for p in watcher.list_reports(save)[:10]],
                    log=watcher.log_path(save))

    def save(self, params):
        allowed = {"enabled", "interval_hours", "window_start", "window_end", "notify_on_change_only"}
        if set(params) - allowed or type(params.get("enabled")) is not bool:
            raise ValueError("감시 설정을 확인하세요")
        save = self._save_dir()
        s, st = watcher.load_settings(save)
        s.interval_hours = self._interval(params.get("interval_hours", s.interval_hours))
        s.window_start = self._hour(params.get("window_start", s.window_start))
        s.window_end = self._hour(params.get("window_end", s.window_end))
        if type(params.get("notify_on_change_only", True)) is not bool:
            raise ValueError("알림 설정을 확인하세요")
        s.notify_on_change_only = params.get("notify_on_change_only", True)
        if params["enabled"]:
            missing = self._missing_paths(s, save)
            if not watcher.machine_recipes(s):
                raise ValueError("먼저 장비별 감시 레시피와 Job 폴더를 지정하세요")
            if missing:
                raise ValueError("Job 폴더가 지정되지 않은 대상이 있습니다: " + ", ".join(missing[:8]))
            self._acquire(save)            # one PC only
        s.enabled = params["enabled"]
        watcher.sync_selection(s)
        watcher.save_settings(save, s, st)
        if not s.enabled:
            self.release()
        return self.state()

    def _missing_paths(self, s, save):
        return [f"{m}/{r}" for m, names in watcher.machine_recipes(s).items() for r in names
                if not watcher.path_for(s.recipe_paths, m, r)]

    def set_path(self, params):
        """Assign (machine, recipe) → Job-relative folder ('' removes the target)."""
        if set(params) != {"machine", "recipe", "rel"}:
            raise ValueError("감시 대상을 확인하세요")
        save = self._save_dir()
        machine, recipe = params["machine"], params["recipe"]
        if machine not in refdata.machines(self._ip_rows(save)):
            raise ValueError("[장비 IP]에 등록된 호기를 고르세요")
        if recipe not in workdirs.list_recipes(save):
            raise ValueError("양식이 있는 레시피를 고르세요")
        rel = valid_rel(params["rel"])
        s, st = watcher.load_settings(save)
        rp = watcher.normalize_recipe_paths(s.recipe_paths)
        inner = dict(rp.get(machine) or {})
        if rel:
            inner[recipe] = rel
        else:
            inner.pop(recipe, None)
        if inner:
            rp[machine] = inner
        else:
            rp.pop(machine, None)
        s.recipe_paths = rp
        watcher.sync_selection(s)
        watcher.save_settings(save, s, st)
        return self.state()

    def copy_paths(self, params):
        """'이 호기 경로를 다른 호기에 복사' (Job trees are often identical)."""
        if set(params) != {"source", "targets"} or not isinstance(params["targets"], list):
            raise ValueError("복사할 호기를 확인하세요")
        save = self._save_dir()
        machines = refdata.machines(self._ip_rows(save))
        if params["source"] not in machines or any(t not in machines for t in params["targets"]):
            raise ValueError("[장비 IP]에 등록된 호기만 고를 수 있습니다")
        s, st = watcher.load_settings(save)
        rp = watcher.normalize_recipe_paths(s.recipe_paths)
        src = dict(rp.get(params["source"]) or {})
        if not src:
            raise ValueError("원본 호기에 지정된 폴더가 없습니다")
        for t in params["targets"]:
            if t != params["source"]:
                rp[t] = dict(src)
        s.recipe_paths = rp
        watcher.sync_selection(s)
        watcher.save_settings(save, s, st)
        return self.state()

    def _job_root(self, machine, ip):
        if self.job_root_override:
            return Path(self.job_root_override(machine))
        return Path(watcher.machine_recipe_dir(ip, ""))

    def jobs(self, params):
        """Browse the machine's Job tree (names only, read-only) to pick a folder."""
        if set(params) != {"machine", "sub"}:
            raise ValueError("호기와 폴더를 확인하세요")
        save = self._save_dir()
        rows = self._ip_rows(save)
        ip = refdata.ip_for(rows, params["machine"])
        if params["machine"] not in refdata.machines(rows) or not ip:
            raise ValueError("[장비 IP]에 IP가 있는 호기를 고르세요")
        sub = valid_rel(params["sub"])
        base = self._job_root(params["machine"], ip)
        folder = base.joinpath(*sub.split("\\")) if sub else base
        if not folder.is_dir():
            raise ValueError("장비의 Job 폴더를 열 수 없습니다. 탐색기(Win+R)로 \\\\장비IP\\c$ 에 먼저 연결하세요.")
        dirs = sorted((p.name for p in collector.list_dirs(folder)), key=str.lower)
        is_recipe = any((folder / f).is_file() for f in collector.FIXED_FILES) or (folder / "Zones").is_dir()
        return dict(machine=params["machine"], sub=sub, dirs=dirs[:500], is_recipe=is_recipe)

    # ---- scheduler ---------------------------------------------------------------
    def due(self):
        """Cheap check for the scheduler. Reads the shared settings at most every
        SHARED_POLL_SEC; returns (settings, state) when this PC should run now."""
        try:
            save = self._save_dir()
        except ValueError:
            return None
        at, cached = self._shared
        fresh = cached is None or time.monotonic() - at >= SHARED_POLL_SEC
        if fresh:
            cached = watcher.load_settings(save)
            self._shared = (time.monotonic(), cached)
        s, st = cached
        if not s.enabled:
            if self.owned:
                self.release()
            return None
        # Only try to take the lock when the shared settings were just re-read, so an
        # idle PC touches the shared folder at most every SHARED_POLL_SEC.
        if self.owned != save and (not fresh or not self._acquire(save, silent=True)):
            return None                       # another PC runs the watch
        return cached if watcher.should_run(datetime.now(), s, st) else None

    def state_cached_enabled(self):
        cached = self._shared[1]
        if cached is None:
            cached = watcher.load_settings(self._save_dir())
            self._shared = (time.monotonic(), cached)
        return bool(cached[0].enabled)

    def poll_shared(self):
        """A cycle finished (on any PC) that this PC has not announced yet → notice."""
        try:
            save = self._save_dir()
        except ValueError:
            return None
        s, st = self._shared[1] or watcher.load_settings(save)
        if not st.last_run:
            return None
        key = "watch_seen:" + save
        cfg = self._cfg()
        seen = cfg.get(key, "")
        if st.last_run == seen:
            return None
        self._mark_seen(key, st.last_run)
        if not seen:
            return None                        # first look: baseline, no alert
        note = st.last_result or ""
        changed = bool(note) and note not in ("변경 없음", "실행 조건 아님(건너뜀)") and not note.startswith("실패")
        if not changed:
            return None
        report = watcher.latest_report(save)
        return dict(kind="param_watch", title="파라미터 자동 감시 — 변경 감지", summary=note,
                    report=report or "", by_other=self.owned != save)

    def _mark_seen(self, key, value):
        from . import atomicfile
        cfg = self._cfg()
        cfg[key] = value
        atomicfile.write_json(str(self.config_path), cfg)       # local config only

    # ---- one cycle -----------------------------------------------------------------
    def run(self, manual=False):
        save = self._save_dir()
        s, st = watcher.load_settings(save)
        if not self._acquire(save, silent=not manual):
            raise ValueError("다른 PC가 자동 감시를 실행 중입니다")
        local = self._local_root()
        try:
            res = self._cycle(save, local, s)
        except Exception as exc:  # noqa: BLE001 - recorded, then reported
            msg = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "수집 중 오류"
            watcher.record_run(save, s, st, ok=False, note=msg)
            watcher.append_log(save, f"회차 실패 — {msg}")
            self._shared = (0.0, None)
            raise ValueError(msg) from exc
        watcher.record_run(save, s, st, ok=True, note=res.summary())
        self._mark_seen("watch_seen:" + save, st.last_run)          # this PC announces it directly
        self._shared = (0.0, None)
        return dict(summary=res.summary(), has_change=res.has_change, report=res.report or "",
                    skipped=list(res.skipped or []), collate=res.collate_file or "")

    def _cycle(self, save, local, s):
        rows = self._ip_rows(save)
        all_machines = refdata.machines(rows)
        avail_r = set(workdirs.list_recipes(save))
        mr = {}
        for m, names in watcher.machine_recipes(s).items():
            keep = [r for r in names if r in avail_r]
            if m in all_machines and keep:
                mr[m] = keep
        recipes = []
        for names in mr.values():
            for r in names:
                if r not in recipes:
                    recipes.append(r)
        prev = workdirs.latest_collate(save)
        watcher.append_log(save, f"회차 시작 — 장비 {len(mr)}대 · 레시피 {len(recipes)}개 · "
                           + ("; ".join(f"{m}({', '.join(v)})" for m, v in mr.items()) or "대상 없음"))
        if not recipes:
            raise RuntimeError("양식이 없습니다('양식 만들기' 먼저)")
        if not mr:
            raise RuntimeError("감시 대상 장비가 없습니다(설정에서 선택)")
        plan = watcher.plan_from_dict(s.plan)
        need = self._missing_paths(s, save)
        if need and plan is None:
            raise RuntimeError("다음 감시 대상의 폴더가 지정되지 않았습니다: " + ", ".join(need[:8]))
        coef_rows = self._coef_rows(save)
        pivot, skipped = self._collect(mr, s, plan, rows, save, local, coef_rows)
        out = collate.build_collation(save, recipes, pivot, all_machines, prev_collate_path=prev,
                                      coef_lookup=coefstore.make_lookup(coef_rows))
        made = {r: v for r, v in out.items() if not v.missing_form}
        if not made:
            raise RuntimeError("취합된 레시피가 없습니다")
        st = workdirs.stamp()
        # Local first; the shared folder gets a new collation only on change / first baseline.
        tmp_dir = localdirs.new_temp_run(localdirs.ensure(local), "취합")
        try:
            tmp = os.path.join(tmp_dir, os.path.basename(workdirs.collate_path(save, st)))
            collate.write_collation(tmp, made, all_machines)
            res = watcher.compare_and_report(save, prev, tmp, st)
            if res.has_change or not prev:
                dest = workdirs.collate_path(save, st)
                shutil.copy2(tmp, dest)
                res.collate_file = dest
            else:
                res.collate_file = prev
        finally:
            localdirs.drop(tmp_dir)
        res.skipped = skipped
        return res

    def _collect(self, mr, s, plan, ip_rows, save, local, coef_rows):
        staging_root = localdirs.new_temp_run(localdirs.ensure(local), "감시")
        sources, skipped, diag = [], [], []

        def no_chooser(*_a, **_kw):
            return None

        def auto_match(job_dirs, levels):
            out, names_seen = {}, [d.name for d in job_dirs]
            for lvl in levels:
                names = (getattr(plan, "recipe_map", None) or {}).get(lvl) or []
                sel = []
                if names:
                    sel, _missing = collector.match_recipes_by_names(job_dirs, names)
                if not sel:
                    cands = [d for d in job_dirs if collector.contains_keyword(d.name, lvl)]
                    if len(cands) == 1:
                        sel = cands
                    elif cands:
                        diag.append(f"{lvl}: 후보 {len(cands)}개로 애매({', '.join(c.name for c in cands[:4])})")
                    else:
                        diag.append(f"{lvl}: 해당 Job 폴더 없음")
                if sel:
                    out[lvl] = sel
            if not out and names_seen:
                diag.append("장비 Job 폴더: " + ", ".join(names_seen[:8]))
            return out

        try:
            for idx, m in enumerate(mr):
                recipes = list(mr.get(m) or [])
                ip = refdata.ip_for(ip_rows, m)
                if not ip:
                    skipped.append(f"{m}(IP 없음)")
                    continue
                if idx:
                    self.sleep(HOST_GAP_SEC)   # not a burst over many admin shares
                try:
                    fixed = {r: watcher.path_for(s.recipe_paths, m, r) for r in recipes}
                    fixed = {r: v for r, v in fixed.items() if v}
                    for lvl, rel in fixed.items():
                        got = self._collect_fixed(ip, m, lvl, rel, staging_root, diag, save)
                        if got:
                            sources.append((got, lvl, m))
                    guess = [r for r in recipes if r not in fixed]
                    if not guess:
                        continue

                    def staging_for(_kw, aoi=m):
                        d = os.path.join(staging_root, _sanitize(aoi))
                        os.makedirs(d, exist_ok=True)
                        return d
                    extra = {"job_root_override": self._job_root(m, ip)} if self.job_root_override else {}
                    _, _plan, srcs = collector.collect_equipment(
                        ip, staging_for, no_chooser, plan=plan, confirm=lambda planned: True,
                        target_levels=list(guess), match_recipes=auto_match, **extra)
                    for d, lvl in srcs:
                        sources.append((d, lvl, m))
                except collector.UserCancelled:
                    skipped.append(f"{m}(자동 매칭 실패)")
                except Exception as e:  # noqa: BLE001
                    skipped.append(f"{m}({e})")
            if skipped:
                watcher.append_log(save, "건너뜀 — " + ", ".join(skipped))
            if diag:
                watcher.append_log(save, "매칭 진단 — " + " / ".join(diag[:8]))
            if not sources:
                raise RuntimeError("수집된 장비가 없습니다: " + (", ".join(skipped) or "-")
                                   + ("\n· " + "\n· ".join(diag[:6]) if diag else ""))
            cfgs = []
            lookup = coefstore.make_lookup(coef_rows)
            for rootp, kw, aoi in sources:
                cfgs += ini_parser.scan_tree(rootp, default_level=kw, default_equipment=aoi, coef_lookup=lookup)
            rows, _ = ini_parser.build_pivot([c for c in cfgs if ini_parser.config_valid(c)])
            watcher.append_log(save, f"수집 완료 — 장비 {len(sources)}건, 파라미터 {len(rows)}행")
            return rows, skipped
        finally:
            localdirs.drop(staging_root)       # temp copies never accumulate

    def _collect_fixed(self, ip, machine, recipe, rel, staging_root, diag, save):
        src = self._job_root(machine, ip).joinpath(*rel.split("\\")) if self.job_root_override else Path(watcher.machine_recipe_dir(ip, rel))
        try:
            if not src.is_dir():
                diag.append(f"{machine}/{recipe}: 지정 폴더 없음({src})")
                return None

            def is_recipe_dir(d):
                return any((d / f).is_file() for f in collector.FIXED_FILES) or (d / "Zones").is_dir()
            if is_recipe_dir(src):
                targets = [src]
            else:
                targets = []
                for _setup, recipes_root in collector.find_setup_candidates(src):
                    targets += [d for d in collector.list_dirs(recipes_root) if is_recipe_dir(d)]
                if not targets:
                    targets = [d for d in collector.list_dirs(src) if is_recipe_dir(d)]
            if not targets:
                diag.append(f"{machine}/{recipe}: 지정 폴더 아래에 레시피(설정파일) 없음({src})")
                return None
            planned = collector.plan_files(targets)
            if not planned:
                diag.append(f"{machine}/{recipe}: 복사할 설정파일 없음")
                return None
            sigs = [(p, watcher.file_sig(p)) for p, _, _ in planned]
            dest = os.path.join(staging_root, _sanitize(machine), _sanitize(recipe))
            collector.copy_planned(planned, Path(dest), header_lines=[f"IP={ip}", f"Machine={machine}",
                                                                      f"Recipe={recipe}", f"Src={src}"])
            unstable = watcher.unstable_files(sigs)
            if unstable:
                diag.append(f"{machine}/{recipe}: 수집 중 변경된 파일 {len(unstable)}개 → 이번 회차 제외")
                watcher.append_log(save, f"불안정 파일 제외 {machine}/{recipe}: "
                                   + ", ".join(os.path.basename(u) for u in unstable[:5]))
                return None
            return dest
        except Exception as e:  # noqa: BLE001
            diag.append(f"{machine}/{recipe}: {e}")
            return None


# =============================================================================
#  Commonality watch (local settings, cmwatcher)
# =============================================================================
class CmWatch(_Base):
    def __init__(self, config_path=None):
        super().__init__(config_path)
        from .desktop_form import DesktopForm
        self.form = DesktopForm(self.config_path)
        self.building = None

    def _load(self):
        local = self._local_root()
        return local, *cmwatcher.load_settings(local)

    def state(self, params=None):
        local, s, st = self._load()
        rows = []
        if s.watch_plan and os.path.isfile(s.watch_plan):
            try:
                rows = cmwatcher.read_watch_plan(s.watch_plan)
            except Exception:  # noqa: BLE001 - a broken plan is shown as empty
                rows = []
        targets = []
        for m in s.machines:
            for dev, lot in cmwatcher.targets_for_machine(rows, m):
                forms = [dict(recipe=f.get("recipe", ""), sm=f.get("sm", ""),
                              ok=bool(f.get("form") and os.path.isfile(f["form"])))
                         for f in cmwatcher.forms_for(s, m, dev, lot)]
                targets.append(dict(machine=m, device=dev, lot=lot, forms=forms))
        roots = self._cfg().get("commonality_roots") or {}
        nxt = watcher.next_run_at(s, st) if st.last_run else None
        return dict(enabled=bool(s.enabled), interval_hours=s.interval_hours,
                    intervals=[dict(hours=h, label=l) for h, l in watcher.INTERVAL_CHOICES],
                    window_start=s.window_start, window_end=s.window_end, settle_minutes=s.settle_minutes,
                    machines=list(s.machines), available=sorted(roots), plan=[
                        dict(device=r.get("디바이스명", ""), lot=r.get("공정번호", ""), machines=r.get("AOI호기", ""),
                             note=r.get("비고", "")) for r in rows],
                    plan_file=s.watch_plan, targets=targets, last_run=st.last_run, last_result=st.last_result,
                    fail_count=int(st.fail_count or 0), baseline=bool(st.baseline),
                    next_run=nxt.strftime("%Y-%m-%d %H:%M") if nxt else "",
                    results=cmwatcher.watch_root(local), log=cmwatcher.log_path(local))

    def save(self, params):
        allowed = {"enabled", "interval_hours", "window_start", "window_end", "settle_minutes", "machines", "plan"}
        if set(params) - allowed or type(params.get("enabled")) is not bool:
            raise ValueError("감시 설정을 확인하세요")
        local, s, st = self._load()
        roots = self._cfg().get("commonality_roots") or {}
        machines = params.get("machines", s.machines)
        if not isinstance(machines, list) or any(m not in roots for m in machines):
            raise ValueError("Scanresult 루트가 등록된 호기만 고를 수 있습니다")
        settle = params.get("settle_minutes", s.settle_minutes)
        if type(settle) not in (int, float) or not 0 <= settle <= 1440:
            raise ValueError("안정화 대기 시간을 확인하세요")
        plan = params.get("plan")
        if plan is not None:
            if not isinstance(plan, list) or len(plan) > 500:
                raise ValueError("감시 대상 계획을 확인하세요")
            rows = []
            for r in plan:
                if not isinstance(r, dict) or set(r) - {"device", "lot", "machines", "note"} or any(
                        not isinstance(v, str) or len(v) > 256 for v in r.values()):
                    raise ValueError("감시 대상 계획 행을 확인하세요")
                if r.get("device", "").strip() or r.get("lot", "").strip():
                    rows.append({"디바이스명": r.get("device", "").strip(), "공정번호": r.get("lot", "").strip(),
                                 "AOI호기": r.get("machines", "").strip(), "비고": r.get("note", "").strip()})
            # The watch plan lives in the local watch folder (not OneDrive), like its results.
            path = os.path.join(cmwatcher.watch_root(local), cmwatcher.WATCH_PLAN_FILENAME)
            cmwatcher.create_watch_plan_template(path, rows)
            s.watch_plan = path
        s.interval_hours = self._interval(params.get("interval_hours", s.interval_hours))
        s.window_start = self._hour(params.get("window_start", s.window_start))
        s.window_end = self._hour(params.get("window_end", s.window_end))
        s.settle_minutes = float(settle)
        s.machines = list(dict.fromkeys(machines))
        s.roots = {m: roots[m] for m in s.machines}
        if params["enabled"] and not (s.machines and s.watch_plan and os.path.isfile(s.watch_plan)):
            raise ValueError("먼저 감시할 호기와 감시 대상 계획을 지정하세요")
        s.enabled = params["enabled"]
        cmwatcher.save_settings(local, s, st)
        return self.state()

    def due(self):
        try:
            local, s, st = self._load()
        except ValueError:
            return None
        if not (s.enabled and s.machines and s.watch_plan and os.path.isfile(s.watch_plan)):
            return None
        return (s, st) if watcher.should_run(datetime.now(), s, st) else None

    def run(self, manual=False):
        local, s, st = self._load()
        if not (s.machines and s.watch_plan and os.path.isfile(s.watch_plan)):
            raise ValueError("먼저 감시할 호기와 감시 대상 계획을 지정하세요")
        save = self._cfg().get("save_dir") or ""
        try:
            res = cmwatcher.run_cycle(s, st, local_root=local, coef_rows=self._coef_rows(save) if save else [])
        except Exception as exc:  # noqa: BLE001
            st.fail_count = int(st.fail_count or 0) + 1
            st.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.last_result = f"실패: {exc}"
            cmwatcher.save_settings(local, s, st)
            cmwatcher.append_log(local, st.last_result)
            raise ValueError(f"Commonality 감시 실패: {exc}") from exc
        if st.fail_count:
            st.fail_count = 0
            cmwatcher.save_settings(local, s, st)
        found = res.get("found") or []
        return dict(summary=cmwatcher.summary(found), found=[
            dict(machine=i.get("machine", ""), device=i["device"], lot=i["lot"], sm=i["sm"],
                 created=i.get("created", ""), surveyed=i["sm"] in (res.get("surveyed") or []))
            for i in found[:50]], surveyed=len(res.get("surveyed") or []), notes=(res.get("notes") or [])[:20])

    # ---- watch form (대표 S/M → per-recipe form) ------------------------------------
    def candidates(self, params):
        if set(params) != {"machine", "device", "lot"}:
            raise ValueError("감시 대상을 확인하세요")
        roots = self._cfg().get("commonality_roots") or {}
        if params["machine"] not in roots:
            raise ValueError("Scanresult 루트가 등록된 호기를 고르세요")
        scan = cm.scanresult_roots(roots[params["machine"]], params["machine"])
        cands = cmwatcher.sm_candidates(scan, params["device"], params["lot"])
        self.building = dict(machine=params["machine"], device=params["device"], lot=params["lot"], cands=cands)
        return dict(candidates=[dict(sm=c["sm"], created=c["created"], scan=c["scan"], slots=c["slots"])
                                for c in cands[:100]])

    def begin(self, params):
        """Copy the chosen representative S/M slot locally, detect recipes, open the
        first recipe's form for editing (scales from 변환계수.xlsx, like tkinter)."""
        if set(params) != {"sm", "title"} or not self.building:
            raise ValueError("대표 S/M 을 다시 고르세요")
        title = params["title"].strip() if isinstance(params["title"], str) else ""
        if not title or len(title) > 60 or re.search(r'[<>:"/\\|?*]', title):
            raise ValueError("조사 제목을 확인하세요")
        b = self.building
        cand = next((c for c in b["cands"] if c["sm"] == params["sm"]), None)
        if cand is None:
            raise ValueError("목록에 있는 S/M 을 고르세요")
        slots = cmwatcher.usable_slots(Path(cand["path"]))
        if not slots:
            raise ValueError(f"'{cand['sm']}' 아래 슬롯에 읽을 설정 파일이 없습니다")
        local = self._local_root()
        st = workdirs.stamp()
        copy_dir = cmwatcher.watch_dir(local, b["machine"], "대표SM복사", st)
        lot_obj = cm.LotFolder(device=b["device"], lot=b["lot"], sm=cand["sm"], machine=b["machine"], label=cand["sm"])
        cm.set_wafer(lot_obj, Path(slots[0]))
        got = cm.copy_lot(lot_obj, copy_dir)                     # original read-only
        local_slot = Path(got["dest"])
        recs = cm.detect_recipes([(cand["sm"], local_slot)])
        queue = ([{"recipe": f"{title}_{r['name']}", "prefix": r["prefix"]} for r in recs] if recs
                 else [{"recipe": title, "prefix": ""}])
        b.update(cand=cand, slot=str(local_slot), queue=queue, idx=0, entries=[],
                 run_dir=cmwatcher.watch_dir(local, b["machine"], "양식"), st=st)
        return self._open_next()

    def _open_next(self):
        b = self.building
        save = self._cfg().get("save_dir") or ""
        rows = self._coef_rows(save) if save else []
        while b["idx"] < len(b["queue"]):
            cur = b["queue"][b["idx"]]
            pivot, _ = cm.parse_lots([(b["cand"]["sm"], Path(b["slot"]))], level=cur["recipe"],
                                     coef_lookup=lambda _e, v="", _m=b["machine"]: coefstore.lookup(rows, _m, v),
                                     recipe_prefix=cur["prefix"])
            if pivot:
                from . import editor_model
                entries = editor_model.build_entries(pivot)
                opened = self.form.load_entries(entries, level=cur["recipe"], recipe=cur["recipe"],
                                                source=f"감시 대표 S/M {b['cand']['sm']}")
                return dict(stage="edit", form=opened, recipe=cur["recipe"], index=b["idx"], total=len(b["queue"]))
            b["idx"] += 1                          # nothing readable for this recipe: skip it
        return self._finish()

    def confirm(self, params):
        if set(params) != {"snapshot"} or not self.building or params["snapshot"] != self.form.version:
            raise ValueError("감시 양식 편집 화면을 새로고침하세요")
        b = self.building
        cur = b["queue"][b["idx"]]
        from . import editor_model
        save = self._cfg().get("save_dir") or ""
        rows = self._coef_rows(save) if save else []

        def coef(variant):
            value = coefstore.lookup(rows, b["machine"], variant)
            return value if value is not None else ini_parser.DEFAULT_SCALE
        selected = [dict(use=e["use"], name=e["name"], reco=e["reco"], variant=e["variant"], zone=e["zone"],
                         alg=e["alg"], ext=e["ext"], method=e["label"], coef=coef(e["variant"]))
                    for e in self.form.entries]
        records, extracts, used = editor_model.build_records(selected, cur["recipe"])
        if not records:
            raise ValueError("사용할 항목이 없습니다. 한 개 이상 체크하세요.")
        form = os.path.join(b["run_dir"], f"감시양식_{dl.safe_name(cur['recipe'])}_{dl.safe_name(b['machine'])}_"
                                          f"{dl.safe_name(b['device'])}_{dl.safe_name(b['lot'])}.xlsx")
        kind = "RDL_ALL" if cur["recipe"].upper().startswith("RDL") else "PI_ALL"
        extract_io.write_snapshot(form, records, machines=[], sheet_name=kind, extracts=extracts, stage="final",
                                  level=cur["recipe"], aoi=b["machine"], source=f"commonality 감시 {cur['recipe']}",
                                  user=engine.current_user(), scales=used)
        b["entries"].append(dict(form=form, recipe=cur["recipe"], prefix=cur["prefix"], sm=b["cand"]["sm"]))
        b["idx"] += 1
        return self._open_next()

    def _finish(self):
        b = self.building
        self.building = None
        if not b["entries"]:
            raise ValueError("확정된 양식이 없습니다")
        local, s, st = self._load()
        cmwatcher.set_forms(s, b["machine"], b["device"], b["lot"], b["entries"])
        cmwatcher.save_settings(local, s, st)
        return dict(stage="done", forms=[e["recipe"] for e in b["entries"]], sm=b["cand"]["sm"])

    def cancel(self, params=None):
        self.building = None
        return dict(cancelled=True)
