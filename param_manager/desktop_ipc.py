"""Versioned, memory-only NDJSON adapter. No file, network or shell commands.

Run with the bundled Python as ``-m param_manager.desktop_ipc``. The native
launcher is intentionally not wired yet. Cancellation is cooperative at engine
boundaries, not an unsafe thread/process termination.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime

from . import batchreport

VERSION = 1
MAX_FRAME = 4 * 1024 * 1024
MAX_PAGE = 200
METHODS = {"contract", "analyze", "table_page", "cancel", "release", "shutdown"}


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

    def dispatch(self, rid, method, params):
        allowed = {"analyze": {"records", "selected"}, "table_page": {"job", "table", "offset", "limit"},
                   "cancel": {"job"}, "release": {"job"}}
        if set(params) - allowed.get(method, set()):
            raise ValueError("Unexpected parameters")
        if method == "contract":
            self.emit(rid, "completed", methods=sorted(METHODS), max_frame=MAX_FRAME, max_page=MAX_PAGE)
        elif method == "analyze":
            if self.job is not None:
                raise ValueError("Release the previous job before starting another")
            validate_records(params.get("records"))
            selected = params.get("selected", list(batchreport.METRICS))
            if not isinstance(selected, list) or not selected or any(not isinstance(k, str) or k not in batchreport.METRICS for k in selected):
                raise ValueError("Invalid metrics")
            self.job = rid
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
            running = self.worker is not None and self.worker.is_alive()
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
                if self.cancelled.is_set():
                    self.emit(rid, "cancelled")
                else:
                    self.result = result
                    self.emit(rid, "completed", summary=result["summary"], tables=[
                        dict(index=i, key=t["key"], title=t["title"], headers=t["headers"], total=len(t["rows"]))
                        for i, t in enumerate(result["tables"])])
        except Exception:
            # Do not expose source content, paths or credentials in protocol errors.
            self.emit(rid, "error", code="analysis_failed")

    def close(self):
        with self.lock:
            self.closed = True
            self.cancelled.set()
        if self.worker is not None:
            self.worker.join()
        self.result = None


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
