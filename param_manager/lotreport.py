"""Batch Report Lot 추적 HTML (lotmodel 결과 → 오프라인 단일 .html).

파일·네트워크 접근 없음 — 메모리의 lotmodel.build 결과만 가공한다. 외부 라이브러리·CDN 없이
CSS/JS 를 모두 내장한다(기존 Batch Report 분석 HTML 과 같은 원칙). Lot 판정 기준 설명(CRITERIA)은
이 모듈 한 곳에서 관리하고 HTML 의 [? Lot 판정 기준] 과 앱 화면의 ? 버튼이 함께 쓴다.
"""
from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from datetime import datetime

from . import lotmodel as lm
from .batchreport_output import PAGE_CSS

# (제목, 설명, 예) — 앱 화면 ? 버튼(desktop_batch.describe → lot_criteria)과 HTML 이 같은 문구를 쓴다.
CRITERIA = [
    ("조사 단위", "Batch Report 1장 = 스캔 시도 1번입니다. 시도를 '묶음'으로, 묶음을 'Lot'으로 묶어 봅니다. "
     "Lot 하나가 Batch Report 여러 장으로 나뉘는 것이 보통입니다.", ""),
    ("S/M", "파일 이름에서 Job/Setup 뒤, 날짜 앞 문자열을 S/M으로 씁니다. 웨이퍼 Lot 칸이 전부 LoadPort여도 "
     "파일 이름에는 남아 있습니다.", "…0A_6392_KDT-PR RW_26-May-06_… → KDT-PR RW"),
    ("Lot 코드", "S/M 안에서 처음 나오는 영문 3글자 단어입니다. 호기마다 Job이나 S/M 꼬리가 달라도 이 3글자는 같습니다. "
     "3글자 단어가 없으면 점검 스캔으로 보고 Lot에서 뺍니다.", "BAW-0911S → BAW · 0701 N SPT … → SPT · 0, FOCUS → 점검 스캔"),
    ("Lot ID 확인", "Wafer ID가 SF14G25-A0 형식이면 앞 5자를 실제 Lot ID로 봅니다. 같은 코드라도 Lot ID가 다르면 "
     "다른 Lot입니다. 1글자만 다르면 ID 판독 오차로 같은 Lot입니다.", "BAH → SC93F · SA78K 두 Lot / SH47T ≈ SA47T"),
    ("묶음", f"한 번의 검사를 끝내려고 연달아 한 시도들입니다. 같은 호기에서 앞 시도 끝부터 다음 시도 시작까지 "
     f"{lm.SAME_MACHINE_GAP_H}시간 이하면 같은 묶음입니다.", "WBG 단계 · CMP 단계 · 재검사는 각각 다른 묶음"),
    ("호기 이동", f"다른 호기의 시도는 ① {lm.MOVE_GAP_H}시간 이내 ② 앞 묶음에 Pass 못 한 웨이퍼가 남음 "
     "③ 같은 공정 단계(Recipe(s))일 때만 같은 묶음으로 잇습니다. 시간만 보면 다음 공정 스캔과 구분되지 않기 때문입니다.",
     "AOI-9에서 3번 실패 → AOI-12에서 완료 = 한 묶음"),
    ("슬롯", "웨이퍼 표가 25행이면 1행 = 25번 … 25행 = 1번입니다(장비가 25→1 순으로 스캔). "
     "25행이 아니면 Wafer ID로 맞춥니다.", "Slot 14 · 14 · SF14G14-A0 → 14번"),
    ("Error 판정", "Pass/Fail 칸이 Pass가 아니면 빈칸을 포함해 전부 Error입니다. 문구가 여럿이면 첫 문구가 원인입니다.",
     "Scan 2D Error. Aborted. → 2D Scan 오류"),
    ("연쇄", "같은 Batch Report에서 앞에 오류가 있었으면 뒤따르는 Aborted · Skipped는 연쇄로 표시합니다. "
     "원인 집계에서는 연쇄를 따로 셉니다.", ""),
    ("웨이퍼 결과", "묶음 안에서 웨이퍼마다 한 번에 Pass · 재스캔 Pass(Error 뒤 다시 스캔해 Pass) · 중복 Pass(Pass 2번 이상) · "
     "Pass 없음(끝까지 Pass 못 함)으로 나눕니다. 묶음이 다르면 중복이 아닙니다.", ""),
    ("오류 표시", "오류는 Batch Report의 Pass/Fail 원문 그대로 보여 줍니다. 묶어서 셀 때만 첫 문구를 씁니다.", "Scan 2D Error. Aborted. → 첫 문구 Scan 2D Error."),
    ("중복 선택 · Dice 합계", "중복이면 가장 나중 Pass를 추천 선택합니다. Dice 합계는 웨이퍼마다 고른 행 하나만 더합니다.", ""),
    ("한계", "Lot ID가 없는 스캔(WBG 숫자 ID)끼리는 같은 3글자를 다른 Lot이 다시 써도 구분할 수 없습니다. "
     "호기 이동은 조사에 포함된 호기의 Batch Report끼리만 이어집니다.", ""),
]

