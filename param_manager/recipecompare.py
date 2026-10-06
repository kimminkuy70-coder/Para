"""레시피 비교 모드(이슈 #14) — 두 레시피 그룹(A=기존, B=신규)을 같은 기준으로 비교한다.

입력은 조사 1회분 View(batchview.View)의 records. 장비 접근 없음 · 읽기 전용.
- 그룹 = 레시피 키 목록. 키 = 'Job · Recipe(s)' (Job/Setup 의 Job + wafer 표 Recipe(s) 최빈값).
- 속도: 정상 WPH(오류 · 중단 없이 25매 모두 Pass) · 정상 전체 WPH · 실제 WPH(오류 · 중단 Report 시간 포함 ÷ Pass wafer),
  순수 스캔(Avg. Scan Time) · 1장 처리(Batch Time ÷ 장수).
- 오류: wafer 비율을 레시피 탓 오류와 작업자 중단(Aborted · Skipped)으로 나눔.
- 검출력: 같은 Wafer ID 를 A와 B로 pair_hours 안에 스캔했고 Scanned Dice 가 같은 Pass 쌍의 Bad Dice. 부호 검정.
- 기준을 바꿔도 결론이 같은가: WPH 기준 3 × 테스트 Lot 2 × 호기 범위 2 = 12 조합의 B ÷ A.
"""
from __future__ import annotations

import html as _html
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from . import wph
from .report_theme import THEME_CSS, page_foot, page_top

OP_STOPS = ("Aborted", "Wafer aborted by user", "Skipped")
TEST_LOT = re.compile(r"test|engineer|scan ?time|^0$|^t$|^loadport", re.I)
REAL_LOT = re.compile(r"^[A-Za-z]{3}(?:[-_ ]|$)")
MAX_KEYS = 300


def _num(v):
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _real_id(w):
    return bool(w) and not w.lower().startswith("slot") and len(w) >= 6 and any(c.isalpha() for c in w) and any(c.isdigit() for c in w)


def is_test(lots):
    """Lot 칸 이름으로 테스트 스캔을 가린다(TEST · engineer · scan time …). 실제 Lot(영문 3글자로 시작)이 있으면 테스트 아님."""
    names = [x for x in lots if x and not x.lower().startswith("loadport")]
    if any(REAL_LOT.match(x) and not TEST_LOT.search(x) for x in names):
        return False
    return any(TEST_LOT.search(x) for x in lots if x)


def cause(status):
    first = str(status).split(".")[0].strip()
    return "작업자 중단 · Skip" if first in OP_STOPS else (first or "(빈 칸)")


def _cols(wafers):
    """wafer 표 열 이름(정규화 → 원래 이름) — 보고서마다 한 번만 만든다(행마다 safe_field 를 부르면 느림)."""
    out = {}
    for w in wafers[:1]:
        for k in w:
            out.setdefault(wph.normalize_key(k), k)
    return out


def feature(record, g):
    rep = record["report"]
    meta = {wph.normalize_key(k): v for k, v in rep.get("metadata", [])}
    job = wph.job_recipe(meta.get("jobsetup", ""))
    wafers = rep.get("wafers") or []
    cols = _cols(wafers)
    k_rec, k_st, k_lot, k_id, k_bad, k_fl, k_sd = (cols.get(x) for x in ("recipes", "passfail", "lot", "waferid", "baddice", "faults", "scanneddice"))
    k_rec = k_rec or cols.get("recipe")
    k_st = k_st or cols.get("status")
    get = lambda w, k: w.get(k, "") if k else ""
    recs = Counter(get(w, k_rec) for w in wafers)
    recs.pop("", None)
    rec = recs.most_common(1)[0][0] if recs else "(Recipe 없음)"
    start = wph.parse_batch_datetime(meta.get("batchstart", "")) or wph.parse_batch_datetime(meta.get("batchend", ""))
    rows, err, lots, n = [], [], [], 0
    for w in wafers:
        st = get(w, k_st)
        lots.append(get(w, k_lot))
        if st.startswith("Skipped"):
            continue
        n += 1
        if st == "Pass":
            rows.append((get(w, k_id), _num(get(w, k_bad)), _num(get(w, k_fl)), _num(get(w, k_sd))))
        else:
            err.append(st)
    lot_names = list(dict.fromkeys(x for x in lots if x))
    return dict(g=g, m=record["machine"], key=f"{job} · {rec}", job=job, rec=rec, start=start,
                s=start.strftime("%Y-%m-%d %H:%M") if start else "", bt=wph.hms_to_seconds(meta.get("batchtime", "")) or 0,
                ast=wph.hms_to_seconds(meta.get("avgscantime", "")), n=n, ok=len(rows), err=err, pass_rows=rows,
                lots=lot_names[:3], test=is_test(lot_names), f=rep.get("file_name", ""))


def features(view):
    cached = getattr(view, "_cmp_features", None)
    if cached is None:
        cached = [feature(r, g) for g, r in enumerate(view.records)]
        view._cmp_features = cached
    return cached


