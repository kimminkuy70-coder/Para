"""저장된 결과 HTML 의 인터랙티브 그래프 — 앱(Batch Report 분석 화면)과 같은 그래프를 외부 라이브러리 없이 (이슈 #13).

앱의 `frontend/src/BatchCharts.tsx`(ColChart · Legend · Seg · Scatter · 툴팁) 와 `BatchUtil.tsx` · `BatchWph.tsx` · `BatchLot.tsx`
그래프 부분을 그대로 옮긴 바닐라 JS(문자열)다. 숫자 계산식은 `batchData.ts`(= `batchsaved.py`) 와 같다 — 새 지표 없음.

- `CORE_JS`  : 공통 — 숫자 · 기간(일/주(ISO WW)/월) · U 행 합 · 툴팁(표처럼 맞춘 rich) · 누적 세로 막대 · 범례(켜고 끄기) · 세그먼트 · 산점도 · 모달.
- `APP_JS`   : 분석 HTML · 가동률 대시보드 — 가동률 탭(호기 탭 · 시간 구성 호기별/기간별 · 24시간 시간표 · 기간 상세 창),
               WPH · 생산능력 탭(상위 레시피 필터 · 하위 레시피 · 호기 · 레시피 비교 · 호기 × 레시피 표 · 기간별 추이 · 레시피 상세 창),
               Lot 추적 탭(기간별 Lot Scan 현황).
- `LOTCHART_JS` : Lot 추적 HTML — 기간별 Lot Scan 현황(누르면 그 기간 Lot 만 목록에) + `#lot=<Lot>` 으로 Lot History 바로 열기.

HTML 은 파일 하나로 열리고(CSP: 인라인 스크립트만, 인터넷 · 외부 파일 없음) 스크립트가 꺼져 있으면 서버에서 만든 정적 막대가 그대로 보인다.
"""
from __future__ import annotations

import json

CHART_CSS = """
.bv-tip{position:fixed;z-index:2147483000;pointer-events:none;background:#1f2937;color:#fff;font-size:12px;line-height:1.6;padding:8px 11px;border-radius:8px;white-space:pre;box-shadow:0 8px 24px rgba(0,0,0,.22)}
.bv-tip::first-line{font-weight:800}
.bv-tip.rich{white-space:normal;padding:9px 12px}
.bv-tip.rich .tt{font-weight:800;margin-bottom:5px;white-space:nowrap}
.bv-tip.rich .tg{display:grid;grid-template-columns:12px max-content max-content max-content;gap:3px 8px;align-items:center;white-space:nowrap}
.bv-tip.rich .tg i{display:block;width:12px;height:12px;border-radius:3px}
.bv-tip.rich .tg b{text-align:right;font-variant-numeric:tabular-nums;min-width:28px}
.bv-tip.rich .tg .tu{color:#cbd5e1}.bv-tip.rich .tf{margin-top:5px;color:#cbd5e1;font-size:11px;white-space:nowrap}
.bvapp .chart{min-width:0;max-width:100%}.bvapp .chartscroll{overflow-x:auto;overflow-y:hidden;max-width:100%;padding-bottom:2px}
.bvapp .chart svg{display:block}
.bvapp .chart svg text{font:11px 'Malgun Gothic','맑은 고딕',sans-serif;fill:#52647d}
.bvapp .chart svg tspan.sub2{font-size:10.5px;fill:#6b7c90}
.bvapp .chart .hit{fill:transparent;cursor:pointer}.bvapp .chart .hit:hover{fill:#31517c12}
.bvapp .chart .selbox{fill:#0d966810;stroke:#0d9668;stroke-width:2}
.bvapp .chart .pt{cursor:pointer}.bvapp .chart .pt:hover{stroke:#1f2937}
.bvapp .chart .ttb{cursor:pointer}.bvapp .chart .ttb:hover{stroke:#1f2937;stroke-width:1.5}.bvapp .chart .ttw{cursor:pointer}
.bvapp .chartcard{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fff;margin:0 0 16px;min-width:0}
.bvapp .ch{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin-bottom:8px}
.bvapp .ch h3{margin:0;font-size:14px;color:var(--navy)}.bvapp .ch h3 small{font-weight:400;color:var(--faint);font-size:12px;margin-left:4px}
.bvapp .grow{flex:1}.bvapp .hint{color:var(--faint);font-size:12px;margin:4px 0}
.bvapp .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff}
.bvapp .seg button{border:0;background:#fff;color:var(--soft);font:inherit;font-size:12.5px;font-weight:700;padding:6px 13px;cursor:pointer}
.bvapp .seg button+button{border-left:1px solid var(--line)}.bvapp .seg button.on{background:var(--navy);color:#fff}
.bvapp .lgd{display:flex;flex-wrap:wrap;gap:6px}
.bvapp .lgd button{border:1px solid var(--line);border-radius:7px;background:#fff;padding:3px 10px;font:inherit;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:6px;color:#3f4b5a;cursor:pointer}
.bvapp .lgd button i{width:11px;height:11px;border-radius:3px;display:inline-block}.bvapp .lgd button.off{opacity:.45;text-decoration:line-through}
.bvapp .viewbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:12px 0 10px}
.bvapp .mtabs{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0}
.bvapp .mtabs button{border:1px solid var(--line);background:#fff;color:var(--soft);border-radius:999px;padding:5px 12px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer}
.bvapp .mtabs button.on{background:var(--navy);border-color:var(--navy);color:#fff}.bvapp .mtabs small{font-weight:400;opacity:.8}
.bvapp .prow{cursor:pointer;border-radius:6px;padding:3px 6px}.bvapp .prow:hover{background:#f3f7fa}
.bvapp .prow.ph{cursor:default;background:none}.bvapp .prows.scroll{max-height:560px;overflow:auto}
.bvapp .stack.big{height:26px;margin:6px 0 10px}
.bvapp .comp>div{display:grid;grid-template-columns:14px minmax(0,1fr) 80px 70px;gap:8px;align-items:center;font-size:12.5px;padding:3px 0;border-bottom:1px solid var(--line2)}
.bvapp .comp>div.sub{padding-left:18px;color:var(--soft)}.bvapp .comp i{width:12px;height:12px;border-radius:3px;display:block}
.bvapp .comp b,.bvapp .comp em{text-align:right;font-style:normal;font-variant-numeric:tabular-nums}
.bvapp .hbar.clickable{cursor:pointer;border-radius:6px}.bvapp .hbar.clickable:hover{background:#f3f7fa}.bvapp .hbar.sel{background:#e3f6ee}
.bvapp .chips{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0}
.bvapp .chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:3px 10px;font:inherit;font-size:12px;color:var(--navy);font-weight:700;cursor:pointer}
.bvapp .chip.nolink{cursor:default;font-weight:400}
.bvapp .ttnav{display:inline-flex;gap:4px;align-items:center}
.bvapp .ttnav button,.bvapp select,.bvapp .ttnav select{border:1px solid var(--line);background:#fff;border-radius:6px;padding:4px 8px;font:inherit;font-size:12.5px;cursor:pointer}
.bvapp .filters{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:flex-end;margin:6px 0 4px}
.bvapp .field{display:flex;flex-direction:column;gap:3px;font-size:11.5px;color:var(--soft);font-weight:700}
.bvapp .field select{min-width:160px;max-width:420px}
.bvapp .caprow.sel{background:#eef8f2;border-radius:6px}.bvapp .capbar>span[data-act]{cursor:pointer}
.bvapp .caprow .cl.linklike{background:none;border:0;padding:0;text-align:left;cursor:pointer;font:inherit;font-weight:800;color:var(--navy)}
.bvapp p.capsel{font-size:12.5px;color:var(--navy);background:#eef3f9;border-radius:6px;padding:6px 10px}.bvapp p.capsel.none{color:var(--rust)}
.bvapp tr.clickable{cursor:pointer}.bvapp tr.clickable:hover td{background:#f3f7fa}.bvapp tr.sel td{background:#e3f6ee!important}
.bvapp td.subr{white-space:nowrap}.bvapp tr.grouphead.job small{font-weight:400;color:var(--faint);margin-left:8px}
.bvapp .tbox{max-height:420px;overflow:auto}
.bvapp .linklike{background:none;border:0;padding:0;color:var(--navy);text-decoration:underline;cursor:pointer;font:inherit}
.bvapp .st{display:inline-block;font-size:11px;font-weight:700;border-radius:4px;padding:1px 6px;background:#eef1f5;color:var(--soft)}
.bvapp .st.done{background:#d1fae5;color:#065f46}.bvapp .st.re{background:#fef3c7;color:#92400e}.bvapp .st.open{background:#fee2e2;color:#991b1b}
.bvapp .st.sd{background:#f3e8ff;color:#6b21a8}.bvapp .st.so{background:#e2e8f0;color:#334155}.bvapp .st.out{background:#f1f5f9;color:#64748b}
.bvapp .wfall .wf{display:grid;grid-template-columns:minmax(150px,300px) minmax(0,1fr) 60px;gap:10px;align-items:center;font-size:12.5px;margin:4px 0}
.bvapp .wfall .track{position:relative;height:16px;background:#eef1f5;border-radius:4px;overflow:hidden}
.bvapp .wfall .track>span{position:absolute;top:0;bottom:0}.bvapp .wfall b{text-align:right;font-variant-numeric:tabular-nums}
.bvapp .two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.bvapp .pilltabs{display:flex;gap:6px;margin:0 0 12px;flex-wrap:wrap}
.bvapp .pilltabs button{border:1px solid var(--line);background:#fff;color:var(--soft);border-radius:999px;padding:6px 14px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer}
.bvapp .pilltabs button.on{background:var(--navy);border-color:var(--navy);color:#fff}
.bvapp .lwmeta{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;color:var(--soft);margin:0 0 10px}
.bvapp .lwmeta .job{font-family:Consolas,monospace;font-size:12px;color:var(--navy)}
.modal.bvwide{max-width:1120px}
#bvovl .mbody h3{font-size:14px;color:var(--navy);margin:16px 0 8px}#bvovl .mbody h3 small{font-weight:400;color:var(--faint);font-size:12px;margin-left:4px}
@media(max-width:720px){.bvapp .two{grid-template-columns:1fr}.bvapp .wfall .wf{grid-template-columns:1fr}}
@media print{.bvapp .seg,.bvapp .lgd,.bvapp .mtabs,.bvapp .ttnav{display:none}}
"""

