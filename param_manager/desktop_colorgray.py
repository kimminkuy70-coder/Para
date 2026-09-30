"""Web UI adapter for Color · Gray 매칭 (`colorgray`).

Flow (the UI drives it one image at a time, so a long job never blocks the engine):
  cgm_scan(root)            → wafer folders under a Lot/Wafer folder
  cgm_start(wafers, output) → match every color image; job plan (no pixels yet)
  cgm_read(w, r, kind)      → one source JPEG (color / gray) as base64
  cgm_put(w, r, kind, data) → one JPEG the UI produced (crop / thumbnails)
  cgm_fail(w, r, reason)    → the UI could not decode/produce that record
  cgm_finish(w)             → comparison workbook + unmatched list for one wafer

Safety: sources are only read, and only files named in the scanned wafers' own
lists. Outputs are written under one output folder the engine chose or checked
(local disk, not OneDrive, not a network share, not inside the source folder),
with names the engine makes — the UI never supplies a path to write.
"""
from __future__ import annotations

import base64
import binascii
import threading
from datetime import datetime
from pathlib import Path

from . import colorgray, desktop_progress

MAX_SOURCE = 2_900_000          # raw bytes per source image (base64 must fit the 4 MB frame)
MAX_OUTPUT = 2_900_000
KINDS_IN = ("color", "gray")
KINDS_OUT = ("crop", "color_thumb", "gray_thumb", "crop_thumb")