def recipes(view):
    """비교에 넣을 수 있는 레시피 목록 — [{key, job, rec, reports, wafers, machines, first, last}] (Report 많은 순)."""
    acc = {}
    for f in features(view):
        a = acc.setdefault(f["key"], dict(key=f["key"], job=f["job"], rec=f["rec"], reports=0, wafers=0, machines=set(), first="", last=""))
        a["reports"] += 1
        a["wafers"] += f["ok"]
        a["machines"].add(f["m"])
        if f["s"]:
            a["first"] = min(a["first"] or f["s"], f["s"])
            a["last"] = max(a["last"], f["s"])
    out = [dict(a, machines=sorted(a["machines"])) for a in acc.values()]
    return sorted(out, key=lambda a: (-a["reports"], a["key"]))


# ---------------------------------------------------------------- 계산
def clean(f):
    return f["bt"] > 0 and not f["err"] and f["n"] > 0 and f["ok"] == f["n"]


def metrics(v, full=25):
    """그룹 숫자. 정상 WPH = 25매 정상 Report, 실제 WPH = Pass wafer × 3600 ÷ 전체 Batch Time."""
    c = [f for f in v if clean(f)]
    c25 = [f for f in c if f["n"] == full]
    allbt = sum(f["bt"] for f in v)
    n = sum(f["n"] for f in v)
    causes = Counter(cause(e) for f in v for e in f["err"])
    op = causes.get("작업자 중단 · Skip", 0)
    scans = [f["ast"] for f in c if f["ast"]]
    faults = [x[2] for f in c for x in f["pass_rows"] if x[2] is not None]
    return dict(
        reports=len(v), clean=len(c), clean25=len(c25), wafers=n, passed=sum(f["ok"] for f in v),
        scan=statistics.median(scans) if scans else None,
        per_wafer=sum(f["bt"] for f in c) / sum(f["n"] for f in c) if c else None,
        wph25=3600 * sum(f["n"] for f in c25) / sum(f["bt"] for f in c25) if c25 else None,
        wph_clean=3600 * sum(f["n"] for f in c) / sum(f["bt"] for f in c) if c else None,
        wph_all=3600 * sum(f["ok"] for f in v) / allbt if allbt else None,
        err_rate=(sum(causes.values()) / n) if n else None, recipe_err=((sum(causes.values()) - op) / n) if n else None,
        op_err=(op / n) if n else None, faults=statistics.median(faults) if faults else None,
        machines=sorted({f["m"] for f in v}))