CORE_JS = r"""
var BV=(function(){
var C={PROC:'#10b981',LOSS:'#c2410c',IDLE:'#dfe5ec',ERR:'#c2410c',OK:'#10b981',WAIT:'#d69e2e',STOP:'#7c8fb0',DEFECT:'#9b4dca',CHECK:'#94a3b8'};
var STOPK={d:'작업자 중단 · Defect 과다',o:'작업자 중단 · 그 외'};
var DONE='한 번에 완료',RE='재스캔으로 완료',OPEN='Pass하지 못한 wafer 존재',ST={};ST[DONE]='done';ST[RE]='re';ST[OPEN]='open';
function num(v,d){return v==null||isNaN(v)?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d||0});}
function f1(x){return num(x,1);}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function hrs(s){return num(s/3600,1);}
function pad(x){return (x<10?'0':'')+x;}
function ymd(dt){return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate());}
function addDays(d,k){var x=new Date(d+'T00:00:00');x.setDate(x.getDate()+k);return ymd(x);}
function niceMax(v){if(!(v>0))return 1;var p=Math.pow(10,Math.floor(Math.log10(v))),ms=[1,2,2.5,5,10];for(var i=0;i<ms.length;i++)if(ms[i]*p>=v)return ms[i]*p;return 10*p;}
function bucket(d,u){if(u==='d')return d;if(u==='m')return d.slice(0,7);var dt=new Date(d+'T00:00:00'),w=(dt.getDay()+6)%7;dt.setDate(dt.getDate()-w);return ymd(dt)+' 주';}
function workWeek(d){var th=new Date(d+'T00:00:00');th.setDate(th.getDate()+3);var j1=new Date(th.getFullYear(),0,1);return Math.floor(Math.round((th.getTime()-j1.getTime())/864e5)/7)+1;}
function shortKey(k,u){return u==='m'?k.slice(2,7):u==='w'?'WW'+workWeek(k.slice(0,10)):k.slice(5,10);}
function weekRange(k){var st=k.slice(0,10),en=addDays(st,6);return '('+st.slice(5).replace('-','/')+'~'+en.slice(5).replace('-','/')+')';}
function periodName(k,u){if(u!=='w')return k;var st=k.slice(0,10),th=addDays(st,3);return th.slice(0,4)+' WW'+workWeek(st)+' '+weekRange(k);}
function ts(s){return new Date(String(s).replace(' ','T')).getTime();}
function mins(a,b){return (ts(b)-ts(a))/60000;}
function dur(m){if(isNaN(m))return '—';m=Math.max(0,m);return m<60?Math.round(m)+'분':m<2880?num(m/60,1)+'시간':num(m/1440,1)+'일';}
function weekday(d){return '일월화수목금토'.charAt(new Date(d+'T00:00:00').getDay());}
function rangeDays(a,b){var o=[];if(!a||!b)return o;for(var d=a;d<=b;d=addDays(d,1))o.push(d);return o;}
function uniq(a){var s={},o=[];a.forEach(function(x){if(!s[x]){s[x]=1;o.push(x);}});return o;}
/* U 행 합 — batchData.ts 와 같은 식 */
var SUMS=['p','du','ck','ps','dn','n','ne','w25','s25','aw','asum'];
function emptyAgg(){return {p:0,du:0,ck:0,e:0,sd:0,so:0,ps:0,dn:0,n:0,ne:0,nsd:0,nso:0,w25:0,s25:0,aw:0,asum:0,err:{},sdl:{},sol:{},rec:{}};}
function addU(a,u){SUMS.forEach(function(k){a[k]+=u[k]||0;});
  a.sd+=u.sd[0];a.nsd+=u.sd[1];u.sd[2].forEach(function(li){a.sdl[li]=1;});a.so+=u.so[0];a.nso+=u.so[1];u.so[2].forEach(function(li){a.sol[li]=1;});
  if(u.p)a.rec[u.r]=(a.rec[u.r]||0)+u.p;
  Object.keys(u.e).forEach(function(k){var x=u.e[k];a.e+=x[0];var t=a.err[k]||(a.err[k]=[0,0,{}]);t[0]+=x[0];t[1]+=x[1];x[2].forEach(function(li){t[2][li]=1;});});return a;}
function sumU(rows){var a=emptyAgg();rows.forEach(function(u){addU(a,u);});return a;}
function addAgg(a,b){var o=Object.assign({},a,{err:Object.assign({},a.err)});['p','du','ck','e','sd','so','ps','dn','n','ne','nsd','nso','w25','s25','aw','asum'].forEach(function(k){o[k]=a[k]+b[k];});return o;}
function lossOf(a){return a.e+a.sd+a.so;}
function wphNormal(a){return a.s25?a.w25*3600/a.s25:null;}
function wphActual(a){var d=a.p+lossOf(a);return d>0?a.ps*3600/d:null;}
function unitSec(a){return a.w25?a.s25/a.w25:null;}
function avgScan(a){return a.aw?a.asum/a.aw:null;}
function pctOf(x,t){return t>0?x/t*100:null;}
function cap(a){var w=wphActual(a);return w==null?null:w*24;}
/* 툴팁 — data-tipx(JSON: 제목 · [색, 이름, 값, 단위] 줄 · 꼬리말) 가 있으면 표처럼, 없으면 data-tip 글자 */
function tipText(x){return [x.t].concat(x.rows.map(function(r){return r[1]+' '+r[2]+(r[3]?' '+r[3]:'');}),x.f||[]).join('\n');}
function tipAttr(x){return ' data-tip="'+esc(tipText(x))+'" data-tipx="'+esc(JSON.stringify(x))+'"';}
var tip=null;
function tipInit(){if(tip)return;tip=document.createElement('div');tip.className='bv-tip';tip.hidden=true;document.body.appendChild(tip);
  document.addEventListener('mousemove',function(e){var t=e.target&&e.target.closest?e.target.closest('[data-tip]'):null;if(!t){tip.hidden=true;return;}
    var rich=t.getAttribute('data-tipx'),x=null;if(rich){try{x=JSON.parse(rich);}catch(_){x=null;}}
    if(x){tip.className='bv-tip rich';var h='<div class="tt">'+esc(x.t)+'</div><div class="tg">';
      x.rows.forEach(function(r){h+='<i style="background:'+esc(r[0])+'"></i><span>'+esc(r[1])+'</span><b>'+esc(r[2])+'</b><span class="tu">'+esc(r[3]||'')+'</span>';});
      h+='</div>';(x.f||[]).forEach(function(l){h+='<div class="tf">'+esc(l)+'</div>';});tip.innerHTML=h;}
    else{tip.className='bv-tip';tip.textContent=t.getAttribute('data-tip');}
    tip.hidden=false;var px=e.clientX+14,py=e.clientY+16,w=tip.offsetWidth,hh=tip.offsetHeight;
    if(px+w>innerWidth-8)px=Math.max(8,e.clientX-w-14);if(py+hh>innerHeight-8)py=Math.max(8,e.clientY-hh-14);tip.style.left=px+'px';tip.style.top=py+'px';});
  window.addEventListener('scroll',function(){if(tip)tip.hidden=true;},true);}
/* 누적 세로 막대(앱 ColChart) — o:{items:[{id,short,short2,v,tip,tipx}],keys:[[k,label,color]],hidden,sel,h,minw,maxw,label,fy,width,act} */
function colChart(o){
  if(!o.items.length)return '<div class="chart"><p class="hint">조사 범위에 자료가 없습니다.</p></div>';
  var hidden=o.hidden||{},fy=o.fy||function(v){return num(v);},minw=o.minw||14,maxw=o.maxw||60,h=o.h||210;
  var two=o.items.some(function(it){return it.short2;}),pl=48,pb=two?44:28,pt=12,cnt=o.items.length,avail=Math.max(320,(o.width||900)-4);
  var cw=Math.max(minw,Math.min(maxw,(avail-pl-36)/cnt)),W=Math.max(avail,pl+cnt*cw+36),ph=h-28-pt;   // 오른쪽 36px: 마지막 날짜 글자가 잘리지 않게
  var tot=o.items.map(function(it){return o.keys.reduce(function(a,k){return a+(hidden[k[0]]?0:(it.v[k[0]]||0));},0);});
  var max=niceMax(Math.max.apply(null,tot.concat([1]))),dv=(max%4===0||max<=1)?4:5,every=Math.max(1,Math.ceil((two?92:56)/cw));
  h+=pb-28;var s='<div class="chart"><div class="chartscroll"><svg width="'+W+'" height="'+h+'" role="img" aria-label="'+esc(o.label)+'">';
  for(var g=0;g<=dv;g++){var y=pt+ph-ph*g/dv;s+='<line x1="'+pl+'" x2="'+(W-4)+'" y1="'+y+'" y2="'+y+'" stroke="#e6ebf0"/><text x="'+(pl-6)+'" y="'+(y+4)+'" text-anchor="end">'+esc(fy(max*g/dv))+'</text>';}
  o.items.forEach(function(it,i){var x=pl+i*cw,bw=Math.max(3,cw*0.7),bx=x+(cw-bw)/2,yy=pt+ph;
    if(o.sel===it.id)s+='<rect class="selbox" x="'+(x+1)+'" y="'+pt+'" width="'+(cw-2)+'" height="'+ph+'" rx="4"/>';
    o.keys.forEach(function(k){if(hidden[k[0]])return;var val=it.v[k[0]]||0;if(val<=0)return;var hh=val/max*ph;yy-=hh;
      s+='<rect x="'+bx.toFixed(1)+'" y="'+yy.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+Math.max(.5,hh).toFixed(1)+'" fill="'+k[2]+'"/>';});
    s+='<rect class="hit" x="'+x+'" y="'+pt+'" width="'+cw+'" height="'+ph+'"'+(it.tipx?tipAttr(it.tipx):' data-tip="'+esc(it.tip)+'"')+(o.act?' data-act="'+o.act+'" data-v="'+esc(it.id)+'"':'')+'/>';
    if(i%every===0)s+='<text x="'+(x+cw/2)+'" y="'+(pt+ph+17)+'" text-anchor="middle">'+esc(it.short)+(it.short2?'<tspan x="'+(x+cw/2)+'" dy="15" class="sub2">'+esc(it.short2)+'</tspan>':'')+'</text>';});
  return s+'<line x1="'+pl+'" x2="'+(W-4)+'" y1="'+(pt+ph)+'" y2="'+(pt+ph)+'" stroke="#94a3b8"/></svg></div></div>';}
/* 범례 = 켜고 끄는 버튼 */
function legend(keys,hidden,act){return '<div class="lgd">'+keys.map(function(k){var off=hidden[k[0]];
  return '<button type="button" class="'+(off?'off':'')+'" aria-pressed="'+(!off)+'" data-act="'+act+'" data-v="'+esc(k[0])+'"><i style="background:'+k[2]+'"></i>'+esc(k[1])+'</button>';}).join('')+'</div>';}
function seg(value,items,act,label){return '<div class="seg" role="group" aria-label="'+esc(label)+'">'+items.map(function(x){var on=value===x[0];
  return '<button type="button" class="'+(on?'on':'')+'" aria-pressed="'+on+'" data-act="'+act+'" data-v="'+esc(x[0])+'">'+esc(x[1])+'</button>';}).join('')+'</div>';}
/* 산점도(Lot별 실제 WPH) + 기준선 */
function scatter(pts,base,width,act){
  if(!pts.length)return '<div class="chart"><p class="hint">조사 범위에 자료가 없습니다.</p></div>';
  var W=Math.max(480,(width||900)-4),H=270,pl=50,pr=16,pt=18,pb=32,pw=W-pl-pr,ph=H-pt-pb;
  var x0=Math.min.apply(null,pts.map(function(p){return p.t;})),x1=Math.max.apply(null,pts.map(function(p){return p.t;}));if(x1===x0)x1=x0+864e5;
  var ymax=niceMax(Math.max.apply(null,pts.map(function(p){return p.y;}).concat([base||0]))*1.06),dv=ymax%4===0?4:5;
  function X(t){return pl+(t-x0)/(x1-x0)*pw;}function Y(v){return pt+ph-v/ymax*ph;}
  var s='<div class="chart"><div class="chartscroll"><svg width="'+W+'" height="'+H+'" role="img" aria-label="Lot별 실제 WPH">';
  for(var g=0;g<=dv;g++){var v=ymax*g/dv,y=Y(v);s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y+'" y2="'+y+'" stroke="#e6ebf0"/><text x="'+(pl-6)+'" y="'+(y+4)+'" text-anchor="end">'+num(v)+'</text>';}
  var d=new Date(x0);d=new Date(d.getFullYear(),d.getMonth()+1,1);
  while(d.getTime()<=x1){var xx=X(d.getTime());s+='<line x1="'+xx+'" x2="'+xx+'" y1="'+pt+'" y2="'+(pt+ph)+'" stroke="#f0f3f6"/><text x="'+xx+'" y="'+(H-10)+'" text-anchor="middle">'+String(d.getFullYear()).slice(2)+'-'+pad(d.getMonth()+1)+'</text>';d=new Date(d.getFullYear(),d.getMonth()+1,1);}
  s+='<text x="'+(pl+4)+'" y="'+(pt+10)+'" style="font-size:10px" font-weight="700">WPH</text>';
  if(base)s+='<line x1="'+pl+'" x2="'+(W-pr)+'" y1="'+Y(base)+'" y2="'+Y(base)+'" stroke="#31517c" stroke-width="2" stroke-dasharray="6 4"/>';
  pts.forEach(function(p){s+='<circle class="pt" cx="'+X(p.t).toFixed(1)+'" cy="'+Y(p.y).toFixed(1)+'" r="5" fill="'+p.c+'" fill-opacity=".85" stroke="#fff" stroke-width="1.5" data-tip="'+esc(p.tip)+'"'+(act?' data-act="'+act+'" data-v="'+p.id+'"':'')+'/>';});
  if(base)s+='<text x="'+(W-pr-4)+'" y="'+(Y(base)-6)+'" text-anchor="end" fill="#31517c" font-weight="700" paint-order="stroke" stroke="#fff" stroke-width="5">정상 스캔 WPH '+num(base,1)+'</text>';
  return s+'</svg></div></div>';}
/* 다시 그리기 — 검색칸 포커스 · 커서 위치 유지, 창 크기 · 탭 전환 때 폭 다시 맞춤 */
var apps=[];
function mount(el,render,onClick,onChange){var a={el:el,draw:function(){var ae=document.activeElement,id=ae&&ae.id&&el.contains(ae)?ae.id:null,pos=null;
    try{pos=id?ae.selectionStart:null;}catch(_){pos=null;}var cs=getComputedStyle(el);
    el.innerHTML=render(Math.max(320,(el.clientWidth-(parseFloat(cs.paddingLeft)||0)-(parseFloat(cs.paddingRight)||0)||900)-36));   // 그래프 카드 안쪽 여백만큼 줄임 — 넘치면 가로 스크롤
    if(id){var b=document.getElementById(id);if(b){b.focus();try{if(pos!=null)b.setSelectionRange(pos,pos);}catch(_){}}}}};
  el.classList.add('bvapp');el.addEventListener('click',function(e){var t=e.target.closest('[data-act]');if(t&&el.contains(t)){onClick(t.getAttribute('data-act'),t.getAttribute('data-v'),t,e);}});
  if(onChange){el.addEventListener('change',function(e){var t=e.target.closest('[data-chg]');if(t)onChange(t.getAttribute('data-chg'),t.value,t);});
    el.addEventListener('input',function(e){var t=e.target.closest('[data-inp]');if(t)onChange(t.getAttribute('data-inp'),t.value,t);});}
  apps.push(a);a.draw();return a;}
function rerender(){apps.forEach(function(a){if(a.el.offsetParent!==null||a.el.closest('#bvovl'))a.draw();});}
var rt=null;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(rerender,150);});
/* 모달(기간 상세 창 · 레시피 상세 창) */
var ovl=null,modalApp=null;
function modal(title,render,onClick,onChange){
  if(!ovl){ovl=document.createElement('div');ovl.className='ovl';ovl.id='bvovl';ovl.setAttribute('role','dialog');ovl.setAttribute('aria-modal','true');
    ovl.innerHTML='<div class="modal bvwide"><div class="mhead"><h3 id="bvmt"></h3><button class="x" type="button" aria-label="닫기">&times;</button></div><div class="mbody" id="bvmb"></div></div>';
    document.body.appendChild(ovl);ovl.querySelector('.x').onclick=closeModal;ovl.addEventListener('click',function(e){if(e.target===ovl)closeModal();});
    document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});}
  document.getElementById('bvmt').textContent=title;
  var old=document.getElementById('bvmb'),body=old.cloneNode(false);old.parentNode.replaceChild(body,old);   // 지난 창의 클릭 처리기를 버린다
  if(modalApp){apps.splice(apps.indexOf(modalApp),1);}ovl.classList.add('on');modalApp=mount(body,render,onClick,onChange);body.scrollTop=0;}
function closeModal(){if(ovl)ovl.classList.remove('on');if(modalApp){apps.splice(apps.indexOf(modalApp),1);modalApp=null;}}
function data(id){var e=document.getElementById(id);return e?JSON.parse(e.textContent):null;}
function ready(fn){if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fn);else fn();}
ready(tipInit);
return {C:C,STOPK:STOPK,DONE:DONE,RE:RE,OPEN:OPEN,ST:ST,num:num,f1:f1,esc:esc,hrs:hrs,pad:pad,addDays:addDays,bucket:bucket,shortKey:shortKey,weekRange:weekRange,
  periodName:periodName,ts:ts,mins:mins,dur:dur,weekday:weekday,rangeDays:rangeDays,uniq:uniq,emptyAgg:emptyAgg,addU:addU,sumU:sumU,addAgg:addAgg,lossOf:lossOf,
  wphNormal:wphNormal,wphActual:wphActual,unitSec:unitSec,avgScan:avgScan,pctOf:pctOf,cap:cap,tipText:tipText,tipAttr:tipAttr,tipInit:tipInit,colChart:colChart,
  legend:legend,seg:seg,scatter:scatter,mount:mount,rerender:rerender,modal:modal,closeModal:closeModal,data:data,ready:ready};
})();
"""

