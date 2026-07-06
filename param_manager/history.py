"""파라미터 이력 확인(AOI 스펙 1.1.1.2) — 헤드리스 로직.

저장된 취합/양식 엑셀 2개(예: 이전 버전 vs 최신 버전)를 비교해 무엇이 바뀌었는지
알아내고, 달라진 부분을 **엑셀(변경내역)** 으로 만든다. 각 변경 행에는 사람이
채울 **비고(메모)** 열을 둔다(특이사항 기록).

매칭 키 = (PI, Recipe(변형), norm Zone, norm Alg, norm Parameter) — refresh/collate 와 동일.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from . import engine


def norm_key(name: str) -> str:
    """매칭용 정규화 — 한글 이름도 보존(rtp_parser.norm_key 는 한글을 버려서
    사람이 붙인 한글 파라미터명이 뭉개짐). 대소문자/공백/기호만 무시."""
    return re.sub(r"[^0-9a-z가-힣µ]", "", str(name).lower())

DIFF_SHEET = "변경내역"
DIFF_HEADERS = ["PI", "Recipe", "Zone", "Alg", "Parameter", "호기",
                "이전 값", "새 값", "구분", "비고(메모)"]


@dataclass
class Change:
    pi: str
    recipe: str
    zone: str
    alg: str
    param: str
    machine: str
    old: str
    new: str
    kind: str                # 값변경 / 추가 / 삭제


@dataclass
class HistoryDiff:
    changes: list[Change] = field(default_factory=list)
    added_rows: list[dict] = field(default_factory=list)     # 새 파일에만 있는 파라미터
    removed_rows: list[dict] = field(default_factory=list)   # 이전 파일에만 있는 파라미터
    machines: list[str] = field(default_factory=list)


def _row_key(pr) -> tuple:
    return (engine._s(pr.get("PI")).strip().lower(),
            engine._s(pr.get("Recipe")).strip().lower(),
            norm_key(pr.get("Zone")), norm_key(pr.get("Alg")),
            norm_key(pr.get("Parameter")))


def _load(path):
    repo = engine.ParamRepository(path)
    repo.load()
    return repo


def _meta(pr) -> dict:
    return {"PI": engine._s(pr.get("PI")), "Recipe": engine._s(pr.get("Recipe")),
            "Zone": engine._s(pr.get("Zone")), "Alg": engine._s(pr.get("Alg")),
            "Parameter": engine._s(pr.get("Parameter"))}


def diff_files(old_path: str, new_path: str) -> HistoryDiff:
    """이전(old) → 최신(new) 취합 엑셀 비교."""
    old, new = _load(old_path), _load(new_path)
    machines = list(dict.fromkeys(list(old.aoi_units) + list(new.aoi_units)))
    diff = HistoryDiff(machines=machines)

    old_idx = {_row_key(pr): pr for pr in old.rows}
    new_idx = {_row_key(pr): pr for pr in new.rows}

    for k, npr in new_idx.items():
        opr = old_idx.get(k)
        if opr is None:
            diff.added_rows.append(_meta(npr))
            continue
        for m in machines:
            ov, nv = engine._s(opr.get(m)), engine._s(npr.get(m))
            if ov == nv:
                continue
            if ov == "" and nv != "":
                kind = "추가"
            elif ov != "" and nv == "":
                kind = "삭제"
            else:
                kind = "값변경"
            meta = _meta(npr)
            diff.changes.append(Change(
                pi=meta["PI"], recipe=meta["Recipe"], zone=meta["Zone"],
                alg=meta["Alg"], param=meta["Parameter"], machine=m,
                old=ov, new=nv, kind=kind))
    for k, opr in old_idx.items():
        if k not in new_idx:
            diff.removed_rows.append(_meta(opr))
    return diff


def write_diff_excel(diff: HistoryDiff, dest_xlsx: str,
                     old_label: str = "", new_label: str = "",
                     memos: dict | None = None) -> str:
    """변경내역 엑셀 생성. memos: {(pi,recipe,zone,alg,param,machine): 메모} 선택.
    반환: dest_xlsx."""
    memos = memos or {}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = DIFF_SHEET
    ws.append(DIFF_HEADERS)
    for c in diff.changes:
        mkey = (c.pi, c.recipe, c.zone, c.alg, c.param, c.machine)
        ws.append([c.pi, c.recipe, c.zone, c.alg, c.param, c.machine,
                   c.old, c.new, c.kind, engine._s(memos.get(mkey, ""))])

    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    white = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = hdr_fill
        cell.font = white
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    for col, w in zip("ABCDEFGHIJ", (8, 12, 18, 16, 26, 10, 16, 16, 10, 40)):
        ws.column_dimensions[col].width = w
    # 구분별 색
    fills = {"값변경": "FFF2CC", "추가": "D9EAD3", "삭제": "F4CCCC"}
    for r in range(2, ws.max_row + 1):
        kind = ws.cell(r, 9).value
        if kind in fills:
            f = PatternFill("solid", fgColor=fills[kind])
            for c in ws[r]:
                c.fill = f

    # 추가/삭제된 파라미터 행 요약 시트
    sm = wb.create_sheet("행 추가·삭제")
    sm.append(["구분", "PI", "Recipe", "Zone", "Alg", "Parameter"])
    for r in diff.added_rows:
        sm.append(["추가", r["PI"], r["Recipe"], r["Zone"], r["Alg"], r["Parameter"]])
    for r in diff.removed_rows:
        sm.append(["삭제", r["PI"], r["Recipe"], r["Zone"], r["Alg"], r["Parameter"]])
    for col, w in zip("ABCDEF", (8, 8, 12, 18, 16, 26)):
        sm.column_dimensions[col].width = w

    info = wb.create_sheet("정보", 0)
    info.append(["항목", "값"])
    info.append(["이전(old)", old_label])
    info.append(["최신(new)", new_label])
    info.append(["값 변경 셀", len(diff.changes)])
    info.append(["행 추가", len(diff.added_rows)])
    info.append(["행 삭제", len(diff.removed_rows)])
    info.append(["안내", "'변경내역' 시트의 '비고(메모)' 열에 특이사항을 적어두세요."])
    info.column_dimensions["A"].width = 14
    info.column_dimensions["B"].width = 70
    wb.save(dest_xlsx)
    return dest_xlsx