def sign_p(up, dn):
    n = up + dn
    if not n:
        return None
    k = min(up, dn)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def _date(text, end=False):
    if not text:
        return None
    try:
        d = datetime.strptime(text, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError("날짜는 YYYY-MM-DD 로 입력하세요") from None
    return d + timedelta(days=1) if end else d


def _spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("비교 조건을 확인하세요")
    groups = {}
    for g in ("a", "b"):
        x = spec.get(g) or {}
        name = str(x.get("name") or ("기존" if g == "a" else "신규")).strip()[:40]
        keys = x.get("keys")
        if not isinstance(keys, list) or not keys or len(keys) > MAX_KEYS or not all(isinstance(k, str) for k in keys):
            raise ValueError(f"{'A' if g == 'a' else 'B'} 그룹에 레시피를 하나 이상 넣으세요")
        groups[g] = dict(name=name, keys=sorted(set(keys)), since=_date(x.get("since", "")), until=_date(x.get("until", ""), True))
    if set(groups["a"]["keys"]) & set(groups["b"]["keys"]):
        raise ValueError("같은 레시피를 A와 B에 모두 넣을 수 없습니다")
    opts = spec.get("options") or {}
    hours = opts.get("pair_hours", 72)
    if type(hours) is not int or not 1 <= hours <= 720:
        raise ValueError("같은 wafer 짝 찾는 시간은 1~720시간입니다")
    return groups, dict(same_machine=bool(opts.get("same_machine", True)), exclude_test=bool(opts.get("exclude_test", True)),
                        pair_hours=hours, full=25)


def _pick(F, grp):
    keys = set(grp["keys"])
    return [f for f in F if f["key"] in keys and (grp["since"] is None or (f["start"] and f["start"] >= grp["since"]))
            and (grp["until"] is None or (f["start"] and f["start"] < grp["until"]))]


def _scope(A, B, same_machine, exclude_test):
    if exclude_test:
        A, B = [f for f in A if not f["test"]], [f for f in B if not f["test"]]
    if same_machine:
        common = {f["m"] for f in A} & {f["m"] for f in B}
        A, B = [f for f in A if f["m"] in common], [f for f in B if f["m"] in common]
    return A, B


def _ratio(a, b):
    return b / a if a and b is not None else None


def pairs(A, B, hours):
    """같은 wafer(A · B 모두 Pass, Scanned Dice 같음, hours 안) — B 의 레시피 키별로 묶는다."""
    by_w = defaultdict(list)
    for f in A:
        for wid, bad, faults, dice in f["pass_rows"]:
            if _real_id(wid) and bad is not None:
                by_w[wid].append((f, bad, faults, dice))
    lim = hours * 3600
    rows = []
    for f in B:
        if not f["start"]:
            continue
        for wid, bad, faults, dice in f["pass_rows"]:
            if not _real_id(wid) or bad is None:
                continue
            cands = [c for c in by_w.get(wid, ()) if c[0]["start"] and c[3] == dice and abs((c[0]["start"] - f["start"]).total_seconds()) <= lim]
            if cands:
                a = min(cands, key=lambda c: abs((c[0]["start"] - f["start"]).total_seconds()))
                rows.append(dict(w=wid, layer=f["key"], bg=f["g"], ag=a[0]["g"], b=bad, a=a[1], fb=faults or 0, fa=a[2] or 0,
                                 gap=round((f["start"] - a[0]["start"]).total_seconds() / 3600, 1)))
    return rows


def _det(rows):
    up = sum(1 for r in rows if r["b"] > r["a"])
    dn = sum(1 for r in rows if r["b"] < r["a"])
    sa, sb = sum(r["a"] for r in rows), sum(r["b"] for r in rows)
    p = sign_p(up, dn)
    verdict = ("표본 없음" if not rows else "차이 없음" if p is None or p >= 0.05 else "B가 더 많이 잡음" if sb > sa else "B가 덜 잡음")
    return dict(n=len(rows), up=up, dn=dn, eq=len(rows) - up - dn, p=p, sa=sa, sb=sb, fa=sum(r["fa"] for r in rows),
                fb=sum(r["fb"] for r in rows), verdict=verdict)


def compare(view, spec):
    groups, o = _spec(spec)
    F = features(view)
    A0, B0 = _pick(F, groups["a"]), _pick(F, groups["b"])
    if not A0 or not B0:
        raise ValueError("고른 레시피 · 기간에 해당하는 Batch Report 가 " + ("A" if not A0 else "B") + " 그룹에 없습니다")
    A, B = _scope(A0, B0, o["same_machine"], o["exclude_test"])
    speed = [dict(name="전체" + (" (같은 호기)" if o["same_machine"] else " 호기"), A=metrics(A, o["full"]), B=metrics(B, o["full"]))]
    for m in sorted({f["m"] for f in A} & {f["m"] for f in B}):
        speed.append(dict(name=m, A=metrics([f for f in A if f["m"] == m], o["full"]), B=metrics([f for f in B if f["m"] == m], o["full"])))
    err = {}
    for g, v in (("A", A), ("B", B)):
        n = sum(f["n"] for f in v)
        c = Counter(cause(e) for f in v for e in f["err"])
        err[g] = dict(wafers=n, items=[[k, x, x / n if n else 0] for k, x in c.most_common(10)])
    P = pairs(*_scope(A0, B0, False, o["exclude_test"]), o["pair_hours"])
    layers = []
    for key in sorted({r["layer"] for r in P}):
        rows = [r for r in P if r["layer"] == key]
        layers.append(dict(key=key, pts=[[r["a"], r["b"], r["w"]] for r in rows][:3000], **_det(rows)))
    grouped = defaultdict(list)
    for r in P:
        grouped[(r["bg"], r["ag"])].append(r)
    pair_list = sorted(([dict(bg=bg, ag=ag, layer=rs[0]["layer"], n=len(rs), sa=sum(r["a"] for r in rs), sb=sum(r["b"] for r in rs), gap=rs[0]["gap"])
                         for (bg, ag), rs in grouped.items()]), key=lambda p: (p["layer"], -p["n"]))
    robust = []
    for basis, label in (("wph25", "정상 WPH (25매)"), ("wph_clean", "정상 WPH (전체 정상 Report)"), ("wph_all", "실제 WPH (오류 포함)")):
        for ex in (True, False):
            for same in (True, False):
                a, b = _scope(A0, B0, same, ex)
                ma, mb = metrics(a, o["full"]), metrics(b, o["full"])
                robust.append(dict(basis=label, test="제외" if ex else "포함", machine="같은 호기" if same else "전 호기",
                                   A=ma[basis], B=mb[basis], ratio=_ratio(ma[basis], mb[basis]), main=(basis == "wph25" and ex == o["exclude_test"] and same == o["same_machine"])))
    rs = [r["ratio"] for r in robust if r["ratio"] is not None]
    # ±2% 안은 '비슷함' — 1.00 · 1.01 처럼 같은 값이 '달라짐'으로 보이지 않게.
    direction = ("계산 불가" if not rs else "B가 빠름" if all(x > 1.02 for x in rs) else "B가 느림" if all(x < 0.98 for x in rs)
                 else "비슷함" if all(0.98 <= x <= 1.02 for x in rs) else "기준에 따라 달라짐")
    main = speed[0]
    ratio = _ratio(main["A"]["wph25"] or main["A"]["wph_clean"], main["B"]["wph25"] or main["B"]["wph_clean"])
    det = _det(P)
    used = sorted({f["g"] for f in A + B} | {p["bg"] for p in pair_list} | {p["ag"] for p in pair_list})
    reps = {f["g"]: dict(g=f["g"], m=f["m"], s=f["s"], f=f["f"], key=f["key"], grp="A" if f["key"] in groups["a"]["keys"] else "B",
                         lots=f["lots"], ok=f["ok"], n=f["n"], ast=f["ast"], fe=f["err"][0] if f["err"] else "", test=f["test"])
            for f in F if f["g"] in set(used)}
    return dict(
        groups={g: dict(name=x["name"], keys=x["keys"], since=x["since"].strftime("%Y-%m-%d") if x["since"] else "",
                        until=(x["until"] - timedelta(days=1)).strftime("%Y-%m-%d") if x["until"] else "") for g, x in groups.items()},
        options=o, speed=speed, err=err, layers=layers, detection=det, pairs=pair_list[:2000], robust=robust,
        summary=dict(ratio=ratio, direction=direction, detection=det["verdict"], a_reports=len(A), b_reports=len(B),
                     a_clean25=main["A"]["clean25"], b_clean25=main["B"]["clean25"]),
        reports=reps, created=datetime.now().strftime("%Y-%m-%d %H:%M"))


# ---------------------------------------------------------------- 결과 HTML(앱 디자인 · 원문 포함)
def _esc(v):
    return _html.escape("" if v is None else str(v))


def _raw_blob(view, gs):
    import base64
    import gzip
    out = {}
    for g in gs:
        r = view.raw(g)
        out[str(g)] = [r["f"], r["m"], r["meta"], r["h"], r["rows"]]
    data = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(data, compresslevel=6, mtime=0)).decode("ascii")