def _t(value):
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else (value or "")


def _esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


RECOVERED, UNRESOLVED, DUPLICATE, OK = lm.RECOVERED, lm.UNRESOLVED, lm.DUPLICATE, lm.OK
VERDICTS = (OK, RECOVERED, DUPLICATE, UNRESOLVED)


def cause_summary(model):
    """오류 첫 문구(원문)별: 영향 Lot 수, 웨이퍼 수, 그중 연쇄, 그 뒤 Pass / Pass 없음."""
    rows = defaultdict(lambda: {"lots": set(), "wafers": 0, "chain": 0, "passed": 0, "open": 0})
    for lot in model["lots"]:
        for bunch in lot["bunches"]:
            for w in bunch["wafers"]:
                if not w["cause"]:
                    continue
                item = rows[w["cause"]]
                item["lots"].add(lot["key"])
                item["wafers"] += 1
                item["chain"] += w["chain_only"]
                item["open" if w["verdict"] == UNRESOLVED else "passed"] += 1
    out = [{"cause": k, "lots": len(v["lots"]), "wafers": v["wafers"], "chain": v["chain"],
            "passed": v["passed"], "open": v["open"]} for k, v in rows.items()]
    return sorted(out, key=lambda r: (-r["lots"], -r["wafers"]))


def to_data(model):
    """HTML 에 넣을 JSON(시각은 문자열). 상태는 원문 그대로."""
    lots = []
    for lot in model["lots"]:
        bunches = []
        for b in lot["bunches"]:
            attempts = [{"machine": a["machine"], "file": a["file"], "path": a["source_folder"], "sm": a["sm"],
                         "step": a["step"], "start": _t(a["start"]), "end": _t(a["end"]), "rows": len(a["rows"]),
                         "pass": sum(r["pass"] for r in a["rows"]), "lot_id": a["lot_id"] or ""}
                        for a in b["attempts"]]
            wafers = [{"slot": w["slot"], "id": w["wafer_id"], "pick": w["pick"], "v": w["verdict"],
                       "cause": w["cause"], "chain": w["chain_only"], "dice": w["dice"],
                       "cells": [[c["attempt"], c["status"] or "(빈 칸)", 1 if c["pass"] else 0, 1 if c["kind"] == "연쇄" else 0]
                                 for c in w["cells"]]}
                      for w in b["wafers"]]
            tot = b["totals"]
            bunches.append({"start": _t(b["start"]), "end": _t(b["end"]), "step": b["step"], "moved": b["moved"],
                            "machines": b["machines"], "hours": round(b["batch_sec"] / 3600, 2),
                            "counts": b["counts"], "attempts": attempts, "wafers": wafers,
                            "totals": {"scanned": tot["scanned"], "bad": tot["bad"], "good": tot["good"],
                                       "yield": round(tot["yield"], 2) if tot["yield"] is not None else None,
                                       "missing": tot["missing"]}})
        causes = Counter(w["cause"] for b in lot["bunches"] for w in b["wafers"] if w["cause"])
        lots.append({"key": lot["key"], "label": lot["label"], "code": lot["code"], "lot_id": lot["lot_id"] or "",
                     "sms": lot["sms"], "jobs": lot["jobs"], "machines": lot["machines"], "attempts": lot["attempts"],
                     "start": _t(lot["start"]), "end": _t(lot["end"]), "state": lot["state"],
                     "unresolved": lot["unresolved"], "duplicates": lot["duplicates"], "moved": lot["moved"],
                     "causes": [f"{k} ×{n}" for k, n in causes.most_common(3)], "bunches": bunches})
    excluded = [{"machine": a["machine"], "sm": a["sm"], "file": a["file"], "start": _t(a["start"]),
                 "rows": len(a["rows"])} for a in model["excluded"]]
    return {"lots": lots, "excluded": excluded, "causes": cause_summary(model)}


