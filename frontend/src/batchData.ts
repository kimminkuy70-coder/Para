import {desktop} from './desktop';

/* Batch Report 화면 데이터 — 엔진 batchview.View.payload() 와 같은 모양.
   요약은 조각(batch_view)으로 받아 이어 붙이고, Lot 상세 · 원문은 누를 때 받는다(4MB 전송 한도). */
export type Rep={f:string;m:string;sm:string;code:string;job:string;setup:string;step:string;s:string;e:string;sec:number;
  lot:number|null;b:number|null;n:number;ok:number;err:number;chain:number;fe:string};
export type Bunch={att:number[];step:string;s:string;e:string;moved:boolean;machines:string[];sec:number};
export type Lot={key:string;label:string;code:string;lot_id:string;sms:string[];jobs:string[];machines:string[];n:number;s:string;e:string;
  state:string;open:number;re:number;dup:number;moved:boolean;saved:number;multi:boolean;causes:[string,number][];cz:[string,number,boolean][];bunches:Bunch[]};
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
export const shortKey=(k:string,u:Unit)=>u==='m'?k.slice(2,7):k.slice(5,10);
export const phList=(o:[string,number][])=>o.map(([k,n])=>k+' ×'+n).join(' · ');
export const isRealId=(id:string)=>!!id&&!/^(slot\s*)?\d{1,2}$/i.test(String(id).trim());
export const WD='일월화수목금토';
export const weekday=(d:string)=>WD[new Date(d+'T00:00:00').getDay()];
export function spanLabel(b:Bunch){return b.s.slice(0,10)===b.e.slice(0,10)?b.s.slice(5)+' ~ '+b.e.slice(11):b.s.slice(5,10)+' ~ '+b.e.slice(5,10);}
export const grpLabel=(b:Bunch)=>(b.step||'—')+' · '+b.s.slice(5,10);
/** Lot 안 Batch Report 를 시간순 번호로 (#1, #2 …) */
export function flat(l:Lot){const out:{g:number;bi:number;ai:number;n:number}[]=[];l.bunches.forEach((b,bi)=>b.att.forEach((g,ai)=>out.push({g,bi,ai,n:out.length+1})));return out;}
