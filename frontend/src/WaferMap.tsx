import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify,fail} from './ui';
import {openPath} from './OpenPath';

/* Wafer Map 수정하기 — 맵 편집기(#91, 2026-11-27).
   TXT(RowData) 를 프로그램 안에서 바로 그리고 Die 의 Bin Code 를 고쳐 새 TXT + 맵 그림(PNG)으로 저장한다(Excel 을 거치지 않음).
   화면 = ① 폴더 고르기 → ② 맵 목록 → ③ 편집(왼쪽 맵 · 오른쪽 Bin Code 리스트 · 아래 좌표) → ④ 비교(원래 · 수정 맵).
   그리기(소유자가 고른 후보 A + C): 맵 = Die 1개가 픽셀 1개인 비트맵을 확대 · 이동 배율로 늘려 그림(번짐 없이),
   많이 확대하면 보이는 영역에만 격자선 · Bin Code 글자. 4만 ~ 100만 Die 도 한 프레임에 한 번만 다시 그린다.
   엔진(param_manager/wafermap.py) = TXT 읽기 · 바뀐 Die 토큰만 바꿔 저장(원본 바이트 그대로) · `___`(웨이퍼 밖) 잠금. */

type Item={id:number;valid:boolean;path:string;relative:string;wafer:string;device:string;lot:string;size:string;bins:Record<string,number>;error:string};
type Scan={root:string;mode:string;items:Item[];valid:number;total:number};
type Code={code:string;name:string;ko:string;color:string};
type Table={codes:Code[];unknown:string;outside:string};
type Opened={id:number;path:string;name:string;folder:string;default_name:string;wafer:string;device:string;lot:string;
  row_count:number;col_count:number;codes:string[];width:number;grid:string};
type Saved={txt:string;png:string;folder:string;changed:number};
type Label='code'|'meaning';
const OUT='___';

/* ------------------------------------------------------------------ 맵 자료 */
class MapModel{
  rc:number;cc:number;palette:string[];grid:Uint16Array;orig:Uint16Array;outside:number;
  rgb:number[][]=[];pix:Uint8ClampedArray<ArrayBuffer>;counts:number[]=[];changed=0;
  constructor(o:Opened,private table:Table){
    this.rc=o.row_count;this.cc=o.col_count;this.palette=[...o.codes];
    const raw=Uint8Array.from(atob(o.grid),ch=>ch.charCodeAt(0)),n=this.rc*this.cc;
    this.grid=new Uint16Array(n);
    if(o.width===2)for(let i=0;i<n;i++)this.grid[i]=raw[2*i]|(raw[2*i+1]<<8);else this.grid.set(raw.subarray(0,n));
    this.orig=this.grid.slice();this.outside=this.palette.indexOf(OUT);
    this.palette.forEach((_,k)=>this.rgb.push(this.colorRgb(k)));
    this.pix=new Uint8ClampedArray(n*4);
    this.counts=new Array(this.palette.length).fill(0);
    for(let i=0;i<n;i++){this.counts[this.grid[i]]++;this.paint(i);}
  }
  colorHex(code:string){if(code===OUT)return this.table.outside;return (this.table.codes.find(c=>c.code===code)?.color)||this.table.unknown;}
  private colorRgb(k:number){const h=this.colorHex(this.palette[k]);return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}
  paint(i:number){const c=this.rgb[this.grid[i]],j=i*4;this.pix[j]=c[0];this.pix[j+1]=c[1];this.pix[j+2]=c[2];this.pix[j+3]=255;}
  index(code:string){let k=this.palette.indexOf(code);
    if(k<0){k=this.palette.length;this.palette.push(code);this.rgb.push(this.colorRgb(k));this.counts.push(0);}return k;}
  code(i:number){return this.palette[this.grid[i]];}
  locked(i:number){return this.grid[i]===this.outside;}
  set(i:number,k:number){const was=this.grid[i];if(was===k)return;
    if(was===this.orig[i])this.changed++;else if(k===this.orig[i])this.changed--;
    this.counts[was]--;this.counts[k]++;this.grid[i]=k;this.paint(i);}
  count(code:string){const k=this.palette.indexOf(code);return k<0?0:this.counts[k];}
  /** 엔진에 보낼 모양(wafermap.decode_grid): 코드 표 + Die 번호 base64. */
  encode(){const n=this.grid.length,w=this.palette.length>256?2:1,b=new Uint8Array(n*w);
    if(w===1)for(let i=0;i<n;i++)b[i]=this.grid[i];else for(let i=0;i<n;i++){b[2*i]=this.grid[i]&255;b[2*i+1]=this.grid[i]>>8;}
    let s='';for(let i=0;i<b.length;i+=0x8000)s+=String.fromCharCode(...b.subarray(i,i+0x8000));
    return {codes:[...this.palette],width:w,grid:btoa(s)};}
  /** 원래 맵(비교 화면 왼쪽) — 같은 코드 표, 원래 번호. */
  original():MapModel{const m=Object.create(MapModel.prototype) as MapModel;
    Object.assign(m,this,{grid:this.orig.slice(),orig:this.orig,pix:new Uint8ClampedArray(this.pix.length),counts:new Array(this.palette.length).fill(0),changed:0});
    for(let i=0;i<m.grid.length;i++){m.counts[m.grid[i]]++;m.paint(i);}return m;}
}
const name=(t:Table,code:string)=>code===OUT?'Outside Wafer':(t.codes.find(c=>c.code===code)?.name||'목록에 없는 코드');

/* ------------------------------------------------------------------ 맵 그리기 · 조작 */
type View={s:number;x:number;y:number};          // 화면 픽셀 = x + col·s, y + row·s
type Hover={i:number;col:number;row:number}|null;
type Tool='brush'|'rect';
type CanvasProps={model:MapModel;version:number;view:View|null;onView:(v:View)=>void;mode:'edit'|'move'|'view';tool?:Tool;
  sel?:Uint8Array;selVersion?:number;onPick?:(ids:number[],add:boolean)=>void;onHover?:(h:Hover)=>void;mark?:Int32Array;label:string};