LOT_CSS = """
.doc{max-width:1180px}
.hbar{display:flex;align-items:flex-start;gap:12px}.hbar h1{flex:1}
.qbtn{border:1.5px solid var(--teal);color:var(--teal);background:#fff;border-radius:999px;padding:6px 14px;font:inherit;font-weight:800;font-size:12.5px;cursor:pointer;white-space:nowrap}
.qbtn:hover,.qbtn[aria-expanded=true]{background:var(--teal);color:#fff}
.crit{display:none;margin:18px 0 4px;border:1px solid var(--line);border-radius:14px;background:var(--teal-bg);padding:14px 18px}
.crit.on{display:block}
.crit dl{display:grid;grid-template-columns:150px 1fr;gap:8px 16px;margin:0}
.crit dt{font-weight:800;color:var(--teal);font-size:13px}.crit dd{margin:0;font-size:13px}
.crit dd small{display:block;color:var(--soft);font-family:Consolas,monospace;font-size:11.5px;margin-top:2px}
.kpis{grid-template-columns:repeat(4,1fr)}
.filters{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:14px 0 6px;padding:12px;background:var(--slate-bg);border:1px solid var(--line);border-radius:12px}
.filters input[type=search]{flex:1;min-width:180px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font:inherit}
.filters select{padding:6px 8px;border:1px solid var(--line);border-radius:8px;font:inherit}
.filters label{font-size:12.5px;color:var(--soft);display:flex;align-items:center;gap:4px}
.count{font-size:12px;color:var(--faint);margin-left:auto}
.tscroll{overflow-x:auto}.tscroll>table{min-width:860px}
.lots tbody tr{cursor:pointer}.lots tbody tr:hover td{background:var(--navy-bg)}
.pill{display:inline-block;font-size:11px;font-weight:800;padding:1px 8px;border-radius:999px;white-space:nowrap}
.pill.ok{background:var(--teal-bg);color:var(--teal)}.pill.rec{background:var(--amber-bg);color:var(--amber)}
.pill.bad{background:var(--rust-bg);color:var(--rust)}.pill.mv{background:var(--navy-bg);color:var(--navy)}
.pill.dup{background:var(--slate-bg);color:var(--slate)}
.modal{max-width:1180px}
.mbody h4{font-size:14px;color:var(--navy);margin:18px 0 6px}
.bunch{border:1px solid var(--line);border-radius:14px;margin:14px 0;overflow:hidden}
.bunch>.bh{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;padding:10px 14px;background:var(--slate-bg);font-size:12.5px;color:var(--soft)}
.bunch>.bh b{color:var(--ink);font-size:13.5px}
.bunch .inner{padding:10px 14px}
.att{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;font-size:12px;padding:4px 0;border-bottom:1px dashed var(--line2)}
.att .n{font-weight:800;color:var(--navy);min-width:26px}
.att code{font-family:Consolas,monospace;font-size:11.5px;color:var(--soft)}
.att a,.att span.dis{margin-left:auto;font-size:11.5px;font-weight:800;color:var(--navy);text-decoration:none;border:1px solid var(--navy);border-radius:6px;padding:1px 8px}
.att span.dis{color:var(--faint);border-color:var(--line)}
.mapwrap{overflow-x:auto;margin-top:10px}
table.map{width:auto;min-width:0;border-radius:0;font-size:11.5px;margin:0}
table.map th,table.map td{padding:2px 7px;border:1px solid var(--line2);white-space:nowrap}
table.map thead th{position:static;background:var(--navy);font-size:11px;line-height:1.3;text-align:center}
table.map thead th small{display:block;font-weight:400;opacity:.8}
table.map tbody tr:nth-child(even) td{background:transparent}
table.map td.n{text-align:right;font-variant-numeric:tabular-nums}
.c-p{background:var(--teal-bg)!important;color:var(--teal)}.c-e{background:var(--rust-bg)!important;color:var(--rust);font-weight:700}
.c-c{background:var(--amber-bg)!important;color:var(--amber)}.c-n{color:#c4cbd4;text-align:center}
.c-pick{box-shadow:inset 0 0 0 2px var(--navy)}.c-drop{text-decoration:line-through;opacity:.55}
.v-ok{color:var(--teal)}.v-re{color:var(--amber);font-weight:800}.v-dup{color:var(--navy);font-weight:800}.v-open{color:var(--rust);font-weight:800}
.mkeys{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:11.5px;color:var(--soft);margin:8px 0}
.mkeys i{font-style:normal;padding:0 5px;border-radius:3px}
@media(max-width:720px){.crit dl{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}}
"""