# Lot 추적: 기간별 Lot Scan 현황 막대(앱 BatchLot 의 ColChart) — 분석 HTML(Lot 추적 탭)과 Lot 추적 HTML 이 같이 쓴다.
LOTKEYS_JS = r"""
function lotItems(lots,unit){var B=BV,by={};
  lots.forEach(function(l){if(!l.s)return;var k=B.bucket(l.s.slice(0,10),unit);var x=by[k]||(by[k]={done:0,re:0,open:0});x[B.ST[l.state]||'open']++;});
  return Object.keys(by).sort().map(function(k){var x=by[k],t=x.done+x.re+x.open,name=B.periodName(k,unit);
    return {id:k,short:B.shortKey(k,unit),short2:unit==='w'?B.weekRange(k):undefined,v:x,
      tipx:{t:name,rows:[[B.C.OK,B.DONE,B.num(x.done),'Lot'],[B.C.WAIT,B.RE,B.num(x.re),'Lot'],[B.C.ERR,B.OPEN,B.num(x.open),'Lot'],['transparent','합계',B.num(t),'Lot']],
        f:['처음 스캔한 날 기준 · 누르면 이 기간 Lot만 아래 목록에']}};});}
var LOTKEYS=[['done',BV.DONE,BV.C.OK],['re',BV.RE,BV.C.WAIT],['open',BV.OPEN,BV.C.ERR]];
"""

