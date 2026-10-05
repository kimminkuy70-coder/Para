import {useEffect,useLayoutEffect,useRef,useState,type ReactNode} from 'react';
import {niceMax,num} from './batchData';

/* 차트(외부 라이브러리 없이 SVG) · 툴팁. 마우스를 올리면 data-tip 문구, 누르면 onClick. */

/** 표처럼 맞춘 툴팁 — 제목 · [색 네모, 이름, 값, 단위] 줄(값은 한 열에 오른쪽 정렬) · 꼬리말.
    data-tipx 에 JSON 으로 넣고, data-tip 은 같은 내용의 글자판(접근성 · 예비)으로 둔다. */
export type TipX={t:string;rows:[string,string,string,string?][];f?:string[]};
function fillRich(tip:HTMLElement,x:TipX){
  tip.replaceChildren();
  const add=(tag:string,cls:string,text:string,parent:HTMLElement=tip)=>{const el=document.createElement(tag);if(cls)el.className=cls;el.textContent=text;parent.appendChild(el);return el;};
  add('div','tt',x.t);
  const grid=add('div','tg','');
  x.rows.forEach(([c,label,val,unit])=>{const i=add('i','',' ',grid);i.style.background=c;add('span','tl',label,grid);add('b','',val,grid);add('span','tu',unit||'',grid);});
  (x.f||[]).forEach(line=>add('div','tf',line));
}
/** data-tip 을 가진 요소 위에서 툴팁을 보여 준다. 열린 창(dialog) 안이면 그 창 위에 띄운다. */
export function TipLayer(){
  useEffect(()=>{
    const tip=document.createElement('div');tip.className='bv-tip';tip.hidden=true;document.body.appendChild(tip);
    const move=(e:MouseEvent)=>{
      const t=(e.target as Element|null)?.closest?.('[data-tip]');
      if(!t){tip.hidden=true;return;}
      const host=(e.target as Element).closest('dialog')||document.body;
      if(tip.parentNode!==host)host.appendChild(tip);
      const rich=t.getAttribute('data-tipx');let tx:TipX|null=null;
      if(rich){try{tx=JSON.parse(rich) as TipX;}catch{tx=null;}}
      if(tx){tip.classList.add('rich');fillRich(tip,tx);}else{tip.classList.remove('rich');tip.textContent=t.getAttribute('data-tip');}
      tip.hidden=false;
      let x=e.clientX+14,y=e.clientY+16;const w=tip.offsetWidth,h=tip.offsetHeight;
      if(x+w>innerWidth-8)x=Math.max(8,e.clientX-w-14);if(y+h>innerHeight-8)y=Math.max(8,e.clientY-h-14);
      tip.style.left=x+'px';tip.style.top=y+'px';};
    const hide=()=>{tip.hidden=true;};
    document.addEventListener('mousemove',move);window.addEventListener('scroll',hide,true);
    return()=>{document.removeEventListener('mousemove',move);window.removeEventListener('scroll',hide,true);tip.remove();};
  },[]);
  return null;
}

/** 요소 폭(차트 크기 맞춤). */
export function useWidth<T extends HTMLElement>(fallback=900):[React.RefObject<T|null>,number]{
  const ref=useRef<T>(null);const [w,setW]=useState(fallback);
  useLayoutEffect(()=>{const el=ref.current;if(!el)return;const set=()=>setW(el.clientWidth||fallback);set();
    const ro=new ResizeObserver(set);ro.observe(el);return()=>ro.disconnect();},[fallback]);
  return [ref,w];
}

export type Key={k:string;label:string;c:string;d?:string};
/** short2 = 막대 아래 둘째 줄(예: 주 단위의 날짜 범위), tipx = 표처럼 맞춘 툴팁 */
export type ColItem={id:string;short:string;short2?:string;v:Record<string,number>;tip:string;tipx?:TipX};

/** 누적 막대(세로) — 눈금은 정수(4 또는 5 등분), 마우스를 올리면 툴팁, 누르면 선택. */
export function ColChart({items,keys,hidden={},sel,onClick,h=210,minw=14,maxw=60,label,fy=num}:{items:ColItem[];keys:Key[];hidden?:Record<string,boolean>;
  sel?:string|null;onClick?:(id:string)=>void;h?:number;minw?:number;maxw?:number;label:string;fy?:(v:number)=>string}){
  const [ref,width]=useWidth<HTMLDivElement>();
  if(!items.length)return <div className="chart" ref={ref}><p className="hint">조사 범위에 자료가 없습니다.</p></div>;
  const two=items.some(it=>it.short2),pl=48,pb=two?44:28,pt=12,cnt=items.length,avail=Math.max(320,width-4);
  const cw=Math.max(minw,Math.min(maxw,(avail-pl-8)/cnt)),W=Math.max(avail,pl+cnt*cw+8),ph=h-28-pt;
  const tot=items.map(it=>keys.reduce((a,k)=>a+(hidden[k.k]?0:(it.v[k.k]||0)),0));
  const max=niceMax(Math.max(...tot,1)),dv=(max%4===0||max<=1)?4:5,every=Math.max(1,Math.ceil((two?92:56)/cw));
  h+=pb-28;
  return <div className="chart" ref={ref}><div className="chartscroll"><svg width={W} height={h} role="img" aria-label={label}>
    {Array.from({length:dv+1},(_,g)=>{const y=pt+ph-ph*g/dv;return <g key={g}><line x1={pl} x2={W-4} y1={y} y2={y} stroke="#e6ebf0"/><text x={pl-6} y={y+4} textAnchor="end">{fy(max*g/dv)}</text></g>;})}
    {items.map((it,i)=>{const x=pl+i*cw,bw=Math.max(3,cw*0.7),bx=x+(cw-bw)/2;let y=pt+ph;
      return <g key={it.id}>{sel===it.id&&<rect className="selbox" x={x+1} y={pt} width={cw-2} height={ph} rx={4}/>}
        {keys.map(k=>{if(hidden[k.k])return null;const val=it.v[k.k]||0;if(val<=0)return null;const hh=val/max*ph;y-=hh;
          return <rect key={k.k} x={bx.toFixed(1)} y={y.toFixed(1)} width={bw.toFixed(1)} height={Math.max(.5,hh).toFixed(1)} fill={k.c}/>;})}
        <rect className="hit" x={x} y={pt} width={cw} height={ph} data-tip={it.tip} data-tipx={it.tipx?JSON.stringify(it.tipx):undefined} onClick={()=>onClick?.(it.id)}/>
        {i%every===0&&<text x={x+cw/2} y={pt+ph+17} textAnchor="middle">{it.short}{it.short2&&<tspan x={x+cw/2} dy={15} className="sub2">{it.short2}</tspan>}</text>}</g>;})}
    <line x1={pl} x2={W-4} y1={pt+ph} y2={pt+ph} stroke="#94a3b8"/></svg></div></div>;
}

