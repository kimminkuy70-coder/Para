import {desktop} from './desktop';

/* Batch Report 화면 데이터 — 엔진 batchview.View.payload() 와 같은 모양.
   요약은 조각(batch_view)으로 받아 이어 붙이고, Lot 상세 · 원문은 누를 때 받는다(4MB 전송 한도). */
/** o = Batch Report 결과(c 정상 · e Error 있음 · s 작업자 중단), sk = 중단 종류(d Defect 과다 · o 그 외), ff = 멈출 때 wafer Faults,
    st = 중단 행 수, sp = 스캔 안 한 슬롯(앞 Error 없는 Skipped) 행 수, r = 레시피(Job · Recipe(s)) */
export type Rep={f:string;m:string;sm:string;code:string;job:string;setup:string;step:string;k:string;s:string;e:string;sec:number;
  lot:number|null;b:number|null;n:number;ok:number;err:number;chain:number;fe:string;st:number;sp:number;o:'c'|'e'|'s';sk:''|'d'|'o';ff:number|null;r:string};
export type Bunch={att:number[];step:string;k:string;s:string;e:string;moved:boolean;machines:string[];sec:number};
export type Lot={key:string;label:string;code:string;lot_id:string;sms:string[];jobs:string[];machines:string[];n:number;s:string;e:string;
  state:string;open:number;re:number;dup:number;moved:boolean;saved:number;scans:string[];multi:boolean;causes:[string,number][];cz:[string,number,boolean][];sz:['d'|'o',number,boolean][];bunches:Bunch[]};
/** 날짜 × 호기 × 레시피 한 칸(초). p 웨이퍼 처리(du 그중 이미 Pass 한 wafer 다시 스캔) · ck 점검 스캔 ·
    e Error 원문별 [손실 초, wafer 수, Lot] · sd/so 작업자 중단 Defect 과다/그 외 [손실 초, Batch Report 수, Lot] ·
    ps Pass 장수 · dn 다시 스캔해 또 Pass 한 장수 · n Batch Report 수 · ne Error 있는 Batch Report 수 ·
    w25/s25 정상 25매 Batch Report 장수/Batch Time · aw/asum Avg. Scan Time 장수/합 */
export type U={d:string;m:string;r:string;p:number;du:number;ck:number;e:Record<string,[number,number,number[]]>;
  sd:[number,number,number[]];so:[number,number,number[]];ps:number;dn:number;n:number;ne:number;w25:number;s25:number;aw:number;asum:number};
/** t = e(Error 뒤) · s(작업자 중단 뒤) 조치 대기 */
export type Wait={m:string;s:string;e:string;li:number;g:number;t:'e'|'s'};
export type Stop={g:number;m:string;r:string;li:number;f:number|null;k:'d'|'o';base:number|null;ps:number};
export type NRep={g:number;m:string;r:string;d:string;s:number;a:number|null;lot:number};
export type LRow={lot:number;b:number;m:string;r:string;d:string;ps:number;s:number;n:number;dn:number};
export type Bases={unit:Record<string,number>;faults:Record<string,[number|null,number]>;min_base:number;full:number};
export type MStat={parsed:number;reused:number;records:number;offline:boolean;cached?:boolean};
export type View={R:Rep[];lots:Lot[];excluded:number[];U:U[];waits:Wait[];stops:Stop[];N:NRep[];L:LRow[];X:Bases;hits:number[];range:[string,string];
  saved:number;criteria:[string,string,string][];
  scope?:{machines:string[];start:string;end:string;reuse:boolean;at:string};restored?:boolean;mstat?:Record<string,MStat>;
  collection?:{parsed:number;reused:number;errors:number;cached_only:number};errors?:[string,string,string][];artifacts?:Record<string,string>;
  find?:{query:string;start:string;end:string;listed:number;total:number};scan?:Record<string,{paths:string[];pattern:string}>;scan_backup?:boolean};
export type ViewMeta={view:string;version:number;size:number;saved?:number;lots?:number;reports?:number};
/** cells = [Batch Report 위치, 원문, Pass, 연쇄, Scanned, Bad, Good, 작업자 중단] */
export type Cell=[number,string,boolean,boolean,number|null,number|null,number|null,boolean?];
export type Wafer={k:string;slot:number|null;id:string;v:string;pick:number|null;rec:number|null;ov:boolean;cause:string;chain:boolean;stop?:boolean;cells:Cell[]};
export type LotDetail={li:number;bunches:{wafers:Wafer[]}[];stats:Record<string,{ph:[string,number][];cph:[string,number][]}>};
export type Raw={g:number;f:string;m:string;folder:string;path:string;meta:[string,string][];h:string[];rows:string[][]};
export type AggCell={g:number;status:string;ok:boolean;id:string;sc:number|null;bad:number|null;good:number|null};
export type AggGroup={li:number;bi:number;att:number[];keys:string[];w:Record<string,{cells:AggCell[];rec:number;auto:number;saved:boolean}>};
export type ViewName='scope'|'find';

