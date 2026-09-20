"""Offline batch analysis. Pure calculations; no source or network writes.

Raw reports are retained by the store; models are rebuilt to apply rule changes.
Numbers marked as proxies must never be used to control equipment automatically.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean, median

from . import wph, wph_status

METRICS = {
    "M01": "WPH (유효 Lot만)", "M02": "스캔 가동률 · 유휴 gap",
    "M03": "오류 유형별 빈도", "M04": "오류 성격",
    "M05": "Aborted 직접 · 연쇄 추정", "M06": "재시작 간격",
    "M07": "복구 baseline", "M08": "Recipe별 정상 Bad Dice 분포",
    "M09": "Yield / Bad Dice 이상 후보", "M10": "완주율",
    "M11": "미분류 상태",
}
RULE_VERSION = 1
PREVENTIVE = {"맵 Import 오류", "2D Scan 오류", "Wafer ID 판독 오류", "검사 대상 없음"}
ACTION = {"Alignment 오류", "Clean Reference 오류", "Focus Mapping 오류"}
EXTRA = {"Clean Reference Error": "Clean Reference 오류",
         "Focus Mapping Error": "Focus Mapping 오류"}


def number(raw):
    try:
        value = float(str(raw).replace(",", "").replace("%", "").strip())
        return value if math.isfinite(value) and value >= 0 else None
    except (TypeError, ValueError):
        return None


def timestamp(raw):
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return wph.parse_batch_datetime(str(raw or ""))


def percentile(values, p):
    """Linear interpolation, matching Excel PERCENTILE.INC."""
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def classify(raw):
    result = []
    for category, text in wph_status.classify(raw):
        if category == "기타 상태":
            for pattern, label in EXTRA.items():
                if re.search(re.escape(pattern), text, re.I):
                    result.append((label, pattern, "조치형"))
                    text = re.sub(re.escape(pattern), "", text, flags=re.I)
            text = text.strip(" .;,+/|\t\n")
            if not text:
                continue
            category = "Unclassified"
        character = ("예방형" if category in PREVENTIVE else
                     "조치형" if category in ACTION else
                     "중단" if category == "작업 중단" else
                     "결과형" if category == "검사 제외" else "미확인")
        result.append((category, text, character))
    return result


def model(report, machine, identity):
    meta = {wph.normalize_key(k): v for k, v in report.get("metadata", [])}
    row = wph.extract_row(report)
    start, end = timestamp(meta.get("batchstart")), timestamp(meta.get("batchend"))
    batch = dict(row, id=identity, machine=machine, start=start, end=end,
                 job_setup=meta.get("jobsetup", ""), user=meta.get("user", ""),
                 date=meta.get("date", ""), wafer_rows=len(report.get("wafers", [])),
                 scanned_dice=number(meta.get("scanneddice")),
                 good_dice=number(meta.get("gooddice")), bad_dice=number(meta.get("baddice")),
                 yield_pct=number(meta.get("yield")))
    wafers, triggered = [], False
    for order, raw in enumerate(report.get("wafers", []), 1):
        status = wph.safe_field(raw, "Pass/Fail", "Status", "State")
        states = classify(status)
        # First non-skipped issue, including first Aborted, starts a chain.
        abort = any(s[0] == "작업 중단" for s in states)
        abort_kind = ("연쇄 추정" if triggered else "직접 추정") if abort else ""
        wafers.append({"batch_id": identity, "machine": machine,
                       "source_file": row["source_file"], "order": order,
                       "no": wph.safe_field(raw, "No", "Slot"),
                       "lot": wph.safe_field(raw, "Lot"),
                       "wafer_id": wph.safe_field(raw, "Wafer ID"),
                       "faults": wph.safe_field(raw, "Faults"),
                       "recipe": wph.safe_field(raw, "Recipe(s)", "Recipe"),
                       "bad_dice": number(wph.safe_field(raw, "Bad Dice")),
                       "good_dice": number(wph.safe_field(raw, "Good Dice")),
                       "scanned_dice": number(wph.safe_field(raw, "Scanned Dice")),
                       "yield_pct": number(wph.safe_field(raw, "Yield")),
                       "status": status, "states": states, "abort_kind": abort_kind,
                       "pass": bool(re.fullmatch(r"pass[.!]?", status.strip(), re.I)),
                       "time": end, "raw": raw})
        triggered |= any(s[0] not in {"검사 제외", "상태 확인 불가"} for s in states)
    batch["has_error"] = any(s[0] != "상태 확인 불가" for wafer in wafers for s in wafer["states"])
    batch["types"] = sorted({s[0] for wafer in wafers for s in wafer["states"]})
    count, denominator = batch["wafers"], len(wafers)
    batch["completion"] = count / denominator * 100 if denominator and count is not None and 0 <= count <= denominator else None
    return batch, wafers


def bucket(dt, unit):
    begin = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "주":
        begin -= timedelta(days=dt.weekday())
        return begin, begin + timedelta(days=7)
    if unit == "월":
        begin = begin.replace(day=1)
        end = (begin.replace(day=28) + timedelta(days=4)).replace(day=1)
        return begin, end
    return begin, begin + timedelta(days=1)


def compute(records, selected=None, valid_wafers=25, min_baseline=20, yield_drop=5.0, now=None):
    """Return common tables consumed by HTML, Excel and GUI.

    Baseline is descriptive, not a certified hold limit. M09 compares each wafer
    against earlier Pass wafers of the same Recipe(s), never future data.
    """
    selected = list(METRICS) if selected is None else list(selected)
    if not selected or any(key not in METRICS for key in selected):
        raise ValueError("분석 지표를 하나 이상 선택하세요")
    if valid_wafers < 1 or min_baseline < 2 or not math.isfinite(yield_drop) or yield_drop < 0:
        raise ValueError("매수/최소 표본/수율 하락 기준을 확인하세요")
    now = now or datetime.now()
    batches, wafers = [], []
    for record in records:
        batch, rows = model(record["report"], record["machine"], record["id"])
        batch['source_folder'] = record.get('source_folder', '')
        for wafer in rows:
            wafer['source_folder'] = batch['source_folder']
        batches.append(batch)
        wafers.extend(rows)
    tables = []

    def table(key, title, headers, rows):
        if key in selected:
            tables.append({"key": key, "title": title, "headers": headers, "rows": list(rows)})

    eligible = [b for b in batches if b["wafers"] == valid_wafers and (b["batch_sec"] or 0) > 0]
    groups = defaultdict(list)
    for b in eligible:
        for key in [("전체", "전체"), (b["machine"], "전체"), (b["machine"], b["recipe"])]:
            groups[key].append(b)
    table("M01", "WPH", ["호기", "Job Recipe", "유효 Batch 수", "합산 WPH (wafer/h)", "평균 WPH (wafer/h)"],
          [(*k, len(v), sum(b["wafers"] for b in v) * 3600 / sum(b["batch_sec"] for b in v),
            mean(b["wafers"] * 3600 / b["batch_sec"] for b in v)) for k, v in sorted(groups.items())])
    table("M01", "시간순 Actual WPH", ["Batch End", "호기", "Report", "Actual WPH (wafer/h)"],
          [(b["end"], b["machine"], b["source_file"], b["wafers"] * 3600 / b["batch_sec"])
           for b in sorted(eligible, key=lambda b: (b["end"] or datetime.max, b["id"]))])
    for unit in ("일", "주", "월"):
        grouped = defaultdict(list)
        for b in batches:
            if b["start"] and b["end"] and b["end"] >= b["start"] and b["batch_sec"] is not None:
                grouped[(b["machine"], bucket(b["start"], unit)[0])].append(b)
        rows = []
        for (machine, begin), items in sorted(grouped.items()):
            _, finish = bucket(begin, unit)
            partial = unit != "일" and begin <= now < finish
            last = max(b["end"] for b in items)
            window_end = min(finish, last, now) if partial else finish
            window = (window_end - begin).total_seconds()
            active = (last - min(b["start"] for b in items)).total_seconds()
            scan = sum(b["batch_sec"] for b in items)
            ratio = scan / window * 100 if window > 0 else None
            rows.append((machine, begin, len(items), scan / 3600, window / 3600,
                         ratio, scan / active * 100 if active > 0 else None,
                         (window - scan) / 3600, "진행 중" if partial else "완료 기간",
                         "100% 초과/중복·기간 걸침 확인" if ratio and ratio > 100 else "선택 자료 기준"))
        table("M02", f"스캔 가동률 · {unit}", ["호기", "기간 시작", "Batch 수", "스캔 (h)", "관측창 (h)",
              "달력 가동률 (%)", "첫~끝 밀도 (%)", "미관측·유휴 추정 (h)", "기간 상태", "자료 범위"], rows)
    bymachine, byjob = defaultdict(list), defaultdict(list)
    for b in batches:
        if b["start"]:
            bymachine[b["machine"]].append(b)
            if b["job_setup"]:
                byjob[(b["machine"], b["job_setup"])].append(b)
    gaps = []
    for machine, items in bymachine.items():
        previous = None
        for b in sorted(items, key=lambda b: (b["start"], b["id"])):
            if previous:
                gap = (b["start"] - previous["end"]).total_seconds() / 60
                gaps.append((machine, previous["source_file"], b["source_file"], b["start"], gap,
                             "겹침" if gap < 0 else "비스캔 간격 (원인 미상)"))
            if b["end"] and (previous is None or b["end"] > previous["end"]):
                previous = b
    table("M02", "배치 간 gap", ["호기", "이전 Report", "다음 Report", "다음 시작", "간격 (분)", "구분"],
          sorted(gaps, key=lambda r: r[4], reverse=True))
    batchmap = {b["id"]: b for b in batches}
    frequency, chars, detail = {}, {}, []
    for wafer in wafers:
        b = batchmap[wafer["batch_id"]]
        for category, original, character in wafer["states"]:
            for scope, machine, recipe in [("전체", "전체", "전체"), ("호기", b["machine"], "전체"),
                                            ("호기×Recipe", b["machine"], b["recipe"])]:
                key = (scope, machine, recipe, category, original)
                item = frequency.setdefault(key, [0, set()])
                item[0] += 1
                item[1].add(b["id"])
            item = chars.setdefault(character, [0, set()])
            item[0] += 1
            item[1].add(b["id"])
            detail.append((b["machine"], b["source_file"], wafer["order"], wafer["wafer_id"], category,
                           original, character, wafer["status"], wafer["abort_kind"]))
    table("M03", "유형별 빈도", ["범위", "호기", "Job Recipe", "유형", "분류 원문", "Wafer 발생 (건)", "Report 수 (건)"],
          [(*k, v[0], len(v[1])) for k, v in sorted(frequency.items())])
    table("M03", "상태 상세", ["호기", "Report", "원본 순서", "Wafer ID", "유형", "분류 원문", "성격", "상태 원문", "Aborted 추정"], detail)
    table("M04", "오류 성격", ["성격", "Wafer 발생 (건)", "Report 수 (건)"],
          [(k, v[0], len(v[1])) for k, v in sorted(chars.items())])
    aborts = Counter(w["abort_kind"] for w in wafers if w["abort_kind"])
    table("M05", "Aborted 보정", ["구분", "Wafer 수 (건)"],
          [("원본 Aborted", sum(aborts.values())), ("직접 추정", aborts["직접 추정"]), ("연쇄 추정", aborts["연쇄 추정"])])
    table("M05", "Aborted 근거", ["호기", "Report", "원본 순서", "Wafer ID", "추정"],
          [(w["machine"], w["source_file"], w["order"], w["wafer_id"], w["abort_kind"]) for w in wafers if w["abort_kind"]])
    nextbatch = {}
    for items in byjob.values():
        items.sort(key=lambda b: (b["start"], b["id"]))
        for current, following in zip(items, items[1:]):
            nextbatch[current["id"]] = following
    restarts, validgaps = [], []
    for b in batches:
        if not b["has_error"]:
            continue
        following = nextbatch.get(b["id"])
        gap, reason = None, ""
        if not b["job_setup"]:
            reason = "Job/Setup 누락"
        elif not b["start"] or not b["end"] or b["end"] < b["start"]:
            reason = "시각 누락/역전"
        elif not following:
            reason = "같은 Job/Setup 다음 배치 없음"
        else:
            gap = (following["start"] - b["end"]).total_seconds() / 60
            reason = "유효" if 0 <= gap <= 1440 else "겹침" if gap < 0 else "24h 초과"
            if reason == "유효":
                validgaps.append(gap)
        restarts.append((b["machine"], b["job_setup"], b["source_file"], ", ".join(b["types"]),
                         following["source_file"] if following else "", gap, reason))
    table("M06", "재시작 간격", ["호기", "Job/Setup", "이슈 Report", "포함 유형", "다음 Report", "간격 (분)", "판정"], restarts)
    by_type = defaultdict(list)
    for item in restarts:
        if item[-1] == '유효':
            for category in item[3].split(', '):
                by_type[category].append(item[-2])
    table("M06", "유형별 재시작 간격 (유형 중복 허용)", ["유형", "유효 Batch 수", "평균 (분)", "중앙 (분)", "P95 (분)", "최대 (분)"],
          [(k, len(v), mean(v), median(v), percentile(v, .95), max(v)) for k, v in sorted(by_type.items())])
    table("M07", "복구 baseline (재시작 간격 proxy)", ["유효 건수", "제외 건수", "평균 (분)", "중앙 (분)", "최대 (분)"],
          [(len(validgaps), len(restarts) - len(validgaps), mean(validgaps) if validgaps else None,
            median(validgaps) if validgaps else None, max(validgaps) if validgaps else None)])
    normal = defaultdict(list)
    for w in wafers:
        if w["pass"] and w["recipe"] and w["bad_dice"] is not None:
            normal[w["recipe"]].append(w["bad_dice"])
    table("M08", "Recipe별 정상 Bad Dice", ["Wafer Recipe(s)", "표본 수", "평균", "중앙", "P95", "최대"],
          [(k, len(v), mean(v), median(v), percentile(v, .95), max(v)) for k, v in sorted(normal.items())])
    # Batch-based evaluation prevents same-report wafers leaking into baseline.
    history_bad, history_yield, bybatch = defaultdict(list), defaultdict(list), defaultdict(list)
    for w in wafers:
        bybatch[w["batch_id"]].append(w)
    anomalies = []
    ordered_batches = sorted(batches, key=lambda b: (b["end"] or datetime.max, b["id"])) if 'M09' in selected else []
    pending, previous_time = [], None
    limits = {}
    for b in ordered_batches:
        if not b["end"]:
            continue
        # Batches with identical end time cannot supply earlier evidence to each other.
        if b['end'] != previous_time:
            for w in pending:
                if w["bad_dice"] is not None:
                    history_bad[w["recipe"]].append(w["bad_dice"])
                if w["yield_pct"] is not None and w["yield_pct"] <= 100:
                    history_yield[w["recipe"]].append(w["yield_pct"])
            pending, limits, previous_time = [], {}, b['end']
        for w in bybatch[b["id"]]:
            recipe = w["recipe"]
            if not recipe:
                continue
            if recipe not in limits:
                bad, yields = history_bad[recipe], history_yield[recipe]
                limits[recipe] = (percentile(bad, .95) if len(bad) >= min_baseline else None,
                                  median(yields) - yield_drop if len(yields) >= min_baseline else None)
            p95, floor = limits[recipe]
            reasons = []
            if p95 is not None and w["bad_dice"] is not None and w["bad_dice"] > p95:
                reasons.append("Bad Dice > 과거 정상 P95")
            if floor is not None and w["yield_pct"] is not None and w["yield_pct"] < floor:
                reasons.append("Yield < 과거 정상 중앙 - 기준 pp")
            if reasons:
                anomalies.append((b["end"], b["machine"], b["source_file"], recipe, w["wafer_id"],
                                  w["bad_dice"], p95, w["yield_pct"], floor, " / ".join(reasons)))
        for w in bybatch[b["id"]]:
            if w["pass"] and w["recipe"]:
                pending.append(w)
    table("M09", "품질 이상 후보 (자동 Hold 아님)", ["Batch End", "호기", "Report", "Wafer Recipe(s)", "Wafer ID", "Bad Dice", "과거 P95", "Yield (%)", "Yield 하한 (%)", "후보 근거"], anomalies)
    completion = Counter("확인 불가" if b["completion"] is None else "완주" if b["completion"] == 100 else "미스캔" if b["completion"] == 0 else "부분" for b in batches)
    table("M10", "완주율 요약", ["구분", "Batch 수"], sorted(completion.items()))
    table("M10", "완주율 상세", ["호기", "Report", "스캔 매수", "Wafer 행 수", "완주율 (%)"],
          [(b["machine"], b["source_file"], b["wafers"], b["wafer_rows"], b["completion"]) for b in batches])
    table("M11", "미분류 · 누락 상태", ["호기", "Report", "원본 순서", "Wafer ID", "유형", "분류 원문", "성격", "상태 원문", "Aborted 추정"],
          [r for r in detail if r[4] in {"Unclassified", "상태 확인 불가"}])
    return {"tables": tables, "batches": batches, "wafers": wafers, "selected": selected,
            "summary": {"Batch 수": len(batches), "Wafer 행 수": len(wafers),
                        "Pass Wafer 수": sum(w["pass"] for w in wafers),
                        "시각 누락/역전 Batch 수": sum(not b['start'] or not b['end'] or b['end'] < b['start'] for b in batches),
                        "Wafer Recipe 누락 행 수": sum(not w['recipe'] for w in wafers),
                        "이슈 Batch 수": sum(b["has_error"] for b in batches),
                        "최근 24h Batch 수": sum(bool(b["end"] and now - timedelta(days=1) <= b["end"] <= now) for b in batches)},
            "settings": {"유효 Lot 매수 (WPH 전용)": valid_wafers, "이상 후보 최소 과거 정상 표본": min_baseline,
                         "Yield 하락 기준 (percentage points)": yield_drop, "분류 규칙 버전": RULE_VERSION},
            "created": now}
