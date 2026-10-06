"""결과 HTML(분석 · 가동률 대시보드 · Lot 추적 · WPH 통합)을 앱 화면과 같은 모양으로 — 공통 머리 · 테마 · 원문 창.

앱(frontend/src/styles.css)의 색 · 상단 바 · 큰 탭 · 흰 패널 · 지표 카드 · 표 · 상태 칩 · 창을 그대로 옮겼다.
기존 각 HTML 의 CSS 뒤에 THEME_CSS 를 붙이고 <body class="app-rpt"> 로 감싸 덮어쓴다(계산 · 스크립트는 그대로).

원문 창: 다른 컴퓨터에서는 장비 Report 폴더 링크(file:///)가 열리지 않으므로, Batch Report 원문 표(Batch Info ·
wafer 표)를 gzip + base64 로 HTML 안에 담아 두고 누를 때 풀어서 앱의 'Batch Report 원문 창'과 같은 배치로 보여 준다.
"""
from __future__ import annotations

import base64
import gzip
import html as _html
import json

APP_NAME = 'Camtek AOI Manager'


def _esc(value):
    return _html.escape('' if value is None else str(value))


THEME_CSS = """
/* ===== 앱 화면 테마(styles.css 와 같은 값) ===== */
body.app-rpt{--ink:#1f2937;--soft:#5f6b7a;--faint:#94a3b8;--line:#e6ebf0;--line2:#eef2f6;--bg:#eef2f4;--paper:#fff;
--navy:#37474f;--teal:#0b5e46;--amber:#8a5a00;--rust:#a33820;--slate:#52647d;--lime:#10b981;--acc2:#0d9668;--blue:#31517c;--band:#f7f9fb;
--navy-bg:#eaf0f6;--teal-bg:#effaf5;--amber-bg:#fffbea;--rust-bg:#fdeae5;--slate-bg:#f7f9fb;
--sh1:0 1px 3px rgba(30,40,80,.08),0 1px 2px rgba(30,40,80,.06);--sh2:0 8px 24px rgba(30,40,80,.13),0 2px 6px rgba(30,40,80,.07);
margin:0;background:var(--bg);color:var(--ink);font-family:'Malgun Gothic','맑은 고딕',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:14px;line-height:1.6;word-break:keep-all}
.app-rpt *{box-sizing:border-box}
.app-rpt .topbar{background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 32px}
.app-rpt .brand{display:flex;align-items:center;gap:12px;color:#fff;font-size:19px;letter-spacing:-.4px;text-decoration:none}
.app-rpt .brand b{font-weight:800}.app-rpt .brand small{display:block;font-size:11px;letter-spacing:.5px;color:#c4cede;margin-top:3px}
.app-rpt .brand-icon{background:var(--lime);color:#04231a;font-size:25px;font-weight:900;width:38px;height:38px;border-radius:10px;display:grid;place-items:center;box-shadow:var(--sh1);flex:none}
.app-rpt .environment{color:#e1e8f2;font-size:12px;white-space:nowrap}.app-rpt .environment span{color:var(--lime);margin-right:6px}
.app-rpt .doc{max-width:none;margin:0;background:transparent;box-shadow:none;border-radius:0;overflow:visible}
.app-rpt .apphead,.app-rpt .pad,.app-rpt .wrap{max-width:1440px;margin:0 auto;padding-left:32px;padding-right:32px}
.app-rpt .apphead{padding-top:30px}
.app-rpt .pad{padding-top:0;padding-bottom:36px}
.app-rpt .page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:14px}
.app-rpt .eyebrow{font-size:10px;letter-spacing:1.9px;font-weight:800;color:var(--acc2);margin:0 0 8px}
.app-rpt .page-heading h1{font-size:29px;font-weight:800;letter-spacing:-1px;margin:0 0 8px;color:var(--ink)}
.app-rpt .page-heading p.desc{color:var(--soft);margin:0;line-height:1.6;font-size:13.5px}
.app-rpt .badges{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}
.app-rpt .connection{font-size:12px;background:#e9eef5;color:#465b77;border-radius:20px;padding:7px 11px;white-space:nowrap}
.app-rpt .connection.connected{background:#d6f2e6;color:#0b5e46}.app-rpt .connection.warn{background:#fdf0d5;color:#8a5a00}
.app-rpt .stamp{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;font-size:12.5px;color:var(--soft);background:#f6f8fb;border:1px solid var(--line);border-radius:8px;padding:9px 14px;margin:0 0 10px}
.app-rpt .stamp b{color:var(--navy);margin-right:4px}
.app-rpt details.scope{font-size:12px;color:var(--soft);margin:0 0 14px}
.app-rpt details.scope summary{cursor:pointer;font-weight:700;color:var(--blue);font-size:12.5px}
.app-rpt details.scope p{margin:6px 0 0;line-height:1.7}
.app-rpt .appfoot{display:flex;justify-content:space-between;gap:18px;padding:14px 32px;border-top:1px solid var(--line);color:var(--soft);font-size:11px;background:transparent}
/* 큰 탭(앱의 maintabs) */
.app-rpt .metricnav{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0 18px;padding:0;background:var(--bg);border:0;border-bottom:1px solid var(--line);border-radius:0;position:sticky;top:0;z-index:5}
.app-rpt .mbtn{border:0;border-radius:10px 10px 0 0;border-bottom:3px solid transparent;background:transparent;color:#596a81;font:inherit;font-size:15px;font-weight:800;padding:12px 24px;cursor:pointer;transition:background .18s,color .18s,border-color .18s}
.app-rpt .mbtn:hover{background:#e6edf2;color:var(--navy);border-color:transparent}
.app-rpt .mbtn.on{background:#eafaf3;color:var(--navy);border-bottom-color:var(--lime)}
.app-rpt .mbtn.help{color:var(--acc2);border-color:transparent;background:transparent}
.app-rpt .mbtn.help.on{background:#eafaf3;color:var(--navy);border-bottom-color:var(--lime)}
.app-rpt .mbtn:active{transform:none}
/* 흰 패널 */
.app-rpt section.metric,.app-rpt .panel{background:#fff;border:1px solid var(--line);border-radius:12px;padding:23px;box-shadow:var(--sh1);min-width:0;animation:none}
.app-rpt h2{font-size:18px;font-weight:800;letter-spacing:-.5px;color:var(--ink);margin:30px 0 4px;padding:0;border:0}
.app-rpt section.metric>h2:first-child,.app-rpt section.metric>div:first-child>h2:first-child,.app-rpt .panel>h2:first-child{margin-top:0}
.app-rpt h2 .mtag{font-size:12px;font-weight:700;color:var(--faint);margin-left:6px;letter-spacing:0}
.app-rpt .sub{color:var(--soft);font-size:12.5px;margin:2px 0 12px;line-height:1.6}
.app-rpt .info{font-size:12px;color:var(--soft)}
/* 지표 카드(앱의 kpib) */
.app-rpt .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:4px 0 18px}
.app-rpt .kpi{display:flex;flex-direction:column;align-items:flex-start;text-align:left;gap:2px;background:#fff;border:1px solid var(--line);border-top:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--sh1);transition:box-shadow .18s,transform .18s}
.app-rpt .kpi:hover{transform:translateY(-1px);box-shadow:var(--sh2)}
.app-rpt .kpi .l{order:-1;font-size:12px;font-weight:800;color:#51647e;margin:0 0 2px;line-height:1.45}
.app-rpt .kpi .n{font-size:28px;font-weight:800;letter-spacing:-1px;line-height:1.25;color:var(--navy);font-variant-numeric:tabular-nums}
.app-rpt .kpi .u{font-size:12px;font-weight:700;color:var(--soft);margin-left:5px;letter-spacing:0}
.app-rpt .kpi .s{font-size:11.5px;color:var(--soft);margin:0}
.app-rpt .kpi.t .n{color:#0b5e46}.app-rpt .kpi.a .n{color:#8a5a00}.app-rpt .kpi.r .n{color:#a33820}
/* 그래프 카드 · 안내 상자 */
.app-rpt .chartbox,.app-rpt .bvapp .chartcard{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:#fff;margin:0 0 16px;box-shadow:none}
.app-rpt .chartbox:hover{box-shadow:none}
.app-rpt .bvapp .ch h3{font-size:15px;color:var(--ink)}
.app-rpt .note{border:1px solid #a7e0cb;border-left-width:1px;background:var(--teal-bg);border-radius:10px;padding:12px 16px;margin:12px 0;font-size:12.5px;line-height:1.75;color:#3f4b5a}
.app-rpt .note .t{display:block;font-size:12px;font-weight:800;letter-spacing:.3px;margin-bottom:4px;color:#0b5e46}
.app-rpt .note.navy{background:#eaf0f6;border-color:#d3dfeb}.app-rpt .note.navy .t{color:var(--blue)}
.app-rpt .note.amber{background:#fffbea;border-color:#f1d38a;color:#5a4a1a}.app-rpt .note.amber .t{color:#8a5a00}
.app-rpt .note.rust{background:#fff4e7;border-color:#e9c39a;color:#79471c}.app-rpt .note.rust .t{color:#a33820}
.app-rpt .note.slate{background:var(--band);border-color:var(--line)}.app-rpt .note.slate .t{color:var(--slate)}
.app-rpt aside{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:18px 0 0;box-shadow:var(--sh1)}
.app-rpt aside h2{font-size:15px;margin:0 0 6px}
.app-rpt aside li{font-size:12.5px;color:var(--soft)}
.app-rpt .foot{margin-top:18px;padding-top:12px;border-top:1px solid var(--line);font-size:11.5px;color:var(--soft)}
/* 표(앱과 같은 머리 · 줄) */
.app-rpt table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px;margin:8px 0;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.app-rpt th,.app-rpt td{border:0;border-bottom:1px solid #e4eaf1;border-right:1px solid #edf1f5;padding:8px 11px;vertical-align:top;line-height:1.55}
.app-rpt th:last-child,.app-rpt td:last-child{border-right:0}
.app-rpt tbody tr:last-child td,.app-rpt tbody tr:last-child th{border-bottom:0}
.app-rpt thead th{background:#edf2f7;color:#425872;font-weight:700;font-size:12px;position:sticky;top:0;z-index:1;white-space:nowrap;overflow-wrap:normal}
.app-rpt td{overflow-wrap:normal}
.app-rpt .modal .tscroll td{white-space:nowrap}
.app-rpt .lots td{min-width:0}
.app-rpt tbody tr:nth-child(even) td{background:#fafbfd}
.app-rpt tbody tr:hover td{background:#effaf5}
.app-rpt table.sortable th:hover{filter:none;background:#e3eaf2}
.app-rpt tr.total td{background:#eaf0f6!important;font-weight:700}
.app-rpt tr.grouphead td{background:var(--band)!important;color:var(--ink);font-weight:800}
.app-rpt .tscroll{border-radius:8px}
.app-rpt .tscroll>table,.app-rpt .scroll>table{margin:0}
.app-rpt table.map{border-radius:0;border:1px solid var(--line);font-size:11.5px;width:auto}
.app-rpt table.map th,.app-rpt table.map td{padding:3px 8px;border-bottom:1px solid #edf1f5;border-right:1px solid #edf1f5;white-space:nowrap;vertical-align:middle}
.app-rpt table.map thead th{background:#edf2f7;color:#425872;text-align:center;font-size:11px;line-height:1.3}
.app-rpt table.map tbody tr:nth-child(even) td{background:transparent}
.app-rpt .c-p{background:#e8f7f0!important;color:#0b5e46}.app-rpt .c-e{background:#fdeae5!important;color:#a33820;font-weight:700}
.app-rpt .c-c{background:#fdf3df!important;color:#8a5a00}.app-rpt .c-s{background:#f1e4fa!important;color:#6b2c91;font-weight:700}
.app-rpt .c-pick{box-shadow:inset 0 0 0 2px var(--blue)}
/* 단추 · 칩 · 입력(앱과 같은 모양) */
.app-rpt button{font-family:inherit}
.app-rpt .periodnav{display:inline-flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff}
.app-rpt .periodnav button{border:0;border-radius:0;background:#fff;color:var(--navy);padding:6px 14px;font-size:12.5px;font-weight:700}
.app-rpt .periodnav button+button{border-left:1px solid var(--line)}
.app-rpt .periodnav button.on{background:var(--navy);color:#fff}
.app-rpt .bvapp .seg button.on,.app-rpt .bvapp .mtabs button.on{background:var(--navy);border-color:var(--navy);color:#fff}
.app-rpt .bvapp .pilltabs{display:inline-flex;gap:4px;background:#e3e9ef;border-radius:999px;padding:4px;margin:4px 0 14px}
.app-rpt .bvapp .pilltabs button{border:0;border-radius:999px;background:transparent;color:#52647d;padding:8px 18px}
.app-rpt .bvapp .pilltabs button.on{background:#fff;color:var(--navy);box-shadow:var(--sh1)}
.app-rpt .bvapp .lgd button{border-radius:8px}
.app-rpt .bvapp .st,.app-rpt .pill{display:inline-block;font-size:11px;font-weight:800;padding:2px 9px;border-radius:999px;white-space:nowrap}
.app-rpt .bvapp .st.done,.app-rpt .pill.ok{background:#d6f2e6;color:#0b5e46}
.app-rpt .bvapp .st.re,.app-rpt .pill.rec{background:#fdf0d5;color:#8a5a00}
.app-rpt .bvapp .st.open,.app-rpt .pill.bad{background:#fde4dc;color:#a33820}
.app-rpt .pill.mv{background:#e5ecf6;color:#31517c}.app-rpt .pill.dup{background:#eef1f5;color:#52647d}
.app-rpt .bvapp .chip,.app-rpt .jf-chip{border-color:var(--line)}
.app-rpt .jobfilter{background:var(--band);border-color:var(--line);border-radius:10px}
.app-rpt .jf-chip.on{background:#eafaf3;border-color:var(--lime)}.app-rpt .jf-chip.on i{background:var(--acc2);border-color:var(--acc2)}
.app-rpt input[type=search],.app-rpt select{border:1px solid #bac7d6;border-radius:6px;padding:7px 10px;font:inherit;font-size:12.5px;color:var(--navy);background:#fff}
.app-rpt .lotlink,.app-rpt td .lotlink{color:var(--blue);border-bottom-color:var(--blue)}
/* 창(앱의 edit-dialog · Lot 창) */
.app-rpt .ovl{background:#1f293766;backdrop-filter:blur(3px)}
.app-rpt .modal{border-radius:16px;border:1px solid var(--line);box-shadow:var(--sh2)}
.app-rpt .modal .mhead{background:var(--band);color:var(--ink);border-bottom:1px solid var(--line);border-radius:16px 16px 0 0;padding:16px 22px}
.app-rpt .modal .mhead h3{font-size:18px;font-weight:800;color:var(--ink)}
.app-rpt .modal .mhead .x{color:var(--soft);opacity:1;border:1px solid var(--line);background:#fff;border-radius:8px;width:34px;height:34px;font-size:20px}
.app-rpt .modal .mbody{padding:18px 22px}
.app-rpt .modal .mbody .job{background:#eef2f6;color:var(--blue)}
/* Lot 추적 */
.app-rpt .qbtn{border:1px solid var(--line);color:var(--navy);background:#fff;border-radius:8px;padding:8px 14px;font-weight:700;font-size:12.5px}
.app-rpt .qbtn:hover,.app-rpt .qbtn[aria-expanded=true]{background:#edf2f6;color:var(--navy)}
.app-rpt .crit{background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:var(--sh1);margin:0 0 14px}
.app-rpt .crit dt{color:var(--navy)}
.app-rpt .filters{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.app-rpt .lots tbody tr:hover td{background:#e9f7f0}
.app-rpt .bunch{border-radius:10px}.app-rpt .bunch>.bh{background:var(--band)}
.app-rpt .att .n{color:var(--blue)}
.app-rpt .att .rawbtn{margin-left:auto;font-size:11.5px;font-weight:700;color:var(--navy);background:#fff;border:1px solid var(--line);border-radius:6px;padding:2px 10px;cursor:pointer}
.app-rpt .att .rawbtn:hover{background:#edf2f6;border-color:#b3c0cc}
.app-rpt .v-ok{color:#0b5e46}.app-rpt .v-re{color:#8a5a00}.app-rpt .v-dup{color:var(--blue)}.app-rpt .v-open{color:#a33820}
/* Batch Report 원문 창 */
.app-rpt #rawovl{z-index:70}
.app-rpt .rawwin{max-width:1180px}
.app-rpt .rawwin .step{font-size:11px;font-weight:800;letter-spacing:.4px;color:#667990;display:block;margin-bottom:2px}
.app-rpt .rawfile{margin:0 0 4px;font-family:Consolas,monospace;font-size:12px;color:#465b77;overflow-wrap:anywhere}
.app-rpt .rawgrid{display:grid;grid-template-columns:minmax(0,330px) minmax(0,1fr);gap:16px;margin-top:10px}
.app-rpt .rawgrid>div{max-height:62vh;overflow:auto;border:1px solid var(--line);border-radius:7px}
.app-rpt .rawgrid table{margin:0;border:0;border-radius:0}
.app-rpt .rawmeta th{background:#edf2f7;color:#425872;white-space:nowrap;width:130px;position:static}
.app-rpt .rawnote{font-size:11.5px;color:var(--soft);margin:8px 2px 0}
/* WPH 통합 */
.app-rpt.wph .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:4px 0 18px}
.app-rpt.wph .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--sh1)}
.app-rpt.wph .card .k{font-size:12px;font-weight:800;color:#51647e}
.app-rpt.wph .card .v{font-size:28px;font-weight:800;letter-spacing:-1px;color:var(--navy);margin-top:2px;font-variant-numeric:tabular-nums}
.app-rpt.wph .card .u{font-size:12px;color:var(--soft);font-weight:700;margin-left:5px;letter-spacing:0}
.app-rpt.wph section{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 23px;margin-bottom:18px;box-shadow:var(--sh1)}
.app-rpt.wph section>h2{font-size:16px;margin:0 0 12px;display:flex;align-items:center;gap:8px}
.app-rpt.wph .tag{font-size:11px;font-weight:800;border-radius:999px;padding:2px 9px;background:#e5ecf6;color:#31517c}
.app-rpt.wph .tag.e{background:#fde4dc;color:#a33820}.app-rpt.wph .tag.w{background:#fdf0d5;color:#8a5a00}
.app-rpt.wph th,.app-rpt.wph td{text-align:right;white-space:nowrap}
.app-rpt.wph th:first-child,.app-rpt.wph td:first-child,.app-rpt.wph th.l,.app-rpt.wph td.l{text-align:left}
.app-rpt.wph tfoot td{font-weight:800;background:#eaf0f6}
.app-rpt.wph .note{background:transparent;border:0;padding:0;margin:10px 0 0;font-size:12px;color:var(--soft)}
.app-rpt.wph .scroll{overflow-x:auto;border-radius:8px}
.app-rpt.wph footer{display:none}
@media(max-width:760px){.app-rpt .topbar{padding:16px 18px}.app-rpt .environment{display:none}
.app-rpt .apphead,.app-rpt .pad,.app-rpt .wrap{padding-left:16px;padding-right:16px}
.app-rpt .page-heading{flex-direction:column}.app-rpt .page-heading h1{font-size:24px}.app-rpt .badges{justify-content:flex-start}
.app-rpt .mbtn{padding:10px 14px;font-size:13.5px}.app-rpt section.metric,.app-rpt .panel{padding:16px}
.app-rpt .rawgrid{grid-template-columns:1fr}.app-rpt .appfoot{flex-direction:column;padding:14px 16px}}
@media print{.app-rpt .topbar,.app-rpt .metricnav{display:none}.app-rpt section.metric{box-shadow:none}}
"""


