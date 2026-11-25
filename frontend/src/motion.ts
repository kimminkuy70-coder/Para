/* 모션 부품(DESIGN.md 8절, 소유자 2026-11-24) — 추가 패키지 없이 스프링 계산 하나 + CSS.
   스프링 값 = "강성 감쇠"(designbookmark tokens.css · Kokonut UI · SmoothUI 원본과 같은 타이밍). 움직일 것이 없으면 계산도 쉰다.
   - 탭 밑줄 · 분절 고른 칸: 앞쪽 끝 620 · 36, 뒤쪽 끝 190 · 19 (installTabInk — 화면 코드를 고치지 않고 붙는다)
   - 돌림 선택(Kokonut wheel-picker): select[data-wheel] 옆에 원통을 그리고 select 를 같이 바꾼다(select 는 그대로 남음 — 키보드 · 화면 읽기 · 시험)
   - 복사(designbookmark copy-button): CopyButton.tsx
   렉이 나면(prefers-reduced-motion 포함) 튀지 않게 임계 감쇠로 바로 멈춘다. */

export const reduced=():boolean=>{try{return matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return false;}};

export type Spring={x:number;v:number;t:number;k:number;c:number};
export const spring=(x:number,k:number,c:number):Spring=>({x,v:0,t:x,k,c:reduced()?2*Math.sqrt(k):c});
export const tune=(s:Spring,k:number,c:number)=>{s.k=k;s.c=reduced()?2*Math.sqrt(k):c;};
export const clamp=(v:number,a:number,b:number)=>Math.min(b,Math.max(a,v));

type Comp={springs:Spring[];render:()=>void;onRest?:()=>void};
const live=new Set<Comp>();let raf=0,last=0;
const rest=(s:Spring)=>Math.abs(s.x-s.t)<5e-4&&Math.abs(s.v)<5e-3;
function loop(now:number){
  const dt=Math.min((now-last)/1000,1/30);last=now;
  for(const c of [...live]){
    const h=dt/4;for(let n=0;n<4;n++)for(const s of c.springs){s.v+=(-s.k*(s.x-s.t)-s.c*s.v)*h;s.x+=s.v*h;}   // 반암시 오일러, 한 화면당 4번
    c.render();
    if(c.springs.every(rest)){c.springs.forEach(s=>{s.x=s.t;s.v=0;});c.render();live.delete(c);c.onRest?.();}
  }
  raf=live.size?requestAnimationFrame(loop):0;
}
export const Engine={
  wake(c:Comp){live.add(c);if(!raf){last=performance.now();raf=requestAnimationFrame(loop);}},
  stop(c:Comp){live.delete(c);},
};

/* ── 탭 밑줄 · 분절 고른 칸 ─────────────────────────────────────────────────────────── */
// line = 2 · 3단계 탭(밑줄 3px 에메랄드), thumb = 4단계 분절(흰 칸 + 그림자). 고른 단추 = .active · .on · [aria-selected=true]
const INK_LINE='.navigation,.subtabs,.bv .maintabs,.watch-tabs,.defect-tabs';
const INK_THUMB='.bv .pilltabs,.bv .seg';
type Ink={box:HTMLElement;el:HTMLElement;L:Spring;R:Spring;comp:Comp;ready:boolean;kind:'line'|'thumb'};
const inks=new Map<HTMLElement,Ink>();
const activeIn=(box:HTMLElement)=>[...box.children].find(b=>b instanceof HTMLElement&&b.tagName==='BUTTON'&&
  (b.classList.contains('active')||b.classList.contains('on')||b.getAttribute('aria-selected')==='true')) as HTMLElement|undefined;
function inkFor(box:HTMLElement,kind:'line'|'thumb'):Ink{
  let k=inks.get(box);if(k)return k;
  const el=document.createElement('span');el.className='tab-ink '+kind;el.setAttribute('aria-hidden','true');
  const L=spring(0,620,36),R=spring(0,620,36);
  const comp:Comp={springs:[L,R],render(){el.style.transform=`translateX(${L.x.toFixed(2)}px)`;el.style.width=Math.max(0,R.x-L.x).toFixed(2)+'px';}};
  k={box,el,L,R,comp,ready:false,kind};inks.set(box,k);box.classList.add('has-ink','ink-'+kind);
  if(getComputedStyle(box).position==='static')box.style.position='relative';
  return k;
}
function moveInk(k:Ink){
  const b=activeIn(k.box);
  if(!k.el.isConnected||k.el.parentElement!==k.box)k.box.appendChild(k.el);
  if(!b||!b.offsetWidth||!k.box.offsetWidth){k.el.classList.remove('show');k.ready=false;return;}
  const t0=b.offsetLeft,t1=b.offsetLeft+b.offsetWidth;
  if(!k.ready){k.L.x=k.L.t=t0;k.R.x=k.R.t=t1;k.L.v=k.R.v=0;k.comp.render();k.ready=true;k.el.classList.add('show');return;}
  if(Math.abs(t0-k.L.t)<.5&&Math.abs(t1-k.R.t)<.5)return;
  if(t0>k.L.t){tune(k.R,620,36);tune(k.L,190,19);}else{tune(k.L,620,36);tune(k.R,190,19);}   // 가는 쪽 끝이 먼저, 뒤 끝이 늘었다 줄며 따라감
  k.L.t=t0;k.R.t=t1;k.el.classList.add('show');Engine.wake(k.comp);
}
function scanInks(){
  document.querySelectorAll<HTMLElement>(INK_LINE).forEach(b=>moveInk(inkFor(b,'line')));
  document.querySelectorAll<HTMLElement>(INK_THUMB).forEach(b=>moveInk(inkFor(b,'thumb')));
  for(const [box,k] of inks)if(!box.isConnected){Engine.stop(k.comp);inks.delete(box);}
}