LOT_JS = r"""
(function(){
var D=window.__LOTDATA,L=D.lots,V=['한 번에 Pass','재스캔 Pass','중복 Pass','Pass 없음'],VC={'한 번에 Pass':'v-ok','재스캔 Pass':'v-re','중복 Pass':'v-dup','Pass 없음':'v-open'};
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function num(v){return v==null?'—':(Math.round(v*100)/100).toLocaleString();}
function pill(l){var c=l.state==='Pass 못 한 웨이퍼 있음'?'bad':l.state==='재스캔으로 완료'?'rec':'ok',h='<span class="pill '+c+'">'+esc(l.state)+'</span>';
 if(l.duplicates)h+=' <span class="pill dup">중복 Pass '+l.duplicates+'</span>';if(l.moved)h+=' <span class="pill mv">호기 이동</span>';return h;}
var q=document.getElementById('q'),st=document.getElementById('st'),mc=document.getElementById('mc'),
    fd=document.getElementById('fd'),fm=document.getElementById('fm'),fs=document.getElementById('fs'),body=document.getElementById('lotbody'),cnt=document.getElementById('cnt');
var ms={};L.forEach(function(l){l.machines.forEach(function(m){ms[m]=1;});});
Object.keys(ms).sort().forEach(function(m){var o=document.createElement('option');o.value=m;o.textContent=m;mc.appendChild(o);});
var last='';
function draw(){
 var t=q.value.trim().toUpperCase(),rows=[],n=0;
 // 같은 조건이면 다시 그리지 않는다 — 검색칸 blur(change)로 표가 바뀌면 그 순간의 행 클릭이 사라진다.
 var key=[t,st.value,mc.value,fd.checked,fm.checked,fs.checked].join('|');if(key===last)return;last=key;
 L.forEach(function(l,i){
  if(t&&(l.label+' '+l.sms.join(' ')+' '+l.lot_id+' '+l.jobs.join(' ')).toUpperCase().indexOf(t)<0)return;
  if(st.value&&l.state!==st.value)return;if(mc.value&&l.machines.indexOf(mc.value)<0)return;
  if(fd.checked&&!l.duplicates)return;if(fm.checked&&!l.moved)return;if(fs.checked&&!l.bunches.some(function(b){return b.attempts.length>1;}))return;
  n++;rows.push('<tr data-i="'+i+'"><td><b>'+esc(l.label)+'</b></td><td>'+esc(l.sms.join(', '))+'</td><td>'+esc(l.machines.join(' → '))+
   '</td><td>'+l.bunches.length+'</td><td>'+l.attempts+'</td><td>'+esc(l.start)+'</td><td>'+pill(l)+'</td><td>'+(l.unresolved||'')+
   '</td><td>'+esc(l.causes.join(' · '))+'</td></tr>');});
 body.innerHTML=rows.join('')||'<tr><td colspan="9">조건에 맞는 Lot이 없습니다.</td></tr>';cnt.textContent=n+' / '+L.length+' Lot';}
q.addEventListener('input',draw);[st,mc,fd,fm,fs].forEach(function(el){el.addEventListener('change',draw);});
body.addEventListener('click',function(e){var tr=e.target.closest('tr[data-i]');if(tr)openLot(+tr.getAttribute('data-i'));});
function fileUrl(a){return a.path?('file:///'+(a.path+'/'+a.file).replace(/\\/g,'/')):'';}
// ① Lot 취합 표 — 묶음마다 한 행(공정 단계가 다른 묶음을 더하면 같은 웨이퍼가 두 번 들어가므로 따로).
function summaryTable(l){
 var h='<div class="tscroll"><table><thead><tr><th>묶음</th><th>공정 단계</th><th>기간</th><th>호기</th><th>시도</th><th>웨이퍼</th>'+V.map(function(v){return '<th>'+v+'</th>';}).join('')+
  '<th>Scanned</th><th>Bad</th><th>Good</th><th>Yield</th></tr></thead><tbody>';
 l.bunches.forEach(function(b,i){var c=b.counts,t=b.totals;
  h+='<tr><td><b>묶음 '+(i+1)+'</b></td><td>'+esc(b.step)+'</td><td>'+esc(b.start)+' ~ '+esc(b.end.slice(5))+'</td><td>'+esc(b.machines.join(' → '))+(b.moved?' <span class="pill mv">호기 이동</span>':'')+
   '</td><td>'+b.attempts.length+'</td><td>'+b.wafers.length+'</td>'+V.map(function(v){return '<td class="'+VC[v]+'">'+(c[v]||'')+'</td>';}).join('')+
   '<td>'+num(t.scanned)+'</td><td>'+num(t.bad)+'</td><td>'+num(t.good)+'</td><td>'+(t.yield==null?'—':t.yield+'%')+'</td></tr>';});
 return h+'</tbody></table></div>';}
// ② 웨이퍼 취합 표 — 슬롯마다 묶음별 최종 결과(고른 Batch Report 의 원문)와 Dice.
function waferTable(l){
 var slots={},keys=[];l.bunches.forEach(function(b,bi){b.wafers.forEach(function(w){var k=w.slot==null?'ID '+w.id:w.slot;if(!slots[k]){slots[k]={};keys.push(k);}slots[k][bi]=w;});});
 keys.sort(function(a,b){return (typeof b==='number'?b:-1)-(typeof a==='number'?a:-1);});
 var h='<div class="mapwrap"><table class="map"><thead><tr><th rowspan="2">슬롯</th><th rowspan="2">Wafer ID</th>';
 l.bunches.forEach(function(b,i){h+='<th colspan="5">묶음 '+(i+1)+' · '+esc(b.step)+'<small>'+esc(b.start.slice(5))+'</small></th>';});
 h+='</tr><tr>';l.bunches.forEach(function(){h+='<th>결과</th><th>선택</th><th>Scanned</th><th>Bad</th><th>Good</th>';});h+='</tr></thead><tbody>';
 keys.forEach(function(k){var row=slots[k],id='';l.bunches.forEach(function(b,bi){if(row[bi]&&/[A-Za-z]/.test(row[bi].id)&&!/^Slot/i.test(row[bi].id))id=row[bi].id;});
  h+='<tr><th>'+esc(k)+'</th><td>'+esc(id||(row[0]||row[Object.keys(row)[0]]).id)+'</td>';
  l.bunches.forEach(function(b,bi){var w=row[bi];if(!w){h+='<td class="c-n" colspan="5">·</td>';return;}
   var picked=w.pick==null?null:w.cells.filter(function(c){return c[0]===w.pick;})[0];
   h+='<td class="'+VC[w.v]+'">'+esc(picked?picked[1]:(w.cells[w.cells.length-1]||[])[1])+(w.v!=='한 번에 Pass'?' <small>('+esc(w.v)+')</small>':'')+'</td><td>'+(w.pick==null?'—':'#'+(w.pick+1))+'</td>'+
    '<td class="n">'+num(w.dice&&w.dice[0])+'</td><td class="n">'+num(w.dice&&w.dice[1])+'</td><td class="n">'+num(w.dice&&w.dice[2])+'</td>';});
  h+='</tr>';});
 return h+'</tbody></table></div>';}
function bunchHtml(b,bi){
 var h='<div class="bunch"><div class="bh"><b>묶음 '+(bi+1)+'</b><span>'+esc(b.start)+' ~ '+esc(b.end)+'</span><span>공정 단계 '+esc(b.step||'—')+
  '</span><span>'+esc(b.machines.join(' → '))+'</span><span>시도 '+b.attempts.length+'회 · 스캔 '+b.hours+'h</span>'+(b.moved?'<span class="pill mv">호기 이동</span>':'')+'</div><div class="inner">';
 b.attempts.forEach(function(a,ai){var u=fileUrl(a);
  h+='<div class="att"><span class="n">#'+(ai+1)+'</span><span>'+esc(a.start)+' ~ '+esc(a.end.slice(11))+'</span><b>'+esc(a.machine)+'</b><span>S/M '+esc(a.sm)+'</span><span>'+esc(a.step)+
   '</span><span>Pass '+a.pass+' / '+a.rows+'행</span><code>'+esc(a.file)+'</code>'+(u?'<a href="'+esc(u)+'" target="_blank" rel="noopener">원문 열기</a>':'<span class="dis">원문(경로 없음)</span>')+'</div>';});
 var head='<tr><th>슬롯</th><th>Wafer ID</th>';b.attempts.forEach(function(a,ai){head+='<th>#'+(ai+1)+'<small>'+esc(a.machine)+' '+esc(a.start.slice(5))+'</small></th>';});
 head+='<th>결과</th><th>첫 오류 원문</th></tr>';var rows='';
 b.wafers.forEach(function(w){var cells=[],k;for(k=0;k<b.attempts.length;k++)cells.push('<td class="c-n">·</td>');
  var passes=w.cells.filter(function(c){return c[2];}).length;
  w.cells.forEach(function(c){var cls=c[2]?'c-p':c[3]?'c-c':'c-e';if(c[2]&&passes>1)cls+=c[0]===w.pick?' c-pick':' c-drop';
   cells[c[0]]='<td class="'+cls+'">'+esc(c[1])+'</td>';});
  rows+='<tr><th>'+(w.slot==null?'?':w.slot)+'</th><td>'+esc(w.id)+'</td>'+cells.join('')+'<td class="'+VC[w.v]+'">'+esc(w.v)+'</td><td>'+esc(w.cause)+(w.chain?' <small>(이 오류 뒤 연쇄)</small>':'')+'</td></tr>';});
 return h+'<div class="mapwrap"><table class="map"><thead>'+head+'</thead><tbody>'+rows+'</tbody></table></div></div></div>';}
var ovl=document.getElementById('ovl'),mt=document.getElementById('mt'),mb=document.getElementById('mb');
function openLot(i){var l=L[i];mt.textContent=l.label+' — '+l.state;
 mb.innerHTML='<div class="job">'+esc(l.jobs.join(' / '))+'</div><div class="info">S/M '+esc(l.sms.join(', '))+(l.lot_id?' · Lot ID '+esc(l.lot_id):'')+' · 호기 '+esc(l.machines.join(' → '))+' · 시도 '+l.attempts+'회</div>'+
  '<h4>Lot 취합</h4>'+summaryTable(l)+'<h4>웨이퍼 취합</h4>'+waferTable(l)+
  '<h4>시도 이력 · Lot × 웨이퍼 오류 지도</h4><div class="mkeys"><span><i class="c-p">Pass</i></span><span><i class="c-e">오류 원문</i> 직접 오류</span><span><i class="c-c">Aborted.</i> 앞 오류 뒤 연쇄</span><span><i class="c-p c-pick">Pass</i> 중복 중 선택</span><span><i class="c-p c-drop">Pass</i> 중복 제외</span></div>'+
  l.bunches.map(bunchHtml).join('');ovl.classList.add('on');mb.scrollTop=0;}
document.getElementById('mx').onclick=function(){ovl.classList.remove('on');};
ovl.addEventListener('click',function(e){if(e.target===ovl)ovl.classList.remove('on');});
document.addEventListener('keydown',function(e){if(e.key==='Escape')ovl.classList.remove('on');});
var qb=document.getElementById('qb'),cr=document.getElementById('crit');
qb.onclick=function(){var on=cr.classList.toggle('on');qb.setAttribute('aria-expanded',on);};
draw();
})();
"""


