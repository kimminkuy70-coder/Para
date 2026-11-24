/* 복사 단추(designbookmark copy-button 타이밍, DESIGN.md 8-2 ⑤): 누르면 아이콘이 돌며 작아지고 체크가 나오며 글자가 위로 말려 '복사됨',
   단추 폭이 맞춰 늘어남. 글자 말림 260 · 20, 아이콘 420 · 18, 폭 300 · 24, 1.8초 뒤 되돌아감. 클립보드가 막히면 안내 토스트. */
import {useEffect,useRef} from 'react';
import {Engine,spring,clamp} from './motion';
import {notify} from './ui';

async function writeClipboard(text:string):Promise<boolean>{
  try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return true;}}catch{/* 아래 방법으로 */}
  try{const t=document.createElement('textarea');t.value=text;t.style.cssText='position:fixed;left:-9999px;top:0';document.body.append(t);t.select();
    const ok=document.execCommand('copy');t.remove();return ok;}catch{return false;}
}

export function CopyButton({text,label='경로 복사'}:{text:string;label?:string}){
  const btn=useRef<HTMLButtonElement>(null),st=useRef<{play:()=>void}|null>(null);
  useEffect(()=>{
    const b=btn.current!;const [iC,iO]=b.querySelectorAll('svg'),roll=b.querySelector('.cpb-roll') as HTMLElement,w=b.querySelector('.cpb-w') as HTMLElement,[a,bb]=[...w.children] as HTMLElement[];
    const R=spring(0,260,20),I=spring(0,420,18),RW=spring(0,300,24);let inited=false,timer=0;
    const comp={springs:[R,I,RW],render(){roll.style.width=RW.x.toFixed(2)+'px';w.style.transform=`translateY(${(-16*R.x).toFixed(2)}px)`;
      const i=clamp(I.x,-.2,1.2),ii=clamp(i,0,1);
      iC.style.opacity=clamp(1-i*1.6,0,1).toFixed(3);iC.style.transform=`scale(${(1-.5*ii).toFixed(3)}) rotate(${(-40*ii).toFixed(1)}deg)`;
      iO.style.opacity=clamp(i*1.6-.4,0,1).toFixed(3);iO.style.transform=`scale(${(.4+.6*i).toFixed(3)})`;}};
    const init=()=>{if(inited||!a.offsetWidth)return;RW.x=RW.t=a.offsetWidth;roll.style.width=RW.x+'px';inited=true;};
    const ro=new ResizeObserver(()=>init());ro.observe(b);
    st.current={play(){init();if(!inited)return;R.t=1;I.t=1;RW.t=bb.offsetWidth;clearTimeout(timer);
      timer=window.setTimeout(()=>{R.t=0;I.t=0;RW.t=a.offsetWidth;Engine.wake(comp);},1800);Engine.wake(comp);}};
    return()=>{ro.disconnect();clearTimeout(timer);Engine.stop(comp);};
  },[]);
  return <button ref={btn} type="button" className="cpb" aria-label={label} disabled={!text}
    onClick={async()=>{st.current?.play();if(!(await writeClipboard(text)))notify('클립보드에 넣지 못했습니다. 경로를 직접 골라 복사해 주세요.','info');}}>
    <span className="cpb-ic" aria-hidden="true">
      <svg viewBox="0 0 24 24"><rect x="8.5" y="8.5" width="11" height="11" rx="3"/><path d="M15.5 8.5V7a2.5 2.5 0 0 0-2.5-2.5H7A2.5 2.5 0 0 0 4.5 7v6A2.5 2.5 0 0 0 7 15.5h1.5"/></svg>
      <svg className="i-ok" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span>
    <span className="cpb-roll" aria-hidden="true"><span className="cpb-w"><b>복사</b><b>복사됨</b></span></span>
  </button>;
}
