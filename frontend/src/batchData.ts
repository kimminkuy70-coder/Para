import {desktop} from './desktop';

/* Batch Report 화면 데이터 — 엔진 batchview.View.payload() 와 같은 모양.
   요약은 조각(batch_view)으로 받아 이어 붙이고, Lot 상세 · 원문은 누를 때 받는다(4MB 전송 한도). */
export type Rep={f:string;m:string;sm:string;code:string;job:string;setup:string;step:string;k:string;s:string;e:string;sec:number;
  lot:number|null;b:number|null;n:number;ok:number;err:number;chain:number;fe:string};
export type Bunch={att:number[];step:string;k:string;s:string;e:string;moved:boolean;machines:string[];sec:number};
export type Lot={key:string;label:string;code:string;lot_id:string;sms:string[];jobs:string[];machines:string[];n:number;s:string;e:string;
  state:string;open:number;re:number;dup:number;moved:boolean;saved:number;scans:string[];multi:boolean;causes:[string,number][];cz:[string,number,boolean][];bunches:Bunch[]};
export type Day={d:string;m:string;valid:number;dropped:number;wait:number;check:number;rec:Record<string,number>;err:Record<string,[number,number,number[],number]>};
export type Wait={m:string;s:string;e:string;li:number;g:number};
export type Base={m:string;r:string;d:string;w:number;s:number;g:number;lot:number};
export type Eff={m:string;r:string;d:string;w:number;s:number;n:number;lot:number;b:number};
export type MStat={parsed:number;reused:number;records:number;offline:boolean;cached?:boolean};
export type View={R:Rep[];lots:Lot[];excluded:number[];B:Day[];waits:Wait[];C:{base:Base[];eff:Eff[]};hits:number[];range:[string,string];
  saved:number;criteria:[string,string,string][];
  scope?:{machines:string[];start:string;end:string;reuse:boolean;at:string};restored?:boolean;mstat?:Record<string,MStat>;
  collection?:{parsed:number;reused:number;errors:number;cached_only:number};errors?:[string,string,string][];artifacts?:Record<string,string>;
  find?:{query:string;start:string;end:string;listed:number;total:number};scan?:Record<string,{paths:string[];pattern:string}>};
export type ViewMeta={view:string;version:number;size:number;saved?:number;lots?:number;reports?:number};
/** cells = [Batch Report 위치, 원문, Pass, 연쇄, Scanned, Bad, Good] */
export type Cell=[number,string,boolean,boolean,number|null,number|null,number|null];
export type Wafer={k:string;slot:number|null;id:string;v:string;pick:number|null;rec:number|null;ov:boolean;cause:string;chain:boolean;cells:Cell[]};
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