def build_html(model, scope="", created=None):
    """lotmodel.build 결과 → 단일 HTML 문자열."""
    data = to_data(model)
    lots = data["lots"]
    created = created or datetime.now()
    kpi = [("", len(lots), "Lot"),
           ("", sum(len(l["bunches"]) for l in lots), "묶음(한 번의 검사)"),
           ("a", sum(1 for l in lots for b in l["bunches"] if len(b["attempts"]) > 1), "나눠 스캔한 묶음"),
           ("a", sum(l["state"] == lm.LOT_RESCANNED for l in lots), "재스캔으로 완료한 Lot"),
           ("r", sum(l["unresolved"] > 0 for l in lots), "Pass 못 한 웨이퍼가 있는 Lot"),
           ("t", sum(1 for l in lots for b in l["bunches"] if any(w["v"] == DUPLICATE for w in b["wafers"])), "중복 Pass 묶음(선택 필요)"),
           ("t", sum(l["moved"] for l in lots), "호기 이동 Lot"),
           ("", len(data["excluded"]), "점검 스캔(제외)")]
    kpi_html = "".join(f'<div class="kpi {c}"><div class="n">{n:,}</div><div class="l">{_esc(l)}</div></div>' for c, n, l in kpi)
    crit = "".join(f"<dt>{_esc(t)}</dt><dd>{_esc(d)}{f'<small>{_esc(e)}</small>' if e else ''}</dd>" for t, d, e in CRITERIA)
    cause_rows = "".join(
        f"<tr><td>{_esc(c['cause'])}</td><td>{c['lots']}</td><td>{c['wafers']}</td><td>{c['chain']}</td>"
        f"<td>{c['passed']}</td><td>{c['open']}</td></tr>" for c in data["causes"]) or '<tr><td colspan="6">오류 없음</td></tr>'
    excluded = "".join(f"<tr><td>{_esc(e['machine'])}</td><td>{_esc(e['sm'])}</td><td>{_esc(e['start'])}</td><td>{e['rows']}</td>"
                       f"<td>{_esc(e['file'])}</td></tr>" for e in data["excluded"])
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
    states = "".join(f'<option value="{s}">{s}</option>' for s in (lm.LOT_OPEN, lm.LOT_RESCANNED, lm.LOT_DONE))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Batch Report Lot 추적</title><style>{PAGE_CSS}{LOT_CSS}</style></head><body><div class="doc">
