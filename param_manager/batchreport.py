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
# Character → the error types (categories) that map to it, for the report legend.
CHAR_MEMBERS = {"예방형": sorted(PREVENTIVE), "조치형": sorted(ACTION),
                "중단": ["작업 중단"], "결과형": ["검사 제외"],
                "미확인": ["기타/미분류 상태", "상태 확인 불가"]}


def is_lot_placeholder(value):
    """A wafer 'Lot' cell that is not a real lot id (unread id → 'LoadPort A' etc.)."""
    v = str(value or "").strip()
    return not v or v == "-" or v.lower().startswith("loadport")


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
    # Lot = 같은 카세트 스캔 단위. batch report 에는 Lot 메타가 없어 wafer 표의 Lot 열
    # (LoadPort/미판독 제외) 중 최빈값을 그 리포트의 lot 으로 본다. 중단·재스캔되면
    # 같은 (Job/Setup, Lot) 이 여러 리포트로 나뉜다 → lot_key 로 묶어 지표를 lot 기준화.
    real = Counter(w["lot"] for w in wafers if not is_lot_placeholder(w["lot"]))
    batch["lot"] = real.most_common(1)[0][0] if real else "(미상)"
    batch["lot_key"] = (batch["job_setup"], batch["lot"])
    for wafer in wafers:
        wafer["job_setup"] = batch["job_setup"]
        wafer["lot"] = batch["lot"]
        wafer["lot_key"] = batch["lot_key"]
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
    # 전체 관측 기간을 일/주/월 버킷으로 쪼개 버킷마다 가동률을 낸다. 자정(버킷 경계)을
    # 넘긴 배치는 시작일에 통째로 넣지 않고 **각 버킷에 걸친 시간만큼만** 배분한다
    # (예전엔 늦게 시작한 긴 배치가 시작일에 다 잡혀 하루 가동률이 139% 처럼 나왔다).
    for unit in ("일", "주", "월"):
        scan = defaultdict(float)    # (호기, 버킷시작) → 스캔 초 (버킷별 배분)
        started = defaultdict(int)   # 그 버킷에서 시작한 배치 수
        for b in batches:
            if not (b["start"] and b["end"] and b["end"] >= b["start"] and b["batch_sec"] is not None):
                continue
            duration = (b["end"] - b["start"]).total_seconds()
            started[(b["machine"], bucket(b["start"], unit)[0])] += 1
            cur = bucket(b["start"], unit)[0]
            while cur <= b["end"]:
                cbeg, cend = bucket(cur, unit)
                overlap = (min(b["end"], cend) - max(b["start"], cbeg)).total_seconds()
                if overlap > 0:
                    scan[(b["machine"], cbeg)] += b["batch_sec"] * overlap / duration if duration > 0 else b["batch_sec"]
                cur = cend
        rows = []
        for machine, begin in sorted(set(scan) | set(started)):
            _, finish = bucket(begin, unit)
            partial = begin <= now < finish
            window = ((min(finish, now) if partial else finish) - begin).total_seconds()
            sec = scan.get((machine, begin), 0.0)
            ratio = sec / window * 100 if window > 0 else None
            state = "진행 중" if partial else "완료"
            if ratio and ratio > 100:
                state = ("진행 중" if partial else "완료") + " · 100% 초과(스캔시간>기간, 원문 확인)"
            rows.append((machine, begin, started.get((machine, begin), 0), sec / 3600,
                         window / 3600, ratio, (window - sec) / 3600, state))
        table("M02", f"스캔 가동률 · {unit}",
              ["호기", "기간", "Batch 수", "스캔 시간 (h)", "기간 길이 (h)", "가동률 (%)", "비스캔 시간 (h)", "기간 상태"], rows)
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
                item = frequency.setdefault(key, [0, set(), set()])
                item[0] += 1
                item[1].add(b["id"])
                item[2].add(b["lot_key"])
            item = chars.setdefault(character, [0, set(), set()])
            item[0] += 1
            item[1].add(b["id"])
            item[2].add(b["lot_key"])
            detail.append((b["machine"], b["source_file"], b["lot"], wafer["order"], wafer["wafer_id"], category,
                           original, character, wafer["status"], wafer["abort_kind"]))
    # Lot 수 = 그 유형/성격이 나타난 서로 다른 (Job/Setup, Lot) 개수(리포트 재스캔 중복 제외).
    table("M03", "유형별 빈도", ["범위", "호기", "Job Recipe", "유형", "분류 원문", "Wafer 발생 (건)", "Report 수 (건)", "Lot 수 (건)"],
          [(*k, v[0], len(v[1]), len(v[2])) for k, v in sorted(frequency.items())])
    table("M03", "상태 상세", ["호기", "Report", "Lot", "원본 순서", "Wafer ID", "유형", "분류 원문", "성격", "상태 원문", "Aborted 추정"], detail)
    table("M04", "Error 성격 분류", ["성격", "Wafer 발생 (건)", "Report 수 (건)", "Lot 수 (건)"],
          [(k, v[0], len(v[1]), len(v[2])) for k, v in sorted(chars.items())])
    aborts = Counter(w["abort_kind"] for w in wafers if w["abort_kind"])
    abort_lots = {kind: {w["lot_key"] for w in wafers if w["abort_kind"] == kind} for kind in ("직접 추정", "연쇄 추정")}
    all_abort_lots = abort_lots["직접 추정"] | abort_lots["연쇄 추정"]
    table("M05", "Aborted 보정", ["구분", "Wafer 수 (건)", "Lot 수 (건)"],
          [("원본 Aborted", sum(aborts.values()), len(all_abort_lots)),
           ("직접 추정", aborts["직접 추정"], len(abort_lots["직접 추정"])),
           ("연쇄 추정", aborts["연쇄 추정"], len(abort_lots["연쇄 추정"]))])
    table("M05", "Aborted 근거", ["호기", "Report", "Lot", "원본 순서", "Wafer ID", "추정"],
          [(w["machine"], w["source_file"], w["lot"], w["order"], w["wafer_id"], w["abort_kind"]) for w in wafers if w["abort_kind"]])
    # 재시작 간격 = **같은 lot** 의 연속 리포트 간격(재스캔 지연). 한 lot 이 중단→재스캔되면
    # 앞 리포트 끝 → 다음 리포트 시작까지 걸린 시간. lot 이 1장뿐이면 재스캔 없음.
    nextinlot = {}
    lotseq = defaultdict(list)
    for b in batches:
        if b["start"]:
            lotseq[b["lot_key"]].append(b)
    for items in lotseq.values():
        items.sort(key=lambda b: (b["start"], b["id"]))
        for current, following in zip(items, items[1:]):
            nextinlot[current["id"]] = following
    restarts, validgaps = [], []
    for b in batches:
        if not b["has_error"]:
            continue
        following = nextinlot.get(b["id"])
        gap, reason = None, ""
        if not b["start"] or not b["end"] or b["end"] < b["start"]:
            reason = "시각 누락/역전"
        elif not following:
            reason = "같은 lot 재스캔 없음"
        else:
            gap = (following["start"] - b["end"]).total_seconds() / 60
            reason = "유효" if 0 <= gap <= 1440 else "겹침" if gap < 0 else "24h 초과"
            if reason == "유효":
                validgaps.append(gap)
        restarts.append((b["machine"], b["job_setup"], b["lot"], b["source_file"], ", ".join(b["types"]),
                         following["source_file"] if following else "", gap, reason))
    table("M06", "재시작 간격(같은 lot 재스캔)",
          ["호기", "Job/Setup", "Lot", "이슈 Report", "포함 유형", "다음 Report", "간격 (분)", "판정"], restarts)
    by_type = defaultdict(list)
    for item in restarts:
        if item[-1] == '유효':
            for category in item[4].split(', '):
                by_type[category].append(item[-2])
    table("M06", "유형별 재시작 간격 (유형 중복 허용)", ["유형", "유효 Batch 수", "평균 (분)", "중앙 (분)", "P95 (분)", "최대 (분)"],
          [(k, len(v), mean(v), median(v), percentile(v, .95), max(v)) for k, v in sorted(by_type.items())])
    table("M07", "복구 baseline (재시작 간격 proxy)", ["유효 건수", "제외 건수", "평균 (분)", "중앙 (분)", "최대 (분)"],
          [(len(validgaps), len(restarts) - len(validgaps), mean(validgaps) if validgaps else None,
            median(validgaps) if validgaps else None, max(validgaps) if validgaps else None)])
    # 정상(Pass) wafer 의 Recipe(=Job/Setup)별 Scanned/Bad/Good Dice 통계.
    # Good = 원문 Good Dice, 없으면 Scanned-Bad 로 보정. 통계값과 함께 차트로 보여준다.
    dice = defaultdict(lambda: {"scanned": [], "bad": [], "good": []})
    for w in wafers:
        if not (w["pass"] and w["job_setup"]):
            continue
        d = dice[w["job_setup"]]
        if w["scanned_dice"] is not None:
            d["scanned"].append(w["scanned_dice"])
        if w["bad_dice"] is not None:
            d["bad"].append(w["bad_dice"])
        good = w["good_dice"]
        if good is None and w["scanned_dice"] is not None and w["bad_dice"] is not None:
            good = w["scanned_dice"] - w["bad_dice"]
        if good is not None:
            d["good"].append(good)
    stat = lambda xs, f: f(xs) if xs else None
    table("M08", "Recipe별 정상 Dice 통계",
          ["Job/Setup (recipe)", "표본 수", "Scanned 평균", "Bad 평균", "Good 평균", "Bad 중앙", "Bad P95", "Bad 최대"],
          [(k, len(d["bad"]), stat(d["scanned"], mean), stat(d["bad"], mean), stat(d["good"], mean),
            stat(d["bad"], median), percentile(d["bad"], .95) if d["bad"] else None, stat(d["bad"], max))
           for k, d in sorted(dice.items())])
    # Lot 별 정상 Dice — 각 lot 이 어느 Job/Setup(recipe)인지 함께 적는다.
    lotdice = defaultdict(lambda: {"scanned": [], "bad": [], "good": [], "job": ""})
    for w in wafers:
        if not (w["pass"] and w["lot_key"]):
            continue
        d = lotdice[w["lot_key"]]
        d["job"] = w["job_setup"]
        if w["scanned_dice"] is not None:
            d["scanned"].append(w["scanned_dice"])
        if w["bad_dice"] is not None:
            d["bad"].append(w["bad_dice"])
        good = w["good_dice"]
        if good is None and w["scanned_dice"] is not None and w["bad_dice"] is not None:
            good = w["scanned_dice"] - w["bad_dice"]
        if good is not None:
            d["good"].append(good)
    table("M08", "Lot별 정상 Dice",
          ["Lot", "Job/Setup (recipe)", "표본 수", "Scanned 평균", "Bad 평균", "Good 평균", "Bad 최대"],
          [(lk[1], d["job"], len(d["bad"]), stat(d["scanned"], mean), stat(d["bad"], mean),
            stat(d["good"], mean), stat(d["bad"], max)) for lk, d in sorted(lotdice.items())])
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
                    history_bad[w["job_setup"]].append(w["bad_dice"])
                if w["yield_pct"] is not None and w["yield_pct"] <= 100:
                    history_yield[w["job_setup"]].append(w["yield_pct"])
            pending, limits, previous_time = [], {}, b['end']
        for w in bybatch[b["id"]]:
            recipe = w["job_setup"]
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
                anomalies.append((b["lot"], recipe, b["end"], b["machine"], b["source_file"], w["wafer_id"],
                                  w["bad_dice"], p95, w["yield_pct"], floor, " / ".join(reasons)))
        for w in bybatch[b["id"]]:
            if w["pass"] and w["job_setup"]:
                pending.append(w)
    # M09 는 lot 을 먼저 요약하고, 그 아래 wafer 상세를 둔다(요청 2026-09-21).
    anom_lot = {}
    for lot, job, end, *_ in anomalies:
        item = anom_lot.setdefault((job, lot), [0, None])
        item[0] += 1
        if end and (item[1] is None or end > item[1]):
            item[1] = end
    table("M09", "품질 이상 Lot 요약", ["Lot", "Job/Setup (recipe)", "이상 Wafer 수", "최근 Batch End"],
          [(lot, job, cnt, end) for (job, lot), (cnt, end) in sorted(anom_lot.items(), key=lambda kv: -kv[1][0])])
    table("M09", "품질 이상 Wafer 상세 (자동 Hold 아님)",
          ["Lot", "Job/Setup (recipe)", "Batch End", "호기", "Report", "Wafer ID", "Bad Dice", "과거 P95", "Yield (%)", "Yield 하한 (%)", "후보 근거"],
          sorted(anomalies, key=lambda a: (a[1], a[0], a[2] or datetime.max)))
    # M10: batch report 에는 lot 기대 매수가 없어 '완주율'은 측정 불가(B안).
    # 대신 lot 단위로 '스캔 중 이슈가 났는지'와 '재스캔(리포트>1) 여부'를 뽑아,
    # 전체 lot 중 문제 lot 비중을 본다. lot = (Job/Setup, Lot).
    lotmap = defaultdict(list)
    for b in batches:
        lotmap[b["lot_key"]].append(b)
    lot_rows, issue_lots, rescan_lots = [], 0, 0
    for (job, lot), items in sorted(lotmap.items()):
        items.sort(key=lambda b: (b["start"] or datetime.max, b["id"]))
        issue = any(b["has_error"] for b in items)
        starts = [b["start"] for b in items if b["start"]]
        ends = [b["end"] for b in items if b["end"]]
        issue_lots += issue
        rescan_lots += len(items) > 1
        if issue:
            # 포함 이슈 유형 = 실제 Pass/Fail 원문(그대로), 유형마다 한 줄(줄바꿈).
            seen, raws = set(), []
            for b in items:
                for w in bybatch[b["id"]]:
                    status = (w["status"] or "").strip()
                    if status and status not in seen and not w["pass"] and any(s[0] != "상태 확인 불가" for s in w["states"]):
                        seen.add(status)
                        raws.append(status)
            lot_rows.append((job, lot, len(items), "\n".join(raws),
                             min(starts) if starts else None, max(ends) if ends else None))
    total_lots = len(lotmap)
    ok_lots = total_lots - issue_lots
    pct = lambda n: n / total_lots * 100 if total_lots else None
    table("M10", "Lot 이슈 요약", ["구분", "Lot 수", "비중 (%)"],
          [("이슈 발생 Lot", issue_lots, pct(issue_lots)),
           ("정상 Lot", ok_lots, pct(ok_lots)),
           ("재스캔(리포트≥2) Lot", rescan_lots, pct(rescan_lots))])
    table("M10", "문제 Lot 상세", ["Job/Setup", "Lot", "스캔 시도(리포트) 수", "포함 이슈 유형", "최초 스캔", "마지막 스캔"],
          sorted(lot_rows, key=lambda r: r[2], reverse=True))
    table("M11", "미분류 · 누락 상태", ["호기", "Report", "Lot", "원본 순서", "Wafer ID", "유형", "분류 원문", "성격", "상태 원문", "Aborted 추정"],
          [r for r in detail if r[5] in {"Unclassified", "상태 확인 불가"}])
    return {"tables": tables, "batches": batches, "wafers": wafers, "selected": selected,
            "summary": {"Batch(리포트) 수": len(batches), "Lot 수": len(lotmap),
                        "Wafer 행 수": len(wafers), "Pass Wafer 수": sum(w["pass"] for w in wafers),
                        "이슈 발생 Lot 수": issue_lots, "재스캔 Lot 수": rescan_lots,
                        "이슈 Batch 수": sum(b["has_error"] for b in batches),
                        "시각 누락/역전 Batch 수": sum(not b['start'] or not b['end'] or b['end'] < b['start'] for b in batches),
                        "최근 24h Batch 수": sum(bool(b["end"] and now - timedelta(days=1) <= b["end"] <= now) for b in batches)},
            "settings": {"유효 Lot 매수 (WPH 전용)": valid_wafers, "이상 후보 최소 과거 정상 표본": min_baseline,
                         "Yield 하락 기준 (percentage points)": yield_drop, "분류 규칙 버전": RULE_VERSION},
            "created": now}