/** 범례 = 켜고 끄는 버튼. */
export function Legend({keys,hidden,onToggle}:{keys:Key[];hidden:Record<string,boolean>;onToggle:(k:string)=>void}){
  return <div className="lgd">{keys.map(k=><button key={k.k} type="button" className={hidden[k.k]?'off':''} aria-pressed={!hidden[k.k]} onClick={()=>onToggle(k.k)}>
    <i style={{background:k.c}}/>{k.label}</button>)}</div>;
}

export function Seg<T extends string>({value,items,onChange,label}:{value:T|null;items:[T,string][];onChange:(v:T)=>void;label:string}){
  return <div className="seg" role="group" aria-label={label}>{items.map(([k,l])=><button key={k} type="button" className={value===k?'on':''} aria-pressed={value===k} onClick={()=>onChange(k)}>{l}</button>)}</div>;
}

export type Pt={t:number;y:number;c:string;tip:string;id:number};
/** 산점도(Lot별 실제 WPH) + 기준선. */
export function Scatter({pts,base,onClick}:{pts:Pt[];base?:number|null;onClick:(id:number)=>void}){
  const [ref,width]=useWidth<HTMLDivElement>();
  if(!pts.length)return <div className="chart" ref={ref}><p className="hint">조사 범위에 자료가 없습니다.</p></div>;
  const W=Math.max(480,width-4),H=270,pl=50,pr=16,pt=18,pb=32,pw=W-pl-pr,ph=H-pt-pb;
  const x0=Math.min(...pts.map(p=>p.t));let x1=Math.max(...pts.map(p=>p.t));if(x1===x0)x1=x0+864e5;
  const ymax=niceMax(Math.max(...pts.map(p=>p.y),base||0)*1.06),dv=ymax%4===0?4:5;
  const X=(t:number)=>pl+(t-x0)/(x1-x0)*pw,Y=(v:number)=>pt+ph-v/ymax*ph;
  const months:ReactNode[]=[];let d=new Date(x0);d=new Date(d.getFullYear(),d.getMonth()+1,1);
  while(d.getTime()<=x1){const xx=X(d.getTime());months.push(<g key={xx}><line x1={xx} x2={xx} y1={pt} y2={pt+ph} stroke="#f0f3f6"/><text x={xx} y={H-10} textAnchor="middle">{String(d.getFullYear()).slice(2)+'-'+String(d.getMonth()+1).padStart(2,'0')}</text></g>);d=new Date(d.getFullYear(),d.getMonth()+1,1);}
  return <div className="chart" ref={ref}><div className="chartscroll"><svg width={W} height={H} role="img" aria-label="Lot별 실제 WPH">
    {Array.from({length:dv+1},(_,g)=>{const v=ymax*g/dv,y=Y(v);return <g key={g}><line x1={pl} x2={W-pr} y1={y} y2={y} stroke="#e6ebf0"/><text x={pl-6} y={y+4} textAnchor="end">{num(v)}</text></g>;})}
    {months}<text x={pl+4} y={pt+10} style={{fontSize:10}} fontWeight={700}>WPH</text>
    {base?<line x1={pl} x2={W-pr} y1={Y(base)} y2={Y(base)} stroke="#31517c" strokeWidth={2} strokeDasharray="6 4"/>:null}
    {pts.map((p,i)=><circle key={i} className="pt" cx={X(p.t).toFixed(1)} cy={Y(p.y).toFixed(1)} r={5} fill={p.c} fillOpacity={.85} stroke="#fff" strokeWidth={1.5} data-tip={p.tip} onClick={()=>onClick(p.id)}/>)}
    {base?<text x={W-pr-4} y={Y(base)-6} textAnchor="end" fill="#31517c" fontWeight={700} paintOrder="stroke" stroke="#fff" strokeWidth={5}>정상 스캔 WPH {num(base,1)}</text>:null}
  </svg></div></div>;
}