def build_html(result, view):
    from .report_theme import RAW_HTML, RAW_JS
    a, b = result["groups"]["a"], result["groups"]["b"]
    title = f"레시피 비교 — {a['name']} ↔ {b['name']}"
    top = page_top(title=title, sub="레시피 비교 결과", eyebrow="PROCESS INTELLIGENCE · 레시피 비교",
                   desc="두 레시피 그룹을 같은 기준으로 비교한 결과 — 속도 · 검출력(같은 wafer) · 오류, 근거가 된 Batch Report 원문 포함.",
                   badges=[(f"생성 {result['created']}", "")],
                   stamp=[("A", f"{a['name']} · 레시피 {len(a['keys'])}개"), ("B", f"{b['name']} · 레시피 {len(b['keys'])}개"),
                          ("호기", "같은 호기끼리" if result["options"]["same_machine"] else "전 호기"),
                          ("테스트 Lot", "제외" if result["options"]["exclude_test"] else "포함"),
                          ("같은 wafer", f"{result['options']['pair_hours']}시간 이내")])
    data = json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str).replace("</", "<\\/")
    blob = _raw_blob(view, [int(g) for g in result["reports"]])
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{_esc(title)}</title><style>{THEME_CSS}{CMP_CSS}</style></head><body class=\"app-rpt\"><div class=\"doc\">{top}"
            f"<div class=\"pad\">{CMP_BODY}</div></div>"
            + page_foot("Camtek AOI Manager · 레시피 비교 결과 파일", "원본 Batch Report 는 읽기만 했습니다")
            + RAW_HTML + f"<script type=\"application/json\" id=\"cmp\">{data}</script>"
            f"<script type=\"application/octet-stream\" id=\"rawgz\">{blob}</script><script>{CMP_JS}</script><script>{RAW_JS}</script></body></html>")


CMP_CSS = """
.app-rpt .ab{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:800;border-radius:999px;padding:3px 10px;white-space:nowrap}
.app-rpt .ab i{width:9px;height:9px;border-radius:50%;display:inline-block}
.app-rpt .ab.a{background:#e5ecf6;color:#31517c}.app-rpt .ab.a i{background:#31517c}
.app-rpt .ab.b{background:#d6f2e6;color:#0b5e46}.app-rpt .ab.b i{background:#0d9668}
.app-rpt .defs2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 16px}
.app-rpt .defs2>div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;box-shadow:var(--sh1)}
.app-rpt .defs2>div.a{border-left:4px solid #31517c}.app-rpt .defs2>div.b{border-left:4px solid #0d9668}
.app-rpt .defs2 ul{margin:6px 0 0;padding-left:18px;font-size:12px;color:var(--soft)}
.app-rpt .num{text-align:right;font-variant-numeric:tabular-nums}
.app-rpt .d-up{color:#8a5a00;font-weight:800}.app-rpt .d-dn{color:#a33820;font-weight:800}.app-rpt .d-eq{color:#94a3b8}
.app-rpt .st{display:inline-block;font-size:11px;font-weight:800;padding:2px 9px;border-radius:999px;white-space:nowrap}
.app-rpt .st.done{background:#d6f2e6;color:#0b5e46}.app-rpt .st.re{background:#fdf0d5;color:#8a5a00}.app-rpt .st.open{background:#fde4dc;color:#a33820}.app-rpt .st.out{background:#f1f3f6;color:#8a97a8}
.app-rpt tr.clickable{cursor:pointer}
.app-rpt .linklike{background:none;border:0;padding:0;color:#31517c;text-decoration:underline;cursor:pointer;font:inherit;font-weight:700;font-size:12px}
.app-rpt .chartcard{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:#fff;margin:0 0 16px}
.app-rpt .chartcard h3{margin:0 0 8px;font-size:15px}
.app-rpt svg text{font:11.5px 'Malgun Gothic','맑은 고딕',sans-serif;fill:#52647d}
.app-rpt .bv-tip{position:fixed;z-index:2147483000;pointer-events:none;background:#1f2937;color:#fff;font-size:12px;line-height:1.6;padding:8px 11px;border-radius:8px;white-space:pre;box-shadow:var(--sh2)}
@media(max-width:760px){.app-rpt .defs2{grid-template-columns:1fr}}
"""