def page_top(*, title, sub, eyebrow, desc='', badges=(), stamp=(), scope=''):
    """앱과 같은 상단 바 + 제목 영역. badges: [(글자, 'connected'|'warn'|'')], stamp: [(이름, 값)]."""
    badge_html = ''.join(f'<span class="connection {c}">{_esc(t)}</span>' for t, c in badges)
    stamp_html = ''.join(f'<span><b>{_esc(k)}</b>{_esc(v)}</span>' for k, v in stamp)
    scope_html = (f'<details class="scope"><summary>조사 범위 보기</summary><p>{_esc(scope)}</p></details>' if scope else '')
    return (f'<header class="topbar"><span class="brand"><span class="brand-icon">C</span><span>Camtek <b>AOI Manager</b>'
            f'<small>{_esc(sub)}</small></span></span><div class="environment"><span>●</span>오프라인 결과 파일 · 원본 Batch Report 읽기 전용</div></header>'
            f'<div class="apphead"><div class="page-heading"><div><p class="eyebrow">{_esc(eyebrow)}</p><h1>{_esc(title)}</h1>'
            + (f'<p class="desc">{_esc(desc)}</p>' if desc else '') + f'</div><div class="badges">{badge_html}</div></div>'
            + (f'<div class="stamp">{stamp_html}</div>' if stamp_html else '') + scope_html + '</div>')


