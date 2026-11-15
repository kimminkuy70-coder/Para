"""Web UI adapter for Color · Gray 매칭 (`colorgray`).

Flow (the UI drives it one image at a time, so a long job never blocks the engine):
  cgm_scan(root)            → wafer folders under a Lot/Wafer folder
  cgm_start(wafers, output) → match every color image; job plan (no pixels yet)
  cgm_read(w, r, kind)      → one source JPEG (color / gray) as base64
  cgm_put(w, r, kind, data) → one JPEG the UI produced (crop / thumbnails)
  cgm_fail(w, r, reason)    → the UI could not decode/produce that record
  cgm_finish(w)             → comparison workbook + unmatched list for one wafer
  v14 최종 목록 CSV(Defect 분석): cgm_csv(text, root) → Wafer = CSV 의 매칭 폴더(그 Defect 만),
  cgm_start 가 CSV 의 Color 만 남기고(프로그램 매칭에 없으면 CSV 의 Gray 위치), 화면이 사진 3장
  (color_view · crop_mark · frame_mark)을 더 올리면 cgm_final → 최종 목록 엑셀(HTML 5-3 과 같은 열 · 사진).

Safety: sources are only read, and only files named in the scanned wafers' own
lists. Outputs are written under one output folder the engine chose or checked
(local disk, not OneDrive, not a network share, not inside the source folder),
with names the engine makes — the UI never supplies a path to write.
"""
from __future__ import annotations

import base64
import binascii
import os
import threading
from datetime import datetime
from pathlib import Path

from . import colorgray, desktop_progress

MAX_SOURCE = 5 * 1024 * 1024    # raw bytes per source image; larger ones are listed as failures
CHUNK = 2_000_000               # read in pieces: base64 of one piece must fit the 4 MB IPC frame
MAX_OUTPUT = 2_900_000
KINDS_IN = ("color", "gray")
KINDS_OUT = ("crop", "color_thumb", "gray_thumb", "crop_thumb")
KINDS_FINAL = ("color_view", "crop_mark", "frame_mark")      # 최종 목록 엑셀 사진(CSV 로 고른 Defect 만)
MAX_FINAL_WAFERS = 1000