CMP_BODY = """
<div class="metricnav" role="tablist"><button class="mbtn on" data-sec="sum">요약</button><button class="mbtn" data-sec="speed">속도 · WPH</button>
<button class="mbtn" data-sec="det">검출력 (같은 wafer)</button><button class="mbtn" data-sec="err">오류</button><button class="mbtn" data-sec="list">Batch Report 목록</button>
<button class="mbtn help" data-sec="defs">📘 기준</button></div>
<section class="metric" id="sec-sum"></section><section class="metric" id="sec-speed" hidden></section><section class="metric" id="sec-det" hidden></section>
<section class="metric" id="sec-err" hidden></section><section class="metric" id="sec-list" hidden></section><section class="metric" id="sec-defs" hidden></section>
"""

CMP_JS = r"""
(function(){
var D=JSON.parse(document.getElementById('cmp').textContent),R=D.reports,GA=D.groups.a,GB=D.groups.b,CA='#31517c',CB='#0d9668',UP='#b7791f',DN='#c2410c';
function $(s){return document.querySelector(s)}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function n1(x,p){if(x==null||isNaN(x))return '—';p=p==null?1:p;return Number(x).toLocaleString('ko-KR',{minimumFractionDigits:p,maximumFractionDigits:p})}
function n0(x){return n1(x,0)}function pct(x){return x==null?'—':(100*x).toFixed(1)+'%'}
function pt(p){return p==null?'—':p>=0.001?String(Number(p.toPrecision(2))):p.toExponential(1)}
function ab(g){return '<span class="ab '+g.toLowerCase()+'"><i></i>'+g+' · '+esc(g==='A'?GA.name:GB.name)+'</span>'}
function svg(w,h,inner){return '<div class="chartscroll"><svg class="wide" viewBox="0 0 '+w+' '+h+'" width="100%" role="img">'+inner+'</svg></div>'}
function verdictChip(v){return '<span class="st '+(v==='차이 없음'?'done':v==='B가 덜 잡음'?'open':v==='표본 없음'?'out':'re')+'">'+esc(v)+'</span>'}
var tip=document.createElement('div');tip.className='bv-tip';tip.hidden=true;document.body.appendChild(tip);
document.addEventListener('mousemove',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');if(!t){tip.hidden=true;return}tip.textContent=t.getAttribute('data-tip');tip.hidden=false;
  var x=e.clientX+14,y=e.clientY+14;if(x+tip.offsetWidth>innerWidth-8)x=e.clientX-tip.offsetWidth-14;if(y+tip.offsetHeight>innerHeight-8)y=e.clientY-tip.offsetHeight-14;tip.style.left=x+'px';tip.style.top=y+'px'});
document.querySelectorAll('.mbtn').forEach(function(b){b.onclick=function(){var k=b.dataset.sec;document.querySelectorAll('section.metric').forEach(function(s){s.hidden=s.id!=='sec-'+k});
  document.querySelectorAll('.mbtn').forEach(function(x){x.classList.toggle('on',x===b)});window.scrollTo(0,0)}});
var S=D.speed[0],sm=D.summary,det=D.detection;
function kpi(cls,l,n,u,s){return '<div class="kpi '+cls+'"><div class="n">'+n+'<span class="u">'+u+'</span></div><div class="l">'+l+'</div><div class="s">'+s+'</div></div>'}
function speedRatio(){return sm.ratio==null?'—':n1(sm.ratio,2)}
$('#sec-sum').innerHTML='<div class="defs2"><div class="a">'+ab('A')+'<ul>'+GA.keys.map(function(k){return '<li>'+esc(k)+'</li>'}).join('')+'</ul>'+(GA.since||GA.until?'<p class="sub">기간 '+esc(GA.since||'처음')+' ~ '+esc(GA.until||'끝')+'</p>':'')+'</div>'+
  '<div class="b">'+ab('B')+'<ul>'+GB.keys.map(function(k){return '<li>'+esc(k)+'</li>'}).join('')+'</ul>'+(GB.since||GB.until?'<p class="sub">기간 '+esc(GB.since||'처음')+' ~ '+esc(GB.until||'끝')+'</p>':'')+'</div></div>'+
  '<div class="kpis">'+kpi(sm.ratio>1?'t':sm.ratio<1?'r':'','정상 WPH B ÷ A',speedRatio(),'배','A '+n1(S.A.wph25||S.A.wph_clean)+' → B '+n1(S.B.wph25||S.B.wph_clean)+' WPH')+
  kpi(sm.direction==='기준에 따라 달라짐'?'a':'','기준을 바꿔도?',esc(sm.direction),'','WPH 기준 3 × 테스트 Lot 2 × 호기 범위 2 = 12 조합')+
  kpi(det.verdict==='차이 없음'?'t':det.verdict==='B가 덜 잡음'?'r':'a','같은 wafer Bad Dice B ÷ A',det.sa?n1(det.sb/det.sa,2):'—','배',det.n+'장 · '+esc(det.verdict)+(det.p!=null?' · p='+pt(det.p):''))+
  kpi('','표본 (정상 25매 Report)',S.A.clean25+' / '+S.B.clean25,'','A / B · Report '+S.A.reports+' / '+S.B.reports)+'</div>'+
  '<h2>기준을 바꿔도 결론이 같은가</h2><p class="sub">한 가지 기준만 보면 숫자가 달라질 수 있어, 조합마다 B ÷ A 를 계산했습니다. 모든 조합에서 방향(1보다 큼/작음)이 같으면 어떤 기준으로 봐도 같은 결론입니다. 굵은 줄 = 이번 비교의 주 기준.</p>'+
  '<div class="tscroll"><table><thead><tr><th>WPH 기준</th><th>테스트 Lot</th><th>호기 범위</th><th class="num">A</th><th class="num">B</th><th class="num">B ÷ A</th></tr></thead><tbody>'+
  D.robust.map(function(r){var c=r.ratio==null?'':r.ratio>1?'d-up':'d-dn';return '<tr'+(r.main?' style="font-weight:800"':'')+'><td>'+esc(r.basis)+'</td><td>'+r.test+'</td><td>'+r.machine+'</td><td class="num">'+n1(r.A)+'</td><td class="num">'+n1(r.B)+'</td><td class="num '+c+'">'+(r.ratio==null?'—':n1(r.ratio,2)+'배')+'</td></tr>'}).join('')+'</tbody></table></div>';
/* 속도 */
function bars(){var L=170,W=980,R=220,rowH=74,rows=D.speed,H=30+rows.length*rowH,mx=0;rows.forEach(function(s){mx=Math.max(mx,s.A.wph25||0,s.B.wph25||0)});mx=(mx||1)*1.08;
  var sc=function(v){return (W-L-R)*v/mx},o='';
  rows.forEach(function(s,i){var y=8+i*rowH;o+='<text x="'+(L-12)+'" y="'+(y+30)+'" text-anchor="end" style="font-weight:700;fill:#1f2937">'+esc(s.name)+'</text>';
    [['A',s.A,CA],['B',s.B,CB]].forEach(function(z,j){var v=z[1].wph25,w=sc(v||0);o+='<rect x="'+L+'" y="'+(y+j*27)+'" width="'+Math.max(w,1)+'" height="22" rx="5" fill="'+z[2]+'" data-tip="'+esc(z[0]+' · '+s.name+'\n정상 WPH '+n1(v)+'\n정상 25매 Report '+z[1].clean25+'개\n1장 처리 '+n0(z[1].per_wafer)+'초 · 순수 스캔 '+n0(z[1].scan)+'초')+'"/>'+
      '<text x="'+(L+w+8)+'" y="'+(y+j*27+16)+'" style="font-weight:800;fill:#1f2937">'+(v==null?'정상 25매 없음':n1(v))+'</text><text x="'+(L+w+(v==null?96:46))+'" y="'+(y+j*27+16)+'">'+z[0]+' · 25매 '+z[1].clean25+'개</text>'})});
  return svg(W,H,o)}
function srow(s,g){var o=s[g];return '<tr><td>'+esc(s.name)+'</td><td>'+ab(g)+'</td><td class="num">'+o.reports+'</td><td class="num">'+o.clean25+'</td><td class="num">'+n0(o.scan)+'초</td><td class="num">'+n0(o.per_wafer)+'초</td><td class="num"><b>'+n1(o.wph25)+'</b></td><td class="num">'+n1(o.wph_clean)+'</td><td class="num">'+n1(o.wph_all)+'</td><td class="num">'+pct(o.recipe_err)+'</td><td class="num">'+n0(o.faults)+'</td></tr>'}
$('#sec-speed').innerHTML='<div class="chartcard"><h3>정상 WPH <small style="font-weight:400;color:#94a3b8">오류 · 중단 없이 25매 모두 Pass한 Report · 막대에 마우스</small></h3>'+bars()+'</div>'+
  '<div class="tscroll"><table><thead><tr><th>범위</th><th>그룹</th><th class="num">Report</th><th class="num">정상 25매</th><th class="num">순수 스캔/장</th><th class="num">1장 처리</th><th class="num">정상 WPH</th><th class="num">정상 전체</th><th class="num">실제 WPH</th><th class="num">레시피 탓 오류</th><th class="num">Faults 중앙</th></tr></thead><tbody>'+
  D.speed.map(function(s){return srow(s,'A')+srow(s,'B')}).join('')+'</tbody></table></div><p class="sub">순수 스캔 = Avg. Scan Time · 1장 처리 = Batch Time ÷ 장수(로봇 · 얼라인 포함) · 실제 WPH = Pass wafer × 3600 ÷ 오류 · 중단 Report 까지 포함한 Batch Time.</p>';
/* 검출력 */
function detBars(){var W=980,L=260,R=290,rowH=62,ls=D.layers,H=16+ls.length*rowH,bw=W-L-R,o='';
  ls.forEach(function(l,i){var y=8+i*rowH,x=L;o+='<text x="'+(L-12)+'" y="'+(y+18)+'" text-anchor="end" style="font-weight:800;fill:#1f2937">'+esc(l.key.length>34?l.key.slice(0,33)+'…':l.key)+'</text><text x="'+(L-12)+'" y="'+(y+34)+'" text-anchor="end">'+l.n+'장</text>';
    [[l.up,UP,'B가 더 많이 잡은 wafer'],[l.eq,'#cbd5e1','같은 개수'],[l.dn,DN,'B가 덜 잡은 wafer']].forEach(function(p){if(!p[0])return;var w=bw*p[0]/l.n;
      o+='<rect x="'+x+'" y="'+y+'" width="'+w+'" height="30" fill="'+p[1]+'" data-tip="'+esc(l.key+'\n'+p[2]+' '+p[0]+'장 / '+l.n+'장')+'"/>'+(w>30?'<text x="'+(x+w/2)+'" y="'+(y+20)+'" text-anchor="middle" style="fill:'+(p[1]==='#cbd5e1'?'#1f2937':'#fff')+';font-weight:800">'+p[0]+'</text>':'');x+=w});
    o+='<text x="'+(L+bw+14)+'" y="'+(y+14)+'" style="font-weight:700;fill:#1f2937">Bad Dice 합 A '+n0(l.sa)+' → B '+n0(l.sb)+'</text><text x="'+(L+bw+14)+'" y="'+(y+32)+'" style="font-weight:800;fill:'+(l.verdict==='차이 없음'?'#0b5e46':l.verdict==='B가 덜 잡음'?'#a33820':'#8a5a00')+'">'+esc(l.verdict)+(l.p!=null?' · p='+pt(l.p):'')+'</text>'});
  return svg(W,H,o)}
$('#sec-det').innerHTML=D.layers.length?'<div class="note amber"><span class="t">어떻게 비교했나</span>똑같은 wafer 한 장을 <b>A로도 B로도 스캔한 경우</b>('+D.options.pair_hours+'시간 안 · Scanned Dice 같음 · 둘 다 Pass)만 골랐습니다. 같은 wafer 라 결함은 같으므로, 두 레시피가 <b>Bad Dice 를 몇 개로 판정했는지</b>가 검출 차이입니다. 줄 = B 레시피.</div>'+
  '<div class="chartcard"><h3>같은 wafer 에서 누가 Bad Dice 를 더 많이 잡았나</h3>'+detBars()+'<p class="sub"><span class="st re">B가 더 많이 잡음</span> 더 잘 찾았거나 가성이 늘었음 · <span class="st open">B가 덜 잡음</span> 놓쳤거나 A의 가성이 많았음 · <span class="st done">차이 없음</span> 판정이 같음 — 어느 쪽인지는 리뷰(실결함/가성)로만 가릴 수 있습니다. p = 우연히 이렇게 갈릴 확률(0.05 미만이면 레시피 차이).</p></div>'+
  '<h2>같은 wafer 비교 목록</h2><p class="sub">행의 [원문]을 누르면 그 Batch Report 원문 표가 열립니다.</p><div class="tscroll" style="max-height:520px;overflow:auto"><table><thead><tr><th>B 레시피</th><th>B 스캔</th><th>A 스캔</th><th class="num">같은 wafer</th><th class="num">Bad Dice A</th><th class="num">Bad Dice B</th><th class="num">B − A</th></tr></thead><tbody>'+
  D.pairs.map(function(p){var a=R[p.ag],b=R[p.bg],d=p.sb-p.sa;return '<tr><td>'+esc(p.layer)+'</td><td>'+esc(b.m)+' · '+esc(b.s)+' · '+esc(b.lots.join(', '))+' <button class="linklike" data-raw="'+p.bg+'">원문</button></td><td>'+esc(a.m)+' · '+esc(a.s)+' · '+esc(a.lots.join(', '))+' <button class="linklike" data-raw="'+p.ag+'">원문</button></td><td class="num">'+p.n+'</td><td class="num">'+p.sa+'</td><td class="num">'+p.sb+'</td><td class="num '+(d>0?'d-up':d<0?'d-dn':'d-eq')+'">'+(d>0?'+':'')+d+'</td></tr>'}).join('')+'</tbody></table></div>'
  :'<div class="note slate"><span class="t">같은 wafer 쌍 없음</span>A와 B로 '+D.options.pair_hours+'시간 안에 함께 스캔한 wafer 가 없습니다. 검출력은 비교할 수 없습니다.</div>';
/* 오류 */
var cs={};['A','B'].forEach(function(g){D.err[g].items.forEach(function(it){cs[it[0]]=1})});var mx=0;Object.keys(cs).forEach(function(k){['A','B'].forEach(function(g){var it=D.err[g].items.filter(function(x){return x[0]===k})[0];if(it)mx=Math.max(mx,it[2])})});
$('#sec-err').innerHTML='<h2>오류 원인별 wafer 비율</h2><p class="sub">A wafer '+n0(D.err.A.wafers)+'장 · B wafer '+n0(D.err.B.wafers)+'장. Pass wafer 만 보면 사라지는 손실입니다 — 레시피 탓 오류(Alignment · Scan 2D · Focus · Clean Reference)와 작업자 중단(Aborted · Skipped)을 나눠 보세요.</p>'+
  '<div class="tscroll"><table><thead><tr><th>원인(첫 문구)</th><th>A</th><th>B</th></tr></thead><tbody>'+Object.keys(cs).map(function(k){var v={};['A','B'].forEach(function(g){var it=D.err[g].items.filter(function(x){return x[0]===k})[0];v[g]=it?it[2]:0});
  function bar(x,c){return '<div style="display:flex;align-items:center;gap:8px"><span style="display:inline-block;height:10px;border-radius:3px;background:'+c+';width:'+Math.max(2,160*x/(mx||1))+'px"></span>'+pct(x)+'</div>'}
  return '<tr><td>'+esc(k)+'</td><td>'+bar(v.A,CA)+'</td><td>'+bar(v.B,CB)+'</td></tr>'}).join('')+'</tbody></table></div>';
/* 목록 */
var ids=Object.keys(R).sort(function(a,b){return R[a].s<R[b].s?-1:1});
$('#sec-list').innerHTML='<h2>비교에 쓴 Batch Report</h2><p class="sub">'+ids.length+'장 · 행을 누르면 원문 창(이 파일에 담아 둔 원문 표 — 다른 컴퓨터에서도 열림).</p><div class="tscroll" style="max-height:640px;overflow:auto"><table><thead><tr><th>그룹</th><th>시작</th><th>호기</th><th>레시피</th><th>Lot</th><th class="num">Pass / 행</th><th class="num">Avg. Scan</th><th>첫 Error 원문</th><th>파일 이름</th></tr></thead><tbody>'+
  ids.map(function(g){var r=R[g];return '<tr class="clickable" data-raw="'+g+'"><td>'+ab(r.grp)+(r.test?' <span class="st out">테스트</span>':'')+'</td><td>'+esc(r.s)+'</td><td>'+esc(r.m)+'</td><td>'+esc(r.key)+'</td><td>'+esc(r.lots.join(', '))+'</td><td class="num">'+r.ok+' / '+r.n+'</td><td class="num">'+(r.ast!=null?r.ast+'초':'—')+'</td><td style="color:#a33820">'+esc(r.fe)+'</td><td style="font-family:Consolas,monospace;font-size:11.5px">'+esc(r.f)+'</td></tr>'}).join('')+'</tbody></table></div>';
/* 기준 */
$('#sec-defs').innerHTML='<h2>이 비교의 기준</h2><div class="tscroll"><table><thead><tr><th>질문</th><th>기준</th><th>이유</th></tr></thead><tbody>'+
  '<tr><td><b>① 레시피가 원래 더 빠른가</b> (주 지표)</td><td>정상 WPH — 오류 · 중단 없이 25매 모두 Pass한 Report, '+(D.options.same_machine?'같은 호기끼리':'전 호기')+'</td><td>로딩 · 얼라인 고정 시간과 오류 손실을 빼고 레시피 자체 속도만 남깁니다.</td></tr>'+
  '<tr><td><b>② 실제 생산에서도 이득인가</b> (보조)</td><td>실제 WPH — 오류 · 중단 Report 시간 포함 ÷ Pass wafer, 테스트 Lot '+(D.options.exclude_test?'제외':'포함')+'</td><td>신규 레시피가 Error 를 늘리면 여기서 깎입니다.</td></tr>'+
  '<tr><td><b>③ 결함을 놓치지 않는가</b> (통과 조건)</td><td>같은 wafer 짝 — '+D.options.pair_hours+'시간 이내 · Scanned Dice 같음 · 부호 검정</td><td>동등하지 않으면 ①이 좋아도 "입증"이라고 쓰지 않습니다.</td></tr>'+
  '<tr><td><b>④ 기준을 바꿔도 같은가</b></td><td>WPH 기준 3 × 테스트 Lot 2 × 호기 범위 2 = 12 조합의 B ÷ A</td><td>모든 조합에서 방향이 같으면 결론이 튼튼합니다.</td></tr></tbody></table></div>'+
  '<div class="note slate"><span class="t">한계</span>Batch Report 에는 실결함/가성 판정이 없어 검출 차이가 좋은지 나쁜지는 리뷰 결과로 판단해야 합니다. 테스트 Lot 은 Lot 이름(TEST · engineer · scan time 등)으로 가립니다.</div>';
})();
"""