def page_foot(left, right=''):
    return f'<footer class="appfoot"><span>{_esc(left)}</span><span>{_esc(right)}</span></footer>'


# ---------------------------------------------------------------- Batch Report 원문 창
def raw_blob(view):
    """조사의 Batch Report 원문 표 전부 → gzip + base64 글자(g 순서). [파일, 호기, Batch Info [[k, v]], 머리, 행]."""
    out = []
    for g in range(len(view.records)):
        r = view.raw(g)
        out.append([r['f'], r['m'], r['meta'], r['h'], r['rows']])
    data = json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(gzip.compress(data, compresslevel=6, mtime=0)).decode('ascii')


RAW_HTML = """<div class="ovl" id="rawovl" role="dialog" aria-modal="true" aria-labelledby="rawt"><div class="modal rawwin">
<div class="mhead"><h3 id="rawt"><span class="step">Batch Report 원문 창</span>Batch Report 원문 — 스캔 1번(Batch Report 1장)의 표 그대로</h3><button class="x" id="rawx" aria-label="닫기">×</button></div>
<div class="mbody"><p class="rawfile" id="rawf"></p><p class="sub" id="raws"></p>
<div class="rawgrid"><div><table class="rawmeta"><tbody id="rawm"></tbody></table></div><div><table class="map"><thead id="rawh"></thead><tbody id="rawb"></tbody></table></div></div>
<p class="rawnote">이 결과 파일 안에 담아 둔 원문 표입니다(장비 Reports 폴더의 Batch Report 와 같은 값). 다른 컴퓨터에서도 열립니다.</p></div></div></div>"""