class DesktopColorGray:
    extra_roots: list = []      # custom output folders DesktopOpen may open

    def __init__(self, config=None):
        self.config = config
        self.root = None
        self.wafers = []
        self.job = None
        self.final = None               # v14: {매칭 폴더: [CSV 줄]} — 최종 목록 CSV 로 고른 경우
        self.final_name = ""
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
        path = Path(root.strip().strip('"').strip())
        if not os.path.isdir(colorgray.long_path(path)):
            raise ValueError("폴더를 찾을 수 없습니다. 장비 공유는 탐색기로 먼저 연결하세요.")
        self.cancel.clear()

        def progress(stage, current, scanned, found, queued):
            if stage == "scanning" and scanned % 5 == 1:
                desktop_progress.report(f"하위 폴더 검색 중 — 확인 {scanned} · Wafer {found} · 대기 {queued}  ({current.name})")
        wafers = colorgray.discover(path, progress, self.cancel)
        self.root, self.wafers, self.final = path, [str(w) for w in wafers], None
        out = dict(root=str(path), wafers=[dict(name=Path(w).name, path=w) for w in self.wafers],
                   limit=colorgray.MAX_WAFERS, default_output=str(self._default_output(path)))
        if not wafers:
            # 못 찾았을 때: 고른 폴더 바로 아래에서 무엇이 없었는지 알려 준다(Para #48)
            names = colorgray.file_names(path)
            out["diagnosis"] = dict(missing=colorgray.missing_files(path, names), files=len(names),
                                    folders=len(colorgray.child_dirs(path)), path_len=len(str(path)))
        return out

    def final_csv(self, params):
        """v14: 최종 목록 CSV(대규모 Defect 분석 5-3 저장) → Wafer = 그 CSV 의 매칭 폴더, 그 Defect 만.
        매칭폴더가 상대 경로(HTML 을 브라우저로 따로 연 경우)면 root = 그때 고른 폴더(예: 레시피 폴더)."""
        text, root, name = params.get("text"), params.get("root") or "", params.get("name") or ""
        if set(params) - {"root", "name"} != {"text"} or not isinstance(text, str) or len(text) > 50_000_000 \
                or not isinstance(root, str) or len(root) > 1024 or not isinstance(name, str):
            raise ValueError("최종 목록 CSV 를 확인하세요")
        rows = colorgray.parse_final_csv(text)
        base = Path(root.strip().strip('"')) if root.strip() else None
        if base is not None and not os.path.isdir(colorgray.long_path(base)):
            raise ValueError("고른 폴더를 찾을 수 없습니다")
        groups, missing = {}, []
        for row in rows:
            folder = colorgray.final_folder(row, base)
            if folder is None:
                missing.append(row)
                continue
            groups.setdefault(str(folder), []).append(row)
        if len(groups) > MAX_FINAL_WAFERS:
            raise ValueError(f"매칭 폴더가 너무 많습니다({len(groups)}개 > {MAX_FINAL_WAFERS})")
        self.final, self.wafers, self.final_name = groups, list(groups), Path(name).stem[:60]
        self.final_missing = missing
        self.root = base or (Path(os.path.commonpath(list(groups))) if groups else None)
        relative = any(not colorgray.is_abs_path(r.get("매칭폴더", "")) for r in missing)   # 전체 경로가 없는 줄 → 고른 폴더가 필요
        return dict(rows=len(rows), wafers=[dict(name=Path(w).name, path=w, rows=len(r)) for w, r in groups.items()],
                    missing=len(missing), missing_examples=[(r.get("매칭폴더") or r.get("매칭폴더(고른 폴더부터)") or "(빈 칸)")
                                                             for r in missing[:5]],
                    need_root=bool(missing) and base is None and relative,
                    default_output=str(self._default_output(Path("최종목록") if not self.final_name else Path(self.final_name))),
                    limit=MAX_FINAL_WAFERS)

    def _default_output(self, source: Path):
        return self._local_root() / "ColorGray매칭" / (source.name or "Lot")

    def _check_output(self, raw):
        """Local disk only: not OneDrive, not a network share, not overlapping the source
        (batchreport_store.local_root enforces exactly these for the batch results)."""
        from . import batchreport_store
        sources = [str(self.root)] + (list(self.final) if self.final else [])
        return batchreport_store.local_root(Path(raw).absolute(), sources)

    def start(self, params):
        if set(params) - {"wafers", "output"} or not isinstance(params.get("wafers"), list):
            raise ValueError("처리할 Wafer 를 확인하세요")
        if self.root is None:
            raise ValueError("먼저 폴더에서 Wafer 를 찾으세요")
        chosen = params["wafers"]
        limit = MAX_FINAL_WAFERS if self.final else colorgray.MAX_WAFERS
        if not chosen or len(chosen) > limit or any(w not in self.wafers for w in chosen):
            raise ValueError("처리할 Wafer 를 목록에서 고르세요")
        raw = params.get("output") or ""
        if not isinstance(raw, str) or len(raw) > 1024:
            raise ValueError("저장 위치를 확인하세요")
        if raw.strip():
            base = self._check_output(raw.strip())
            if str(base) not in DesktopColorGray.extra_roots:
                DesktopColorGray.extra_roots.append(str(base))
        else:
            base = self._default_output(Path(self.final_name or "최종목록") if self.final else Path(self.root))
        output = base / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cancel.clear()
        wafers, items = [], []
        for n, path in enumerate(chosen, 1):
            name = Path(path).name
            desktop_progress.report(f"[{n}/{len(chosen)}] {name} 좌표 매칭 중…")
            try:
                records, failures, total = colorgray.plan_wafer(path)
            except (OSError, KeyError, ValueError, IndexError) as exc:
                records, failures, total = [], [("(전체)", f"설정 파일을 읽지 못함: {exc}")], 0
            result = output / name
            if self.final is not None:
                records, failures = self._final_records(path, records, result, items)
            for r in records:
                r["outputs"] = {k: str(result / v) for k, v in colorgray.output_names(r["index"], r["color_file"]).items()}
                if r.get("final") is not None:
                    r["outputs"].update({k: str(result / "_final_images" / f"{r['index']:04d}_{k}.jpg") for k in KINDS_FINAL})
                r["done"] = set()
            diag = None
            if failures:
                try:
                    diag = colorgray.diagnose(path, failures, records)
                except (OSError, ValueError, KeyError, IndexError):
                    diag = None
            coord = getattr(colorgray.plan_wafer, "last_coord", None) if total else None
            if diag is not None:
                diag["coord"] = coord
            wafers.append(dict(name=name, path=path, result=result, records=records, failures=failures,
                               colors=total, finished=None, diagnosis=diag, coord=coord))
        if self.final is not None:
            for row in getattr(self, "final_missing", []):
                items.append(dict(row=row, rec=None, done=False, folder="",
                                  reason="매칭 폴더를 찾지 못함: " + (row.get("매칭폴더") or row.get("매칭폴더(고른 폴더부터)") or "(빈 칸)")))
            order = lambda it: (colorgray._num(it["row"].get("5-1 #")) or 0)   # noqa: E731
            items.sort(key=order)
        self.job = dict(output=output, wafers=wafers, final=items if self.final is not None else None)
        return self.view()

    def _final_records(self, path, records, result, items):
        """최종 목록 CSV 의 이 폴더 줄만 남긴다: 프로그램 매칭 결과에서 Color 이름이 같은 것 → 없으면 CSV 의 Gray 위치(대체)."""
        rows = self.final.get(path, [])
        by_color = {colorgray.base_name(r["color_file"]).lower(): r for r in records}
        keep, failures, used = [], [], set()
        next_index = max([r["index"] for r in records] + [0]) + 1
        for row in rows:
            key = colorgray.base_name(row.get(colorgray.FINAL_COLOR_COL, "")).lower()
            item = dict(row=row, rec=None, done=False, folder=path, reason="")
            rec = by_color.get(key) if key and key not in used else None
            if rec is not None:
                rec = dict(rec, calc="Para 프로그램")
            else:
                rec, why = colorgray.final_fallback(Path(path), row, next_index)
                if rec is not None:
                    rec["calc"] = "최종 목록 CSV 값(HTML 계산)"
                    next_index += 1
                else:
                    item["reason"] = why
                    failures.append((row.get(colorgray.FINAL_COLOR_COL, "") or "(빈 칸)", why))
            if rec is not None:
                used.add(key)
                rec["final"] = item
                item["rec"] = rec
                keep.append(rec)
            items.append(item)
        return keep, failures

    def view(self):
        job = self.job
        if not job:
            return dict(job=None)
        return dict(job=dict(
            output=str(job["output"]),
            wafers=[dict(name=w["name"], colors=w["colors"], failed=len(w["failures"]), finished=w["finished"],
                         diagnosis=w.get("diagnosis"), coord=w.get("coord"),
                         records=[dict(color=r["color_file"], gray=r["gray_file"], px=r["pixel_x"], py=r["pixel_y"],
                                       gw=colorgray.GW, gh=colorgray.GH, crop_w=r["crop_w"], crop_h=r["crop_h"],
                                       out_w=r["out_w"], out_h=r["out_h"],
                                       **({"box": [colorgray._num(r["final"]["row"].get("BoxW")) or 4,
                                                   colorgray._num(r["final"]["row"].get("BoxH")) or 4]}
                                          if r.get("final") is not None else {})) for r in w["records"]])
                    for w in job["wafers"]],
            final=None if job.get("final") is None else dict(rows=len(job["final"]),
                                                             workbook=job.get("final_workbook", ""))))

    def read(self, params):
        """One source image, in CHUNK-sized pieces (`offset` → next piece) so a file up
        to MAX_SOURCE never exceeds the IPC frame limit."""
        if set(params) - {"offset"} != {"wafer", "record", "kind"} or params.get("kind") not in KINDS_IN:
            raise ValueError("읽을 이미지를 확인하세요")
        offset = params.get("offset", 0)
        if type(offset) is not int or offset < 0:
            raise ValueError("읽을 위치를 확인하세요")
        _, rec = self._record(params)
        path = Path(rec["color_path" if params["kind"] == "color" else "gray_path"])
        size = os.stat(colorgray.long_path(path)).st_size
        if size > MAX_SOURCE:
            raise ValueError(f"이미지가 너무 큽니다({size / 1048576:.1f} MB > 5 MB): {path.name}")
        if offset > size:
            raise ValueError("읽을 위치를 확인하세요")
        with open(colorgray.long_path(path), "rb") as fh:
            fh.seek(offset)
            piece = fh.read(CHUNK)
        end = offset + len(piece)
        return dict(name=path.name, size=size, data=base64.b64encode(piece).decode("ascii"),
                    next=end if end < size else None)

    def put(self, params):
        if set(params) - {"wafer", "record", "kind", "data", "box"} or params.get("kind") not in KINDS_OUT + KINDS_FINAL:
            raise ValueError("저장할 이미지를 확인하세요")
        wafer, rec = self._record(params)
        if params["kind"] in KINDS_FINAL and rec.get("final") is None:
            raise ValueError("최종 목록 사진은 최종 목록 CSV 로 고른 Defect 만 저장합니다")
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
            if rec.get("final") is not None:
                it = rec["final"]
                it["done"] = set(KINDS_FINAL) <= rec["done"]
                it["pictures"] = {k: rec["outputs"][k] for k in KINDS_FINAL if k in rec["done"]}
                if not it["done"] and not it["reason"]:
                    it["reason"] = rec.get("error") or "사진 처리 안 됨(취소 또는 오류)"
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

    def final_finish(self, params):
        """v14: 모든 Wafer 를 마친 뒤 최종 목록 엑셀 하나(CSV 차례, HTML 5-3 과 같은 열 · 사진 3장)."""
        if params:
            raise ValueError("최종 목록 엑셀 요청을 확인하세요")
        job = self.job
        if not job or job.get("final") is None:
            raise ValueError("최종 목록 CSV 로 시작한 작업이 없습니다")
        items = job["final"]

        def progress(done, total):
            if done == 1 or done % 10 == 0 or done == total:
                desktop_progress.report(f"최종 목록 엑셀 사진 넣는 중 {done}/{total}")
        name = f"최종목록_{self.final_name}.xlsx" if self.final_name else "최종목록.xlsx"
        path = colorgray.build_final_workbook(Path(job["output"]) / name, items, progress)
        job["final_workbook"] = str(path)
        done = sum(1 for it in items if it.get("done"))
        return dict(workbook=str(path), rows=len(items), done=done, missing=len(items) - done, output=str(job["output"]))

    def reset(self, params):
        if params:
            raise ValueError("초기화 요청을 확인하세요")
        self.cancel.set()
        self.job = None
        return dict(job=None)