<div class="head"><div class="kick">AOI Batch Report · Lot 추적 · 오프라인 자동 산출</div>
<div class="hbar"><h1>Batch Report Lot 추적</h1><button type="button" class="qbtn" id="qb" aria-expanded="false" aria-controls="crit">? Lot 판정 기준</button></div>
<div class="meta"><span><b>생성</b> {_esc(_t(created))}</span><span><b>조사 범위</b> {_esc(scope or '—')}</span></div>
<div class="crit" id="crit"><dl>{crit}</dl></div></div>
<div class="pad">
<div class="kpis">{kpi_html}</div>
<h2>Lot 목록</h2><p class="sub">행을 누르면 그 Lot의 취합 표 · 웨이퍼 표가 먼저 나오고, 아래에 시도 이력과 Lot × 웨이퍼 오류 지도가 나옵니다.</p>
<div class="filters"><input type="search" id="q" placeholder="Lot 코드 · S/M · Lot ID · Job 검색" aria-label="Lot 검색">
<select id="st" aria-label="상태"><option value="">전체 상태</option>{states}</select>
<select id="mc" aria-label="호기"><option value="">전체 호기</option></select>
<label><input type="checkbox" id="fs"> 나눠 스캔</label><label><input type="checkbox" id="fd"> 중복 있음</label>
<label><input type="checkbox" id="fm"> 호기 이동</label><span class="count" id="cnt"></span></div>
<div class="tscroll"><table class="lots"><thead><tr><th>Lot</th><th>S/M</th><th>호기</th><th>묶음</th><th>시도</th><th>처음 스캔</th><th>상태</th><th>Pass 없는 웨이퍼</th><th>첫 오류 원문(웨이퍼 수)</th></tr></thead>
<tbody id="lotbody"></tbody></table></div>
<h2>오류 원문별 Lot</h2><p class="sub">웨이퍼마다 Pass/Fail 원문의 첫 문구로 셉니다. 앞 오류 때문에 따라온 Aborted. · Skipped.(연쇄)는 그 앞 오류 문구로 셉니다. 이후 Pass = 같은 묶음에서 다시 스캔해 Pass, Pass 없음 = 끝까지 Pass 못 함.</p>
<div class="tscroll"><table><thead><tr><th>오류 원문(첫 문구)</th><th>영향 Lot</th><th>웨이퍼</th><th>그중 연쇄</th><th>이후 Pass</th><th>Pass 없음</th></tr></thead><tbody>{cause_rows}</tbody></table></div>
<h2>점검 스캔 (Lot에서 제외)</h2><p class="sub">S/M에 영문 3글자 단어가 없어 Lot으로 보지 않은 Batch Report입니다.</p>
<div class="tscroll"><table><thead><tr><th>호기</th><th>S/M</th><th>시작</th><th>행</th><th>파일</th></tr></thead><tbody>{excluded or '<tr><td colspan="5">없음</td></tr>'}</tbody></table></div>
<div class="foot">※ 원본 Batch Report는 읽기만 했습니다. 판정 기준은 위 [? Lot 판정 기준]에 있습니다. 중복 웨이퍼는 가장 나중 Pass를 추천 선택한 결과입니다.</div>
</div></div>
<div class="ovl" id="ovl" role="dialog" aria-modal="true" aria-labelledby="mt"><div class="modal"><div class="mhead"><h3 id="mt"></h3><button class="x" id="mx" aria-label="닫기">×</button></div><div class="mbody" id="mb"></div></div></div>
<script>window.__LOTDATA={payload};</script><script>{LOT_JS}</script></body></html>"""
