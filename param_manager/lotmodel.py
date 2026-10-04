"""Lot 단위 Batch Report 모델 (헤드리스 · 파일/네트워크 접근 없음).

대전제(사용자 확정 2026-10-04): Lot 1개 = Batch Report 1장이 아니다. 이슈로 나눠 스캔·재스캔하고,
다른 호기로 옮겨 다시 돌리기도 한다. 그래서 Batch Report(=스캔 시도)를 다음 순서로 묶는다.

  시도(Batch Report 1장) → 묶음(한 번의 검사를 끝내려고 연달아 한 시도들) → Lot

규칙(모두 CLAUDE.md 'Batch Report 명칭 통일 + 재설계 방향' 절의 확정 사항):
- S/M = 파일 이름에서 본문 Job/Setup 뒤·날짜 앞 문자열(Lot 칸이 전부 LoadPort 여도 남아 있다).
- Lot 코드 = S/M 안의 첫 '단독 영문 3글자'(`BAW-0911S`→BAW, `0701 N SPT …`→SPT). 없으면 점검 스캔.
- 같은 코드라도 전체 Wafer ID(`SF14G25-A0`)의 Lot ID(앞 5자)가 다르면 다른 Lot. 1글자 차이는 판독 오차.
- 슬롯: 웨이퍼 표가 25행이면 1행=25번 … 25행=1번. 아니면 Wafer ID(`Slot 14`·`14`·`SF14G14-xx`).
- Pass 가 아니면 전부 Error(빈칸 포함). 문구가 여럿이면 첫 문구가 원인.
- 묶음: 같은 호기에서 시도 간격 12시간 이하. 다른 호기는 '호기 이동 재스캔'일 때만 이어 붙인다
  (앞 묶음에 미해결 웨이퍼가 남았고, 같은 공정 단계(Recipe(s))이며, move_gap_h 이내).
- 웨이퍼 판정: 한 번에 Pass / 재스캔 Pass(Error 뒤 다시 스캔해 Pass) / 중복 Pass(Pass 2번 이상) / Pass 없음.
- 중복 Pass 는 가장 나중 Pass 를 추천 선택, 사람이 overrides 로 바꾼다. 오류는 원문 그대로 보여 준다.

입력 record 는 batchreport_store.collect 의 것과 같다: {id, machine, source_folder?, report}.
출력은 JSON 으로 그대로 보낼 수 있는 dict/list(시각만 datetime).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from . import wph, wph_status

SAME_MACHINE_GAP_H = 12          # 같은 호기: 이 간격 이하면 같은 묶음 (사용자 확정)
MOVE_GAP_H = 48                  # 다른 호기 재스캔으로 볼 최대 간격 (사용자 제안 2일)
FULL_SLOTS = 25                  # all slot 스캔의 웨이퍼 표 행 수

CODE_RE = re.compile(r"(?<![A-Za-z])([A-Za-z]{3})(?![A-Za-z])")
FULL_ID_RE = re.compile(r"([A-Z0-9]{5})(\d{2})-[A-Z0-9]{2}")
SLOT_RE = re.compile(r"(?:slot\s*)?(\d{1,2})", re.I)
DATE_TAIL_RE = re.compile(r"_\d{2}-[A-Za-z]{3}-\d{2}_\(\d{2}\.\d{2}\.\d{2}\)_BatchReport\.html?$", re.I)
PASS_RE = re.compile(r"pass[.!]?", re.I)

# 원인 문구(첫 문구가 원인). 7개 기본 유형 + 장비에서 실제로 나오는 조치형 2개.
CAUSES = [*wph_status.TYPES,
          ("Clean Reference 오류", "Clean Reference Error."),
          ("Focus Mapping 오류", "Focus Mapping Error.")]
CHAIN_TYPES = {"작업 중단", "검사 제외"}       # 앞 오류 뒤에 따라붙는 Aborted / Skipped
EMPTY = "상태 없음"
UNKNOWN = "미분류"

# 판정(묶음 안 웨이퍼 최종 결과) — 사용자 피드백(2026-10-04)으로 '회복' 같은 해석어 대신 일어난 일을 그대로 쓴다.
OK, RECOVERED, DUPLICATE, UNRESOLVED = "한 번에 Pass", "재스캔 Pass", "중복 Pass", "Pass 없음"
# Lot 상태
LOT_DONE, LOT_RESCANNED, LOT_OPEN = "한 번에 완료", "재스캔으로 완료", "Pass하지 못한 wafer 존재"


# ---------------------------------------------------------------------------
#  문자열 규칙
# ---------------------------------------------------------------------------
def _number(raw):
    try:
        value = float(str(raw).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    return value if value == value and value >= 0 else None


def sm_of(file_name, job, setup, lot_cells=()):
    """파일 이름에서 S/M 을 꺼낸다. 형식이 다르면 웨이퍼 Lot 칸의 최빈값(LoadPort 제외)."""
    name = str(file_name or "")
    stem = DATE_TAIL_RE.sub("", name)
    prefix = f"{job}_{setup}_"
    if stem != name and job and stem.startswith(prefix) and len(stem) > len(prefix):
        return stem[len(prefix):].strip()
    real = Counter(c for c in lot_cells if c and c != "-" and not c.lower().startswith("loadport"))
    return real.most_common(1)[0][0] if real else ""


def lot_code(sm):
    """S/M 안의 첫 단독 영문 3글자(대문자). 없으면 None → 점검 스캔."""
    m = CODE_RE.search(str(sm or ""))
    return m.group(1).upper() if m else None


def is_pass(status):
    return bool(PASS_RE.fullmatch(str(status or "").strip()))


def cause_of(status):
    """(유형, 원문 문구). Pass 면 None. 문구가 여럿이면 원문에서 가장 앞에 나온 것."""
    text = wph.clean_text(status)
    if is_pass(text):
        return None
    if not text:
        return (EMPTY, "(빈 칸)")
    best = None
    for label, phrase in CAUSES:
        m = re.search(r"\b" + re.escape(phrase.rstrip(".")) + r"\b\.?", text, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), label, m.group(0))
    if best:
        return (best[1], best[2])
    return (UNKNOWN, text)


def full_id(wafer_id):
    """`SF14G25-A0` → ('SF14G', 25). 다른 형식이면 (None, None)."""
    m = FULL_ID_RE.fullmatch(str(wafer_id or "").strip())
    return (m.group(1), int(m.group(2))) if m else (None, None)


def wafer_slot(index, nrows, wafer_id):
    """슬롯 번호. 25행 표면 행 위치(1행=25번), 아니면 Wafer ID 에서. 모르면 None."""
    if nrows == FULL_SLOTS:
        return FULL_SLOTS - index
    text = str(wafer_id or "").strip()
    m = SLOT_RE.fullmatch(text)
    if m and 1 <= int(m.group(1)) <= FULL_SLOTS:
        return int(m.group(1))
    _, slot = full_id(text)
    return slot if slot and 1 <= slot <= FULL_SLOTS else None


def is_real_id(wafer_id):
    """사람이 붙인 진짜 Wafer ID 인가(`Slot N`·숫자만은 아님)."""
    text = str(wafer_id or "").strip()
    return bool(text) and not SLOT_RE.fullmatch(text)


def ids_close(a, b):
    """Lot ID 가 같은가 — 길이 같고 1글자 이하 차이(판독 오차 `SH47T`≈`SA47T`)."""
    return a == b or (len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1)


def _cluster(ids):
    """Lot ID 들을 판독 오차 허용으로 묶어 대표값(가장 많이 나온 것) 목록으로."""
    groups = []                              # [[대표, Counter]]
    for value, n in Counter(ids).most_common():
        for group in groups:
            if ids_close(group[0], value):
                group[1][value] += n
                break
        else:
            groups.append([value, Counter({value: n})])
    return [g[0] for g in groups]


def _represent(lot_id, reps):
    for rep in reps:
        if ids_close(rep, lot_id):
            return rep
    return lot_id


# ---------------------------------------------------------------------------
#  시도(Batch Report 1장)
# ---------------------------------------------------------------------------
def attempt(record):
    report = record["report"]
    meta = {wph.normalize_key(k): v for k, v in report.get("metadata", [])}
    job_setup = wph.clean_text(meta.get("jobsetup", ""))
    job, _, setup = job_setup.partition("/")
    raw_rows = report.get("wafers", [])
    lots = [wph.safe_field(w, "Lot") for w in raw_rows]
    sm = sm_of(report.get("file_name", ""), job, setup, lots)
    rows, trigger, trigger_phrase = [], None, ""
    for index, raw in enumerate(raw_rows):
        wid = wph.safe_field(raw, "Wafer ID")
        status = wph.safe_field(raw, "Pass/Fail", "Status", "State")
        cause = cause_of(status)
        kind = None
        if cause:
            # 앞에 오류가 있었으면 Aborted/Skipped 는 연쇄(원인 = 그 앞 첫 오류), 아니면 그 자체가 원인(직접).
            kind = "연쇄" if cause[0] in CHAIN_TYPES and trigger else "원인"
            if not trigger:
                trigger, trigger_phrase = cause[0], cause[1]
        good = _number(wph.safe_field(raw, "Good Dice"))
        scanned = _number(wph.safe_field(raw, "Scanned Dice"))
        bad = _number(wph.safe_field(raw, "Bad Dice"))
        if good is None and scanned is not None and bad is not None:
            good = scanned - bad
        rows.append({"order": index + 1, "slot": wafer_slot(index, len(raw_rows), wid),
                     "wafer_id": wid, "lot_id": full_id(wid)[0], "status": status,
                     "pass": cause is None, "cause": cause[0] if cause else "",
                     "phrase": cause[1] if cause else "", "kind": kind,
                     "trigger": trigger if kind == "연쇄" else "",
                     "trigger_phrase": trigger_phrase if kind == "연쇄" else "",
                     "scanned": scanned, "bad": bad, "good": good,
                     "yield": _number(wph.safe_field(raw, "Yield")),
                     "recipe": wph.safe_field(raw, "Recipe(s)", "Recipe")})
    ids = [r["lot_id"] for r in rows if r["lot_id"]]
    reps = _cluster(ids)
    step = Counter(r["recipe"] for r in rows if r["recipe"]).most_common(1)
    return {"id": record["id"], "machine": record["machine"],
            "source_folder": record.get("source_folder", ""),
            "file": report.get("file_name", ""), "job": job, "setup": setup, "job_setup": job_setup,
            "sm": sm, "code": lot_code(sm), "lot_id": reps[0] if reps else None,
            "step": step[0][0] if step else "",
            "start": wph.parse_batch_datetime(meta.get("batchstart", "")),
            "end": wph.parse_batch_datetime(meta.get("batchend", "")),
            "batch_sec": wph.hms_to_seconds(meta.get("batchtime", "")),
            "wafers_scanned": _number(meta.get("wafersscanned")),
            "rows": rows}


# ---------------------------------------------------------------------------
#  묶음 · 웨이퍼 최종 결과
# ---------------------------------------------------------------------------
def _when(a):
    return a["start"] or a["end"] or datetime.max


def _key(row, id_slots):
    if row["slot"] is not None:
        return f"S{row['slot']:02d}"
    slot = id_slots.get(row["wafer_id"])
    return f"S{slot:02d}" if slot is not None else "ID:" + row["wafer_id"]


def resolve(attempts, overrides=None, bunch_key=None):
    """묶음 안 웨이퍼별 결과. overrides = {(bunch_key, wafer_key): attempt_id} 로 사람 선택 반영."""
    overrides = overrides or {}
    id_slots = {r["wafer_id"]: r["slot"] for a in attempts for r in a["rows"]
                if r["slot"] is not None and is_real_id(r["wafer_id"])}
    cells = defaultdict(list)
    for position, a in enumerate(attempts):
        for row in a["rows"]:
            cells[_key(row, id_slots)].append((position, row))
    wafers, counts = [], Counter()
    totals = {"scanned": 0.0, "bad": 0.0, "good": 0.0, "missing": 0}
    for key in sorted(cells, key=lambda k: (not k.startswith("S"), -int(k[1:]) if k.startswith("S") else 0, k)):
        items = cells[key]
        passes = [(p, r) for p, r in items if r["pass"]]
        errors = [(p, r) for p, r in items if not r["pass"]]
        pick = passes[-1] if passes else None
        chosen = overrides.get((bunch_key, key))
        overridden = False
        if chosen is not None:
            for p, r in items:
                if attempts[p]["id"] == chosen:
                    pick, overridden = (p, r), True
                    break
        if not passes:
            verdict = UNRESOLVED
        elif len(passes) > 1:
            verdict = DUPLICATE
        else:
            verdict = RECOVERED if errors else OK
        counts[verdict] += 1
        if pick and pick[1]["pass"]:
            row = pick[1]
            if None in (row["scanned"], row["bad"], row["good"]):
                totals["missing"] += 1
            else:
                for name in ("scanned", "bad", "good"):
                    totals[name] += row[name]
        # 웨이퍼의 원인 = 직접 오류의 첫 문구. 연쇄뿐이면 그 연쇄를 일으킨 같은 Batch Report 의 첫 오류.
        direct = next((r for _, r in errors if r["kind"] == "원인"), None)
        chained = next((r for _, r in errors if r["kind"] == "연쇄"), None)
        slots = [r["slot"] for _, r in items if r["slot"] is not None]
        wafers.append({"key": key, "slot": slots[0] if slots else None,
                       "wafer_id": next((r["wafer_id"] for _, r in items if is_real_id(r["wafer_id"])), items[0][1]["wafer_id"]),
                       "cells": [{"attempt": p, "order": r["order"], "status": r["status"], "pass": r["pass"], "cause": r["cause"],
                                  "kind": r["kind"]} for p, r in items],
                       "pick": pick[0] if pick else None, "overridden": overridden,
                       "picked_status": pick[1]["status"] if pick else "",
                       "dice": [pick[1]["scanned"], pick[1]["bad"], pick[1]["good"]] if pick else None,
                       "verdict": verdict,
                       # 표시는 Batch Report 원문 그대로(간소화 금지, 사용자 지시). cause_type 은 내부 분류.
                       "cause": direct["phrase"] if direct else chained["trigger_phrase"] if chained else "",
                       "cause_type": direct["cause"] if direct else chained["trigger"] if chained else "",
                       "chain_only": bool(chained and not direct)})
    totals["yield"] = totals["good"] / totals["scanned"] * 100 if totals["scanned"] else None
    return wafers, dict(counts), totals


def _step(attempts):
    """묶음의 공정 단계(Recipe(s)) — Pass 웨이퍼가 많은 시도 기준(잘못 고른 레시피 재시도는 Pass 가 없다)."""
    weight = Counter()
    for a in attempts:
        if a["step"]:
            weight[a["step"]] += 1 + sum(r["pass"] for r in a["rows"]) * 100
    return weight.most_common(1)[0][0] if weight else ""


def _bunch(attempts, overrides, moved):
    key = attempts[0]["id"]
    wafers, counts, totals = resolve(attempts, overrides, key)
    return {"key": key, "attempts": attempts,
            "machines": list(dict.fromkeys(a["machine"] for a in attempts)),
            "moved": moved, "step": _step(attempts),
            "start": min((a["start"] for a in attempts if a["start"]), default=None),
            "end": max((a["end"] for a in attempts if a["end"]), default=None),
            "batch_sec": sum(a["batch_sec"] or 0 for a in attempts),
            "wafers": wafers, "counts": counts, "totals": totals,
            "unresolved": counts.get(UNRESOLVED, 0), "duplicates": counts.get(DUPLICATE, 0)}


def _split_bunches(attempts, same_gap_h, move_gap_h):
    """시간순 시도들을 묶음으로. [(시도 목록, 호기 이동 여부)]"""
    same, move = timedelta(hours=same_gap_h), timedelta(hours=move_gap_h)
    out = []
    for a in sorted(attempts, key=lambda a: (_when(a), a["id"])):
        if out:
            group, moved = out[-1]
            last = group[-1]
            end = max((g["end"] or g["start"] for g in group if g["end"] or g["start"]), default=None)
            gap = (a["start"] - end) if (a["start"] and end) else None
            if a["machine"] == last["machine"]:
                if gap is not None and gap <= same:
                    group.append(a)
                    continue
            elif gap is not None and gap <= move:
                # 다른 호기: 앞 묶음에 미해결이 남았고 같은 공정 단계일 때만 '호기 이동 재스캔'.
                step = _step(group)
                same_step = not step or not a["step"] or step == a["step"]
                if same_step and resolve(group)[1].get(UNRESOLVED, 0):
                    group.append(a)
                    out[-1] = (group, True)
                    continue
        out.append(([a], False))
    return out


def _split_by_lot_id(group):
    """한 묶음 안에 Lot ID 가 둘 이상이면 나눈다. ID 없는 시도는 시간상 가장 가까운 쪽으로."""
    reps = _cluster([a["lot_id"] for a in group if a["lot_id"]])
    if len(reps) <= 1:
        return [(reps[0] if reps else None, group)]
    parts = {rep: [] for rep in reps}
    for a in group:
        if a["lot_id"]:
            parts[_represent(a["lot_id"], reps)].append(a)
    for a in group:
        if not a["lot_id"]:
            nearest = min(reps, key=lambda rep: min(abs((_when(a) - _when(b)).total_seconds()) for b in parts[rep]))
            parts[nearest].append(a)
    return [(rep, sorted(items, key=lambda a: (_when(a), a["id"]))) for rep, items in parts.items()]


# ---------------------------------------------------------------------------
#  Lot
# ---------------------------------------------------------------------------
def build(records, overrides=None, same_gap_h=SAME_MACHINE_GAP_H, move_gap_h=MOVE_GAP_H):
    """records → {"lots": [...], "excluded": [...]}.

    Lot = (코드, Lot ID). Lot ID 가 하나뿐인 코드는 ID 없는 묶음(WBG 숫자 ID)도 그 Lot 에 넣고,
    둘 이상이면 ID 없는 묶음은 `lot_id=None`(Lot ID 미확인) Lot 으로 따로 둔다.
    """
    overrides = overrides or {}
    attempts = [attempt(r) for r in records]
    excluded = [a for a in attempts if not a["code"]]
    bycode = defaultdict(list)
    for a in attempts:
        if a["code"]:
            bycode[a["code"]].append(a)
    lots = []
    for code, items in bycode.items():
        reps = _cluster([a["lot_id"] for a in items if a["lot_id"]])
        grouped = defaultdict(list)                       # lot_id → [(묶음 시도들, moved)]
        for group, moved in _split_bunches(items, same_gap_h, move_gap_h):
            for rep, part in _split_by_lot_id(group):
                rep = _represent(rep, reps) if rep else (reps[0] if len(reps) == 1 else None)
                grouped[rep].append((part, moved))
        for rep, parts in grouped.items():
            bunches = [_bunch(part, overrides, moved) for part, moved in parts]
            bunches.sort(key=lambda b: (b["start"] or datetime.max, b["key"]))
            all_attempts = [a for b in bunches for a in b["attempts"]]
            unresolved = sum(b["unresolved"] for b in bunches)
            recovered = sum(b["counts"].get(RECOVERED, 0) for b in bunches)
            lots.append({"key": f"{code}:{rep or '?'}", "code": code, "lot_id": rep,
                         "label": f"{code} · {rep}" if rep and len(reps) > 1 else
                                  (f"{code} · Lot ID 미확인" if not rep and len(reps) > 1 else code),
                         "sms": sorted({a["sm"] for a in all_attempts}),
                         "jobs": sorted({a["job"] for a in all_attempts}),
                         "machines": list(dict.fromkeys(a["machine"] for a in all_attempts)),
                         "attempts": len(all_attempts), "bunches": bunches,
                         "start": bunches[0]["start"], "end": max((b["end"] for b in bunches if b["end"]), default=None),
                         "unresolved": unresolved, "recovered": recovered,
                         "duplicates": sum(b["duplicates"] for b in bunches),
                         "moved": any(b["moved"] for b in bunches),
                         "state": LOT_OPEN if unresolved else LOT_RESCANNED if recovered else LOT_DONE})
    lots.sort(key=lambda lot: (lot["start"] or datetime.max, lot["key"]))
    return {"lots": lots, "excluded": excluded}