function fitView(m:MapModel,w:number,h:number):View{const pad=34,s=Math.max(0.02,Math.min((w-pad)/m.cc,(h-pad-22)/m.rc));
  return {s,x:(w-m.cc*s)/2,y:(h-22-m.rc*s)/2};}

function MapCanvas({model,version,view,onView,mode,tool='brush',sel,selVersion=0,onPick,onHover,mark,label}:CanvasProps){
  const box=useRef<HTMLDivElement>(null),cv=useRef<HTMLCanvasElement>(null);
  const bmp=useRef<HTMLCanvasElement|undefined>(undefined),selBmp=useRef<HTMLCanvasElement|undefined>(undefined);
  const [size,setSize]=useState({w:0,h:0});
  const hover=useRef<Hover>(null),drag=useRef<{kind:'pan'|'brush'|'rect';x0:number;y0:number;v0:View;last:number;ids:Set<number>;add:boolean}|null>(null);
  const rect=useRef<{c0:number;r0:number;c1:number;r1:number}|null>(null);
  const raf=useRef(0),viewRef=useRef(view);viewRef.current=view;
  // 비트맵(Die = 픽셀 1개): 자료가 바뀌면 통째로 한 번 putImageData(100만 Die ≈ 수 ms).
  useEffect(()=>{const c=bmp.current||(bmp.current=document.createElement('canvas'));c.width=model.cc;c.height=model.rc;
    c.getContext('2d')!.putImageData(new ImageData(model.pix,model.cc,model.rc),0,0);draw();},[model,version]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{if(!sel)return;const c=selBmp.current||(selBmp.current=document.createElement('canvas'));c.width=model.cc;c.height=model.rc;
    const px=new Uint8ClampedArray(sel.length*4);for(let i=0;i<sel.length;i++)if(sel[i]){px[i*4]=37;px[i*4+1]=99;px[i*4+2]=235;px[i*4+3]=150;}
    c.getContext('2d')!.putImageData(new ImageData(px,model.cc,model.rc),0,0);draw();},[model,sel,selVersion]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{const el=box.current;if(!el)return;const ro=new ResizeObserver(()=>setSize({w:el.clientWidth,h:el.clientHeight}));ro.observe(el);return()=>ro.disconnect();},[]);
  useEffect(()=>{if(size.w&&!view)onView(fitView(model,size.w,size.h));draw();},[size,view]);// eslint-disable-line react-hooks/exhaustive-deps

  function draw(){cancelAnimationFrame(raf.current);raf.current=requestAnimationFrame(paint);}
  function paint(){
    const c=cv.current,v=viewRef.current;if(!c||!v||!bmp.current)return;
    const dpr=window.devicePixelRatio||1,W=size.w,H=size.h;if(!W||!H)return;
    if(c.width!==Math.round(W*dpr)||c.height!==Math.round(H*dpr)){c.width=Math.round(W*dpr);c.height=Math.round(H*dpr);}
    const g=c.getContext('2d')!;g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,W,H);
    g.fillStyle='#F3F5F8';g.fillRect(0,0,W,H);
    const {s,x,y}=v,mw=model.cc*s,mh=model.rc*s;
    g.imageSmoothingEnabled=false;g.drawImage(bmp.current,x,y,mw,mh);
    if(sel&&selBmp.current)g.drawImage(selBmp.current,x,y,mw,mh);
    // 보이는 영역(후보 C): 격자선 · 글자 · 표시는 화면 안 Die 만.
    const c0=Math.max(0,Math.floor(-x/s)),c1=Math.min(model.cc,Math.ceil((W-x)/s)),r0=Math.max(0,Math.floor(-y/s)),r1=Math.min(model.rc,Math.ceil((H-y)/s));
    if(s>=6&&c1>c0&&r1>r0){g.strokeStyle='rgba(30,41,59,.22)';g.lineWidth=1;g.beginPath();
      for(let col=c0;col<=c1;col++){const px=Math.round(x+col*s)+.5;g.moveTo(px,y+r0*s);g.lineTo(px,y+r1*s);}
      for(let r=r0;r<=r1;r++){const py=Math.round(y+r*s)+.5;g.moveTo(x+c0*s,py);g.lineTo(x+c1*s,py);}g.stroke();}
    if(s>=26){g.font=`${Math.min(14,Math.floor(s*.36))}px 'Pretendard','Malgun Gothic',sans-serif`;g.textAlign='center';g.textBaseline='middle';
      for(let r=r0;r<r1;r++)for(let col=c0;col<c1;col++){const i=r*model.cc+col;if(model.locked(i))continue;
        const k=model.grid[i],rgb=model.rgb[k];g.fillStyle=(rgb[0]*299+rgb[1]*587+rgb[2]*114)/1000<140?'#fff':'#1F2A37';
        g.fillText(model.palette[k],x+col*s+s/2,y+r*s+s/2+.5);}}
    if(mark&&mark.length){g.strokeStyle='#E11D48';g.lineWidth=Math.max(1.5,Math.min(3,s*.12));
      for(let n=0;n<mark.length;n++){const i=mark[n],col=i%model.cc,r=(i-col)/model.cc;if(col<c0-1||col>c1||r<r0-1||r>r1)continue;
        const q=Math.max(s,4),off=(q-s)/2;g.strokeRect(x+col*s-off+.75,y+r*s-off+.75,q-1.5,q-1.5);}}
    const h=hover.current;if(h){g.strokeStyle='#111827';g.lineWidth=2;const q=Math.max(s,5),off=(q-s)/2;g.strokeRect(x+h.col*s-off,y+h.row*s-off,q,q);}
    const rr=rect.current;if(rr){const a=Math.min(rr.c0,rr.c1),b=Math.min(rr.r0,rr.r1);g.strokeStyle='#2563EB';g.setLineDash([5,4]);g.lineWidth=1.5;
      g.strokeRect(x+a*s,y+b*s,(Math.abs(rr.c1-rr.c0)+1)*s,(Math.abs(rr.r1-rr.r0)+1)*s);g.setLineDash([]);}
    g.strokeStyle='#94A3B8';g.lineWidth=1;g.strokeRect(x-.5,y-.5,mw+1,mh+1);
    const nx=x+mw/2,ny=y+mh+4;g.beginPath();g.moveTo(nx-7,ny+12);g.lineTo(nx+7,ny+12);g.lineTo(nx,ny);g.closePath();g.fillStyle='#fff';g.fill();g.strokeStyle='#334155';g.stroke();
    g.fillStyle='#334155';g.font="11px 'Pretendard','Malgun Gothic',sans-serif";g.textAlign='center';g.textBaseline='top';g.fillText("Notch 6'",nx,ny+14);
    c.dataset.s=String(s);c.dataset.x=String(x);c.dataset.y=String(y);
  }
  useEffect(()=>{draw();},[mark]);// eslint-disable-line react-hooks/exhaustive-deps

  const at=(e:{clientX:number;clientY:number})=>{const r=cv.current!.getBoundingClientRect(),v=viewRef.current!;
    return {px:e.clientX-r.left,py:e.clientY-r.top,col:Math.floor((e.clientX-r.left-v.x)/v.s),row:Math.floor((e.clientY-r.top-v.y)/v.s)};};
  const inside=(col:number,row:number)=>col>=0&&row>=0&&col<model.cc&&row<model.rc;
  // 휠 = 확대 · 축소(편집 · 이동 모드 모두, 소유자 #91 10번) — 마우스 자리를 중심으로.
  useEffect(()=>{const c=cv.current;if(!c)return;const wheel=(e:WheelEvent)=>{e.preventDefault();const v=viewRef.current;if(!v)return;
    const {px,py}=at(e),fit=fitView(model,size.w,size.h).s,k=Math.exp(-e.deltaY*0.0015);
    const s=Math.max(fit*0.5,Math.min(80,v.s*k));onView({s,x:px-(px-v.x)*s/v.s,y:py-(py-v.y)*s/v.s});};
    c.addEventListener('wheel',wheel,{passive:false});return()=>c.removeEventListener('wheel',wheel);},[model,size,onView]);// eslint-disable-line react-hooks/exhaustive-deps

  function line(a:number,b:number,ids:Set<number>){   // 끌기 사이 Die 를 빠짐없이(빠르게 움직여도)
    let x0=a%model.cc,y0=(a-x0)/model.cc;const x1=b%model.cc,y1=(b-x1)/model.cc,dx=Math.abs(x1-x0),dy=-Math.abs(y1-y0),sx=x0<x1?1:-1,sy=y0<y1?1:-1;let err=dx+dy;
    for(;;){const i=y0*model.cc+x0;if(!model.locked(i))ids.add(i);if(x0===x1&&y0===y1)break;const e2=2*err;if(e2>=dy){err+=dy;x0+=sx;}if(e2<=dx){err+=dx;y0+=sy;}}}
  function down(e:React.PointerEvent){
    if(!viewRef.current)return;const p=at(e);cv.current!.setPointerCapture(e.pointerId);
    const pan=mode!=='edit'||e.button===1;
    if(pan){drag.current={kind:'pan',x0:p.px,y0:p.py,v0:viewRef.current,last:-1,ids:new Set(),add:false};return;}
    if(e.button!==0)return;
    const add=e.ctrlKey||e.metaKey||e.shiftKey;
    if(tool==='rect'){const c=Math.max(0,Math.min(model.cc-1,p.col)),r=Math.max(0,Math.min(model.rc-1,p.row));
      rect.current={c0:c,r0:r,c1:c,r1:r};drag.current={kind:'rect',x0:p.px,y0:p.py,v0:viewRef.current,last:-1,ids:new Set(),add};draw();return;}
    const ids=new Set<number>();let last=-1;
    if(inside(p.col,p.row)){last=p.row*model.cc+p.col;if(!model.locked(last))ids.add(last);}
    drag.current={kind:'brush',x0:p.px,y0:p.py,v0:viewRef.current,last,ids,add};onPick?.([...ids],add);
  }
  function move(e:React.PointerEvent){
    const p=at(e),d=drag.current;
    if(d?.kind==='pan'){onView({...d.v0,x:d.v0.x+p.px-d.x0,y:d.v0.y+p.py-d.y0});return;}
    if(d?.kind==='rect'&&rect.current){rect.current.c1=Math.max(0,Math.min(model.cc-1,p.col));rect.current.r1=Math.max(0,Math.min(model.rc-1,p.row));draw();}
    if(d?.kind==='brush'&&inside(p.col,p.row)){const i=p.row*model.cc+p.col;if(i!==d.last){if(d.last>=0)line(d.last,i,d.ids);else if(!model.locked(i))d.ids.add(i);d.last=i;onPick?.([...d.ids],d.add);}}
    const h=inside(p.col,p.row)?{i:p.row*model.cc+p.col,col:p.col,row:p.row}:null;
    if(h?.i!==hover.current?.i){hover.current=h;onHover?.(h);draw();}
  }
  function up(){const d=drag.current;drag.current=null;
    if(d?.kind==='rect'&&rect.current){const rr=rect.current,ids:number[]=[];rect.current=null;
      for(let r=Math.min(rr.r0,rr.r1);r<=Math.max(rr.r0,rr.r1);r++)for(let c=Math.min(rr.c0,rr.c1);c<=Math.max(rr.c0,rr.c1);c++){const i=r*model.cc+c;if(!model.locked(i))ids.push(i);}
      onPick?.(ids,d.add);draw();}}
  function leave(){if(hover.current){hover.current=null;onHover?.(null);draw();}}
  const cursor=mode==='edit'?(tool==='rect'?'crosshair':'cell'):drag.current?.kind==='pan'?'grabbing':'grab';
  return <div className="wme-canvas" ref={box}>
    <canvas ref={cv} aria-label={label} style={{cursor}} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onPointerLeave={leave}
      onAuxClick={e=>e.preventDefault()} onContextMenu={e=>e.preventDefault()}/>
  </div>;
}