/* ── 돌림 선택(Kokonut UI wheel-picker, MIT) ─────────────────────────────────────────────
   한 칸 가기 472 · 36.9(원본 0.4초 · 튐 0.15), 튕김 140 · 24 + 놓을 때 속도 × 0.32초 미끄럼, 끝 너머 최대 1.2칸, 휠 = 멈추고 0.12초 뒤 가까운 칸 */
const IH=36,IA=20,RAD=Math.round(IH/2/Math.tan(IA/2*Math.PI/180)*100)/100,WIN=Math.ceil(90/IA),COAST=.32,MAXO=1.2,VWIN=80,SLOP=4;
const damp=(d:number,m:number)=>m*(1-Math.exp(-d/m));
const esc=(s:string)=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]!));
type Wheel={sel:HTMLSelectElement;root:HTMLElement;sync:()=>void};
const wheels=new Map<HTMLSelectElement,Wheel>();
const setSelect=(sel:HTMLSelectElement,v:string)=>{
  if(sel.value===v)return;
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value')!.set!.call(sel,v);   // React 의 값 추적이 바뀐 것을 알도록 원래 setter 로
  sel.dispatchEvent(new Event('change',{bubbles:true}));
};
function mountWheel(sel:HTMLSelectElement):Wheel{
  const root=document.createElement('div');root.className='wp';root.setAttribute('aria-hidden','true');   // 키보드 · 화면 읽기는 select 가 맡는다
  root.innerHTML='<div class="wp-band"></div><span class="wp-tick l"></span><span class="wp-tick r"></span><div class="wp-col"><div class="wp-fade"><div class="wp-drum"><div class="wp-rot"></div></div><div class="wp-drum clip"><div class="wp-rot"></div></div></div></div>';
  sel.classList.add('wp-src');sel.after(root);
  const col=root.querySelector('.wp-col') as HTMLElement,rots=root.querySelectorAll<HTMLElement>('.wp-rot');
  let opts:{value:string;label:string}[]=[],sig='',center:number|null=null,drag:null|{id:number;y:number;p:number;moved:boolean;s:{t:number;v:number}[]}=null;
  const readOpts=()=>{const o=[...sel.options].map(x=>({value:x.value,label:x.textContent||''}));const s=JSON.stringify(o);if(s!==sig){sig=s;opts=o;center=null;}};
  readOpts();
  const idxOf=(v:string)=>Math.max(0,opts.findIndex(o=>o.value===v));
  const pos=spring(idxOf(sel.value),472,36.9);
  const count=()=>opts.length;
  const rows=(c:number)=>{let h='';for(let i=c-WIN;i<=c+WIN;i++){if(i<0||i>=count())continue;h+=`<div class="wp-row" style="transform:rotateX(${-i*IA}deg) translateZ(${RAD}px)">${esc(opts[i].label)}</div>`;}return h;};
  const comp:Comp={springs:[pos],render(){const tf=`translateZ(${-RAD}px) rotateX(${(pos.x*IA).toFixed(3)}deg)`;rots.forEach(r=>r.style.transform=tf);
    const c=Math.round(pos.x);if(c!==center){center=c;const h=rows(c);rots.forEach(r=>r.innerHTML=h);}},onRest(){settle();}};
  const clampI=(i:number)=>clamp(i,0,Math.max(0,count()-1));
  function settle(){const o=opts[clampI(Math.round(pos.x))];if(o)setSelect(sel,o.value);}
  function goTo(t:number){tune(pos,472,36.9);pos.t=t;if(reduced()){pos.x=t;pos.v=0;comp.render();settle();return;}Engine.wake(comp);}
  const over=(raw:number)=>raw<0?-damp(-raw,MAXO):raw>count()-1?count()-1+damp(raw-(count()-1),MAXO):raw;
  col.addEventListener('pointerdown',e=>{if(sel.disabled||drag||(e.pointerType==='mouse'&&e.button!==0))return;Engine.stop(comp);pos.v=0;col.setPointerCapture(e.pointerId);
    drag={id:e.pointerId,y:e.clientY,p:pos.x,moved:false,s:[{t:e.timeStamp,v:pos.x}]};});
  col.addEventListener('pointermove',e=>{const d=drag;if(!d||d.id!==e.pointerId)return;const dy=e.clientY-d.y;if(!d.moved&&Math.abs(dy)<SLOP)return;d.moved=true;
    const raw=d.p-dy/IH;pos.x=pos.t=over(raw);comp.render();d.s.push({t:e.timeStamp,v:raw});while(d.s.length>2&&e.timeStamp-d.s[0].t>VWIN)d.s.shift();});
  const up=(e:PointerEvent)=>{const d=drag;if(!d||d.id!==e.pointerId)return;drag=null;
    if(!d.moved){if(e.type!=='pointerup'){goTo(clampI(Math.round(pos.x)));return;}
      const r=col.getBoundingClientRect(),rat=clamp((e.clientY-(r.top+r.height/2))/RAD,-1,1);goTo(clampI(Math.round(pos.x)+Math.round(Math.asin(rat)*180/Math.PI/IA)));return;}
    const f=d.s[0],l=d.s[d.s.length-1],span=(l.t-f.t)/1000,paused=e.timeStamp-l.t>VWIN,vel=span>0&&!paused?(l.v-f.v)/span:0,p=pos.x,oob=p<0||p>count()-1;
    if(reduced()||oob||Math.abs(vel)<2){goTo(clampI(Math.round(p)));return;}
    tune(pos,140,24);pos.v=vel;pos.t=clampI(Math.round(p+vel*COAST));Engine.wake(comp);};
  col.addEventListener('pointerup',up);col.addEventListener('pointercancel',up);col.addEventListener('lostpointercapture',up);
  let wt=0;col.addEventListener('wheel',e=>{if(sel.disabled)return;e.preventDefault();Engine.stop(comp);pos.v=0;
    const d=e.deltaMode===1?e.deltaY*IH:e.deltaMode===2?e.deltaY*IH*5:e.deltaY,raw=pos.x+clamp(d/IH*.4,-1,1);   // 한 번 굴림 = 최대 한 칸
    pos.x=pos.t=clamp(raw,-.4,count()-1+.4);comp.render();
    clearTimeout(wt);wt=window.setTimeout(()=>{wt=0;goTo(clampI(Math.round(pos.x)));},120);},{passive:false});
  // 원통을 눌러도 label 이 select 를 열지 않게(소유자 2026-11-25 '누르면 전체 시간 목록이 뜸')
  root.addEventListener('click',e=>e.preventDefault());root.addEventListener('mousedown',e=>e.preventDefault());
  // 굴리는 중 · 미끄러지는 중에는 select 값으로 되돌리지 않음(종전 = 0.4초마다 되돌아가 휠이 안 먹음)
  const sync=()=>{readOpts();root.classList.toggle('off',sel.disabled);if(drag||wt||live.has(comp))return;const i=idxOf(sel.value);if(Math.round(pos.x)!==i||center===null){pos.x=pos.t=i;pos.v=0;comp.render();}};
  sel.addEventListener('change',sync);sel.addEventListener('focus',()=>root.classList.add('focus'));sel.addEventListener('blur',()=>root.classList.remove('focus'));
  comp.render();sync();
  return {sel,root,sync};
}
function scanWheels(){
  document.querySelectorAll<HTMLSelectElement>('select[data-wheel]').forEach(s=>{if(wheels.has(s)||s.classList.contains('wp-src'))return;
    try{wheels.set(s,mountWheel(s));}catch(e){s.classList.remove('wp-src');s.nextElementSibling?.classList.contains('wp')&&s.nextElementSibling.remove();console.error(e);}});   // 실패하면 select 그대로
  for(const [s,w] of wheels){if(!s.isConnected){w.root.remove();wheels.delete(s);}else w.sync();}
}

/* ── 설치: 화면 코드를 고치지 않고 붙는다(클래스 · 고른 단추가 바뀌면 다음 화면 그리기 전에 따라감) ── */
let started=false;
export function startMotion(){
  if(started)return;started=true;
  let q=0;const run=()=>{q=0;scanInks();scanWheels();};
  const later=()=>{if(!q)q=requestAnimationFrame(run);};
  new MutationObserver(later).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class','aria-selected','hidden','disabled']});
  addEventListener('resize',()=>{for(const k of inks.values())k.ready=false;later();});
  document.fonts?.ready.then(()=>{for(const k of inks.values())k.ready=false;later();});
  window.setInterval(()=>{for(const w of wheels.values())w.sync();},400);   // React 가 select 값을 바꾼 것(이벤트 없음)도 따라감
  later();
}