class DesktopColorGray:
    extra_roots: list = []      # custom output folders DesktopOpen may open

    def __init__(self, config=None):
        self.config = config
        self.root = None
        self.wafers = []
        self.job = None
        self.cancel = threading.Event()

    # ------------------------------------------------------------ helpers
    def _local_root(self):
        return Path(self.config.local_state()["root"]) if self.config else Path.cwd()

    def _wafer(self, params):
        job = self.job
        if not job:
            raise ValueError("진행 중인 작업이 없습니다")
        w = params.get("wafer")
        if type(w) is not int or not 0 <= w < len(job["wafers"]):
            raise ValueError("Wafer 번호를 확인하세요")
        return job["wafers"][w]

    def _record(self, params):
        wafer = self._wafer(params)
        r = params.get("record")
        if type(r) is not int or not 0 <= r < len(wafer["records"]):
            raise ValueError("이미지 번호를 확인하세요")
        return wafer, wafer["records"][r]

    # ------------------------------------------------------------ steps
    def scan(self, params):
        root = params.get("root")
        if set(params) != {"root"} or not isinstance(root, str) or not root.strip() or len(root) > 1024:
            raise ValueError("Lot 또는 Wafer 폴더를 입력하세요")
        path = Path(root.strip())
        if not path.is_dir():
            raise ValueError("폴더를 찾을 수 없습니다. 장비 공유는 탐색기로 먼저 연결하세요.")
        self.cancel.clear()

        def progress(stage, current, scanned, found, queued):
            if stage == "scanning" and scanned % 5 == 1:
                desktop_progress.report(f"하위 폴더 검색 중 — 확인 {scanned} · Wafer {found} · 대기 {queued}  ({current.name})")
        wafers = colorgray.discover(path, progress, self.cancel)
        self.root, self.wafers = path, [str(w) for w in wafers]
        return dict(root=str(path), wafers=[dict(name=Path(w).name, path=w) for w in self.wafers],
                    limit=colorgray.MAX_WAFERS, default_output=str(self._default_output(path)))

    def _default_output(self, source: Path):
        return self._local_root() / "ColorGray매칭" / (source.name or "Lot")

    def _check_output(self, raw):
        """Local disk only: not OneDrive, not a network share, not overlapping the source
        (batchreport_store.local_root enforces exactly these for the batch results)."""
        from . import batchreport_store
        return batchreport_store.local_root(Path(raw).absolute(), [str(self.root)])

    def start(self, params):
        if set(params) - {"wafers", "output"} or not isinstance(params.get("wafers"), list):
            raise ValueError("처리할 Wafer 를 확인하세요")
        if self.root is None:
            raise ValueError("먼저 폴더에서 Wafer 를 찾으세요")
        chosen = params["wafers"]
        if not chosen or len(chosen) > colorgray.MAX_WAFERS or any(w not in self.wafers for w in chosen):
            raise ValueError("처리할 Wafer 를 목록에서 고르세요")
        raw = params.get("output") or ""
        if not isinstance(raw, str) or len(raw) > 1024:
            raise ValueError("저장 위치를 확인하세요")
        if raw.strip():
            base = self._check_output(raw.strip())
            if str(base) not in DesktopColorGray.extra_roots:
                DesktopColorGray.extra_roots.append(str(base))
        else:
            base = self._default_output(Path(self.root))
        output = base / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cancel.clear()
        wafers = []
        for n, path in enumerate(chosen, 1):
            name = Path(path).name
            desktop_progress.report(f"[{n}/{len(chosen)}] {name} 좌표 매칭 중…")
            try:
                records, failures, total = colorgray.plan_wafer(path)
            except (OSError, KeyError, ValueError, IndexError) as exc:
                records, failures, total = [], [("(전체)", f"설정 파일을 읽지 못함: {exc}")], 0
            result = output / name
            for r in records:
                r["outputs"] = {k: str(result / v) for k, v in colorgray.output_names(r["index"], r["color_file"]).items()}
                r["done"] = set()
            wafers.append(dict(name=name, path=path, result=result, records=records, failures=failures,
                               colors=total, finished=None))
        self.job = dict(output=output, wafers=wafers)
        return self.view()

    def view(self):
        job = self.job
        if not job:
            return dict(job=None)
        return dict(job=dict(
            output=str(job["output"]),
            wafers=[dict(name=w["name"], colors=w["colors"], failed=len(w["failures"]), finished=w["finished"],
                         records=[dict(color=r["color_file"], gray=r["gray_file"], px=r["pixel_x"], py=r["pixel_y"],
                                       gw=colorgray.GW, gh=colorgray.GH, crop_w=r["crop_w"], crop_h=r["crop_h"],
                                       out_w=r["out_w"], out_h=r["out_h"]) for r in w["records"]])
                    for w in job["wafers"]]))

    def read(self, params):
        if set(params) != {"wafer", "record", "kind"} or params.get("kind") not in KINDS_IN:
            raise ValueError("읽을 이미지를 확인하세요")
        _, rec = self._record(params)
        path = Path(rec["color_path" if params["kind"] == "color" else "gray_path"])
        size = path.stat().st_size
        if size > MAX_SOURCE:
            raise ValueError(f"이미지가 너무 큽니다({size // 1024} KB): {path.name}")
        return dict(name=path.name, data=base64.b64encode(path.read_bytes()).decode("ascii"))

    def put(self, params):
        if set(params) - {"wafer", "record", "kind", "data", "box"} or params.get("kind") not in KINDS_OUT:
            raise ValueError("저장할 이미지를 확인하세요")
        wafer, rec = self._record(params)
        data = params.get("data")
        if not isinstance(data, str) or len(data) > MAX_OUTPUT * 4 // 3 + 8:
            raise ValueError("이미지 데이터를 확인하세요")
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("이미지 데이터를 확인하세요") from exc
        if not colorgray.jpeg_size(raw):
            raise ValueError("JPEG 이미지가 아닙니다")
        target = Path(rec["outputs"][params["kind"]])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        if params["kind"] == "crop" and isinstance(params.get("box"), list) and len(params["box"]) == 4 \
                and all(type(v) is int for v in params["box"]):
            rec["crop_box"] = params["box"]
        rec["done"].add(params["kind"])
        return dict(saved=params["kind"])

    def fail(self, params):
        if set(params) != {"wafer", "record", "reason"} or not isinstance(params.get("reason"), str):
            raise ValueError("실패 사유를 확인하세요")
        wafer, rec = self._record(params)
        rec["error"] = params["reason"][:200]
        return dict(ok=True)

    def finish(self, params):
        if set(params) != {"wafer"}:
            raise ValueError("Wafer 번호를 확인하세요")
        wafer, job = self._wafer(params), self.job
        result = wafer["result"]
        result.mkdir(parents=True, exist_ok=True)
        ready, failures = [], list(wafer["failures"])
        for rec in wafer["records"]:
            if set(KINDS_OUT) <= rec["done"]:
                ready.append(dict(rec, crop_path=rec["outputs"]["crop"],
                                  **{k: rec["outputs"][k] for k in ("color_thumb", "gray_thumb", "crop_thumb")}))
            else:
                failures.append((rec["color_file"], rec.get("error") or "이미지 처리 안 됨(취소 또는 오류)"))

        def progress(done, total):
            if done == 1 or done % 10 == 0 or done == total:
                desktop_progress.report(f"{wafer['name']} Excel 이미지 삽입 {done}/{total}")
        workbook = colorgray.build_workbook(result, wafer["name"], ready, progress)
        failed_csv = str(colorgray.write_failures(result, failures)) if failures else ""
        wafer["finished"] = dict(workbook=str(workbook), matched=len(ready), failed=len(failures),
                                 failures_csv=failed_csv, folder=str(result))
        return dict(wafer["finished"], output=str(job["output"]))

    def reset(self, params):
        if params:
            raise ValueError("초기화 요청을 확인하세요")
        self.cancel.set()
        self.job = None
        return dict(job=None)