/* ------------------------------------------------------------------ 저장 그림(PNG) — 종전 renderMap 과 같은 모양 */
const MAP_FONT="'Pretendard','Malgun Gothic','맑은 고딕',sans-serif";
const fontsReady=()=>Promise.all(['400','700'].map(w=>document.fonts.load(`${w} 14px Pretendard`))).catch(()=>undefined);
function renderPng(m:MapModel,t:Table,wafer:string,label:Label){
  const cc=m.cc,rc=m.rc,cell=Math.max(1,Math.min(22,Math.round(1100/Math.max(cc,rc))));
  const padL=54,padT=78,padB=108,gap=30;
  const present=m.palette.map((c,k)=>({c,k})).filter(e=>e.c!==OUT&&m.counts[e.k]>0).sort((a,b)=>a.c==='000'?-1:b.c==='000'?1:a.c<b.c?-1:1);
  const entries=present.map(e=>({color:'#'+m.colorHex(e.c),count:m.counts[e.k],text:label==='code'?`Bin ${e.c}`:`Bin ${e.c} · ${name(t,e.c)}`}));
  const probe=document.createElement('canvas').getContext('2d')!;probe.font=`14px ${MAP_FONT}`;
  let lw=160;for(const e of entries)lw=Math.max(lw,Math.ceil(probe.measureText(`${e.text} (${e.count})`).width)+66);
  const gw=cc*cell,gh=rc*cell,W=padL+gw+gap+lw+16,H=Math.max(padT+gh+padB,padT+(entries.length+2)*26+40);
  const c=document.createElement('canvas');c.width=W;c.height=H;const g=c.getContext('2d')!;
  g.fillStyle='#fff';g.fillRect(0,0,W,H);
  g.fillStyle='#1F2A37';g.font=`bold 20px ${MAP_FONT}`;g.fillText(`${wafer}  ${label==='code'?'Bin Code Map':'Bin Code + Defect Map'} | Notch 6 o'clock`,padL,36);
  const b=document.createElement('canvas');b.width=cc;b.height=rc;b.getContext('2d')!.putImageData(new ImageData(m.pix,cc,rc),0,0);
  g.imageSmoothingEnabled=false;g.drawImage(b,padL,padT,gw,gh);
  if(cell>=4){g.strokeStyle='#BCD0C0';g.lineWidth=cell>=8?.5:.3;g.beginPath();
    for(let col=0;col<=cc;col++){g.moveTo(padL+col*cell,padT);g.lineTo(padL+col*cell,padT+gh);}
    for(let r=0;r<=rc;r++){g.moveTo(padL,padT+r*cell);g.lineTo(padL+gw,padT+r*cell);}g.stroke();}
  g.strokeStyle='#8AA0A8';g.lineWidth=1;g.strokeRect(padL+.5,padT+.5,gw,gh);
  const step=Math.max(10,Math.ceil(Math.max(cc,rc)/40/10)*10);
  g.fillStyle='#556070';g.font=`11px ${MAP_FONT}`;g.textBaseline='middle';
  g.textAlign='center';for(let col=0;col<cc;col+=step)g.fillText(String(col),padL+col*cell+cell/2,padT+gh+16);
  g.textAlign='right';for(let r=0;r<rc;r+=step)g.fillText(String(rc-1-r),padL-6,padT+r*cell+cell/2);
  g.textAlign='center';g.fillText('Col (0-based, left to right)',padL+gw/2,padT+gh+42);
  g.save();g.translate(16,padT+gh/2);g.rotate(-Math.PI/2);g.fillText('Row (0-based, bottom to top)',0,0);g.restore();
  const nx=padL+gw/2,ny=padT+gh;g.beginPath();g.moveTo(nx-10,ny+24);g.lineTo(nx+10,ny+24);g.lineTo(nx,ny+4);g.closePath();
  g.fillStyle='#fff';g.fill();g.strokeStyle='#263238';g.lineWidth=1.4;g.stroke();g.fillStyle='#263238';g.font=`bold 12px ${MAP_FONT}`;g.fillText("Notch 6'",nx,ny+42);
  const lx=padL+gw+gap,ly=padT+8;g.textAlign='left';g.fillStyle='#1F4E78';g.font=`bold 15px ${MAP_FONT}`;g.fillText('범례',lx,ly);g.font=`14px ${MAP_FONT}`;
  entries.forEach((e,i)=>{const yy=ly+28+i*26;g.fillStyle=e.color;g.fillRect(lx,yy-9,18,18);g.strokeStyle='#999';g.lineWidth=1;g.strokeRect(lx+.5,yy-8.5,18,18);
    g.fillStyle='#222';g.fillText(`${e.text} (${e.count})`,lx+26,yy);});
  return c;
}
async function pngB64(c:HTMLCanvasElement){const buf=new Uint8Array(await (await new Promise<Blob>((res,rej)=>c.toBlob(b=>b?res(b):rej(new Error('PNG 를 만들지 못했습니다')),'image/png'))).arrayBuffer());
  let s='';for(let i=0;i<buf.length;i+=0x8000)s+=String.fromCharCode(...buf.subarray(i,i+0x8000));return btoa(s);}