APP_JS = LOTKEYS_JS + r"""
(function(){var B=BV,C=B.C,num=B.num,f1=B.f1,esc=B.esc,hrs=B.hrs,D=B.data('bvdata');if(!D)return;
var lots=D.lots.map(function(x){return {label:x[0],s:x[1],state:x[2],m:x[3]};});
var days=B.rangeDays(D.range[0],D.range[1]);
function lotBtn(li){var l=lots[li];if(!l)return '';return D.lotHref?'<button type="button" class="chip" data-act="lot" data-v="'+li+'" title="Lot 추적 HTML 에서 Lot History 열기">'+esc(l.label)+'</button>'
  :'<span class="chip nolink">'+esc(l.label)+'</span>';}
function openLot(li){var l=lots[+li];if(l&&D.lotHref)window.open(D.lotHref+'#lot='+encodeURIComponent(l.label),'_blank');}
function pc(x,t){return num(B.pctOf(x,t),1)+'%';}
function pcv(x){return x==null?'—':num(x,1)+'%';}
function drop(n,a){return n&&a!=null?(1-a/n)*100:null;}
function sw(c){return '<i class="msw" style="background:'+c+'"></i>';}

/* ---------------- Lot 추적 탭: 기간별 Lot Scan 현황 ---------------- */
var lotEl=document.getElementById('lotchart');
if(lotEl){var LS={unit:'w',hid:{},period:null};
  B.mount(lotEl,function(w){var items=lotItems(lots,LS.unit),h='<div class="chartcard"><div class="ch"><h3>기간별 Lot Scan 현황</h3><span class="hint">막대에 마우스를 올리면 자세히, 누르면 그 기간 Lot만 아래 목록에 보입니다.</span><span class="grow"></span>'+
      B.legend(LOTKEYS,LS.hid,'lgd')+B.seg(LS.unit,[['d','일'],['w','주'],['m','월']],'unit','기간 단위')+'</div>'+
      B.colChart({items:items,keys:LOTKEYS,hidden:LS.hid,sel:LS.period,maxw:LS.unit==='w'?100:60,label:'기간별 Lot Scan 현황',width:w,act:'per'});
    if(LS.period){var list=lots.map(function(l,i){return [l,i];}).filter(function(x){return x[0].s&&B.bucket(x[0].s.slice(0,10),LS.unit)===LS.period;}).sort(function(a,b){return a[0].s<b[0].s?1:-1;});
      h+='<div class="ch" style="margin-top:8px"><h3>'+esc(B.periodName(LS.period,LS.unit))+' · Lot '+list.length+'개</h3><span class="grow"></span><button type="button" class="linklike" data-act="per" data-v="'+esc(LS.period)+'">선택 해제</button></div>'+
        '<div class="tbox"><table><thead><tr><th>Lot</th><th>처음 스캔</th><th>호기</th><th>상태</th></tr></thead><tbody>'+
        list.map(function(x){var l=x[0];return '<tr><td>'+lotBtn(x[1])+'</td><td>'+esc(l.s)+'</td><td>'+esc(l.m)+'</td><td><span class="st '+(B.ST[l.state]||'')+'">'+esc(l.state)+'</span></td></tr>';}).join('')+'</tbody></table></div>'+
        (D.lotHref?'<p class="hint">Lot을 누르면 Lot 추적 HTML 에서 그 Lot의 Lot History 가 열립니다.</p>':'');}
    return h+'</div>';},
  function(act,v){if(act==='unit'){LS.unit=v;LS.period=null;}else if(act==='lgd'){LS.hid[v]=!LS.hid[v];}else if(act==='per'){LS.period=LS.period===v?null:v;}else if(act==='lot'){openLot(v);return;}
    B.rerender();});}

/* ---------------- 가동률 탭 (앱 BatchUtil) ---------------- */
var KEYS=[['proc','웨이퍼 처리',C.PROC],['loss','Error · 중단 및 조치',C.LOSS],['idle','유휴',C.IDLE]];
function comp(a,cal){var proc=a.p+a.ck,loss=B.lossOf(a);return {proc:proc,loss:loss,idle:Math.max(0,cal-proc-loss),cal:cal,a:a};}
function tipOf(title,c,foot){return {t:title,rows:[[C.PROC,'웨이퍼 처리',hrs(c.proc),'h · '+pc(c.proc,c.cal)],[C.LOSS,'Error · 중단 및 조치',hrs(c.loss),'h · '+pc(c.loss,c.cal)],
  [C.IDLE,'유휴',hrs(c.idle),'h · '+pc(c.idle,c.cal)],['transparent','달력 시간',hrs(c.cal),'h']],f:foot?[foot]:undefined};}
function stack(c,hid,big){return '<span class="stack'+(big?' big':'')+'">'+KEYS.map(function(k){var x=c[k[0]];return !hid[k[0]]&&x>0&&c.cal>0?'<span style="width:'+(x/c.cal*100).toFixed(2)+'%;background:'+k[2]+'"></span>':'';}).join('')+'</span>';}
function dataDaysOf(use,from){var s={};D.R.forEach(function(r){if(r.s&&use.indexOf(r.m)>=0)s[r.s.slice(0,10)]=1;});return from.filter(function(d){return s[d];});}
function kind(r){return r.lot==null?['점검 스캔',C.CHECK,'out']:r.o==='e'?['Error 포함',C.ERR,'open']:r.o==='s'?(r.sk==='d'?[B.STOPK.d,C.DEFECT,'sd']:[B.STOPK.o,C.STOP,'so']):['모두 Pass',C.OK,'done'];}
var byMachine={};D.R.forEach(function(r,g){(byMachine[r.m]=byMachine[r.m]||[]).push(g);});
/* 24시간 시간표 — 줄마다 (호기, 날짜). 막대 = Batch Report, 아래 줄 = Error · 중단 뒤 조치 대기(누르면 Lot) */
function timeTable(rows,width){var R=D.R,W=Math.max(640,width-4),L=100,RH=30,top=24,H=top+rows.length*RH+8,pw=W-L-12,svg='',ev=[],seen={};
  function X(ms){return L+ms/864e5*pw;}
  for(var hh=0;hh<=24;hh+=2){var x=L+hh/24*pw;svg+='<line x1="'+x+'" x2="'+x+'" y1="'+(top-4)+'" y2="'+(H-4)+'" stroke="'+(hh%6?'#eef1f5':'#d5dde6')+'"/><text x="'+x+'" y="'+(top-9)+'" text-anchor="middle">'+B.pad(hh)+'시</text>';}
  rows.forEach(function(rw,ri){var y=top+ri*RH,d0=B.ts(rw.day+' 00:00'),d1=d0+864e5;
    svg+='<rect x="'+L+'" y="'+(y+2)+'" width="'+pw+'" height="'+(RH-4)+'" fill="'+(ri%2?'#f8fafc':'#fff')+'" stroke="#e6ebf0"/><text x="'+(L-8)+'" y="'+(y+RH/2+4)+'" text-anchor="end" font-weight="700">'+esc(rw.label)+'</text>';
    if(!rw.day)return;
    (byMachine[rw.m]||[]).forEach(function(g){var r=R[g];if(!r.s||!r.e)return;var a=B.ts(r.s),b=B.ts(r.e);if(b<=d0||a>=d1)return;var k=kind(r),x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      var t=r.s.slice(11)+' ~ '+r.e.slice(11)+' · '+r.m+' · '+k[0]+'\n'+(r.lot!=null&&lots[r.lot]?'Lot '+lots[r.lot].label+' · ':'')+'S/M '+r.sm+' · '+r.step+'\nPass '+r.ok+' / '+r.n+'행'+
        (r.fe?'\n첫 Error: '+r.fe:'')+(r.o==='s'?'\n작업자 중단 · 멈출 때 Faults '+(r.ff==null?'—':r.ff):'')+'\n'+r.f;
      svg+='<rect class="ttb" x="'+x0.toFixed(1)+'" y="'+(y+5)+'" width="'+Math.max(2,x1-x0).toFixed(1)+'" height="'+(RH-17)+'" rx="2" fill="'+k[1]+'" data-tip="'+esc(t)+'"'+(r.lot!=null?' data-act="lot" data-v="'+r.lot+'"':'')+'/>';
      if(!seen['r'+g]){seen['r'+g]=1;ev.push({t:r.s,g:g});}});
    D.waits.forEach(function(w,wi){if(w.m!==rw.m)return;var a=B.ts(w.s),b=B.ts(w.e);if(b<=d0||a>=d1)return;var x0=X(Math.max(a,d0)-d0),x1=X(Math.min(b,d1)-d0);
      var t=(w.t==='s'?'작업자 중단':'Error')+' 뒤 조치 대기 · Lot '+(lots[w.li]?lots[w.li].label:'')+'\n'+w.s.slice(5)+' → '+w.e.slice(5)+' ('+B.dur(B.mins(w.s,w.e))+')\n'+
        (w.t==='s'?'중단: '+(R[w.g]&&R[w.g].sk==='d'?'Defect 과다':'그 외'):'앞 Batch Report 첫 Error: '+((R[w.g]&&R[w.g].fe)||'—'))+'\n그 사이 다른 스캔 시간은 빼고 셉니다'+(D.lotHref?'\n누르면 Lot History':'');
      svg+='<rect class="ttw" x="'+x0.toFixed(1)+'" y="'+(y+RH-11)+'" width="'+Math.max(2,x1-x0).toFixed(1)+'" height="5" rx="1" fill="'+(w.t==='s'?C.STOP:C.WAIT)+'" data-tip="'+esc(t)+'" data-act="lot" data-v="'+w.li+'"/>';
      if(!seen['w'+wi]){seen['w'+wi]=1;ev.push({t:w.s,w:wi});}});});
  ev.sort(function(a,b){return a.t<b.t?-1:a.t>b.t?1:0;});
  var keys='<div class="keys" style="margin-top:0"><span><i style="background:'+C.OK+'"></i>모두 Pass</span><span><i style="background:'+C.ERR+'"></i>Error 포함</span><span><i style="background:'+C.DEFECT+'"></i>'+B.STOPK.d+'</span>'+
    '<span><i style="background:'+C.STOP+'"></i>'+B.STOPK.o+'</span><span><i style="background:'+C.CHECK+'"></i>점검 스캔</span><span><i style="background:'+C.WAIT+'"></i>아래 줄 = 조치 대기(Error 뒤)</span>'+
    '<span><i style="background:'+C.STOP+'"></i>아래 줄 = 조치 대기(중단 뒤)</span><span>빈칸 = 유휴</span></div>';
  var tb='<details><summary>이 시간표의 Batch Report · 조치 대기 목록 ('+ev.length+'건)</summary><div class="tbox"><table><thead><tr><th>시작</th><th>끝</th><th>호기</th><th>한 일</th><th>Lot</th><th>S/M</th><th class="num">Pass / 행</th><th>첫 Error 원문 · 중단</th><th class="num">시간</th></tr></thead><tbody>'+
    ev.map(function(x){if(x.w!=null){var w=D.waits[x.w];return '<tr><td>'+esc(w.s)+'</td><td>'+esc(w.e.slice(5))+'</td><td>'+esc(w.m)+'</td><td><span class="st re">조치 대기</span></td><td>'+lotBtn(w.li)+'</td><td></td><td></td><td>'+esc(w.t==='s'?'작업자 중단 뒤':(D.R[w.g]||{}).fe)+'</td><td class="num">'+B.dur(B.mins(w.s,w.e))+'</td></tr>';}
      var r=D.R[x.g],k=kind(r);return '<tr><td>'+esc(r.s)+'</td><td>'+esc(r.e.slice(5))+'</td><td>'+esc(r.m)+'</td><td><span class="st '+k[2]+'">'+esc(k[0])+'</span></td><td>'+(r.lot!=null?lotBtn(r.lot):'')+'</td><td>'+esc(r.sm)+'</td><td class="num">'+r.ok+' / '+r.n+'</td><td>'+
        esc(r.fe||(r.o==='s'?'Aborted. · Faults '+(r.ff==null?'—':r.ff):''))+'</td><td class="num">'+B.dur(r.sec/60)+'</td></tr>';}).join('')+
    (ev.length?'':'<tr><td colspan="9">이 범위에 스캔 기록이 없습니다.</td></tr>')+'</tbody></table></div></details>';
  return keys+'<div class="chart"><div class="chartscroll"><svg width="'+W+'" height="'+H+'" role="img" aria-label="24시간 시간표">'+svg+'</svg></div></div>'+tb;}

var utilEl=document.getElementById('utilapp');
if(utilEl){var S={unit:'w',hid:{},mach:'all',view:'comp',by:'m',tDay:null};
  var uRows=D.U;
  function cur(){var m=S.mach!=='all'&&D.ids.indexOf(S.mach)<0?'all':S.mach,use=m==='all'?D.ids:[m];return {m:m,use:use,nm:Math.max(1,use.length)};}
  function utilDay(use){var dd=dataDaysOf(use,days);return {dd:dd,day:S.tDay&&dd.indexOf(S.tDay)>=0?S.tDay:dd[dd.length-1]||''};}
  B.mount(utilEl,function(w){var c=cur(),m=c.m,use=c.use,nm=c.nm,mine=uRows.filter(function(u){return use.indexOf(u.m)>=0;}),all=comp(B.sumU(mine),days.length*86400*nm);
    var U_={d:'일',w:'주',m:'월'}[S.unit];
    var h='<div class="viewbar"><b style="color:var(--navy)">기간 단위</b>'+B.seg(S.unit,[['d','일'],['w','주'],['m','월']],'unit','기간 단위')+'</div>';
    h+='<div class="mtabs" role="tablist" aria-label="호기별 보기"><button type="button" class="'+(m==='all'?'on':'')+'" data-act="mach" data-v="all">전체 호기 <small>'+D.ids.length+'대</small></button>'+
      D.ids.map(function(id){return '<button type="button" class="'+(m===id?'on':'')+'" data-act="mach" data-v="'+esc(id)+'">'+esc(id)+'</button>';}).join('')+'</div>';
    var K=[['가동률',num(B.pctOf(all.proc,all.cal),1),'%',hrs(all.proc)+'시간',C.PROC,'t'],['Error · 중단 및 조치',num(B.pctOf(all.loss,all.cal),1),'%','Error '+hrs(all.a.e)+' + 작업자 중단 '+hrs(all.a.sd+all.a.so)+'시간',C.LOSS,'r'],
      ['유휴',num(B.pctOf(all.idle,all.cal),1),'%',hrs(all.idle)+'시간',C.IDLE,''],['달력 시간',hrs(all.cal),'h',days.length+'일 × '+nm+'대 · 하루 24시간','','']];
    h+='<div class="kpis k4">'+K.map(function(k){return '<div class="kpi '+k[5]+'"><div class="n">'+esc(k[1])+'<span class="u">'+k[2]+'</span></div><div class="l">'+(k[4]?'<i class="sw" style="background:'+k[4]+'"></i>':'')+esc(k[0])+'</div><div class="s">'+esc(k[3])+'</div></div>';}).join('')+'</div>';
    h+='<div class="viewbar">'+B.seg(S.view,[['comp','시간 구성'],['time','24시간 시간표']],'view','보기')+(S.view==='comp'&&m==='all'?B.seg(S.by,[['m','호기별'],['p','기간별']],'by','나눠 보기'):'')+
      '<span class="grow"></span>'+(S.view==='comp'?B.legend(KEYS,S.hid,'lgd'):'')+'</div>';
    if(S.view==='comp'){
      if(m==='all'&&S.by==='m'){h+='<div class="chartcard"><div class="ch"><h3>호기별 시간 구성 <small>'+esc(D.range[0])+' ~ '+esc(D.range[1])+'</small></h3><span class="hint">마우스 = 값 · 누르면 그 호기</span></div><div class="prows"><div class="prow ph"><span>호기</span><span>100% = 24시간 × '+days.length+'일</span><span>가동률</span></div>'+
        D.ids.map(function(id){var cc=comp(B.sumU(uRows.filter(function(u){return u.m===id;})),days.length*86400);
          return '<div class="prow"'+B.tipAttr(tipOf(id,cc,'누르면 이 호기 탭으로'))+' data-act="mach" data-v="'+esc(id)+'"><span class="pl">'+esc(id)+'</span>'+stack(cc,S.hid)+'<span class="pv">'+pc(cc.proc,cc.cal)+'</span></div>';}).join('')+'</div></div>';}
      else{var o={};days.forEach(function(d){var k=B.bucket(d,S.unit);(o[k]=o[k]||{days:0,a:B.emptyAgg()}).days++;});mine.forEach(function(u){var k=B.bucket(u.d,S.unit);if(o[k])B.addU(o[k].a,u);});
        var ks=Object.keys(o).sort().reverse();
        h+='<div class="chartcard"><div class="ch"><h3>기간별 시간 구성 <small>'+U_+' · '+(m==='all'?'전체 호기':esc(m))+'</small></h3><span class="hint">마우스 = 값 · 누르면 그 기간 상세 창</span></div><div class="prows scroll"><div class="prow ph"><span>기간</span><span>100% = '+(nm>1?nm+'대 × ':'')+'24시간 × 일수</span><span>가동률</span></div>'+
          ks.map(function(k){var cc=comp(o[k].a,o[k].days*86400*nm);return '<div class="prow"'+B.tipAttr(tipOf(B.periodName(k,S.unit),cc,'누르면 이 기간 상세 창'))+' data-act="pwin" data-v="'+esc(k)+'"><span class="pl">'+esc(S.unit==='w'?B.shortKey(k,S.unit)+' '+k.slice(5,10):k)+'</span>'+stack(cc,S.hid)+'<span class="pv">'+pc(cc.proc,cc.cal)+'</span></div>';}).join('')+
          (ks.length?'':'<p class="hint">조사 범위에 자료가 없습니다.</p>')+'</div></div>';}}
    else{var dd=utilDay(use),day=dd.day,week=[];
      if(day){var dt=new Date(day+'T00:00:00'),st=B.addDays(day,-((dt.getDay()+6)%7));for(var i=0;i<7;i++){var x=B.addDays(st,i);if(x>=D.range[0]&&x<=D.range[1])week.push(x);}}
      var rows=m==='all'?D.ids.map(function(id){return {label:id,day:day,m:id};}):week.map(function(d){return {label:d.slice(5)+' ('+B.weekday(d)+')',day:d,m:m};});
      h+='<div class="chartcard"><div class="ch"><h3>24시간 시간표 — '+(m==='all'?esc(day)+' ('+(day?B.weekday(day):'')+') · 호기별':esc(m)+' · '+esc((week[0]||'').slice(5))+' ~ '+esc((week[week.length-1]||'').slice(5)))+'</h3><span class="grow"></span>'+
        '<span class="ttnav"><button type="button" data-act="step" data-v="-1" aria-label="'+(m==='all'?'전날':'전주')+'">◀</button><select data-chg="tday" aria-label="날짜">'+dd.dd.map(function(d){return '<option'+(d===day?' selected':'')+'>'+d+'</option>';}).join('')+'</select>'+
        '<button type="button" data-act="step" data-v="1" aria-label="'+(m==='all'?'다음날':'다음주')+'">▶</button></span></div>'+timeTable(rows,w-30)+'</div>';}
    return h;},
  function(act,v){var c=cur();
    if(act==='unit')S.unit=v;else if(act==='mach')S.mach=v;else if(act==='view')S.view=v;else if(act==='by')S.by=v;else if(act==='lgd')S.hid[v]=!S.hid[v];
    else if(act==='lot'){openLot(v);return;}else if(act==='pwin'){periodWindow(v,S.unit,c.use);return;}
    else if(act==='step'){var k=+v,dd=utilDay(c.use),i;if(c.m==='all'){i=dd.dd.indexOf(dd.day)+k;if(i>=0&&i<dd.dd.length)S.tDay=dd.dd[i];}
      else{var target=B.addDays(dd.day,7*k),cand=k>0?dd.dd.filter(function(d){return d>=target;})[0]:dd.dd.filter(function(d){return d<=target;}).pop();if(cand)S.tDay=cand;}}
    B.rerender();},
  function(key,val){if(key==='tday'){S.tDay=val;B.rerender();}});}

/* 기간 상세 창 — 시간 구성 · 손실 이유 · 24시간 시간표 */
function periodWindow(k,unit,use){var P={tab:'comp',sel:null,tDay:null},pd=days.filter(function(d){return B.bucket(d,unit)===k;}),nm=use.length,one=nm===1;
  var a=B.sumU(D.U.filter(function(u){return use.indexOf(u.m)>=0&&B.bucket(u.d,unit)===k;})),c=comp(a,pd.length*86400*nm);
  B.modal('기간 상세 창 · '+B.periodName(k,unit)+' · '+(one?use[0]:'전체 호기 '+nm+'대'),function(w){
    var h='<div class="lwmeta"><span>달력 시간 '+hrs(c.cal)+'h ('+pd.length+'일 × '+nm+'대)</span><span>가동률 <b>'+pc(c.proc,c.cal)+'</b></span><span>Error · 중단 및 조치 '+pc(c.loss,c.cal)+'</span><span>유휴 '+pc(c.idle,c.cal)+'</span></div>'+
      '<div class="pilltabs" role="tablist">'+[['comp','시간 구성'],['loss','손실 이유'],['time','24시간 시간표']].map(function(t){return '<button type="button" class="'+(P.tab===t[0]?'on':'')+'" data-act="tab" data-v="'+t[0]+'">'+t[1]+'</button>';}).join('')+'</div>';
    function line(col,label,x,sub){return '<div class="'+(sub?'sub':'')+'"><i style="background:'+col+'"></i><span>'+esc(label)+'</span><b>'+hrs(x)+'h</b><em>'+pc(x,c.cal)+'</em></div>';}
    if(P.tab==='comp'){var recs=Object.keys(a.rec).map(function(r){return [r,a.rec[r]];}).sort(function(x,y){return y[1]-x[1];}),rtot=recs.reduce(function(s,x){return s+x[1];},0)||1;
      h+=stack(c,{},true)+'<div class="comp">'+line(C.PROC,'웨이퍼 처리',c.proc)+line(C.OK,'그중 같은 wafer 다시 스캔',a.du,1)+line(C.CHECK,'그중 점검 스캔',a.ck,1)+line(C.LOSS,'Error · 중단 및 조치',c.loss)+
        line(C.ERR,'Error',a.e,1)+line(C.DEFECT,B.STOPK.d,a.sd,1)+line(C.STOP,B.STOPK.o,a.so,1)+line(C.IDLE,'유휴',c.idle)+'</div><h3>레시피(Job · Recipe(s))별 웨이퍼 처리 시간</h3>'+
        (recs.length?recs.map(function(x){return '<div class="hbar" data-tip="'+esc(x[0]+'\n웨이퍼 처리 '+hrs(x[1])+'h · '+pc(x[1],rtot))+'"><span class="lab">'+esc(x[0])+'</span><span class="track"><span style="width:'+(x[1]/rtot*100).toFixed(1)+'%;background:var(--navy)"></span></span><span class="val">'+pc(x[1],rtot)+' · '+hrs(x[1])+'h</span></div>';}).join(''):'<p class="hint">웨이퍼 처리 없음</p>');}
    else if(P.tab==='loss'){var rs=Object.keys(a.err).map(function(e){var t=a.err[e];return [e,e,t[0],Object.keys(t[2]).map(Number),C.ERR];});
      rs.push(['__d',B.STOPK.d,a.sd,Object.keys(a.sdl).map(Number),C.DEFECT]);rs.push(['__o',B.STOPK.o,a.so,Object.keys(a.sol).map(Number),C.STOP]);
      rs=rs.filter(function(x){return x[2]>0;}).sort(function(x,y){return y[2]-x[2];});var rmx=rs.length?rs[0][2]:1,cr=rs.filter(function(x){return x[0]===P.sel;})[0];
      h+='<h3>무엇으로 시간을 잃었나 <small>Batch Report의 남은 시간 + 다시 스캔하기까지 조치 · 막대를 누르면 그 Lot</small></h3>'+
        (rs.length?rs.map(function(x){return '<div class="hbar clickable'+(P.sel===x[0]?' sel':'')+'" data-act="rsel" data-v="'+esc(x[0])+'" data-tip="'+esc(x[1]+'\n'+hrs(x[2])+'시간 · Lot '+x[3].length+'개\n누르면 Lot 목록')+'"><span class="lab">'+esc(x[1])+'</span><span class="track"><span style="width:'+(x[2]/rmx*100).toFixed(1)+'%;background:'+x[4]+'"></span></span><span class="val">'+hrs(x[2])+'h · Lot '+x[3].length+'</span></div>';}).join(''):'<p class="hint">잃은 시간이 없습니다.</p>');
      if(cr)h+='<p class="hint">'+esc(cr[1])+' — Lot '+cr[3].length+'개'+(D.lotHref?' (누르면 Lot 추적 HTML 의 Lot History)':'')+'</p><div class="chips">'+cr[3].slice(0,120).map(lotBtn).join('')+'</div>';
      h+='<p class="hint" style="margin-top:14px">작업자 중단(앞 Error 없는 Aborted.)은 Error가 아니지만 결과를 내지 못한 시간이라 여기에 넣습니다.</p>';}
    else{var dd=dataDaysOf(use,pd),day=P.tDay&&dd.indexOf(P.tDay)>=0?P.tDay:dd[dd.length-1]||'';
      h+='<div class="ch"><h3 style="margin:0">24시간 시간표 — '+(one?esc(use[0])+' · 날마다 한 줄':esc(day)+' ('+(day?B.weekday(day):'')+') · 호기별')+'</h3><span class="grow"></span>'+
        (one?'':'<span class="ttnav"><select data-chg="tday" aria-label="날짜">'+dd.map(function(d){return '<option'+(d===day?' selected':'')+'>'+d+'</option>';}).join('')+'</select></span>')+'</div>'+
        timeTable(one?pd.map(function(d){return {label:d.slice(5)+' ('+B.weekday(d)+')',day:d,m:use[0]};}):use.map(function(id){return {label:id,day:day,m:id};}),w);}
    return h;},
  function(act,v){if(act==='tab')P.tab=v;else if(act==='rsel')P.sel=v;else if(act==='lot'){openLot(v);return;}B.rerender();},
  function(key,val){if(key==='tday'){P.tDay=val;B.rerender();}});}

/* ---------------- WPH · 생산능력 탭 (앱 BatchWph) ---------------- */
function jobOf(r){return r.split(' · ')[0];}
function stepOf(r){return r.slice(jobOf(r).length+3);}
function capSum(us){var o={};us.forEach(function(u){(o[u.m]=o[u.m]||[]).push(u);});return Object.keys(o).reduce(function(s,m){return s+(B.cap(B.sumU(o[m]))||0);},0);}
var wphEl=document.getElementById('wphapp');
if(wphEl){var W={recipe:'',mach:'',tab:'cmp',unit:'w',jobs:[],q:'',met:'wa',pick:null};
  var wRows=D.U.filter(function(u){return D.ids.indexOf(u.m)>=0&&(u.n||u.p);});
  var recipes=B.uniq(wRows.filter(function(u){return u.n;}).map(function(u){return u.r;})).sort(),jobs=B.uniq(recipes.map(jobOf));
  function state(){var js=W.jobs.filter(function(j){return jobs.indexOf(j)>=0;}),inJob=function(r){return !js.length||js.indexOf(jobOf(r))>=0;};
    var r0=recipes.indexOf(W.recipe)>=0&&inJob(W.recipe)?W.recipe:'';
    var shown=js.length?recipes.filter(inJob):r0?recipes.filter(function(r){return jobOf(r)===jobOf(r0);}):recipes;
    var o={};wRows.forEach(function(u){if(W.mach&&u.m!==W.mach)return;(o[u.r+'||'+u.m]=o[u.r+'||'+u.m]||[]).push(u);});
    var cells=Object.keys(o).map(function(k){return {r:k.split('||')[0],m:k.split('||')[1],a:B.sumU(o[k])};}).filter(function(c){return c.a.n>0;});
    var sel=wRows.filter(function(u){return (r0?u.r===r0:!js.length||js.indexOf(jobOf(u.r))>=0)&&(!W.mach||u.m===W.mach);});
    return {js:js,r0:r0,shown:shown,cells:cells,sel:sel};}
  function jobFilter(js){if(!jobs.length)return '';var ql=W.q.trim().toLowerCase(),list=jobs.filter(function(j){return !ql||j.toLowerCase().indexOf(ql)>=0||js.indexOf(j)>=0;});
    return '<div class="jobfilter" role="group" aria-label="상위 레시피 필터"><div class="jf-head"><span class="lv up">상위 레시피</span><b>필터</b><span class="jf-state">'+(js.length?js.length+'개 고름 / '+jobs.length+'개':'전체 '+jobs.length+'개 (고르지 않으면 전체)')+'</span><span class="grow"></span>'+
      (jobs.length>8?'<input type="search" id="bvjfq" data-inp="q" placeholder="상위 레시피 찾기" aria-label="상위 레시피 찾기" value="'+esc(W.q)+'">':'')+
      (ql?'<button type="button" class="linklike" data-act="jfound">찾은 것 모두 고르기</button>':'')+'<button type="button" class="linklike" data-act="jall"'+(js.length?'':' disabled')+'>전체 보기</button></div>'+
      '<div class="jf-chips">'+list.map(function(j){var on=js.indexOf(j)>=0;return '<button type="button" class="jf-chip'+(on?' on':'')+'" aria-pressed="'+on+'" title="'+esc(j)+'" data-act="job" data-v="'+esc(j)+'"><i aria-hidden="true">'+(on?'✓':'')+'</i><span>'+esc(j)+'</span><small>하위 '+recipes.filter(function(r){return jobOf(r)===j;}).length+'</small></button>';}).join('')+
      (list.length?'':'<span class="hint">찾는 상위 레시피가 없습니다.</span>')+'</div></div>';}
  function compare(cells,shown,sel,w){var rows=shown.map(function(r){var all=cells.filter(function(c){return c.r===r;}),cs=all.filter(function(c){return B.cap(c.a);}).sort(function(a,b){return (B.cap(b.a)||0)-(B.cap(a.a)||0);});
      return {r:r,cs:cs,sum:cs.reduce(function(s,c){return s+(B.cap(c.a)||0);},0),wn:B.wphNormal(all.reduce(function(acc,c){return B.addAgg(acc,c.a);},B.emptyAgg()))};});
    if(!rows.length)return '<div class="chartcard"><p class="hint">조사 범위에 WPH 자료가 없습니다.</p></div>';
    var mx=Math.max.apply(null,[1].concat(rows.map(function(x){return x.sum;}))),cur=rows.filter(function(x){return x.r===sel;})[0];
    var h='<div class="chartcard"><div class="ch"><h3>레시피별 하루 생산능력 <small>막대 한 칸 = 호기 1대 (24 × 실제 WPH)</small></h3><span class="grow"></span><span class="hint">마우스 = 호기별 값 · 누르면 레시피 상세 창</span></div>';
    if(cur)h+='<p class="capsel'+(cur.wn==null?' none':'')+'">고른 레시피: <b>'+esc(stepOf(cur.r))+'</b> (상위 레시피 '+esc(jobOf(cur.r))+') — '+(cur.wn==null?'정상 WPH 없음 (정상 25매 Batch Report가 없습니다)':'정상 WPH '+f1(cur.wn))+(cur.cs.length?'':' · 실제 WPH 자료 없음')+'</p>';
    B.uniq(rows.map(function(x){return jobOf(x.r);})).forEach(function(j){var sub=rows.filter(function(x){return jobOf(x.r)===j;}),jc=cells.filter(function(c){return jobOf(c.r)===j;});
      h+='<div class="capgrp" role="group" aria-label="상위 레시피 '+esc(j)+'"><div class="capjob"><span class="lv up">상위 레시피</span><b title="'+esc(j)+'">'+esc(j)+'</b><small>하위 레시피 '+sub.length+'개 · 호기 '+B.uniq(jc.map(function(c){return c.m;})).length+'대 · Batch Report '+num(jc.reduce(function(s,c){return s+c.a.n;},0))+'개</small></div>';
      sub.forEach(function(x){h+='<div class="caprow sub'+(x.r===sel?' sel':'')+'"><button type="button" class="linklike cl" title="'+esc(x.r)+'" data-act="rwin" data-v="'+esc(x.r)+'||"><span class="lv dn">하위</span>'+esc(stepOf(x.r))+'</button><span class="capbar">'+
        x.cs.map(function(c){var cp=B.cap(c.a)||0,wd=cp/mx*100,t={t:c.m+' · '+stepOf(x.r),rows:[[D.colors[c.m],'하루 생산능력',num(cp),'장'],['transparent','실제 WPH',f1(B.wphActual(c.a)),''],['transparent','정상 WPH',f1(B.wphNormal(c.a)),''],['transparent','Batch Report',num(c.a.n),'개']],f:['누르면 이 호기의 레시피 상세 창']};
          return '<span style="width:'+wd.toFixed(2)+'%;background:'+D.colors[c.m]+'"'+B.tipAttr(t)+' data-act="rwin" data-v="'+esc(x.r+'||'+c.m)+'">'+(wd>6?esc(c.m):'')+'</span>';}).join('')+
        (x.cs.length?'':'<span class="capnone">실제 WPH 자료 없음 (Pass한 Batch Report 없음)</span>')+'</span><span class="capv">'+(x.cs.length?'<b>'+num(x.sum)+'</b>장/일 · '+x.cs.length+'대':'—')+'<small class="'+(x.wn==null?'none':'')+'">'+(x.wn==null?'정상 WPH 없음':'정상 WPH '+f1(x.wn))+'</small></span></div>';});
      h+='</div>';});
    var used=B.uniq([].concat.apply([],rows.map(function(x){return x.cs.map(function(c){return c.m;});}))).sort();
    return h+'<div class="keys">'+used.map(function(m){return '<span><i style="background:'+D.colors[m]+'"></i>'+esc(m)+'</span>';}).join('')+'<span>같은 호기 = 같은 색</span><span><span class="lv up">상위 레시피</span> Job</span><span><span class="lv dn">하위</span> Recipe(s)</span></div></div>';}
  function table(cells,shown){function row(r,m,a,sum,total){var n=B.wphNormal(a),w=B.wphActual(a),u=B.unitSec(a),sc=B.avgScan(a);
      return '<tr class="clickable'+(total?' total':'')+'" data-act="rwin" data-v="'+esc(r+'||'+(total?'':m))+'"><td class="'+(total?'subr':'')+'">'+(total?'<span class="lv dn">하위</span><b>'+esc(stepOf(r))+'</b>':'')+'</td><td>'+(total?'<b>합계 ('+esc(m)+')</b>':sw(D.colors[m])+esc(m))+'</td>'+
        '<td class="num">'+(u==null?'—':num(u)+'초')+'</td><td class="num">'+(sc==null?'—':num(sc)+'초')+'</td><td class="num">'+f1(n)+'</td><td class="num"><b>'+f1(w)+'</b></td><td class="num">'+pcv(drop(n,w))+'</td><td class="num"><b>'+(sum==null?'—':num(sum))+'</b></td><td class="num">'+num(a.n)+'</td></tr>';}
    var body='';shown.forEach(function(r,i){var cs=cells.filter(function(c){return c.r===r;});if(!cs.length)return;var newJob=!i||jobOf(shown[i-1])!==jobOf(r);
      if(newJob){var jc=cells.filter(function(c){return jobOf(c.r)===jobOf(r);});body+='<tr class="grouphead job"><td colspan="9"><span class="lv up">상위 레시피</span><b>'+esc(jobOf(r))+'</b><small>하위 레시피 '+shown.filter(function(x){return jobOf(x)===jobOf(r)&&cells.some(function(c){return c.r===x;});}).length+'개 · 호기 '+B.uniq(jc.map(function(c){return c.m;})).length+'대 · Batch Report '+num(jc.reduce(function(s,c){return s+c.a.n;},0))+'개</small></td></tr>';}
      body+=row(r,cs.length+'대',cs.reduce(function(acc,c){return B.addAgg(acc,c.a);},B.emptyAgg()),cs.reduce(function(s,c){return s+(B.cap(c.a)||0);},0),true)+cs.map(function(c){return row(r,c.m,c.a,B.cap(c.a),false);}).join('');});
    return '<div class="chartcard"><div class="tscroll tbox" style="max-height:560px"><table><thead><tr><th>레시피 (상위 › 하위)</th><th>호기</th><th class="num">1장 처리 시간</th><th class="num">Avg. Scan Time</th><th class="num">정상 WPH</th><th class="num">실제 WPH</th><th class="num">처리량 감소</th><th class="num">하루 생산능력</th><th class="num">Batch Report</th></tr></thead><tbody>'+
      (body||'<tr><td colspan="9">조사 범위에 WPH 자료가 없습니다.</td></tr>')+'</tbody></table></div><p class="hint">행을 누르면 레시피 상세 창</p></div>';}
  var PK=[['wa','실제 WPH','#10b981'],['wn','정상 WPH','#31517c'],['cap','하루 생산능력','#2a9d8f'],['ps','Pass 장수','#7b5ea7']];
  function periods(rows,r0,w){var o={},unit=W.unit;days.forEach(function(d){(o[B.bucket(d,unit)]=o[B.bucket(d,unit)]||{days:[],us:[]}).days.push(d);});
    rows.forEach(function(u){var k=B.bucket(u.d,unit);(o[k]=o[k]||{days:[u.d],us:[]}).us.push(u);});
    var list=Object.keys(o).sort().map(function(k){var x=o[k],a=B.sumU(x.us);return {k:k,days:x.days,a:a,wn:B.wphNormal(a),wa:B.wphActual(a),cap:x.us.some(function(u){return u.n;})?capSum(x.us):null,machines:B.uniq(x.us.filter(function(u){return u.n;}).map(function(u){return u.m;})).length};});
    var pk=PK.filter(function(p){return p[0]===W.met;})[0],label=pk[1],color=pk[2],U_={d:'일',w:'주',m:'월'}[unit];
    function val(x){return W.met==='wa'?x.wa:W.met==='wn'?x.wn:W.met==='cap'?x.cap:x.a.ps;}
    function per(x){return x.days.length?x.a.ps/x.days.length:null;}
    var items=list.map(function(x){var t={t:B.periodName(x.k,unit),rows:[[PK[0][2],'실제 WPH',f1(x.wa),''],[PK[1][2],'정상 WPH',f1(x.wn),''],['transparent','처리량 감소',pcv(drop(x.wn,x.wa)),''],
        [PK[2][2],'하루 생산능력',x.cap==null?'—':num(x.cap),'장/일'+(x.machines>1?' · '+x.machines+'대':'')],[PK[3][2],'Pass 장수',num(x.a.ps),'장 · 하루 평균 '+num(per(x))],['transparent','Batch Report',num(x.a.n),'개']],f:r0&&x.a.n?['누르면 이 기간의 레시피 상세 창']:undefined};
      return {id:x.k,short:B.shortKey(x.k,unit),short2:unit==='w'?B.weekRange(x.k):undefined,v:{y:val(x)||0},tipx:t};});
    var has=list.some(function(x){return x.a.n;});
    var h='<div class="chartcard"><div class="ch"><h3>기간별 '+esc(label)+' <small>'+U_+' 단위 · 왼쪽이 오래된 기간</small></h3><span class="grow"></span>'+B.seg(W.met,PK.map(function(p){return [p[0],p[1]];}),'met','그래프 값')+'</div>';
    if(!has)return h+'<p class="hint">조사 범위에 WPH 자료가 없습니다.</p></div>';
    h+=B.colChart({items:items,keys:[['y',label,color]],h:220,minw:unit==='d'?14:26,maxw:70,sel:W.pick,label:'기간별 '+label,fy:W.met==='wa'||W.met==='wn'?function(x){return num(x,1);}:num,width:w-30,act:'pper'});
    h+='<div class="tscroll tbox"><table><thead><tr><th>기간</th><th class="num">정상 WPH</th><th class="num">실제 WPH</th><th class="num">처리량 감소</th><th class="num">하루 생산능력</th><th class="num">Pass 장수</th><th class="num">하루 평균 Pass</th><th class="num">Batch Report</th></tr></thead><tbody>'+
      list.slice().reverse().map(function(x){return '<tr class="'+(r0&&x.a.n?'clickable':'')+(W.pick===x.k?' sel':'')+'" data-act="pper" data-v="'+esc(x.k)+'"><td>'+esc(B.periodName(x.k,unit))+(unit==='d'?'':'<small> · '+x.days.length+'일</small>')+'</td><td class="num">'+f1(x.wn)+'</td><td class="num"><b>'+f1(x.wa)+'</b></td><td class="num">'+pcv(drop(x.wn,x.wa))+'</td>'+
        '<td class="num"><b>'+(x.cap==null?'—':num(x.cap))+'</b>'+(x.machines>1?'<small> · '+x.machines+'대</small>':'')+'</td><td class="num">'+num(x.a.ps)+'</td><td class="num">'+(x.a.n?num(per(x)):'—')+'</td><td class="num">'+num(x.a.n)+'</td></tr>';}).join('')+'</tbody></table></div>'+
      '<p class="hint">'+(r0?'기간을 누르면 그 기간의 레시피 상세 창이 열립니다.':'레시피를 고르면 기간을 눌러 그 기간의 레시피 상세 창을 볼 수 있습니다.')+' 하루 생산능력 = 호기마다 24 × 그 기간 실제 WPH 의 합'+(r0?'':'(레시피 통합)')+', 하루 평균 Pass = Pass 장수 ÷ 기간 일수(조사 범위 안).</p></div>';
    W._list=list;return h;}
  B.mount(wphEl,function(w){var s=state(),A=B.sumU(s.sel),wn=B.wphNormal(A),wa=B.wphActual(A),r0=s.r0;
    var total=r0?s.cells.filter(function(c){return c.r===r0;}).reduce(function(t,c){return t+(B.cap(c.a)||0);},0):W.mach?B.cap(A):null;
    var nMach=r0?s.cells.filter(function(c){return c.r===r0&&B.cap(c.a);}).length:0;
    var h='<div class="filters"><label class="field">하위 레시피(Recipe(s))<select data-chg="recipe"><option value="">'+(s.js.length?'고른 상위 레시피 '+s.js.length+'개 전체':'전체 레시피')+'</option>'+
      jobs.filter(function(j){return !s.js.length||s.js.indexOf(j)>=0;}).map(function(j){return '<optgroup label="'+esc('상위 · '+j)+'">'+recipes.filter(function(r){return jobOf(r)===j;}).map(function(r){return '<option value="'+esc(r)+'"'+(r===r0?' selected':'')+'>'+esc(stepOf(r))+'</option>';}).join('')+'</optgroup>';}).join('')+'</select></label>'+
      '<label class="field">호기<select data-chg="mach"><option value="">전체 호기</option>'+D.ids.map(function(id){return '<option'+(id===W.mach?' selected':'')+'>'+esc(id)+'</option>';}).join('')+'</select></label></div>'+jobFilter(s.js);
    var K=[['정상 WPH',f1(wn),'','정상 25매 Batch Report '+num(A.w25/25)+'장',''],['실제 WPH',f1(wa),'','Pass '+num(A.ps)+'장 · 유휴만 뺀 시간','t'],['처리량 감소',pcv(drop(wn,wa)).replace('%',''),'%','1 − 실제 ÷ 정상','r'],
      [r0?'하루 생산능력 · 레시피 합계':'하루 생산능력',total==null?'—':num(total),total==null?'':'장/일',r0?nMach+'대 합계':W.mach?W.mach+' · 레시피 통합':'레시피 또는 호기를 고르세요','a']];
    h+='<div class="kpis k4">'+K.map(function(k){return '<div class="kpi '+k[4]+'"><div class="n">'+esc(k[1])+'<span class="u">'+k[2]+'</span></div><div class="l">'+esc(k[0])+'</div><div class="s">'+esc(k[3])+'</div></div>';}).join('')+'</div>';
    h+='<div class="viewbar">'+B.seg(W.tab,[['cmp','레시피 비교'],['tbl','호기 × 레시피 표'],['per','기간별 추이']],'tab','보기')+(W.tab==='per'?B.seg(W.unit,[['d','일'],['w','주'],['m','월']],'unit','기간 단위'):'')+'<span class="grow"></span><span class="hint">'+
      esc(W.tab==='per'?(r0?stepOf(r0)+' · '+(W.mach||'전체 호기'):(s.js.length?'상위 레시피 '+s.js.length+'개':'전체 레시피')+' · '+(W.mach?W.mach+' · 레시피 통합':'전체 호기')+(s.js.length?'':' (레시피를 고르면 그 레시피만)'))
        :s.js.length?'상위 레시피 '+s.js.length+'개의 하위 레시피끼리 비교':r0?jobOf(r0)+'의 하위 레시피끼리 비교':'상위 레시피를 고르거나 하위 레시피를 고르면 같은 상위 레시피끼리 비교합니다')+'</span></div>';
    h+=W.tab==='cmp'?compare(s.cells,s.shown,r0,w):W.tab==='tbl'?table(s.cells,s.shown):periods(s.sel,r0,w);
    return h;},
  function(act,v){var s=state();
    if(act==='tab')W.tab=v;else if(act==='unit'){W.unit=v;W.pick=null;}else if(act==='met')W.met=v;
    else if(act==='job'){var i=W.jobs.indexOf(v);if(i>=0)W.jobs.splice(i,1);else W.jobs.push(v);}
    else if(act==='jall')W.jobs=[];
    else if(act==='jfound'){var ql=W.q.trim().toLowerCase();jobs.forEach(function(j){if(j.toLowerCase().indexOf(ql)>=0&&W.jobs.indexOf(j)<0)W.jobs.push(j);});}
    else if(act==='rwin'){var p=v.split('||');recipeWindow(p[0],p[1]||'',D.range[0],D.range[1]);return;}
    else if(act==='pper'){W.pick=W.pick===v?null:v;var x=(W._list||[]).filter(function(y){return y.k===v;})[0];
      if(s.r0&&x&&x.a.n&&x.days.length){B.rerender();recipeWindow(s.r0,W.mach,x.days[0],x.days[x.days.length-1]);return;}}
    B.rerender();},
  function(key,val){if(key==='recipe')W.recipe=val;else if(key==='mach')W.mach=val;else if(key==='q')W.q=val;B.rerender();});}

/* 레시피 상세 창 — WPH 분해 · 1장 처리 시간 · Lot별 실제 WPH. m = '' 이면 그 레시피를 돌린 호기 전체 */
function recipeWindow(r,m,from,to){var P={tab:'split',bin:null};
  function inR(d){return d>=from&&d<=to;}function okM(x){return m?x===m:D.ids.indexOf(x)>=0;}
  var us=D.U.filter(function(u){return u.r===r&&okM(u.m)&&inR(u.d);}),A=B.sumU(us),wn=B.wphNormal(A),wa=B.wphActual(A),Dd=A.p+B.lossOf(A),wp=A.p?A.ps*3600/A.p:null;
  var machines=B.uniq(us.filter(function(u){return u.n;}).map(function(u){return u.m;})).sort();
  var perM=machines.map(function(x){return {m:x,a:B.sumU(us.filter(function(u){return u.m===x;}))};});
  B.modal('레시피 상세 창 · '+stepOf(r)+' · '+(m||'호기 '+machines.length+'대'),function(w){
    var h='<div class="lwmeta"><span class="job">'+esc(jobOf(r))+'</span><span>정상 WPH <b>'+f1(wn)+'</b></span><span>실제 WPH <b>'+f1(wa)+'</b></span><span>처리량 감소 '+pcv(drop(wn,wa))+'</span>'+
      '<span>하루 생산능력 <b>'+(m?num(B.cap(A)):num(perM.reduce(function(s,x){return s+(B.cap(x.a)||0);},0)))+'</b>장'+(m?'':' ('+machines.length+'대 합계)')+'</span><span>'+esc(from)+' ~ '+esc(to)+'</span></div>'+
      '<div class="pilltabs" role="tablist">'+[['split','WPH 분해'],['unit','1장 처리 시간'],['lots','Lot별 실제 WPH']].map(function(t){return '<button type="button" class="'+(P.tab===t[0]?'on':'')+'" data-act="tab" data-v="'+t[0]+'">'+t[1]+'</button>';}).join('')+'</div>';
    if(P.tab==='split'){var steps=[];if(wn!=null&&wp!=null)steps.push(['기타 차이 (25매가 아닌 Lot · 느렸던 스캔 · 다시 스캔)',wn-wp,C.IDLE]);
      if(wp!=null&&Dd>0){steps.push(['Error',wp*A.e/Dd,C.ERR]);steps.push([B.STOPK.d,wp*A.sd/Dd,C.DEFECT]);steps.push([B.STOPK.o,wp*A.so/Dd,C.STOP]);}
      var top=Math.max(wn||0,wp||0,1),at=wn!=null?wn:wp!=null?wp:0;
      h+='<h3>정상 WPH에서 실제 WPH까지</h3><div class="wfall">'+(wn!=null?'<div class="wf"><span class="lab">정상 WPH</span><span class="track"><span style="left:0;width:'+(wn/top*100)+'%;background:#31517c"></span></span><b>'+f1(wn)+'</b></div>':'')+
        steps.map(function(s){var a=at,b=at-s[1];at=b;var lo=Math.min(a,b),wd=Math.abs(s[1]);return '<div class="wf" data-tip="'+esc(s[0]+'\n'+(s[1]>=0?'−':'+')+num(Math.abs(s[1]),2)+' WPH')+'"><span class="lab">'+esc(s[0])+'</span><span class="track"><span style="left:'+(lo/top*100)+'%;width:'+Math.max(.4,wd/top*100)+'%;background:'+s[2]+'"></span></span><b>'+(s[1]>=0?'−':'+')+Math.abs(s[1]).toFixed(1)+'</b></div>';}).join('')+
        '<div class="wf"><span class="lab">실제 WPH</span><span class="track"><span style="left:0;width:'+((wa||0)/top*100)+'%;background:'+C.OK+'"></span></span><b>'+f1(wa)+'</b></div></div>';
      function rate(x,n){return n?num(x/n*100,1)+'% ('+num(x)+' / '+num(n)+')':'—';}
      h+='<div class="two"><div><h3>시간 <small>유휴는 빼고 셉니다</small></h3><table><tbody><tr><td>웨이퍼 처리</td><td class="num">'+hrs(A.p)+'h</td><td class="num">'+pcv(B.pctOf(A.p,Dd))+'</td></tr><tr><td>Error</td><td class="num">'+hrs(A.e)+'h</td><td class="num">'+pcv(B.pctOf(A.e,Dd))+'</td></tr>'+
        '<tr><td>'+B.STOPK.d+'</td><td class="num">'+hrs(A.sd)+'h</td><td class="num">'+pcv(B.pctOf(A.sd,Dd))+'</td></tr><tr><td>'+B.STOPK.o+'</td><td class="num">'+hrs(A.so)+'h</td><td class="num">'+pcv(B.pctOf(A.so,Dd))+'</td></tr></tbody></table></div>'+
        '<div><h3>얼마나 자주</h3><table><tbody><tr><td>Error 발생률</td><td class="num">'+rate(A.ne,A.n)+'</td></tr><tr><td>중단 발생률 · Defect 과다</td><td class="num">'+rate(A.nsd,A.n)+'</td></tr><tr><td>중단 발생률 · 그 외</td><td class="num">'+rate(A.nso,A.n)+'</td></tr><tr><td>재스캔 참고 비율</td><td class="num">'+rate(A.dn,A.ps)+'</td></tr></tbody></table></div></div>';
      var errs=Object.keys(A.err).map(function(e){return [e,A.err[e]];}).sort(function(a,b){return b[1][0]-a[1][0];}),emx=errs.length?errs[0][1][0]:1;
      h+='<h3>Error 원문별 잃은 시간 <small>Batch Report 남은 시간 + 다시 스캔하기까지 조치</small></h3>'+(errs.length?errs.map(function(x){return '<div class="hbar"><span class="lab" title="'+esc(x[0])+'">'+esc(x[0])+'</span><span class="track"><span style="width:'+(x[1][0]/emx*100)+'%;background:'+C.ERR+'"></span></span><span class="val">'+hrs(x[1][0])+'h · wafer '+num(x[1][1])+'</span></div>';}).join(''):'<p class="hint">Error로 잃은 시간이 없습니다.</p>');}
    else if(P.tab==='unit'){var umx=Math.max.apply(null,[1].concat(perM.map(function(x){return B.unitSec(x.a)||0;})));
      h+='<h3>1장 처리 시간 = Avg. Scan Time + 로봇 이동 · 로딩 · 얼라인</h3>'+(perM.length?perM.map(function(x){var u=B.unitSec(x.a),s=B.avgScan(x.a);
        return '<div class="caprow" data-tip="'+esc(x.m+'\n1장 처리 시간 '+(u==null?'—':num(u,1)+'초')+'\nAvg. Scan Time '+(s==null?'—':num(s,1)+'초')+'\n로봇 이동 등 '+(u!=null&&s!=null?num(u-s,1)+'초':'—')+'\n정상 25매 Batch Report '+num(x.a.w25/25)+'장')+'"><span class="cl">'+esc(x.m)+'</span><span class="capbar">'+
          (u!=null&&s!=null?'<span style="width:'+(s/umx*100)+'%;background:#31517c">Avg. Scan '+num(s)+'초</span><span style="width:'+((u-s)/umx*100)+'%;background:#9db7d9"></span>':u!=null?'<span style="width:'+(u/umx*100)+'%;background:#9db7d9"></span>':'')+'</span><span class="capv"><b>'+(u==null?'—':num(u))+'</b>초</span></div>';}).join(''):'<p class="hint">자료가 없습니다.</p>')+
        '<div class="keys"><span><i style="background:#31517c"></i>Avg. Scan Time(순수 스캔, 원문)</span><span><i style="background:#9db7d9"></i>로봇 이동 · 로딩 · 얼라인</span><span>정상 25매 Batch Report 기준</span></div>';
      var cl=D.N.filter(function(x){return x.r===r&&okM(x.m)&&inR(x.d);}).map(function(x){return {x:x,w:25*3600/x.s,bin:''};}),bins=[];
      if(cl.length){var vs=cl.map(function(c){return c.w;}),lo=Math.min.apply(null,vs),hi=Math.max.apply(null,vs),span=Math.max(hi-lo,1),st=[0.5,1,2,2.5,5,10,20].filter(function(s){return span/s<=14;})[0]||20,s0=Math.floor(lo/st)*st,nb=Math.floor((hi-s0)/st)+1;
        for(var i=0;i<nb;i++)bins.push({id:String(i),lo:s0+i*st,hi:s0+(i+1)*st,n:0});cl.forEach(function(c){var i=Math.min(nb-1,Math.floor((c.w-s0)/st));bins[i].n++;c.bin=String(i);});}
      var cb=P.bin!=null&&bins[+P.bin]?P.bin:null,list=cl.filter(function(c){return cb==null||c.bin===cb;}).sort(function(a,b){return D.R[a.x.g].s<D.R[b.x.g].s?1:-1;});
      h+='<h3>정상 25매 Batch Report의 WPH 분포 <small>막대를 누르면 그 구간만 목록에</small></h3>'+(cl.length?B.colChart({items:bins.map(function(b){return {id:b.id,short:num(b.lo,1),v:{n:b.n},tip:'WPH '+num(b.lo,1)+' ~ '+num(b.hi,1)+'\n정상 25매 Batch Report '+b.n+'개\n누르면 이 구간만 목록에'};}),
          keys:[['n','Batch Report','#31517c']],h:190,minw:18,maxw:70,sel:cb,label:'정상 WPH 분포',width:w,act:'bin'})+
        '<div class="tbox" style="max-height:300px"><table><thead><tr><th>시작</th><th>호기</th><th>Lot</th><th class="num">Batch Time</th><th class="num">Avg. Scan Time</th><th class="num">WPH</th></tr></thead><tbody>'+
        list.map(function(c){var rr=D.R[c.x.g];return '<tr><td>'+esc(rr.s)+'</td><td>'+esc(rr.m)+'</td><td>'+lotBtn(c.x.lot)+'</td><td class="num">'+B.dur(c.x.s/60)+'</td><td class="num">'+(c.x.a==null?'—':num(c.x.a)+'초')+'</td><td class="num"><b>'+num(c.w,1)+'</b></td></tr>';}).join('')+'</tbody></table></div>'
        :'<p class="hint">정상 25매 Batch Report가 없습니다.</p>');}
    else{var L=D.L.filter(function(x){return x.r===r&&okM(x.m)&&inR(x.d);});
      var worst=L.filter(function(x){return x.n>1;}).map(function(x){return [x,x.ps*3600/x.s];}).sort(function(a,b){return a[1]-b[1];}).slice(0,40);
      h+='<h3>Lot별 실제 WPH <small>점 하나 = Lot 한 번의 스캔(공정 단계)'+(D.lotHref?' · 누르면 Lot History':'')+'</small></h3><div class="keys"><span><i style="background:'+C.OK+'"></i>한 번에 스캔</span><span><i style="background:'+C.WAIT+'"></i>재스캔 포함</span><span>점선 = 정상 WPH</span></div>'+
        B.scatter(L.map(function(x){var y=x.ps*3600/x.s,lb=lots[x.lot]?lots[x.lot].label:'';return {t:new Date(x.d+'T12:00:00').getTime(),y:y,id:x.lot,c:x.n>1?C.WAIT:C.OK,
          tip:'Lot '+lb+' · '+x.m+'\n'+x.d+'\nBatch Report '+x.n+'개 · Pass '+x.ps+'장'+(x.dn?' (다시 스캔해 또 Pass '+x.dn+')':'')+'\n쓴 시간 '+hrs(x.s)+'h (조치 대기 포함)\n실제 WPH '+num(y,1)+(D.lotHref?'\n누르면 Lot History':'')};}),wn,w,'lot')+
        '<h3>처리량이 많이 줄어든 Lot <small>재스캔이 있었던 Lot 중 실제 WPH가 낮은 순</small></h3><div class="tbox" style="max-height:330px"><table><thead><tr><th>Lot</th><th>시작</th><th>호기</th><th class="num">Batch Report</th><th class="num">쓴 시간(h)</th><th class="num">실제 WPH</th><th class="num">처리량 감소</th></tr></thead><tbody>'+
        worst.map(function(p){var x=p[0];return '<tr><td>'+lotBtn(x.lot)+'</td><td>'+esc(x.d)+'</td><td>'+esc(x.m)+'</td><td class="num">'+x.n+'</td><td class="num">'+hrs(x.s)+'</td><td class="num">'+num(p[1],1)+'</td><td class="num">'+pcv(drop(wn,p[1]))+'</td></tr>';}).join('')+
        (worst.length?'':'<tr><td colspan="7">재스캔한 Lot이 없습니다.</td></tr>')+'</tbody></table></div>';}
    return h;},
  function(act,v){if(act==='tab')P.tab=v;else if(act==='bin')P.bin=P.bin===v?null:v;else if(act==='lot'){openLot(v);return;}B.rerender();});}
})();
"""