export async function loadView(meta:ViewMeta):Promise<View|undefined>{
  if(!meta.version||!meta.size)return undefined;
  let data='',offset=0;
  while(offset<meta.size){
    const r=(await desktop.request('batch_view',{view:meta.view,version:meta.version,offset}).promise).batch as {data:string;size:number};
    if(!r.data.length)break;
    data+=r.data;offset+=r.data.length;
  }
  return JSON.parse(data) as View;
}
export async function batchCall<T>(method:string,params:object):Promise<T>{
  return (await desktop.request(method,params).promise).batch as T;
}

export const V=['한 번에 Pass','재스캔 Pass','중복 Pass','Pass 없음'];
export const VC:Record<string,string>={'한 번에 Pass':'v1','재스캔 Pass':'v2','중복 Pass':'v3','Pass 없음':'v4'};
export const DONE='한 번에 완료',RE='재스캔으로 완료',OPEN='Pass하지 못한 wafer 존재',STATES=[DONE,RE,OPEN];
export const ST:Record<string,string>={[DONE]:'done',[RE]:'re',[OPEN]:'open'};
export const C_OK='#10b981',C_ERR='#c2410c',C_WAIT='#d69e2e',C_CHAIN='#f0b44c';
/** 시간 3칸 · 작업자 중단 색 */
export const C_PROC=C_OK,C_LOSS=C_ERR,C_IDLE='#dfe5ec',C_STOP='#7c8fb0',C_DEFECT='#9b4dca',C_CHECK='#94a3b8',C_DUP='#6ee7b7';
export const STOPK:Record<string,string>={d:'작업자 중단 · Defect 과다',o:'작업자 중단 · 그 외'};
/** 호기 색 — 같은 호기는 어느 그래프 · 어느 레시피에서도 같은 색(이슈 #7). 호기 이름 정렬 순서로 정하므로 레시피 · 정렬과 무관.
    저장된 결과 파일(`batchsaved.MACH_PAL`)도 같은 표 · 같은 순서를 쓴다. */
export const MACH_PAL=['#1f77b4','#2a9d8f','#e07b39','#7b5ea7','#3a7d44','#c44e7a','#5b8fc7','#b8860b','#17859b','#8c564b','#4c6ef5','#6b8e23','#d1495b','#31517c','#9c6ade','#00a676'];
export function machColors(ids:string[]):Record<string,string>{const o:Record<string,string>={};[...new Set(ids)].sort().forEach((m,i)=>{o[m]=MACH_PAL[i%MACH_PAL.length];});return o;}

/** U 행을 더한 값(초). 화면이 호기 · 기간 · 레시피로 골라 더한다. */
export type Agg={p:number;du:number;ck:number;e:number;sd:number;so:number;ps:number;dn:number;n:number;ne:number;nsd:number;nso:number;
  w25:number;s25:number;aw:number;asum:number;err:Record<string,[number,number,Record<number,1>]>;sdl:Record<number,1>;sol:Record<number,1>;rec:Record<string,number>};
export function emptyAgg():Agg{return {p:0,du:0,ck:0,e:0,sd:0,so:0,ps:0,dn:0,n:0,ne:0,nsd:0,nso:0,w25:0,s25:0,aw:0,asum:0,err:{},sdl:{},sol:{},rec:{}};}
export function addU(a:Agg,u:U){
  a.p+=u.p;a.du+=u.du;a.ck+=u.ck;a.ps+=u.ps;a.dn+=u.dn;a.n+=u.n;a.ne+=u.ne;a.w25+=u.w25;a.s25+=u.s25;a.aw+=u.aw;a.asum+=u.asum;
  a.sd+=u.sd[0];a.nsd+=u.sd[1];u.sd[2].forEach(li=>{a.sdl[li]=1;});a.so+=u.so[0];a.nso+=u.so[1];u.so[2].forEach(li=>{a.sol[li]=1;});
  if(u.p)a.rec[u.r]=(a.rec[u.r]||0)+u.p;
  Object.entries(u.e).forEach(([k,x])=>{a.e+=x[0];const t=a.err[k]||(a.err[k]=[0,0,{}]);t[0]+=x[0];t[1]+=x[1];x[2].forEach(li=>{t[2][li]=1;});});
  return a;
}
export function sumU(rows:U[]){const a=emptyAgg();rows.forEach(u=>addU(a,u));return a;}
/** Error · 중단 및 조치(손실) 초 */
export const lossOf=(a:Agg)=>a.e+a.sd+a.so;
/** 정상 WPH = 정상 25매 Batch Report 장수 합 × 3600 ÷ Batch Time 합 */
export const wphNormal=(a:Agg)=>a.s25?a.w25*3600/a.s25:null;
/** 실제 WPH = Pass 장수 × 3600 ÷ (웨이퍼 처리 + Error · 중단 및 조치) — 유휴만 뺀 시간 */
export const wphActual=(a:Agg)=>{const d=a.p+lossOf(a);return d>0?a.ps*3600/d:null;};
export const unitSec=(a:Agg)=>a.w25?a.s25/a.w25:null;
export const avgScan=(a:Agg)=>a.aw?a.asum/a.aw:null;
export const pctOf=(x:number,t:number)=>t>0?x/t*100:null;

