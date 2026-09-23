"""Versioned NDJSON adapter with explicitly allowlisted domain operations.

The fixed native launcher owns this process. Filesystem access is confined by
the domain adapters to configured sources, local outputs and shared workbooks.
Cancellation is cooperative, never an unsafe thread/process termination.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime

from . import batchreport, batchreport_store
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

VERSION = 1
MAX_FRAME = 4 * 1024 * 1024
MAX_PAGE = 200
METHODS = {"contract", "configuration", "batch_reports", "investigate", "analyze", "table_page", "cancel", "release", "shutdown", "recipe_open", "recipe_page", "recipe_edit", "recipe_export", "recipe_delete_preview", "recipe_delete", "recipe_paint", "recipe_close", "form_catalog", "form_versions", "form_open", "form_page", "form_edit", "form_scales", "form_confirm", "document_open", "document_page", "document_edit", "document_append", "document_delete", "document_close", "commonality_catalog", "commonality_compare", "commonality_page", "commonality_export", "cmsurvey_config", "cmsurvey_preflight", "history_files", "history_diff", "history_page", "history_export", "config_state", "config_set_save_dir", "config_set_report_path", "config_set_scanresult_root", "config_remove", "config_set_batch_auto", "config_set_extra_paths", "config_set_hide_kla", "config_local_state", "config_set_local_dir", "config_purge_temp", "config_about", "update_prepare", "update_set_local_source", "update_collect", "update_preview", "update_commit", "update_cancel", "cmrun_plan", "cmrun_copy", "cmrun_units", "cmrun_detect", "cmrun_parse", "cmrun_page", "cmrun_edit", "cmrun_confirm", "cmrun_collate", "cmrun_reset", "formnew_prepare", "formnew_collect", "formnew_parse", "formnew_cancel", "appupdate_check", "appupdate_skip", "appupdate_apply", "appupdate_publish", "appupdate_open_dir", "open_path"}


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
        self.formnew = DesktopFormNew(self.form)
        self.appupdate = DesktopAppUpdate()
        self.documents = DesktopDocuments()
        self.commonality = DesktopCommonality()
        self.running = False

    def emit(self, request_id, event, **data):
        with self.lock:
            payload = encoded(dict(version=VERSION, id=request_id, event=event, **data))
            if len(payload) > MAX_FRAME:
                payload = encoded(dict(version=VERSION, id=request_id, event="error", code="response_too_large"))
            self.output.write(payload)
            self.output.flush()

    def handle(self, request):
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
                   "cancel": {"job"}, "release": {"job"},
                   "recipe_page": {"snapshot","recipe","query","offset","limit","machine_offset","machine_limit","selected_machine","zone","hide_kla"},
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
                       form_page={'snapshot','variant','query','used_only','offset','limit'},
                       form_edit={'snapshot','row','kind','value'}, form_scales={'snapshot','machine'},
                       form_confirm={'snapshot','machine','scales'})
        allowed.update(cmsurvey_config=set(), cmsurvey_preflight={'machine','plan'})
        allowed.update(history_files=set(), history_diff={'catalog','old','new','files'},
                       history_page={'snapshot','pair','offset','limit','kind','query'},
                       history_export={'snapshot','pair'})
        allowed.update(config_state=set(), config_set_save_dir={'path'},
                       config_set_report_path={'machine','path'}, config_set_scanresult_root={'machine','path'},
                       config_remove={'kind','machine'}, open_path={'path','reveal'},
                       config_set_batch_auto={'enabled'}, config_set_extra_paths={'machine','paths'},
                       config_set_hide_kla={'enabled'}, config_local_state=set(), config_set_local_dir={'path'},
                       config_purge_temp=set(), config_about=set())
        allowed.update(update_prepare=set(), update_set_local_source={'path'},
                       update_collect={'recipes','machines','source','answers'}, update_preview={'mapping'},
                       update_commit={'include'}, update_cancel=set())
        allowed.update(cmrun_plan={'machine','plan'}, cmrun_copy={'picks'}, cmrun_units=set(),
                       cmrun_detect={'unit','base'}, cmrun_parse={'unit','scales','base_form'},
                       cmrun_page={'snapshot','variant','query','used_only','offset','limit'},
                       cmrun_edit={'snapshot','row','kind','value'}, cmrun_confirm={'unit','snapshot'},
                       cmrun_collate={'unit','mapping'}, cmrun_reset=set())
        allowed.update(formnew_prepare=set(), formnew_collect={'recipe','machines','source','answers'},
                       formnew_parse={'scales','base_form'}, formnew_cancel=set())
        allowed.update(appupdate_check=set(), appupdate_skip={'version'}, appupdate_apply=set(),
                       appupdate_publish={'path','notes'}, appupdate_open_dir=set())
        if set(params) - allowed.get(method, set()):
            raise ValueError("Unexpected parameters")
        if method.startswith('commonality_'):
            if self.running:
                raise ValueError('진행 중인 작업이 끝난 뒤 실행하세요')
            if method in ('commonality_compare', 'commonality_export'):
                self.running = True
                self.emit(rid, 'accepted')
                self.worker = threading.Thread(target=self.commonality_work, args=(rid, method, params))
                self.worker.start()
            else:
                value = self.commonality.catalog() if method == 'commonality_catalog' else self.commonality.page(params)
                self.emit(rid, 'completed', commonality=value)
        elif method.startswith('document_'):
            if self.running and method!='document_close':raise ValueError('배치 조사 완료 후 문서를 열어 주세요')
            action={'document_open':lambda:self.documents.open(params.get('kind')),
                    'document_page':lambda:self.documents.page(params),'document_edit':lambda:self.documents.edit(params),
                    'document_append':lambda:self.documents.append(params),
                    'document_delete':lambda:self.documents.delete(params)}
            action['document_close']=lambda:self.documents.close()
            if method in ('document_page','document_close'):
                self.emit(rid,'completed',document=action[method]())
            else:
                self.running = True
                self.emit(rid, 'accepted')
                self.worker = threading.Thread(target=self.document_work, args=(rid, action[method]))
                self.worker.start()
        elif method.startswith('recipe_'):
            if self.running and method != 'recipe_close':
                raise ValueError('배치 조사 완료 후 비교 화면을 열어 주세요')
            action = {'recipe_open': lambda: self.recipe.open(), 'recipe_page': lambda: self.recipe.page(params),
                      'recipe_edit': lambda: self.recipe.edit(params),
                      'recipe_export': lambda: self.recipe.export(params),
                      'recipe_delete_preview': lambda: self.recipe.delete_preview(params),
                      'recipe_delete': lambda: self.recipe.delete(params),
                      'recipe_paint': lambda: self.recipe.paint(params),
                      'recipe_close': lambda: self.recipe.close()}
            if method in ('recipe_open', 'recipe_edit', 'recipe_export', 'recipe_delete'):
                # Collation/workbook reads and writes (often on OneDrive) run off the input thread (A9).
                self.background(rid, 'recipe', action[method], '레시피 작업을 완료하지 못했습니다. 파일 접근과 잠금을 확인하세요.')
            else:
                self.emit(rid, "completed", recipe=action[method]())
        elif method.startswith('form_'):
            if self.running:
                raise ValueError('배치 조사 완료 후 양식 만들기를 열어 주세요')
            if method == 'form_confirm':
                # Confirmation writes a workbook and takes the form lock: run off the input thread.
                self.running = True
                self.emit(rid, 'accepted')
                self.worker = threading.Thread(target=self.form_work, args=(rid, params))
                self.worker.start()
            else:
                action = {'form_catalog': lambda: self.form.catalog(), 'form_open': lambda: self.form.open(params),
                          'form_page': lambda: self.form.page(params), 'form_edit': lambda: self.form.edit(params),
                          'form_scales': lambda: self.form.scales(params),
                          'form_versions': lambda: self.form.versions(params)}
                if method in ('form_catalog', 'form_versions', 'form_open', 'form_scales'):
                    # Reads candidate/coefficient workbooks from the save folder (A9).
                    self.background(rid, 'form', action[method], '양식을 읽지 못했습니다. 파일 접근과 잠금을 확인하세요.')
                else:
                    self.emit(rid, 'completed', form=action[method]())
        elif method.startswith('cmsurvey_'):
            if self.running:
                raise ValueError('배치 조사 완료 후 Commonality 계획을 확인하세요')
            action = {'cmsurvey_config': lambda: self.cmsurvey.config(),
                      'cmsurvey_preflight': lambda: self.cmsurvey.preflight(params)}
            if method == 'cmsurvey_preflight':
                # Scanresult traversal over the equipment share (A9).
                self.background(rid, 'cmsurvey', action[method], 'Scanresult 폴더를 확인하지 못했습니다. 장비 연결을 확인하세요.')
            else:
                self.emit(rid, 'completed', cmsurvey=action[method]())
        elif method.startswith('history_'):
            if self.running:
                raise ValueError('배치 조사 완료 후 이력 확인을 열어 주세요')
            action = {'history_files': lambda: self.history.files(),
                      'history_diff': lambda: self.history.diff(params),
                      'history_page': lambda: self.history.page(params),
                      'history_export': lambda: self.history.export(params)}
            if method in ('history_diff', 'history_export'):
                # Loading two or more collation workbooks is slow on OneDrive (A9).
                self.background(rid, 'history', action[method], '취합 파일을 비교하지 못했습니다. 파일 접근을 확인하세요.')
            else:
                self.emit(rid, 'completed', history=action[method]())
        elif method.startswith('config_'):
            if self.running and method in ('config_set_save_dir', 'config_set_local_dir', 'config_purge_temp'):
                raise ValueError('진행 중인 작업이 끝난 뒤 폴더 설정을 바꾸세요')
            action = {'config_state': lambda: self.config.state(),
                      'config_set_save_dir': lambda: self.config.set_save_dir(params),
                      'config_set_report_path': lambda: self.config.set_report_path(params),
                      'config_set_scanresult_root': lambda: self.config.set_scanresult_root(params),
                      'config_remove': lambda: self.config.remove(params),
                      'config_set_batch_auto': lambda: self.config.set_batch_auto(params),
                      'config_set_extra_paths': lambda: self.config.set_extra_paths(params),
                      'config_set_hide_kla': lambda: self.config.set_hide_kla(params),
                      'config_local_state': lambda: self.config.local_state(),
                      'config_set_local_dir': lambda: self.config.set_local_dir(params),
                      'config_purge_temp': lambda: self.config.purge_temp(params),
                      'config_about': lambda: self.config.about(params)}
            self.emit(rid, 'completed', config=action[method]())
        elif method.startswith('update_'):
            if self.running:
                raise ValueError('진행 중인 작업이 끝난 뒤 값 업데이트를 진행하세요')
            action = {'update_prepare': lambda: self.update.prepare(params),
                      'update_set_local_source': lambda: self.update.set_local_source(params),
                      'update_collect': lambda: self.update.collect(params),
                      'update_preview': lambda: self.update.preview(params),
                      'update_commit': lambda: self.update.commit(params),
                      'update_cancel': lambda: self.update.cancel(params)}
            if method in ('update_collect', 'update_preview', 'update_commit'):
                # Equipment reads, parsing and the collation write run off the input thread.
                self.background(rid, 'update', action[method], '값 업데이트를 완료하지 못했습니다. 장비 연결과 파일 접근을 확인하세요.')
            else:
                self.emit(rid, 'completed', update=action[method]())
        elif method.startswith('cmrun_'):
            if self.running:
                raise ValueError('진행 중인 작업이 끝난 뒤 Commonality 조사를 진행하세요')
            action = {'cmrun_plan': lambda: self.cmrun.plan(params), 'cmrun_copy': lambda: self.cmrun.copy(params),
                      'cmrun_units': lambda: self.cmrun.units(params), 'cmrun_detect': lambda: self.cmrun.detect(params),
                      'cmrun_parse': lambda: self.cmrun.parse(params), 'cmrun_page': lambda: self.cmrun.form.page(params),
                      'cmrun_edit': lambda: self.cmrun.form.edit(params), 'cmrun_confirm': lambda: self.cmrun.confirm(params),
                      'cmrun_collate': lambda: self.cmrun.collate(params), 'cmrun_reset': lambda: self.cmrun.reset(params)}
            if method in ('cmrun_page', 'cmrun_edit', 'cmrun_units', 'cmrun_reset'):
                self.emit(rid, 'completed', cmrun=action[method]())
            else:
                # Scanresult traversal, safe copy, parsing and workbook writes run off the input thread.
                self.background(rid, 'cmrun', action[method], 'Commonality 조사를 완료하지 못했습니다. 폴더 접근과 로컬 저장 공간을 확인하세요.')
        elif method.startswith('formnew_'):
            if self.running:
                raise ValueError('진행 중인 작업이 끝난 뒤 양식을 만드세요')
            action = {'formnew_prepare': lambda: self.formnew.prepare(params),
                      'formnew_collect': lambda: self.formnew.collect(params),
                      'formnew_parse': lambda: self.formnew.parse(params),
                      'formnew_cancel': lambda: self.formnew.cancel(params)}
            if method in ('formnew_collect', 'formnew_parse'):
                self.background(rid, 'formnew', action[method], '양식 만들기 수집을 완료하지 못했습니다. 장비 연결과 파일 접근을 확인하세요.')
            else:
                self.emit(rid, 'completed', formnew=action[method]())
        elif method.startswith('appupdate_'):
            action = {'appupdate_check': lambda: self.appupdate.check(params),
                      'appupdate_skip': lambda: self.appupdate.skip(params),
                      'appupdate_apply': lambda: self.appupdate.apply(params),
                      'appupdate_publish': lambda: self.appupdate.publish(params),
                      'appupdate_open_dir': lambda: self.appupdate.open_dir(params)}
            if method in ('appupdate_apply', 'appupdate_publish'):
                if self.running:
                    raise ValueError('진행 중인 작업이 끝난 뒤 업데이트하세요')
                # Copy/verify/extract or zip a whole package: worker thread.
                self.background(rid, 'appupdate', action[method], '업데이트를 준비하지 못했습니다. 게시 폴더와 로컬 저장 공간을 확인하세요.')
            else:
                self.emit(rid, 'completed', appupdate=action[method]())
        elif method == 'open_path':
            # Allowed while a job runs: opening a finished output never touches the job.
            self.emit(rid, 'completed', opened=self.opener.open(params))
        elif method == "contract":
            self.emit(rid, "completed", methods=sorted(METHODS), max_frame=MAX_FRAME, max_page=MAX_PAGE)
        elif method == "configuration":
            self.emit(rid, "completed", **self.batch.describe())
        elif method == "batch_reports":
            if self.running:
                raise ValueError("배치 조사 완료 후 목록을 다시 확인하세요")
            self.emit(rid, "completed", reports=self.batch.reports(params))
        elif method == "investigate":
            if self.job is not None or self.running:
                raise ValueError("Release the previous job before starting another")
            prepared = self.batch.prepare(params)
            self.job, self.running = rid, True
            self.cancelled.clear()
            self.emit(rid, "accepted", job=rid)
            self.worker = threading.Thread(target=self.investigate, args=(rid, prepared))
            self.worker.start()
        elif method == "analyze":
            if self.job is not None or self.running:
                raise ValueError("Release the previous job before starting another")
            validate_records(params.get("records"))
            selected = params.get("selected", list(batchreport.METRICS))
            if not isinstance(selected, list) or not selected or any(not isinstance(k, str) or k not in batchreport.METRICS for k in selected):
                raise ValueError("Invalid metrics")
            self.job = rid
            self.running = True
            self.cancelled.clear()
            self.emit(rid, "accepted", job=rid)
            self.worker = threading.Thread(target=self.run, args=(rid, params["records"], selected))
            self.worker.start()
        elif method == "shutdown":
            self.closed = True
            self.cancelled.set()
            self.emit(rid, "completed")
        else:
            if not integer(params.get("job"), 1, 2**53 - 1) or params["job"] != self.job:
                raise ValueError("Unknown job")
            running = self.running
            if method == "cancel":
                self.cancelled.set()
                self.emit(rid, "completed", cancellation_requested=running)
            elif method == "release":
                if running:
                    raise ValueError("Job still running")
                self.result, self.job, self.worker = None, None, None
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
                self.running = False
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
                self.running = False
                self.emit(rid, "error", code="analysis_failed")

    def investigate(self, rid, prepared):
        def progress(*args):
            self.emit(rid, "progress", phase="investigating", message=str(args[-1]),
                      current=args[0] if len(args) == 3 else None,
                      total=args[1] if len(args) == 3 else None)
        try:
            output = self.batch.run(prepared, progress, self.cancelled.is_set)
            result, collection = output["result"], output["collection"]
            result["tables"].append(dict(key="READ", title="원본 읽기 오류", headers=["호기", "Report", "오류"],
                rows=[(e["machine"], e["source_file"], e["error"]) for e in collection["errors"]]))
            try:
                self.batch.record_run(True, partial=bool(collection["errors"] or output["dashboard_error"]))
            except (OSError, ValueError):
                pass  # schedule bookkeeping never hides a finished analysis
            with self.lock:
                self.running = False
                self.result = result
                # Service has committed its outputs. A late cancel is not a rollback.
                self.emit(rid, "completed", summary=result["summary"],
                    artifacts={k: output[k] for k in ("outdir", "html", "xlsx", "dashboard", "dashboard_error")},
                    collection={"parsed": collection["parsed"], "reused": collection["reused"],
                                "errors": len(collection["errors"]), "cached_only": collection["cached_only"]},
                    tables=[dict(index=i, key=t["key"], title=t["title"], headers=t["headers"], total=len(t["rows"]))
                            for i, t in enumerate(result["tables"])])
        except batchreport_store.Cancelled:
            with self.lock:
                self.running = False
                self.emit(rid, "cancelled")
        except Exception:
            try:
                self.batch.record_run(False, error="조사 실패")
            except (OSError, ValueError):
                pass
            with self.lock:
                self.running = False
                self.emit(rid, "error", code="investigation_failed")

    def background(self, rid, key, action, failure):
        """Run one slow file operation on a worker; same single-job rule as documents."""
        self.running = True
        self.emit(rid, 'accepted')

        def work():
            try:
                value = action()
                with self.lock:
                    self.running = False
                    self.emit(rid, 'completed', **{key: value})
            except Exception as exc:
                if not isinstance(exc, ValueError):
                    log_failure(key, exc)
                with self.lock:
                    self.running = False
                    self.emit(rid, 'error', code=f'{key}_failed',
                              message=str(exc) if isinstance(exc, ValueError) else failure)
        self.worker = threading.Thread(target=work)
        self.worker.start()

    def document_work(self, rid, action):
        # Workbook I/O and lock verification must not block protocol input.
        # Saves are atomic operations: shutdown waits rather than interrupting them.
        try:
            value = action()
            with self.lock:
                self.running = False
                self.emit(rid, 'completed', document=value)
        except Exception as exc:
            with self.lock:
                self.running = False
                self.emit(rid, 'error', code='document_failed',
                          message=str(exc) if isinstance(exc, ValueError) else '공유 문서를 처리하지 못했습니다. 파일 접근과 잠금을 확인하세요.')

    def form_work(self, rid, params):
        # Confirmation writes final + original workbooks under the form lock.
        try:
            value = self.form.confirm(params)
            with self.lock:
                self.running = False
                self.emit(rid, 'completed', form=value)
        except Exception as exc:
            with self.lock:
                self.running = False
                self.emit(rid, 'error', code='form_failed',
                          message=str(exc) if isinstance(exc, ValueError) else '양식을 확정하지 못했습니다. 파일 접근과 잠금을 확인하세요.')

    def commonality_work(self, rid, method, params):
        try:
            action = self.commonality.compare if method == 'commonality_compare' else self.commonality.export
            value = action(params)
            with self.lock:
                self.running = False
                self.emit(rid, 'completed', commonality=value)
        except Exception as exc:
            with self.lock:
                self.running = False
                self.emit(rid, 'error', code='commonality_failed',
                          message=str(exc) if isinstance(exc, ValueError) else 'Commonality 결과를 처리하지 못했습니다.')

    def close(self):
        with self.lock:
            self.closed = True
            self.cancelled.set()
        if self.worker is not None:
            self.worker.join()
        self.result = None
        try:
            self.update.cancel({})      # never leave the global collate lock behind
            self.documents.close()      # nor a held document edit lock
            self.recipe.close()
            self.formnew.cancel({})
        except Exception:  # noqa: BLE001
            pass


def serve(source, output):
    session = Session(output)
    try:
        while not session.closed:
            frame = source.readline(MAX_FRAME + 1)
            if not frame:
                break
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