RAW_JS = r"""
(function(){
var el=document.getElementById('rawgz'),RAW=null,ovl=document.getElementById('rawovl');if(!el||!ovl)return;
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function load(){if(RAW)return Promise.resolve(RAW);
  if(typeof DecompressionStream==='undefined')return Promise.reject(new Error('이 브라우저는 원문 풀기를 지원하지 않습니다. Edge 또는 Chrome 으로 여세요.'));
  var b=atob(el.textContent.trim()),u=new Uint8Array(b.length);for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i);
  return new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream('gzip'))).text().then(function(t){RAW=JSON.parse(t);return RAW;});}
function show(g){document.getElementById('rawf').textContent='원문을 여는 중…';document.getElementById('raws').textContent='';
  document.getElementById('rawm').innerHTML='';document.getElementById('rawh').innerHTML='';document.getElementById('rawb').innerHTML='';ovl.classList.add('on');
  load().then(function(R){var r=R[g];if(!r){document.getElementById('rawf').textContent='Batch Report 를 찾지 못했습니다.';return;}
    var h=r[3],si=h.findIndex(function(x){return String(x).toLowerCase().replace(/[^a-z0-9]/g,'')==='passfail';});
    document.getElementById('rawf').textContent=r[0];document.getElementById('raws').textContent=r[1]+' · 원문 그대로(이 결과 파일에 담아 둔 표). 장비 원본은 수정하지 않습니다.';
    document.getElementById('rawm').innerHTML=r[2].map(function(kv){return '<tr><th>'+esc(kv[0])+'</th><td>'+esc(kv[1])+'</td></tr>';}).join('');
    document.getElementById('rawh').innerHTML='<tr><th>#</th>'+h.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')+'</tr>';
    document.getElementById('rawb').innerHTML=r[4].map(function(w,k){var ok=/^pass[.!]?$/i.test(String(w[si]||'').trim());
      return '<tr><th>'+(k+1)+'</th>'+w.map(function(x,j){return '<td'+(j===si?' class="'+(ok?'c-p':'c-e')+'"':'')+'>'+esc(x)+'</td>';}).join('')+'</tr>';}).join('');
  }).catch(function(e){document.getElementById('rawf').textContent=e.message;});}
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-raw]');if(b){e.preventDefault();e.stopPropagation();show(+b.getAttribute('data-raw'));}},true);
document.getElementById('rawx').onclick=function(){ovl.classList.remove('on');};
ovl.addEventListener('click',function(e){if(e.target===ovl)ovl.classList.remove('on');});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&ovl.classList.contains('on')){ovl.classList.remove('on');e.stopImmediatePropagation();}},true);
window.__showRaw=show;
})();
"""


def raw_parts(view):
    """(창 HTML, 데이터 script, 스크립트) — view 가 없으면 빈 글자(원문 창 없음)."""
    if view is None:
        return '', '', ''
    return RAW_HTML, f'<script type="application/octet-stream" id="rawgz">{raw_blob(view)}</script>', f'<script>{RAW_JS}</script>'