# Lot 추적 HTML — 기간별 Lot Scan 현황(누르면 그 기간 Lot 만 목록에, 앱 Lot 추적과 같음) + #lot=<Lot> 으로 Lot History 바로 열기.
LOTCHART_JS = LOTKEYS_JS + r"""
(function(){var B=BV,el=document.getElementById('lotchart');if(!el||!window.__LOTDATA)return;var L=window.__LOTDATA.lots,P=window.__LOTPERIOD;
  var lots=L.map(function(l){return {s:l.start,state:l.state};});
  B.mount(el,function(w){return '<div class="chartcard"><div class="ch"><h3>기간별 Lot Scan 현황</h3><span class="hint">막대에 마우스를 올리면 자세히, 누르면 그 기간 Lot만 아래 목록에 보입니다.</span><span class="grow"></span>'+
      B.legend(LOTKEYS,P.hid,'lgd')+B.seg(P.unit,[['d','일'],['w','주'],['m','월']],'unit','기간 단위')+'</div>'+
      B.colChart({items:lotItems(lots,P.unit),keys:LOTKEYS,hidden:P.hid,sel:P.period,maxw:P.unit==='w'?100:60,label:'기간별 Lot Scan 현황',width:w,act:'per'})+
      (P.period?'<p class="hint">기간 '+B.esc(B.periodName(P.period,P.unit))+' 의 Lot만 아래 목록에 보입니다. <button type="button" class="linklike" data-act="per" data-v="'+B.esc(P.period)+'">기간 선택 해제</button></p>':'')+'</div>';},
    function(act,v){if(act==='unit'){P.unit=v;P.period=null;}else if(act==='lgd')P.hid[v]=!P.hid[v];else if(act==='per')P.period=P.period===v?null:v;
      B.rerender();if(window.__lotRedraw)window.__lotRedraw();});
  function fromHash(){var m=/^#lot=(.+)$/.exec(location.hash||'');if(!m)return;var label=decodeURIComponent(m[1]);
    for(var i=0;i<L.length;i++)if(L[i].label===label){if(window.__openLot)window.__openLot(i);return;}}
  fromHash();window.addEventListener('hashchange',fromHash);
})();
"""


def data_script(element_id, obj):
    """JSON 을 <script type="application/json"> 으로 — '</' · '<!--' 를 막아 HTML 을 깨지 않게."""
    blob = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return f'<script type="application/json" id="{element_id}">{blob}</script>'
