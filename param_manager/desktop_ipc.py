"""Versioned NDJSON adapter with explicitly allowlisted domain operations.

The fixed native launcher owns this process. Filesystem access is confined by
the domain adapters to configured sources, local outputs and shared workbooks.
Cancellation is cooperative, never an unsafe thread/process termination.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime

from . import batchreport, batchreport_store, desktop_diag, desktop_progress, engine, locking
from .desktop_batch import DesktopBatch
from .desktop_recipe import DesktopRecipe
from .desktop_form import DesktopForm
from .desktop_documents import DesktopDocuments
from .desktop_commonality import DesktopCommonality
from .desktop_cmsurvey import DesktopCmSurvey
from .desktop_history import DesktopHistory
from .desktop_config import DesktopConfig
from .desktop_open import DesktopOpen
from .desktop_update import DesktopUpdate
from .desktop_cmrun import DesktopCmRun
from .desktop_formnew import DesktopFormNew
from .desktop_appupdate import DesktopAppUpdate
from .desktop_colorgray import DesktopColorGray
from .desktop_wafermap import DesktopWaferMap
from .desktop_watch import CmWatch, ParamWatch

VERSION = 1
MAX_FRAME = 4 * 1024 * 1024
MAX_PAGE = 200
BUSY_LABEL = {'batch': 'Batch Report 분석', 'recipe': 'Recipe 값 확인', 'document': '문서', 'form': 'Recipe 양식 편집하기',
              'formnew': '신규 Recipe 만들기',
              'commonality': 'Commonality 결과', 'cmsurvey': 'Commonality 계획 확인', 'history': '레시피 날짜별 비교하기',
              'update': '레시피 업데이트', 'cmrun': 'Commonality 조사', 'appupdate': '업데이트', 'config': '설정',
              'pwatch': '파라미터 감시 설정', 'cmwatch': 'Commonality 감시', 'equipment': '장비(원본 폴더) 읽기',
              'watch': '자동 감시 회차', 'colorgray': 'Color·Gray 매칭', 'wafermap': 'Wafer Map 수정하기',
              'batchexport': 'Batch Report Excel 저장'}
METHODS = {"contract", "configuration", "batch_reports", "investigate", "batch_restore", "batch_view", "batch_lot", "batch_raw", "batch_choices", "batch_find", "batch_find_load", "batch_aggregate", "batch_export", "batch_compare_recipes", "batch_compare", "batch_compare_export", "batch_cache_export", "analyze", "table_page", "cancel", "release", "shutdown", "recipe_open", "recipe_page", "recipe_edit", "recipe_export", "recipe_delete_preview", "recipe_delete", "recipe_paint", "recipe_close", "form_catalog", "form_versions", "form_open", "form_page", "form_edit", "form_scales", "form_confirm", "form_bulk", "cmrun_bulk", "cmwatch_bulk", "formnew_page", "formnew_edit", "formnew_bulk", "formnew_scales", "formnew_confirm", "document_open", "document_page", "document_edit", "document_append", "document_delete", "document_close", "commonality_catalog", "commonality_compare", "commonality_page", "commonality_export", "cmsurvey_config", "cmsurvey_preflight", "cmsurvey_plan_template", "cmsurvey_read_plan", "history_files", "history_diff", "history_page", "history_export", "config_state", "config_set_save_dir", "config_set_report_path", "config_set_scanresult_root", "config_remove", "config_edit_root", "config_set_batch_auto", "config_set_extra_paths", "config_set_aoi_root", "config_edit_aoi_root", "config_remove_aoi", "config_set_aoi_extra", "config_set_hide_kla", "config_set_scan_backup", "config_local_state", "config_set_local_dir", "config_purge_temp", "config_about", "update_prepare", "update_set_local_source", "update_collect", "update_preview", "update_commit", "update_cancel", "cmrun_plan", "cmrun_copy", "cmrun_units", "cmrun_detect", "cmrun_parse", "cmrun_page", "cmrun_edit", "cmrun_confirm", "cmrun_collate", "cmrun_reset", "formnew_prepare", "formnew_collect", "formnew_parse", "formnew_cancel", "appupdate_check", "appupdate_skip", "appupdate_apply", "appupdate_publish", "appupdate_open_dir", "open_path", "watch_status", "pwatch_state", "pwatch_save", "pwatch_set_path", "pwatch_copy_paths", "pwatch_jobs", "pwatch_connections", "pwatch_run", "diag_client", "diag_bundle", "cgm_scan", "cgm_start", "cgm_state", "cgm_read", "cgm_put", "cgm_fail", "cgm_finish", "cgm_reset", "wm_scan", "wm_start", "wm_state", "wm_convert", "wm_image", "wm_reset", "cmwatch_state", "cmwatch_save", "cmwatch_run", "cmwatch_candidates", "cmwatch_begin", "cmwatch_recipes", "cmwatch_page", "cmwatch_edit", "cmwatch_confirm", "cmwatch_cancel"}
method_of = {}           # request id -> method name (for the slow-request log)
# Background jobs that only read (local or OneDrive/equipment). Closing the app does not
# wait for them — waiting for a slow read kept the old engine alive after the window
# closed, and a quick relaunch then had to wait for it. Jobs that write always finish.
READ_ONLY = {"recipe_open", "recipe_delete_preview", "document_open", "form_catalog", "form_versions", "form_open",
             "form_scales", "formnew_prepare", "formnew_scales", "history_files", "history_diff",
             "commonality_catalog", "commonality_compare", "cmsurvey_preflight", "cmsurvey_read_plan",
             "update_prepare", "appupdate_check", "pwatch_state", "pwatch_jobs", "cmwatch_state",
             "cmwatch_candidates", "batch_reports", "batch_restore", "watch_status", "cmrun_plan", "cgm_scan", "cgm_read", "wm_scan"}
# Frequent page/scroll requests: only logged in the detailed log when slow.
DIAG_QUIET = {"table_page", "batch_view", "batch_lot", "batch_raw", "recipe_page", "form_page", "document_page", "history_page", "commonality_page",
              "cmrun_page", "cmwatch_page", "formnew_page", "diag_client", "open_path", "cgm_read", "cgm_put", "wm_image"}
WATCH_PROGRESS_SEC = 1.0  # live '진행 중' notice: at most one update per second
TICK_SEC = 60            # scheduler: due checks (settings reads are throttled inside)
LOCK_REFRESH_SEC = 300  # held edit/watch locks: locking.refresh rewrites only near expiry


def encoded(value):
    def convert(obj):
        if isinstance(obj, datetime):
            return obj.isoformat(sep=" ")
        raise TypeError("Unsupported result type")
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, default=convert)
            + "\n").encode("utf-8")


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def validate_records(records):
    if not isinstance(records, list) or len(records) > 2000:
        raise ValueError("records must be a list of at most 2000 reports")
    ids = set()
    wafer_count = 0
    for record in records:
        if not isinstance(record, dict) or set(record) != {"id", "machine", "report"}:
            raise ValueError("record requires only id, machine and report")
        for field in ("id", "machine"):
            if not isinstance(record[field], str) or not 1 <= len(record[field]) <= 256:
                raise ValueError("Invalid record identity")
        if record["id"] in ids:
            raise ValueError("Duplicate report identity")
        ids.add(record["id"])
        report = record["report"]
        if not isinstance(report, dict) or set(report) - {"file_name", "metadata", "wafers", "table_count"}:
            raise ValueError("Invalid report fields")
        if not isinstance(report.get("file_name"), str) or len(report["file_name"]) > 1024:
            raise ValueError("Invalid report name")
        metadata, wafers = report.get("metadata"), report.get("wafers")
        if not isinstance(metadata, list) or len(metadata) > 256 or not isinstance(wafers, list):
            raise ValueError("Invalid metadata or wafer list")
        for pair in metadata:
            if not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(v, str) or len(v) > 4096 for v in pair):
                raise ValueError("Invalid metadata pair")
        wafer_count += len(wafers)
        if wafer_count > 100000:
            raise ValueError("Too many wafer rows")
        for wafer in wafers:
            if not isinstance(wafer, dict) or len(wafer) > 128 or any(
                not isinstance(k, str) or len(k) > 256 or not isinstance(v, str) or len(v) > 4096
                for k, v in wafer.items()
            ):
                raise ValueError("Invalid wafer fields")


def log_failure(method, exc):
    """Record the traceback in the local error log that 설정 › 정보 opens (never
    OneDrive). Logging must never raise into the protocol."""
    try:
        from . import errlog, localdirs
        localdirs.set_root(str(DesktopBatch().configuration()[2]))
        errlog.write_log(None, f"WEB-{method}", f"웹 엔진 {method} 실패", exc)
    except Exception:  # noqa: BLE001
        pass


def failure_code(exc, request):
    if isinstance(request, dict) and request.get("method") == "configuration":
        return "configuration_failed"
    if isinstance(exc, PermissionError):
        return "access_denied"
    if isinstance(exc, FileNotFoundError):
        return "file_missing"
    if isinstance(exc, OSError):
        return "io_failed"
    return "engine_failed"


def investigation_message(exc):
    """Batch Report 조사 실패 → 화면 문장(원인별). 경로 · 자격 증명은 넣지 않는다."""
    if isinstance(exc, MemoryError):
        return ('메모리가 부족해 조사를 끝내지 못했습니다. 한 번에 조사한 호기 · 기간이 너무 많습니다. '
                '다른 프로그램을 닫고 앱을 다시 시작하거나, 호기를 나눠(예: 9대씩) 조사하세요.')
    if isinstance(exc, (ValueError, RuntimeError)) and str(exc):
        return str(exc)[:300]                    # 엔진이 만든 한국어 안내(폴더 설정 · 이미 실행 중 등)
    if isinstance(exc, OSError):
        reason = exc.strerror or type(exc).__name__
        code = getattr(exc, 'winerror', None) or exc.errno
        return (f'결과 파일을 읽거나 쓰지 못했습니다({reason}{f" · 코드 {code}" if code else ""}). '
                '로컬 작업 폴더의 디스크 공간과 접근 권한을 확인하세요.')
    return (f'조사 중 예상하지 못한 오류({type(exc).__name__})로 끝내지 못했습니다. '
            '설정 › 정보의 [진단 로그 묶기] 파일을 담당자에게 전달하세요.')


class Session:
    def __init__(self, output, compute=None):
        self.output = output
        self.compute = compute or batchreport.compute
        self.lock = threading.RLock()
        self.worker = None
        self.cancelled = threading.Event()
        self.result = None
        self.job = None
        self.closed = False
        self.last_id = 0
        self.batch = DesktopBatch()
        self.recipe = DesktopRecipe()
        self.form = DesktopForm()
        self.cmsurvey = DesktopCmSurvey()
        self.history = DesktopHistory()
        self.config = DesktopConfig()
        self.opener = DesktopOpen()
        self.update = DesktopUpdate()
        self.cmrun = DesktopCmRun()
        self.formnew = DesktopFormNew(DesktopForm())
        self.appupdate = DesktopAppUpdate()
        self.documents = DesktopDocuments()
        self.commonality = DesktopCommonality()
        self.colorgray = DesktopColorGray(self.config)
        self.wafermap = DesktopWaferMap(self.config)
        self.busy = {}                  # domain slot -> request id (see claim())
        self.busy_kind = {}
        self.workers = set()
        self.pwatch = ParamWatch()
        self.cmwatch = CmWatch()
        self.watching = None            # 'param' | 'cm' while a watch cycle runs
        self.watch_thread = None
        self.notices = []               # recent watch notices (re-shown after a UI reload)
        self.stop_ticks = threading.Event()
        self.ticker = None

    def emit(self, request_id, event, **data):
        with self.lock:
            payload = encoded(dict(version=VERSION, id=request_id, event=event, **data))
            if len(payload) > MAX_FRAME:
                payload = encoded(dict(version=VERSION, id=request_id, event="error", code="response_too_large"))
            self.output.write(payload)
            self.output.flush()

    def handle(self, request):
        started = time.monotonic()
        method = request.get("method") if isinstance(request, dict) else "?"
        rid0 = request.get("id") if isinstance(request, dict) else None
        if method not in DIAG_QUIET:
            desktop_diag.event(f"요청 받음 #{rid0} {method} (앞 요청 뒤 대기 {getattr(self, 'frame_wait', 0):.2f}s)")
        try:
            self._handle(request)
        finally:
            took = time.monotonic() - started
            if method not in DIAG_QUIET or took >= 0.5:
                bgjob = rid0 in self.busy.values()
                desktop_diag.event(f"요청 처리 #{rid0} {method} {took * 1000:.0f}ms" + (" → 백그라운드 작업으로 넘김" if bgjob else ""))
            desktop_progress.log_slow(f"{method} (입력 처리)", time.monotonic() - started)
            rid = request.get("id") if isinstance(request, dict) else None
            if rid not in self.busy.values():
                method_of.pop(rid, None)     # background jobs drop their own entry

    def _handle(self, request):
        request_id = None
        try:
            if not isinstance(request, dict) or set(request) != {"version", "id", "method", "params"}:
                raise ValueError("Invalid request envelope")
            request_id = request["id"]
            if not integer(request_id, 1, 2**53 - 1) or request_id <= self.last_id:
                request_id = None
                raise ValueError("Request ids must be increasing safe integers")
            self.last_id = request_id
            if type(request["version"]) is not int or request["version"] != VERSION:
                raise ValueError("Unsupported protocol version")
            method, params = request["method"], request["params"]
            if not isinstance(method, str) or method not in METHODS or not isinstance(params, dict):
                raise ValueError("Unsupported method or params")
            with self.lock:
                if self.closed:
                    raise ValueError("Session closed")
                method_of[request_id] = method
                self.dispatch(request_id, method, params)
        except (ValueError, TypeError, KeyError) as exc:
            self.emit(request_id, "error", code="invalid_request", message=str(exc))
        except Exception as exc:
            # Classify without exposing paths or source content (A6): only the
            # configuration request itself reports a configuration failure.
            log_failure(request.get("method") if isinstance(request, dict) else "?", exc)
            self.emit(request_id, "error", code=failure_code(exc, request))

    def dispatch(self, rid, method, params):
        allowed = {"analyze": {"records", "selected"}, "investigate": {"targets", "options"}, "batch_reports": {"machine", "query", "start", "end"}, "table_page": {"job", "table", "offset", "limit"},
                   "batch_restore": set(), "batch_view": {"view", "version", "offset"}, "batch_lot": {"view", "lot"},
                   "batch_raw": {"view", "report"}, "batch_choices": {"view", "changes"},
                   "batch_find": {"machines", "query", "start", "end", "stage"}, "batch_find_load": {"hits"}, "batch_aggregate": {"view", "reports"},
                   "batch_export": {"view", "kind", "reports", "choices", "lot", "drafts", "stamp"}, "batch_compare_recipes": {"view"}, "batch_compare": {"view", "spec"}, "batch_compare_export": {"view", "spec"}, "batch_cache_export": set(),
                   "cancel": {"job"}, "release": {"job"},
                   "recipe_page": {"snapshot","recipe","query","offset","limit","machine_offset","machine_limit","selected_machine","zone","hide_kla",
                                   "hide_empty","group","collapsed"},
                   "recipe_edit": {"snapshot","row","kind","value","target"},
                   "recipe_export": {"snapshot","recipes","machines","query","zone"},
                   "recipe_delete_preview": {"recipe"}, "recipe_delete": {"recipe","confirm"},
                   "recipe_paint": {"snapshot","cells"}, "recipe_close": set()}
        allowed.update(document_open={'kind'},document_page={'snapshot','offset','limit'},
                       document_edit={'snapshot','row','column','value','color'},
                       document_append={'snapshot','values'}, document_delete={'snapshot','row'}, document_close=set())
        allowed.update(commonality_catalog=set(), commonality_compare={'catalog','files'},
                       commonality_page={'snapshot','offset','limit','column','query','changed_only'},
                       commonality_export={'snapshot','changed_only'})
        allowed.update(form_catalog=set(), form_versions={'recipe'}, form_open={'recipe','stamp'},
                       form_page={'snapshot','variant','query','used_only','offset','limit','zone'},
                       form_edit={'snapshot','row','kind','value'}, form_scales={'snapshot','machine'}, form_bulk={'snapshot','value','variant','query','used_only','zone'}, cmrun_bulk={'snapshot','value','variant','query','used_only','zone'}, cmwatch_bulk={'snapshot','value','variant','query','used_only','zone'},
                       form_confirm={'snapshot','machine','scales'})
        allowed.update(cmsurvey_config=set(), cmsurvey_preflight={'machine','plan'}, cmsurvey_plan_template={'rows'},
                       cmsurvey_read_plan={'path'})
        allowed.update(history_files=set(), history_diff={'catalog','old','new','files'},
                       history_page={'snapshot','pair','offset','limit','kind','query'},
                       history_export={'snapshot','pair'})
        allowed.update(config_state=set(), config_set_save_dir={'path'},
                       config_set_report_path={'machine','path'}, config_set_scanresult_root={'machine','path'},
                       config_remove={'kind','machine'}, config_edit_root={'kind','machine','new_machine','path'}, open_path={'path','reveal'},
                       config_set_batch_auto={'enabled','interval_hours'}, config_set_extra_paths={'machine','paths'},
                       config_set_aoi_root={'machine','path'}, config_edit_aoi_root={'machine','new_machine','path'},
                       config_remove_aoi={'machine'}, config_set_aoi_extra={'machine','kind','paths'},
                       config_set_hide_kla={'enabled'}, config_set_scan_backup={'enabled'}, config_local_state=set(), config_set_local_dir={'path'},
                       config_purge_temp=set(), config_about=set())
        allowed.update(update_prepare=set(), update_set_local_source={'path'},
                       update_collect={'recipes','machines','source','answers'}, update_preview={'mapping'},
                       update_commit={'include'}, update_cancel=set())
        allowed.update(cmrun_plan={'machine','plan'}, cmrun_copy={'picks'}, cmrun_units=set(),
                       cmrun_detect={'unit','base'}, cmrun_parse={'unit','scales','base_form'},
                       cmrun_page={'snapshot','variant','query','used_only','offset','limit','zone'},
                       cmrun_edit={'snapshot','row','kind','value'}, cmrun_confirm={'unit','snapshot'},
                       cmrun_collate={'unit','mapping'}, cmrun_reset=set())
        allowed.update(formnew_prepare=set(), formnew_collect={'recipe','machines','source','answers'},
                       formnew_parse={'scales','base_form','variants'}, formnew_cancel=set(),
                       formnew_page={'snapshot','variant','query','used_only','offset','limit','zone'},
                       formnew_edit={'snapshot','row','kind','value'}, formnew_bulk={'snapshot','value','variant','query','used_only','zone'},
                       formnew_scales={'snapshot','machine'}, formnew_confirm={'snapshot','machine','scales'})
        allowed.update(appupdate_check=set(), appupdate_skip={'version'}, appupdate_apply=set(),
                       appupdate_publish={'path','notes'}, appupdate_open_dir=set())
        allowed.update(watch_status=set(), pwatch_state=set(),
                       pwatch_save={'enabled','interval_hours','window_start','window_end','notify_on_change_only'},
                       pwatch_set_path={'machine','recipe','rel'}, pwatch_copy_paths={'source','targets'},
                       pwatch_jobs={'machine','sub'}, pwatch_connections={'machines'}, diag_client={'events'}, diag_bundle=set(), cgm_scan={'root'}, cgm_start={'wafers','output'}, cgm_state=set(), cgm_read={'wafer','record','kind','offset'}, cgm_put={'wafer','record','kind','data','box'}, cgm_fail={'wafer','record','reason'}, cgm_finish={'wafer'}, cgm_reset=set(), wm_scan={'root','mode'}, wm_start={'ids','output'}, wm_state=set(), wm_convert={'index'}, wm_image={'index','kind','data'}, wm_reset=set(), pwatch_run=set(), cmwatch_state=set(),
                       cmwatch_save={'enabled','interval_hours','window_start','window_end','settle_minutes','machines','plan'},
                       cmwatch_run=set(), cmwatch_candidates={'machine','device','lot'}, cmwatch_begin={'sm','title'}, cmwatch_recipes={'indexes'},
                       cmwatch_page={'snapshot','variant','query','used_only','offset','limit','zone'},
                       cmwatch_edit={'snapshot','row','kind','value'}, cmwatch_confirm={'snapshot'}, cmwatch_cancel=set())
        if set(params) - allowed.get(method, set()):
            raise ValueError("Unexpected parameters")
        self.route(rid, method, params)

    # ---- job slots ------------------------------------------------------------------
    # One slot per screen/domain instead of one global "busy" flag: a slow read on one
    # screen (e.g. a large collation on OneDrive) must not leave every other screen
    # stuck at "불러오는 중". Jobs that read the equipment or its shares also take the
    # shared 'equipment' slot so this PC never reads equipment twice at once.
    @property
    def running(self):
        return bool(self.busy)

    def claim(self, rid, *domains):
        for d in domains:
            if d in self.busy:
                raise ValueError(f"{BUSY_LABEL.get(self.busy_kind.get(d, d), d)} 작업이 아직 진행 중입니다. 끝난 뒤 다시 시도하세요.")
        for d in domains:
            self.busy[d] = rid
            self.busy_kind[d] = d

    def free(self, *domains):
        for d in domains:
            self.busy.pop(d, None)
            self.busy_kind.pop(d, None)

    def idle(self, domain):
        if domain in self.busy:
            raise ValueError(f"{BUSY_LABEL.get(domain, domain)} 작업이 아직 진행 중입니다. 끝난 뒤 다시 시도하세요.")

    def spawn(self, target, *args, read_only=False):
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.read_only = read_only
        self.worker = thread
        self.workers.add(thread)
        thread.start()
        return thread

    def background(self, rid, key, action, failure, domains=None):
        """Run one slow operation on a worker. `key` is the reply field; the job
        holds its domain slot(s) (default: the key) until it finishes."""
        domains = tuple(domains or (key,))
        self.claim(rid, *domains)
        self.emit(rid, 'accepted')

        started, steps = time.monotonic(), []

        def step(message):
            # Engine step message → the UI progress panel (and the slow-request log).
            steps.append((time.monotonic() - started, message))
            desktop_diag.event(f"  #{rid} {method_of.get(rid, key)} 단계 +{steps[-1][0]:.1f}s {message}")
            self.emit(rid, 'progress', message=message)

        def work():
            desktop_progress.set_reporter(step)
            try:
                value = action()
                with self.lock:
                    self.free(*domains)
                    self.emit(rid, 'completed', **{key: value})
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    log_failure(key, exc)
                with self.lock:
                    self.free(*domains)
                    self.emit(rid, 'error', code=f'{key}_failed',
                              message=str(exc) if isinstance(exc, ValueError) else failure)
            finally:
                desktop_progress.set_reporter(None)
                desktop_diag.event(f"작업 끝 #{rid} {method_of.get(rid, key)} {(time.monotonic() - started) * 1000:.0f}ms")
                desktop_progress.log_slow(method_of.get(rid, key), time.monotonic() - started, steps)
                method_of.pop(rid, None)
                self.workers.discard(threading.current_thread())
        self.spawn(work, read_only=method_of.get(rid) in READ_ONLY)

    def route(self, rid, method, params):
        bg = self.background
        if method.startswith('commonality_'):
            self.idle('commonality')
            if method in ('commonality_compare', 'commonality_export'):
                action = self.commonality.compare if method == 'commonality_compare' else self.commonality.export
                bg(rid, 'commonality', lambda: action(params), 'Commonality 결과를 처리하지 못했습니다.')
            elif method == 'commonality_catalog':
                bg(rid, 'commonality', self.commonality.catalog, 'Commonality 결과 목록을 읽지 못했습니다. 로컬 작업 폴더를 확인하세요.')
            else:
                self.emit(rid, 'completed', commonality=self.commonality.page(params))
        elif method.startswith('document_'):
            if method == 'document_close':
                # Always allowed: leaving the screen must hand the edit lock back.
                self.emit(rid, 'completed', document=self.documents.close() if 'document' not in self.busy else None)
                return
            self.idle('document')
            action = {'document_open': lambda: self.documents.open(params.get('kind')),
                      'document_edit': lambda: self.documents.edit(params),
                      'document_append': lambda: self.documents.append(params),
                      'document_delete': lambda: self.documents.delete(params)}
            if method == 'document_page':
                self.emit(rid, 'completed', document=self.documents.page(params))
            else:
                # Workbook I/O and lock verification must not block protocol input.
                bg(rid, 'document', action[method], '공유 문서를 처리하지 못했습니다. 파일 접근과 잠금을 확인하세요.')
        elif method.startswith('recipe_'):
            if method == 'recipe_close':
                self.emit(rid, 'completed', recipe=self.recipe.close() if 'recipe' not in self.busy else None)
                return
            self.idle('recipe')
            action = {'recipe_open': lambda: self.recipe.open(), 'recipe_page': lambda: self.recipe.page(params),
                      'recipe_edit': lambda: self.recipe.edit(params),
                      'recipe_export': lambda: self.recipe.export(params),
                      'recipe_delete_preview': lambda: self.recipe.delete_preview(params),
                      'recipe_delete': lambda: self.recipe.delete(params),
                      'recipe_paint': lambda: self.recipe.paint(params)}
            if method in ('recipe_page',):
                self.emit(rid, 'completed', recipe=action[method]())
            else:
                # Collation/workbook reads and writes (often on OneDrive) run off the input thread (A9).
                bg(rid, 'recipe', action[method], '레시피 작업을 완료하지 못했습니다. 파일 접근과 잠금을 확인하세요.')
        elif method.startswith('form_'):
            self.idle('form')
            action = {'form_catalog': lambda: self.form.catalog(), 'form_open': lambda: self.form.open(params),
                      'form_page': lambda: self.form.page(params), 'form_edit': lambda: self.form.edit(params),
                      'form_bulk': lambda: self.form.bulk(params),
                      'form_scales': lambda: self.form.scales(params),
                      'form_versions': lambda: self.form.versions(params),
                      'form_confirm': lambda: self.form.confirm(params)}
            if method in ('form_page', 'form_edit', 'form_bulk'):
                self.emit(rid, 'completed', form=action[method]())
            else:
                bg(rid, 'form', action[method], '양식을 처리하지 못했습니다. 파일 접근과 잠금을 확인하세요.')
        elif method.startswith('cmsurvey_'):
            if method == 'cmsurvey_preflight':
                # Scanresult traversal over the equipment share (A9).
                bg(rid, 'cmsurvey', lambda: self.cmsurvey.preflight(params),
                   'Scanresult 폴더를 확인하지 못했습니다. 장비 연결을 확인하세요.', ('cmsurvey', 'equipment'))
            elif method == 'cmsurvey_plan_template':
                bg(rid, 'cmsurvey', lambda: self.cmsurvey.plan_template(params), '계획 엑셀을 만들지 못했습니다. 로컬 작업 폴더를 확인하세요.')
            elif method == 'cmsurvey_read_plan':
                bg(rid, 'cmsurvey', lambda: self.cmsurvey.read_plan(params), '계획 엑셀을 읽지 못했습니다. 파일이 열려 있거나 형식이 다른지 확인하세요.')
            else:
                self.idle('cmsurvey')
                self.emit(rid, 'completed', cmsurvey=self.cmsurvey.config())
        elif method.startswith('history_'):
            self.idle('history')
            action = {'history_files': lambda: self.history.files(),
                      'history_diff': lambda: self.history.diff(params),
                      'history_page': lambda: self.history.page(params),
                      'history_export': lambda: self.history.export(params)}
            if method == 'history_page':
                self.emit(rid, 'completed', history=action[method]())
            else:
                # Listing/loading collation workbooks is slow on OneDrive (A9).
                bg(rid, 'history', action[method], '취합 파일을 읽지 못했습니다. 파일 접근을 확인하세요.')
        elif method.startswith('config_'):
            if self.busy and method in ('config_set_save_dir', 'config_set_local_dir', 'config_purge_temp'):
                raise ValueError('진행 중인 작업이 끝난 뒤 폴더 설정을 바꾸세요')
            action = {'config_state': lambda: self.config.state(),
                      'config_set_save_dir': lambda: self.config.set_save_dir(params),
                      'config_set_report_path': lambda: self.config.set_report_path(params),
                      'config_set_scanresult_root': lambda: self.config.set_scanresult_root(params),
                      'config_remove': lambda: self.config.remove(params),
                      'config_edit_root': lambda: self.config.edit_root(params),
                      'config_set_batch_auto': lambda: self.config.set_batch_auto(params),
                      'config_set_extra_paths': lambda: self.config.set_extra_paths(params),
                      'config_set_aoi_root': lambda: self.config.set_aoi_root(params),
                      'config_edit_aoi_root': lambda: self.config.edit_aoi_root(params),
                      'config_remove_aoi': lambda: self.config.remove_aoi(params),
                      'config_set_aoi_extra': lambda: self.config.set_aoi_extra(params),
                      'config_set_hide_kla': lambda: self.config.set_hide_kla(params),
                      'config_set_scan_backup': lambda: self.config.set_scan_backup(params),
                      'config_local_state': lambda: self.config.local_state(),
                      'config_set_local_dir': lambda: self.config.set_local_dir(params),
                      'config_purge_temp': lambda: self.config.purge_temp(params),
                      'config_about': lambda: self.config.about(params)}
            if method in ('config_set_save_dir', 'config_set_report_path', 'config_set_scanresult_root',
                          'config_edit_root', 'config_set_extra_paths', 'config_set_local_dir',
                          'config_set_aoi_root', 'config_edit_aoi_root', 'config_set_aoi_extra'):
                # These check the chosen folder (OneDrive / equipment share): never on the input thread.
                bg(rid, 'config', action[method], '폴더를 확인하지 못했습니다. 경로와 연결 상태를 확인하세요.')
            else:
                self.emit(rid, 'completed', config=action[method]())
        elif method.startswith('update_'):
            self.idle('update')
            action = {'update_prepare': lambda: self.update.prepare(params),
                      'update_set_local_source': lambda: self.update.set_local_source(params),
                      'update_collect': lambda: self.update.collect(params),
                      'update_preview': lambda: self.update.preview(params),
                      'update_commit': lambda: self.update.commit(params),
                      'update_cancel': lambda: self.update.cancel(params)}
            if method == 'update_cancel':
                self.emit(rid, 'completed', update=action[method]())
            else:
                bg(rid, 'update', action[method], '값 업데이트를 완료하지 못했습니다. 장비 연결과 파일 접근을 확인하세요.',
                   ('update', 'equipment') if method == 'update_collect' else ('update',))
        elif method.startswith('cmrun_'):
            self.idle('cmrun')
            action = {'cmrun_plan': lambda: self.cmrun.plan(params), 'cmrun_copy': lambda: self.cmrun.copy(params),
                      'cmrun_units': lambda: self.cmrun.units(params), 'cmrun_detect': lambda: self.cmrun.detect(params),
                      'cmrun_parse': lambda: self.cmrun.parse(params), 'cmrun_page': lambda: self.cmrun.form.page(params),
                      'cmrun_edit': lambda: self.cmrun.form.edit(params), 'cmrun_confirm': lambda: self.cmrun.confirm(params),
                      'cmrun_bulk': lambda: self.cmrun.form.bulk(params),
                      'cmrun_collate': lambda: self.cmrun.collate(params), 'cmrun_reset': lambda: self.cmrun.reset(params)}
            if method in ('cmrun_page', 'cmrun_edit', 'cmrun_bulk', 'cmrun_units', 'cmrun_reset'):
                self.emit(rid, 'completed', cmrun=action[method]())
            else:
                # Scanresult traversal, safe copy, parsing and workbook writes run off the input thread.
                bg(rid, 'cmrun', action[method], 'Commonality 조사를 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인하세요.',
                   ('cmrun', 'equipment') if method in ('cmrun_plan', 'cmrun_copy') else ('cmrun',))
        elif method.startswith('formnew_'):
            # 신규 Recipe 만들기 has its own editor state (separate from Recipe 양식 편집하기)
            # so both tabs can be open at once.
            self.idle('formnew')
            action = {'formnew_prepare': lambda: self.formnew.prepare(params),
                      'formnew_collect': lambda: self.formnew.collect(params),
                      'formnew_parse': lambda: self.formnew.parse(params),
                      'formnew_cancel': lambda: self.formnew.cancel(params),
                      'formnew_page': lambda: self.formnew.form.page(params),
                      'formnew_edit': lambda: self.formnew.form.edit(params),
                      'formnew_bulk': lambda: self.formnew.form.bulk(params),
                      'formnew_scales': lambda: self.formnew.form.scales(params),
                      'formnew_confirm': lambda: self.formnew.form.confirm(params)}
            if method in ('formnew_cancel', 'formnew_page', 'formnew_edit', 'formnew_bulk'):
                self.emit(rid, 'completed', formnew=action[method]())
            else:
                bg(rid, 'formnew', action[method], '신규 Recipe 만들기를 완료하지 못했습니다. 장비 연결과 파일 접근을 확인하세요.',
                   ('formnew', 'equipment') if method == 'formnew_collect' else ('formnew',))
        elif method.startswith('appupdate_'):
            action = {'appupdate_check': lambda: self.appupdate.check(params),
                      'appupdate_skip': lambda: self.appupdate.skip(params),
                      'appupdate_apply': lambda: self.appupdate.apply(params),
                      'appupdate_publish': lambda: self.appupdate.publish(params),
                      'appupdate_open_dir': lambda: self.appupdate.open_dir(params)}
            if method in ('appupdate_apply', 'appupdate_publish'):
                if method == 'appupdate_apply' and self.busy:
                    raise ValueError('진행 중인 작업이 끝난 뒤 업데이트하세요')
                # Copy/verify/extract or zip a whole package: worker thread.
                bg(rid, 'appupdate', action[method], '업데이트를 준비하지 못했습니다. 게시 폴더와 로컬 저장 공간을 확인하세요.')
            elif method == 'appupdate_check':
                # Reads the manifest in the (OneDrive) program folder.
                bg(rid, 'appupdate', action[method], '업데이트 정보를 읽지 못했습니다. 게시 폴더를 확인하세요.')
            else:
                self.emit(rid, 'completed', appupdate=action[method]())
        elif method == 'watch_status':
            # Reads the watch settings in the (OneDrive) save folder: never on the input
            # thread, or a slow OneDrive read at start-up delays every other screen.
            bg(rid, 'watch', self.watch_status, '자동 감시 상태를 읽지 못했습니다.', ('watchstatus',))
        elif method in ('pwatch_run', 'cmwatch_run'):
            # '▶ 즉시 확인': same cycle as the scheduler, on the watch thread.
            self.idle('equipment')
            self.emit(rid, 'accepted')
            self.start_watch('param' if method == 'pwatch_run' else 'cm', rid)
        elif method.startswith('pwatch_'):
            action = {'pwatch_state': lambda: self.pwatch.state(params), 'pwatch_save': lambda: self.pwatch.save(params),
                      'pwatch_set_path': lambda: self.pwatch.set_path(params),
                      'pwatch_copy_paths': lambda: self.pwatch.copy_paths(params),
                      'pwatch_jobs': lambda: self.pwatch.jobs(params),
                      'pwatch_connections': lambda: self.pwatch.connections(params)}
            if method in ('pwatch_save', 'pwatch_set_path', 'pwatch_copy_paths') and self.watching == 'param':
                raise ValueError('감시 회차가 끝난 뒤 설정을 바꾸세요')
            # Shared settings / equipment folder listing: off the input thread.
            bg(rid, 'pwatch', action[method], '자동 감시 설정을 처리하지 못했습니다. 저장폴더와 장비 연결을 확인하세요.',
               ('pwatch', 'equipment') if method in ('pwatch_copy_paths', 'pwatch_connections') else ('pwatch',))
        elif method.startswith('cmwatch_'):
            action = {'cmwatch_state': lambda: self.cmwatch.state(params), 'cmwatch_save': lambda: self.cmwatch.save(params),
                      'cmwatch_candidates': lambda: self.cmwatch.candidates(params),
                      'cmwatch_begin': lambda: self.cmwatch.begin(params),
                      'cmwatch_recipes': lambda: self.cmwatch.pick_recipes(params),
                      'cmwatch_page': lambda: self.cmwatch.form.page(params),
                      'cmwatch_edit': lambda: self.cmwatch.form.edit(params),
                      'cmwatch_bulk': lambda: self.cmwatch.form.bulk(params),
                      'cmwatch_confirm': lambda: self.cmwatch.confirm(params),
                      'cmwatch_cancel': lambda: self.cmwatch.cancel(params)}
            if method in ('cmwatch_save', 'cmwatch_confirm') and self.watching == 'cm':
                raise ValueError('감시 회차가 끝난 뒤 설정을 바꾸세요')
            self.idle('cmwatch')
            if method in ('cmwatch_page', 'cmwatch_edit', 'cmwatch_bulk', 'cmwatch_cancel'):
                self.emit(rid, 'completed', cmwatch=action[method]())
            else:
                bg(rid, 'cmwatch', action[method], 'Commonality 감시 작업을 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인하세요.',
                   ('cmwatch', 'equipment') if method in ('cmwatch_candidates', 'cmwatch_begin') else ('cmwatch',))
        elif method.startswith('cgm_'):
            cg = self.colorgray
            action = {'cgm_scan': lambda: cg.scan(params), 'cgm_start': lambda: cg.start(params),
                      'cgm_read': lambda: cg.read(params), 'cgm_finish': lambda: cg.finish(params)}
            if method in action:
                # Folder search / source reads (maybe an equipment share) / Excel build: worker.
                bg(rid, 'colorgray', action[method], 'Color·Gray 매칭 작업을 완료하지 못했습니다. 폴더 연결과 로컬 저장 공간을 확인하세요.',
                   ('colorgray', 'equipment') if method in ('cgm_scan', 'cgm_start') else ('colorgray',))
            else:
                quick = {'cgm_state': lambda: cg.view(), 'cgm_put': lambda: cg.put(params),
                         'cgm_fail': lambda: cg.fail(params), 'cgm_reset': lambda: cg.reset(params)}
                if method == 'cgm_reset' and 'colorgray' in self.busy:
                    cg.cancel.set()      # stop a folder search; the running step ends on its own
                    self.emit(rid, 'completed', colorgray=dict(cancelling=True))
                else:
                    self.emit(rid, 'completed', colorgray=quick[method]())
        elif method.startswith('wm_'):
            wm = self.wafermap
            action = {'wm_scan': lambda: wm.scan(params), 'wm_convert': lambda: wm.convert(params)}
            if method in action:
                # Folder scan / one-file conversion (maybe an equipment share): worker.
                bg(rid, 'wafermap', action[method], 'Wafer Map 변환을 완료하지 못했습니다. 폴더 연결과 저장 공간을 확인하세요.',
                   ('wafermap', 'equipment') if method == 'wm_scan' else ('wafermap',))
            else:
                quick = {'wm_state': lambda: wm.view(), 'wm_start': lambda: wm.start(params),
                         'wm_image': lambda: wm.image(params), 'wm_reset': lambda: wm.reset(params)}
                if method == 'wm_reset' and 'wafermap' in self.busy:
                    wm.cancel.set()      # stop a folder scan; the running step ends on its own
                    self.emit(rid, 'completed', wafermap=dict(cancelling=True))
                else:
                    self.emit(rid, 'completed', wafermap=quick[method]())
        elif method == 'diag_client':
            self.emit(rid, 'completed', diag=desktop_diag.client_events(params))
        elif method == 'diag_bundle':
            from . import localdirs
            folder = os.path.dirname(desktop_diag.path()) or localdirs.logs_dir(self.config.local_state()["root"])
            self.emit(rid, 'completed', diag=dict(path=desktop_diag.bundle(folder), log=desktop_diag.path()))
        elif method == 'open_path':
            # Allowed while a job runs: opening a finished output never touches the job.
            self.emit(rid, 'completed', opened=self.opener.open(params))
        elif method == "contract":
            self.emit(rid, "completed", methods=sorted(METHODS), max_frame=MAX_FRAME, max_page=MAX_PAGE)
        elif method == "configuration":
            self.emit(rid, "completed", **self.batch.describe())
        elif method == "batch_reports":
            # Lists an equipment Report folder (network): never on the input thread.
            bg(rid, 'reports', lambda: self.batch.reports(params),
               'Report 폴더를 읽지 못했습니다. 장비 연결을 확인하세요.', ('batch',))
        elif method in ("batch_view", "batch_lot", "batch_raw", "batch_aggregate"):
            # In-memory view (built after an investigation / search): quick, on the input thread.
            action = {"batch_view": self.batch.view_chunk, "batch_lot": self.batch.view_lot,
                      "batch_raw": self.batch.view_raw, "batch_aggregate": self.batch.aggregate}[method]
            self.emit(rid, "completed", batch=action(params))
        elif method == "batch_restore":
            # Last investigation from the local cache only (no equipment access).
            bg(rid, 'batch', self.batch.restore, '지난 조사 결과를 불러오지 못했습니다. 로컬 작업 폴더를 확인하세요.', ('batch',))
        elif method == "batch_choices":
            # Saved duplicate-Pass choices (local Cache) → recompute every view with them.
            bg(rid, 'batch', lambda: self.batch.save_choices(params), '선택을 저장하지 못했습니다. 로컬 작업 폴더를 확인하세요.', ('batch',))
        elif method == "batch_export":
            bg(rid, 'batch', lambda: self.batch.export(params), 'Excel 을 저장하지 못했습니다. 로컬 작업 폴더와 Excel 열림 여부를 확인하세요.',
               ('batchexport',))
        elif method in ("batch_compare_recipes", "batch_compare"):
            # 레시피 비교: 메모리의 조사 결과만 계산(처음 한 번 Report 특징을 뽑는 데 몇 초) — 작업 스레드.
            action = self.batch.compare_recipes if method == "batch_compare_recipes" else self.batch.compare
            bg(rid, 'batch', lambda: action(params), '레시피 비교를 계산하지 못했습니다. 조사를 다시 시작해 보세요.', ('batch',))
        elif method == "batch_compare_export":
            bg(rid, 'batch', lambda: self.batch.compare_export(params), '비교 결과 HTML 을 저장하지 못했습니다. 로컬 작업 폴더를 확인하세요.',
               ('batchexport',))
        elif method == "batch_cache_export":
            # 취합 캐시(로컬 배치분석/누적) → zip. 장비 접근 없음, 큰 파일 압축이라 작업 스레드.
            bg(rid, 'batch', lambda: self.batch.cache_export(params), '캐시를 내보내지 못했습니다. 로컬 작업 폴더와 저장 공간을 확인하세요.',
               ('batchexport',))
        elif method == "batch_find":
            # 1단계(#19) — 파일 이름만: stage='cache' = 로컬 조사 캐시만(장비 접근 없음), 'equipment' = Reports 폴더 이름 목록도.
            stage = params.get("stage", "equipment")
            if stage not in ("cache", "equipment"):
                raise ValueError("검색 조건을 확인하세요")
            prepared = self.batch.prepare_find({k: v for k, v in params.items() if k != "stage"})
            bg(rid, 'batch', lambda: self.batch.find(prepared, stage, desktop_progress.report),
               'Batch Report 를 찾지 못했습니다. 장비 연결과 로컬 작업 폴더를 확인하세요.',
               ('batch',) if stage == "cache" else ('batch', 'equipment'))
        elif method == "batch_find_load":
            # 2단계(#19) — 고른 것 + 같은 호기 앞뒤 24시간만 읽어 Lot 으로(캐시에 없을 때만 장비 접근).
            bg(rid, 'batch', lambda: self.batch.find_load(params, desktop_progress.report),
               'Batch Report 를 읽지 못했습니다. 장비 연결과 로컬 작업 폴더를 확인하세요.', ('batch', 'equipment'))
        elif method == "investigate":
            if self.job is not None:
                raise ValueError("Release the previous job before starting another")
            prepared = self.batch.prepare(params)
            self.claim(rid, 'batch', 'equipment')
            self.job = rid
            self.cancelled.clear()
            self.emit(rid, "accepted", job=rid)
            self.spawn(self.investigate, rid, prepared)
        elif method == "analyze":
            if self.job is not None:
                raise ValueError("Release the previous job before starting another")
            validate_records(params.get("records"))
            selected = params.get("selected", list(batchreport.METRICS))
            if not isinstance(selected, list) or not selected or any(not isinstance(k, str) or k not in batchreport.METRICS for k in selected):
                raise ValueError("Invalid metrics")
            self.claim(rid, 'batch')
            self.job = rid
            self.cancelled.clear()
            self.emit(rid, "accepted", job=rid)
            self.spawn(self.run, rid, params["records"], selected)
        elif method == "shutdown":
            self.closed = True
            self.cancelled.set()
            self.emit(rid, "completed")
        else:
            if not integer(params.get("job"), 1, 2**53 - 1) or params["job"] != self.job:
                raise ValueError("Unknown job")
            running = 'batch' in self.busy
            if method == "cancel":
                self.cancelled.set()
                self.emit(rid, "completed", cancellation_requested=running)
            elif method == "release":
                if running:
                    raise ValueError("Job still running")
                self.result, self.job = None, None
                self.emit(rid, "completed")
            elif method == "table_page":
                if self.result is None:
                    raise ValueError("Result not available")
                table, offset, limit = params.get("table"), params.get("offset", 0), params.get("limit", MAX_PAGE)
                if not integer(table, 0, len(self.result["tables"]) - 1) or not integer(offset, 0, 2**31 - 1) or not integer(limit, 1, MAX_PAGE):
                    raise ValueError("Invalid page bounds")
                rows = self.result["tables"][table]["rows"]
                self.emit(rid, "completed", table=table, offset=offset, total=len(rows), rows=rows[offset:offset + limit])

    def run(self, rid, records, selected):
        try:
            self.emit(rid, "progress", phase="computing")
            result = None if self.cancelled.is_set() else self.compute(records, selected=selected)
            with self.lock:
                self.free('batch')
                if self.cancelled.is_set():
                    self.emit(rid, "cancelled")
                else:
                    self.result = result
                    self.emit(rid, "completed", summary=result["summary"], tables=[
                        dict(index=i, key=t["key"], title=t["title"], headers=t["headers"], total=len(t["rows"]))
                        for i, t in enumerate(result["tables"])])
        except Exception:
            # Do not expose source content, paths or credentials in protocol errors.
            with self.lock:
                self.free('batch')
                self.emit(rid, "error", code="analysis_failed")

    def investigate(self, rid, prepared):
        def progress(*args):
            self.emit(rid, "progress", phase="investigating", message=str(args[-1]),
                      current=args[0] if len(args) == 3 else None,
                      total=args[1] if len(args) == 3 else None)
        try:
            output = self.batch.run(prepared, progress, self.cancelled.is_set)
            result, collection = output["result"], output["collection"]
            view = None
            try:
                progress("화면용 Lot · 가동률 · WPH 를 계산하는 중…")
                view = self.batch.set_view("scope", collection["records"], extra=self.batch.scope_extra(prepared, output),
                                         view=output.get("view"))
            except Exception as exc:  # noqa: BLE001 - the saved outputs are still valid
                log_failure("batch_view", exc)
            result["tables"].append(dict(key="READ", title="원본 읽기 오류", headers=["호기", "Report", "오류"],
                rows=[(e["machine"], e["source_file"], e["error"]) for e in collection["errors"]]))
            try:
                self.batch.record_run(True, partial=bool(collection["errors"] or output["dashboard_error"]))
            except (OSError, ValueError):
                pass  # schedule bookkeeping never hides a finished analysis
            with self.lock:
                self.free('batch', 'equipment')
                self.result = result
                # Service has committed its outputs. A late cancel is not a rollback.
                self.emit(rid, "completed", summary=result["summary"], view=view,
                    artifacts={k: output[k] for k in ("outdir", "html", "lots", "xlsx", "dashboard", "dashboard_error")},
                    collection={"parsed": collection["parsed"], "reused": collection["reused"],
                                "errors": len(collection["errors"]), "cached_only": collection["cached_only"]},
                    tables=[dict(index=i, key=t["key"], title=t["title"], headers=t["headers"], total=len(t["rows"]))
                            for i, t in enumerate(result["tables"])])
        except batchreport_store.Cancelled:
            with self.lock:
                self.free('batch', 'equipment')
                self.emit(rid, "cancelled")
        except Exception as exc:  # noqa: BLE001 - reported below
            # 원인을 오류 로그에 남기고 화면에도 원인별 문장을 보낸다(이슈 #15: 예전에는 원인이 어디에도 남지 않았다).
            log_failure("investigate", exc)
            message = investigation_message(exc)
            try:
                self.batch.record_run(False, error=message[:200])
            except (OSError, ValueError):
                pass
            with self.lock:
                self.free('batch', 'equipment')
                self.emit(rid, "error", code="investigation_failed", message=message)

    # ---- automatic watches ------------------------------------------------------
    def watch_status(self):
        try:
            p_on = self.pwatch.state_cached_enabled()
        except Exception:  # noqa: BLE001 - no save folder yet
            p_on = False
        try:
            c_on = bool(self.cmwatch._load()[1].enabled)
        except Exception:  # noqa: BLE001
            c_on = False
        return dict(param=p_on, param_owned=bool(self.pwatch.owned), commonality=c_on,
                    busy=self.watching or "", notices=list(self.notices[-20:]))

    def notify(self, notice):
        notice = dict(notice, at=datetime.now().strftime("%Y-%m-%d %H:%M"))
        # A watch cycle keeps one live '진행 중' line: every new notice of the same watch
        # replaces it (the next step, or the final result).
        watch = notice.get('watch')
        kept = [n for n in self.notices if not (watch and n.get('live') and n.get('watch') == watch)]
        self.notices = (kept + [notice])[-50:]
        self.emit(None, 'notice', notice=notice)

    def start_watch(self, kind, rid=None):
        """One watch cycle on its own thread. Manual runs answer `rid`; scheduled
        runs only publish a notice (when something was found / changed / failed)."""
        self.claim(rid, 'equipment')     # one equipment reader at a time on this PC
        self.busy_kind['equipment'] = 'watch'
        self.watching = kind
        watch = self.pwatch if kind == 'param' else self.cmwatch
        key = 'pwatch' if kind == 'param' else 'cmwatch'
        label = '파라미터 자동 감시' if kind == 'param' else 'Commonality 자동 감시'
        # Every cycle leaves a trail in 최근 알림: 시작 → 진행 중(한 줄, 계속 바뀜) → 결과.
        # quiet = list only (no pop-up); changes, new S/M and failures still pop up.
        self.notify(dict(kind=f'{key}_start', watch=key, quiet=True, title=f'{label} — 시작',
                         summary=('즉시 확인' if rid is not None else '정기 회차') + '를 시작합니다.'))
        last = [0.0]

        def progress(message):
            now = time.monotonic()
            if now - last[0] < WATCH_PROGRESS_SEC:
                return                                  # at most one line per second
            last[0] = now
            with self.lock:
                if not self.closed:
                    self.notify(dict(kind=f'{key}_progress', watch=key, quiet=True, live=True,
                                     title=f'{label} — 진행 중', summary=str(message)[:300]))

        def work():
            desktop_progress.set_reporter(progress)
            try:
                value = watch.run(manual=rid is not None)
                err = None
            except Exception as exc:  # noqa: BLE001 - reported below
                if not isinstance(exc, ValueError):
                    log_failure(f'{kind}_watch', exc)
                value, err = None, (str(exc) if isinstance(exc, ValueError) else '감시 회차를 완료하지 못했습니다.')
            finally:
                desktop_progress.set_reporter(None)
            with self.lock:
                self.watching = None
                self.free('equipment')
                if self.closed:
                    return
                if rid is not None:
                    if err:
                        self.emit(rid, 'error', code=f'{key}_failed', message=err)
                    else:
                        self.emit(rid, 'completed', **{key: value})
                if err:
                    self.notify(dict(kind=f'{key}_failed', watch=key, quiet=rid is not None,
                                     title=f'{label} — 실패', summary=err))
                elif kind == 'param' and value.get('has_change'):
                    self.notify(dict(kind='param_watch', watch=key, quiet=rid is not None,
                                     title='파라미터 자동 감시 — 변경 감지',
                                     summary=value['summary'], report=value.get('report', '')))
                elif kind == 'cm' and value.get('found'):
                    self.notify(dict(kind='cm_watch', watch=key, quiet=rid is not None,
                                     title='Commonality 자동 감시 — 새 S/M', summary=value['summary'], report=''))
                else:
                    # Nothing new: still say the cycle ran and what it saw (list only).
                    extra = value.get('skipped') if kind == 'param' else value.get('notes')
                    detail = f" · 건너뜀/메모: {', '.join(map(str, extra[:5]))}" if extra else ''
                    self.notify(dict(kind=f'{key}_done', watch=key, quiet=True, title=f'{label} — 완료',
                                     summary=f"{value.get('summary') or '변경 없음'}{detail}"))
        self.watch_thread = threading.Thread(target=work, daemon=True)
        self.watch_thread.start()

    def tick(self, now=None):
        """Scheduler step (every TICK_SEC). Never overlaps another equipment reader
        (a user's collection or another cycle), like the tkinter `_watch_busy` rule."""
        import time as _time
        now = _time.monotonic() if now is None else now
        with self.lock:
            if self.closed:
                return
            if now - getattr(self, '_last_refresh', -1e9) >= LOCK_REFRESH_SEC:
                self._last_refresh = now
                user = engine.current_user()
                for held in (getattr(self.documents, 'held', None), getattr(self.recipe, 'held', None)):
                    if held:
                        try:
                            locking.refresh(str(held), user)
                        except OSError:
                            pass
                try:
                    self.pwatch.refresh_lock()
                except OSError:
                    pass
            if self.watching or 'equipment' in self.busy:
                return
        try:
            if self.cmwatch.due():
                with self.lock:
                    if not (self.watching or 'equipment' in self.busy or self.closed):
                        self.start_watch('cm')
                return
            if self.pwatch.due():
                with self.lock:
                    if not (self.watching or 'equipment' in self.busy or self.closed):
                        self.start_watch('param')
                return
            notice = self.pwatch.poll_shared()       # a cycle finished on another PC
            if notice:
                with self.lock:
                    self.notify(notice)
        except Exception as exc:  # noqa: BLE001 - the scheduler must keep running
            log_failure('watch_tick', exc)

    def start_scheduler(self):
        def loop():
            while not self.stop_ticks.wait(TICK_SEC):
                self.tick()
        self.ticker = threading.Thread(target=loop, daemon=True)
        self.ticker.start()

    def close(self):
        with self.lock:
            self.closed = True
            self.cancelled.set()
        self.stop_ticks.set()
        started = time.monotonic()
        for worker in list(self.workers):
            if not getattr(worker, 'read_only', False):
                worker.join()            # saves are atomic: wait, never interrupt
        self.result = None
        try:
            self.update.cancel({})      # never leave the global collate lock behind
            self.documents.close()      # nor a held document edit lock
            self.recipe.close()
            self.formnew.cancel({})
            self.pwatch.release()       # another PC may take the watch over
        except Exception:  # noqa: BLE001
            pass
        if getattr(self, 'log_timing', False):
            desktop_progress.log_event(f"엔진 종료 {time.monotonic() - started:.1f}s")


def serve(source, output, startup=""):
    with desktop_diag.timed("엔진 세션 준비"):
        session = Session(output)
    from . import localdirs
    try:
        # Logs (errors, slow-request timings) go to the web app's local folder,
        # never the install folder or the save folder.
        with desktop_diag.timed("시작 설정 읽기(로컬 작업 폴더 확인)"):
            localdirs.set_root(str(DesktopBatch(session.batch.config_path).configuration()[2]))
    except Exception:  # noqa: BLE001 - a bad local setting is reported by the screens
        pass
    try:
        root = localdirs.active_root()
        if not root:
            from .desktop_appupdate import default_local_root
            root = str(default_local_root())
        desktop_diag.attach(localdirs.logs_dir(root))
    except Exception:  # noqa: BLE001 - diagnostics are best effort
        pass
    if startup:
        session.log_timing = True
        desktop_progress.log_event(startup)
        desktop_diag.event(startup)
    with desktop_diag.timed("자동 감시 스케줄러 시작"):
        session.start_scheduler()
    desktop_diag.event("요청 받을 준비 완료 — 이 시각 전에 화면이 보낸 요청은 여기까지 대기했습니다")
    try:
        while not session.closed:
            idle = time.monotonic()
            frame = source.readline(MAX_FRAME + 1)
            if not frame:
                break
            session.frame_wait = time.monotonic() - idle
            if len(frame) > MAX_FRAME:
                session.emit(None, "error", code="frame_too_large")
                break  # Fail closed; do not reinterpret the tail as another request.
            try:
                request = json.loads(frame.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except (ValueError, UnicodeError, RecursionError):
                session.emit(None, "error", code="invalid_json")
                continue
            session.handle(request)
    finally:
        session.close()


if __name__ == "__main__":
    serve(sys.stdin.buffer, sys.stdout.buffer)