export function num(v:number|null|undefined,d=0){return v==null||Number.isNaN(v)?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:d});}
export const hrs=(s:number)=>num(s/3600,1);
export const ts=(s:string)=>new Date(String(s).replace(' ','T')).getTime();
export const mins=(a:string,b:string)=>(ts(b)-ts(a))/60000;
export function dur(m:number){if(Number.isNaN(m))return '—';m=Math.max(0,m);return m<60?Math.round(m)+'분':m<2880?num(m/60,1)+'시간':num(m/1440,1)+'일';}
export const pad=(x:number)=>(x<10?'0':'')+x;
export const ymd=(dt:Date)=>dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate());
export function addDays(d:string,k:number){const x=new Date(d+'T00:00:00');x.setDate(x.getDate()+k);return ymd(x);}
export function niceMax(v:number){if(!(v>0))return 1;const p=Math.pow(10,Math.floor(Math.log10(v)));for(const m of [1,2,2.5,5,10])if(m*p>=v)return m*p;return 10*p;}
export type Unit='d'|'w'|'m';
export function bucket(d:string,u:Unit){if(u==='d')return d;if(u==='m')return d.slice(0,7);const dt=new Date(d+'T00:00:00'),w=(dt.getDay()+6)%7;dt.setDate(dt.getDate()-w);return ymd(dt)+' 주';}
export function bucketDays(key:string,u:Unit){if(u==='d')return 1;if(u==='m'){const y=+key.slice(0,4),m=+key.slice(5,7);return new Date(y,m,0).getDate();}return 7;}
export const shortKey=(k:string,u:Unit)=>u==='m'?k.slice(2,7):u==='w'?'WW'+workWeek(k.slice(0,10)):k.slice(5,10);
/** 주 번호(WW) — ISO 주(월요일 시작, 1월 4일이 든 주 = WW1)라 한 해는 보통 WW1~WW52(가끔 WW53). d = 그 주 월요일. */
export function workWeek(d:string){const th=new Date(d+'T00:00:00');th.setDate(th.getDate()+3);
  const j1=new Date(th.getFullYear(),0,1);return Math.floor(Math.round((th.getTime()-j1.getTime())/864e5)/7)+1;}
/** 주 막대 아래 둘째 줄 — (MM/DD~MM/DD) */
export function weekRange(k:string){const st=k.slice(0,10),en=addDays(st,6);return '('+st.slice(5).replace('-','/')+'~'+en.slice(5).replace('-','/')+')';}
/** 기간 이름(툴팁 제목) — 주는 'YYYY WWn (MM/DD~MM/DD)' */
export function periodName(k:string,u:Unit){if(u!=='w')return k;const st=k.slice(0,10),th=addDays(st,3);return th.slice(0,4)+' WW'+workWeek(st)+' '+weekRange(k);}
export const phList=(o:[string,number][])=>o.map(([k,n])=>k+' ×'+n).join(' · ');
export const isRealId=(id:string)=>!!id&&!/^(slot\s*)?\d{1,2}$/i.test(String(id).trim());
export const WD='일월화수목금토';
export const weekday=(d:string)=>WD[new Date(d+'T00:00:00').getDay()];
export function spanLabel(b:Bunch){return b.s.slice(0,10)===b.e.slice(0,10)?b.s.slice(5)+' ~ '+b.e.slice(11):b.s.slice(5,10)+' ~ '+b.e.slice(5,10);}
/** 3D 스캔 = S/M 에 단독 3D(ABC-3D). 레시피가 2D 와 같아 이름으로만 구분하고 2D 와 따로 센다(대전제). */
export const is3D=(k?:string)=>k==='3D';
export const kindWord=(k?:string)=>is3D(k)?'3D 스캔':'2D 스캔';
export const stepLabel=(b:{step:string;k?:string})=>(b.step||'—')+(is3D(b.k)?' · 3D 스캔':'');
export const grpLabel=(b:Bunch)=>stepLabel(b)+' · '+b.s.slice(5,10);
/** Lot 안 Batch Report 를 시간순 번호로 (#1, #2 …).
   R 를 주면 공정 단계 줄(2D · 3D)이 섞여도 실제 스캔 시각 순서로 번호를 매긴다. */
export function flat(l:Lot,R?:Rep[]){const out:{g:number;bi:number;ai:number;n:number}[]=[];l.bunches.forEach((b,bi)=>b.att.forEach((g,ai)=>out.push({g,bi,ai,n:0})));
  if(R)out.sort((a,b)=>R[a.g].s<R[b.g].s?-1:R[a.g].s>R[b.g].s?1:0);out.forEach((x,i)=>{x.n=i+1;});return out;}