/* ------------------------------------------------------------------ 편집 화면 */
type Step={idx:Int32Array;from:Uint16Array;to:Uint16Array};
function Editor({opened,table,onBack,onSaved}:{opened:Opened;table:Table;onBack:()=>void;onSaved:(m:MapModel,s:Saved,label:Label)=>void}){
  const model=useMemo(()=>new MapModel(opened,table),[opened,table]);
  const [version,setVersion]=useState(0),[view,setView]=useState<View|null>(null);
  const [mode,setMode]=useState<'edit'|'move'>('edit'),[tool,setTool]=useState<Tool>('brush');
  const sel=useMemo(()=>new Uint8Array(model.grid.length),[model]);
  const [selN,setSelN]=useState(0),[selV,setSelV]=useState(0),[hover,setHover]=useState<Hover>(null);
  const undo=useRef<Step[]>([]),redo=useRef<Step[]>([]),[,bump]=useState(0);
  const base=useRef<number[]>([]);                 // Ctrl 없이 끌기 시작 = 새 선택, Ctrl/Shift = 더함
  const [extra,setExtra]=useState<string[]>([]),[newCode,setNewCode]=useState(''),[filter,setFilter]=useState('');
  const [saving,setSaving]=useState(false),[showSave,setShowSave]=useState(false);
  const [label,setLabel]=useState<Label>('code'),[fname,setFname]=useState(opened.default_name),[where,setWhere]=useState<'source'|'custom'>('source'),[folder,setFolder]=useState('');

  const pick=useCallback((ids:number[],add:boolean)=>{
    sel.fill(0);for(const i of (add?base.current:[]))sel[i]=1;for(const i of ids)sel[i]=1;
    let n=0;for(let i=0;i<sel.length;i++)n+=sel[i];setSelN(n);setSelV(v=>v+1);
  },[sel]);
  // 끌기가 끝나면 지금 선택을 '기준'으로(다음 Ctrl 끌기가 더함).
  useEffect(()=>{const up=()=>{const a:number[]=[];for(let i=0;i<sel.length;i++)if(sel[i])a.push(i);base.current=a;};
    window.addEventListener('pointerup',up);return()=>window.removeEventListener('pointerup',up);},[sel]);
  const clearSel=()=>{sel.fill(0);base.current=[];setSelN(0);setSelV(v=>v+1);};
  function apply(code:string){
    if(!selN)return notify('먼저 맵에서 Die 를 고르세요 (편집 모드 · 클릭 / 끌기 / 사각형).','info');
    const k=model.index(code),ids:number[]=[];for(let i=0;i<sel.length;i++)if(sel[i]&&model.grid[i]!==k&&!model.locked(i))ids.push(i);
    if(ids.length){const st:Step={idx:Int32Array.from(ids),from:Uint16Array.from(ids,i=>model.grid[i]),to:new Uint16Array(ids.length).fill(k)};
      for(const i of ids)model.set(i,k);undo.current.push(st);if(undo.current.length>300)undo.current.shift();redo.current=[];setVersion(v=>v+1);}
    notify(`Die ${selN}개를 Bin ${code} 로 바꿨습니다.`,'ok');clearSel();
  }
  function stepBack(from:Step[],to:Step[],back:boolean){const st=from.pop();if(!st)return;
    for(let n=0;n<st.idx.length;n++)model.set(st.idx[n],back?st.from[n]:st.to[n]);to.push(st);setVersion(v=>v+1);bump(x=>x+1);}
  const doUndo=()=>stepBack(undo.current,redo.current,true),doRedo=()=>stepBack(redo.current,undo.current,false);
  useEffect(()=>{const key=(e:KeyboardEvent)=>{const t=e.target as HTMLElement;if(t&&/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))return;
    const k=e.key.toLowerCase();
    if((e.ctrlKey||e.metaKey)&&k==='z'&&!e.shiftKey){e.preventDefault();doUndo();}
    else if((e.ctrlKey||e.metaKey)&&(k==='y'||(k==='z'&&e.shiftKey))){e.preventDefault();doRedo();}
    else if(k==='escape')clearSel();};
    window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);});
  function addCode(){let c=newCode.trim().toUpperCase();if(/^\d{1,2}$/.test(c))c=c.padStart(3,'0');
    if(!/^[0-9A-Z]{1,8}$/.test(c))return notify('새 코드는 영문 · 숫자 1 ~ 8 자로 쓰세요 (숫자 1 ~ 2 자리는 앞에 0 을 붙입니다).','error');
    if(c===OUT)return notify('___ 는 웨이퍼 밖 표시라 쓸 수 없습니다.','error');
    if(!list.some(x=>x.code===c))setExtra(x=>[...x,c]);setNewCode('');notify(`Bin ${c} 를 리스트에 넣었습니다.`,'ok');}
  const list=useMemo(()=>{const known=table.codes.map(c=>({code:c.code,name:c.name,color:c.color}));
    const more=[...model.palette.filter(c=>c!==OUT),...extra].filter((c,i,a)=>a.indexOf(c)===i&&!known.some(k=>k.code===c))
      .map(c=>({code:c,name:'목록에 없는 코드',color:table.unknown}));return [...known,...more];},[table,model,extra,version]);// eslint-disable-line react-hooks/exhaustive-deps
  const shown=list.filter(c=>!filter.trim()||(c.code+' '+c.name).toLowerCase().includes(filter.trim().toLowerCase()));
  const hcode=hover?model.code(hover.i):'';
  const selCode=useMemo(()=>{if(selN!==1)return '';for(let i=0;i<sel.length;i++)if(sel[i])return model.code(i);return '';},[selN,selV]);// eslint-disable-line react-hooks/exhaustive-deps

  async function save(overwrite=false){
    if(where==='custom'&&!folder.trim())return notify('저장 폴더를 고르세요.','error');
    setSaving(true);
    try{const g=model.encode();
      const r=(await desktop.request('wm_edit_save',{id:opened.id,...g,folder:where==='custom'?folder.trim():'',name:fname,label,overwrite}).promise).wafermap as Saved&{exists?:string};
      if(r.exists){setSaving(false);if(window.confirm(`같은 이름의 파일이 있습니다.\n${r.exists}\n\n덮어쓸까요?`))return save(true);return;}
      await fontsReady();
      await desktop.request('wm_edit_image',{id:opened.id,data:await pngB64(renderPng(model,table,opened.wafer,label))}).promise;
      notify(`저장했습니다: ${r.txt}`,'ok');onSaved(model,r,label);
    }catch(e){fail(e);}finally{setSaving(false);}
  }
  const leave=()=>{if(model.changed&&!window.confirm(`저장하지 않은 수정(Die ${model.changed}개)이 있습니다. 버리고 목록으로 갈까요?`))return;onBack();};

  return <div className="wme">
    <div className="wme-top">
      <div className="wme-title"><b>{opened.wafer}</b><span>{opened.name} · {opened.col_count} × {opened.row_count} · Die {(model.grid.length-model.count(OUT)).toLocaleString()}개</span></div>
      <div className="wme-tools" role="toolbar" aria-label="맵 도구">
        <div className="wme-seg" role="radiogroup" aria-label="모드">
          <button type="button" role="radio" aria-checked={mode==='edit'} className={mode==='edit'?'on':''} title="편집 모드: Die 를 골라 Bin Code 를 바꿉니다" onClick={()=>setMode('edit')}>✏️ 편집</button>
          <button type="button" role="radio" aria-checked={mode==='move'} className={mode==='move'?'on':''} title="이동 모드: 끌어서 이동, 휠로 확대 (Die 는 안 눌림)" onClick={()=>setMode('move')}>✋ 이동</button>
        </div>
        {mode==='edit'&&<div className="wme-seg" role="radiogroup" aria-label="고르기 방식">
          <button type="button" role="radio" aria-checked={tool==='brush'} className={tool==='brush'?'on':''} title="클릭 = Die 하나, 끌기 = 지나간 Die 모두" onClick={()=>setTool('brush')}>🖌 클릭 · 끌기</button>
          <button type="button" role="radio" aria-checked={tool==='rect'} className={tool==='rect'?'on':''} title="끌어서 사각형 안 Die 모두" onClick={()=>setTool('rect')}>⬚ 사각형</button>
        </div>}
        <button type="button" disabled={!selN} onClick={clearSel} title="Esc">선택 해제</button>
        <button type="button" disabled={!undo.current.length} onClick={doUndo} title="Ctrl+Z">↶ 되돌리기</button>
        <button type="button" disabled={!redo.current.length} onClick={doRedo} title="Ctrl+Y">↷ 다시 하기</button>
        <button type="button" onClick={()=>setView(null)} title="맵 전체가 보이게">⤢ 전체 보기</button>
        <span className="wme-gap"/>
        <button type="button" onClick={leave}>◀ 목록으로</button>
        <button type="button" className="primary" disabled={saving} onClick={()=>setShowSave(true)}>💾 저장</button>
      </div>
    </div>
    <div className="wme-body">
      <MapCanvas model={model} version={version} view={view} onView={setView} mode={mode} tool={tool} sel={sel} selVersion={selV}
        onPick={pick} onHover={setHover} label="Wafer Map 편집"/>
      <aside className="wme-side" aria-label="Bin Code 리스트">
        <div className="wme-side-head"><b>Bin Code</b><span>{selN?`선택 Die ${selN.toLocaleString()}개${selCode?` (지금 ${selCode})`:''} → 코드를 누르세요`:'맵에서 Die 를 고르세요'}</span></div>
        <input className="wme-find" aria-label="코드 찾기" placeholder="🔍 코드 · 이름 찾기" value={filter} onChange={e=>setFilter(e.target.value)}/>
        <ul className="wme-codes">{shown.map(c=><li key={c.code}>
          <button type="button" className={(c.code===selCode||c.code===hcode)?'cur':''} disabled={!selN} onClick={()=>apply(c.code)} title={`선택한 Die 를 Bin ${c.code} 로`}>
            <i className="wm-sw" style={{background:'#'+c.color}} aria-hidden="true"/><b>{c.code}</b><span>{c.name}</span><em>{model.count(c.code).toLocaleString()}</em></button></li>)}</ul>
        <div className="wme-add"><input aria-label="새 코드" placeholder="새 코드 (예: 095)" value={newCode} onChange={e=>setNewCode(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')addCode();}}/>
          <button type="button" onClick={addCode}>＋ 추가</button></div>
      </aside>
    </div>
    <div className="wme-status" role="status" aria-label="Die 정보">
      <span className="wme-hover">{hover?<>Col <b>{hover.col}</b> · Row <b>{model.rc-1-hover.row}</b> · Bin <b>{hcode}</b> ({name(table,hcode)}){model.locked(hover.i)?' — 편집 안 됨':''}</>:'맵 위에 마우스를 올리면 Die 좌표 · Bin Code 가 보입니다.'}</span>
      <span>선택 {selN.toLocaleString()} · 바뀐 Die <b>{model.changed.toLocaleString()}</b> · 확대 {view?Math.round(view.s*100)/100:'-'} px/Die</span>
    </div>
    {showSave&&<div className="wm-viewer" role="dialog" aria-label="저장" onClick={()=>!saving&&setShowSave(false)}>
      <div className="wm-viewer-box wme-save" onClick={e=>e.stopPropagation()}>
        <div className="wm-viewer-top"><b>수정한 맵 저장</b><button disabled={saving} onClick={()=>setShowSave(false)}>닫기 ✕</button></div>
        <div className="wme-save-body">
          <p className="hint">고친 TXT 와 맵 그림(PNG)을 저장합니다. 원본 TXT 는 바뀌지 않습니다. 바뀐 Die: <b>{model.changed.toLocaleString()}</b>개</p>
          <fieldset><legend>맵 그림 범례</legend>
            <label><input type="radio" name="wme-label" checked={label==='code'} onChange={()=>setLabel('code')}/> Bin Code 만 (예: Bin 003)</label>
            <label><input type="radio" name="wme-label" checked={label==='meaning'} onChange={()=>setLabel('meaning')}/> Bin Code + Defect 이름 (예: Bin 003 · Metal Residue)</label></fieldset>
          <label className="field">저장 이름 (.txt 없이)<input aria-label="저장 이름" value={fname} onChange={e=>setFname(e.target.value)}/></label>
          <fieldset><legend>저장 위치</legend>
            <label><input type="radio" name="wme-where" checked={where==='source'} onChange={()=>setWhere('source')}/> 원본 TXT 와 같은 폴더 <code>{opened.folder}</code></label>
            <label><input type="radio" name="wme-where" checked={where==='custom'} onChange={()=>setWhere('custom')}/> 다른 폴더</label>
            {where==='custom'&&<div className="form-filter"><input aria-label="저장 폴더" style={{flex:1}} placeholder="폴더 경로" value={folder} onChange={e=>setFolder(e.target.value)}/>
              <button type="button" onClick={()=>void pickFolder().then(p=>{if(p)setFolder(p);})}>📁 찾아보기…</button></div>}</fieldset>
          <p className="hint">만들 파일: <code>{fname.trim()||'(이름)'}.txt</code> · <code>{fname.trim()||'(이름)'}_{label==='code'?'BinCode_Map':'BinMeaning_Map'}.png</code></p>
          <div className="toolbar"><button className="primary" disabled={saving||!fname.trim()} onClick={()=>void save()}>{saving?'저장 중…':'💾 저장'}</button></div>
        </div></div></div>}
  </div>;
}

/* ------------------------------------------------------------------ 비교 화면 */
function Compare({edited,opened,saved,table,onHome}:{edited:MapModel;opened:Opened;saved:Saved;table:Table;onHome:()=>void}){
  const orig=useMemo(()=>edited.original(),[edited]);
  const [view,setView]=useState<View|null>(null),[hover,setHover]=useState<Hover>(null);
  const mark=useMemo(()=>{const a:number[]=[];for(let i=0;i<edited.grid.length;i++)if(edited.grid[i]!==edited.orig[i])a.push(i);return Int32Array.from(a);},[edited]);
  const pairs=useMemo(()=>{const m=new Map<string,number>();for(const i of mark){const k=`${edited.palette[edited.orig[i]]} → ${edited.palette[edited.grid[i]]}`;m.set(k,(m.get(k)||0)+1);}
    return [...m.entries()].sort((a,b)=>b[1]-a[1]);},[edited,mark]);
  const info=(m:MapModel)=>hover?<>Col <b>{hover.col}</b> · Row <b>{m.rc-1-hover.row}</b> · Bin <b>{m.code(hover.i)}</b> ({name(table,m.code(hover.i))})</>:'\u00a0';
  return <div className="wme">
    <div className="wme-top"><div className="wme-title"><b>{opened.wafer} — 저장 완료</b><span>바뀐 Die {mark.length.toLocaleString()}개 · 두 맵은 확대 · 이동이 같이 움직입니다</span></div>
      <div className="wme-tools"><button type="button" onClick={()=>setView(null)}>⤢ 전체 보기</button><span className="wme-gap"/>
        <button type="button" onClick={()=>void openPath(saved.folder)}>📂 저장 폴더 열기</button>
        <button type="button" className="primary" onClick={onHome}>처음 화면으로</button></div></div>
    <div className="wme-compare">
      <figure><figcaption>원래 맵 <code>{opened.name}</code></figcaption>
        <MapCanvas model={orig} version={0} view={view} onView={setView} mode="view" onHover={setHover} mark={mark} label="원래 맵"/><p className="wme-mini">{info(orig)}</p></figure>
      <figure><figcaption>수정 맵 <code>{saved.txt.split(/[\\/]/).pop()}</code> <span className="wme-red">□ 바뀐 Die</span></figcaption>
        <MapCanvas model={edited} version={0} view={view} onView={setView} mode="view" onHover={setHover} mark={mark} label="수정 맵"/><p className="wme-mini">{info(edited)}</p></figure>
    </div>
    <div className="wme-sum">
      <table className="tbl t-compact" aria-label="바뀐 Die 요약"><thead><tr><th>바뀐 코드 (원래 → 수정)</th><th>Die 수</th></tr></thead>
        <tbody>{pairs.length?pairs.map(([k,v])=><tr key={k}><td><code>{k}</code></td><td>{v.toLocaleString()}</td></tr>):<tr><td colSpan={2}>바뀐 Die 가 없습니다 (원본과 같은 내용으로 저장).</td></tr>}</tbody></table>
      <table className="tbl t-compact" aria-label="저장 파일"><tbody>
        <tr><th>TXT</th><td><code>{saved.txt}</code> <button type="button" onClick={()=>void openPath(saved.txt,true)}>폴더에서 보기</button></td></tr>
        <tr><th>맵 그림</th><td><code>{saved.png}</code> <button type="button" onClick={()=>void openPath(saved.png)}>열기</button></td></tr></tbody></table>
    </div>
  </div>;
}

/* ------------------------------------------------------------------ 탭 */
export function WaferMap(){
  const [screen,setScreen]=useState<'pick'|'list'|'edit'|'done'>('pick');
  const [root,setRoot]=useState(''),[scan,setScan]=useState<Scan>(),[busy,setBusy]=useState(false),[find,setFind]=useState('');
  const [table,setTable]=useState<Table>({codes:[],unknown:'F4B183',outside:'FFFFFF'});
  const [opened,setOpened]=useState<Opened>(),[done,setDone]=useState<{model:MapModel;saved:Saved}>();
  const [saved,setSaved]=useState<Record<number,Saved>>({});
  useEffect(()=>{void desktop.request('wm_state').promise.then(r=>{const w=r.wafermap as {codes?:Code[];unknown_color?:string;outside_color?:string}|undefined;
    if(w?.codes)setTable({codes:w.codes,unknown:w.unknown_color||'F4B183',outside:w.outside_color||'FFFFFF'});}).catch(()=>undefined);},[]);

  async function doScan(){
    if(!root.trim())return notify('폴더 경로를 입력하세요.','error');
    setBusy(true);
    try{const r=(await desktop.request('wm_scan',{root:root.trim(),mode:'txt'}).promise).wafermap as Scan;
      setScan(r);setSaved({});
      if(r.valid){notify(`Wafer Map TXT ${r.valid}개를 찾았습니다.${r.total>r.valid?` (읽기 오류 ${r.total-r.valid}개)`:''}`,'ok');setScreen('list');}
      else notify('Wafer Map TXT 를 찾지 못했습니다. (_Converted.txt 는 제외합니다)','error');
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  async function open(it:Item){
    if(!it.valid)return notify(`읽을 수 없는 파일입니다: ${it.error}`,'error');
    setBusy(true);
    try{setOpened((await desktop.request('wm_open',{id:it.id}).promise).wafermap as Opened);setScreen('edit');}
    catch(e){notify(errorText(e),'error');}finally{setBusy(false);}
  }
  function restart(){setScan(undefined);setSaved({});setOpened(undefined);setDone(undefined);setFind('');setScreen('pick');
    void desktop.request('wm_reset').promise.catch(()=>undefined);}

  const items=(scan?.items||[]).filter(i=>!find.trim()||find.trim().toLowerCase().split(/\s+/).every(w=>(i.wafer+' '+i.relative+' '+i.lot+' '+i.device).toLowerCase().includes(w)));
  return <section className="panel wm-panel">
    <div className="section-heading"><div><span className="step">WAFER MAP</span><h2>Wafer Map 수정하기</h2></div>
      <span className="count">{screen==='pick'?'원본 읽기 전용':screen==='list'?`맵 ${scan?.valid||0}개`:opened?.wafer}</span></div>
    {screen==='pick'&&<>
      <p className="hint">Wafer Map TXT 가 있는 폴더를 고르면 하위 폴더까지 모두 찾습니다. 맵을 하나씩 열어 Die 의 Bin Code 를 고치고 새 TXT + 맵 그림으로 저장합니다.
        원본 TXT 는 읽기만 합니다. 장비 공유 폴더는 탐색기(Win+R → <code>\\IP\c$</code>)로 먼저 연결해야 보입니다.</p>
      <div className="form-filter">
        <label className="field" style={{flex:1}}>폴더 경로<input aria-label="폴더 경로" value={root} onChange={e=>setRoot(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void doScan();}} placeholder="예: D:\WaferMaps\LOT01"/></label>
        <button disabled={busy} onClick={()=>void pickFolder().then(p=>{if(p)setRoot(p);})}>📁 찾아보기…</button>
        <button className="primary" disabled={busy||!root.trim()} onClick={()=>void doScan()}>{busy?'찾는 중…':'맵 찾기'}</button>
      </div>
      {busy&&<p className="hint" role="status"><span className="spinner" aria-hidden="true"/> 하위 폴더에서 TXT 를 찾는 중입니다.
        <button onClick={()=>void desktop.request('wm_reset').promise.catch(()=>undefined)}>검색 취소</button></p>}
    </>}
    {screen==='list'&&scan&&<>
      <div className="form-filter">
        <p className="hint" style={{flex:1,margin:0}}>폴더 <code>{scan.root}</code> — 고칠 맵의 [열기] 를 누르세요. 저장한 맵은 ✓ 로 표시됩니다.</p>
        <input aria-label="맵 찾기" placeholder="🔍 Wafer · 위치 찾기" value={find} onChange={e=>setFind(e.target.value)}/>
        <button onClick={restart}>⟲ 새로 시작하기</button>
      </div>
      <div className="table-scroll" style={{maxHeight:'calc(100vh - 300px)'}}><table className="tbl" aria-label="맵 목록"><thead><tr><th>Wafer</th><th>크기</th><th>Bin (수량)</th><th>위치</th><th>저장</th><th/></tr></thead>
        <tbody>{items.map(i=><tr key={i.id} className={i.valid?'':'dim'} onDoubleClick={()=>void open(i)}>
          <td><b>{i.wafer}</b></td><td>{i.valid?i.size:<span className="warn">오류</span>}</td>
          <td>{i.valid?(Object.keys(i.bins).length?Object.entries(i.bins).map(([k,v])=>`${k}:${v}`).join('  '):'불량 없음'):<span className="hint">{i.error}</span>}</td>
          <td><code>{i.relative}</code></td><td>{saved[i.id]?<span className="st-on" title={saved[i.id].txt}>✓ {saved[i.id].txt.split(/[\\/]/).pop()}</span>:''}</td>
          <td><button type="button" disabled={!i.valid||busy} onClick={()=>void open(i)}>{busy?'…':'열기'}</button></td></tr>)}</tbody></table></div>
    </>}
    {screen==='edit'&&opened&&<Editor key={opened.id+':'+opened.path} opened={opened} table={table} onBack={()=>setScreen('list')}
      onSaved={(model,s)=>{setSaved(x=>({...x,[opened.id]:s}));setDone({model,saved:s});setScreen('done');}}/>}
    {screen==='done'&&opened&&done&&<Compare edited={done.model} opened={opened} saved={done.saved} table={table} onHome={()=>{setDone(undefined);setScreen('list');}}/>}
  </section>;
}
