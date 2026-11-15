import {useRef,useState} from 'react';
import {desktop,errorText,pickFolder} from './desktop';
import {notify,fail,Stepper,StepNav} from './ui';
import {RowPick} from './RowPick';
import {OpenPath} from './OpenPath';

/* Color · Gray 매칭 (AOI Color-Gray Matcher v16 이식).
   엔진 = 폴더 탐색 · 좌표 매칭 · 파일 읽기/쓰기 · Excel. 이 화면 = 이미지 픽셀 작업
   (디코드 · Crop · 썸네일 · JPEG 인코딩 — 프로그램에 이미지 패키지를 추가하지 않기 위해 WebView canvas 사용). */

type Wafer={name:string;path:string};
type Rec={color:string;gray:string;px:number;py:number;gw:number;gh:number;crop_w:number;crop_h:number;out_w:number;out_h:number;
  /** v14: 최종 목록 CSV 로 고른 Defect — Defect 상자 크기(Gray 3168×1024 기준). 있으면 최종 목록 엑셀 사진 3장을 더 만든다. */
  box?:[number,number]};
type Diag={coord?:string|null;reasons?:Record<string,number>;transform?:string[];colors?:number;frames?:number;jpg_files?:number;frame_recipes?:string[];color_recipes?:string[];frame_example?:string;color_example?:string;
  nearest?:{color:string;fault:number[];frame:string;px:number;py:number;gw:number;gh:number}};
type JobWafer={name:string;colors:number;failed:number;records:Rec[];finished?:Finished|null;diagnosis?:Diag|null;coord?:string|null};
/** 매칭 실패 진단 문구(Para #49) — 이 줄을 이슈에 붙이면 원인을 찾을 수 있다. */
const diagText=(d:Diag)=>[
  d.coord&&`좌표 기준 ${d.coord}`,
  d.reasons&&Object.entries(d.reasons).map(([k,v])=>`${k} ${v}장`).join(' · '),
  `변환 파일 ${(d.transform||[]).join(', ')||'없음'}`,
  `Gray 프레임 목록 ${d.frames??'?'}줄 (레시피 ${(d.frame_recipes||[]).join(',')}) · Color 레시피 ${(d.color_recipes||[]).join(',')} · 폴더 jpg ${d.jpg_files??'?'}개`,
  d.frame_example&&`목록 예 ${d.frame_example}`,
  d.nearest&&`가장 가까운 프레임 ${d.nearest.frame}: Fault (${d.nearest.fault.join(', ')}) → Gray 픽셀 (${d.nearest.px}, ${d.nearest.py}) / 범위 ${d.nearest.gw}×${d.nearest.gh}`,
].filter(Boolean).join(' | ');
type Job={output:string;wafers:JobWafer[];final?:{rows:number;workbook:string}|null};
type CsvInfo={name:string;rows:number;missing:number;examples:string[];needRoot:boolean};
type FinalOut={workbook:string;rows:number;done:number;missing:number};
type Finished={workbook:string;matched:number;failed:number;failures_csv:string;folder:string};
const STEPS=['폴더 선택','Wafer 확인','저장 위치','실행 검토','처리 진행','완료'];
const TW=360,TH=270;

const b64Bytes=(b64:string)=>{const s=atob(b64);const a=new Uint8Array(new ArrayBuffer(s.length));for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a;};
async function toB64(canvas:OffscreenCanvas,quality:number){
  const buf=new Uint8Array(await (await canvas.convertToBlob({type:'image/jpeg',quality})).arrayBuffer());
  let s='';for(let i=0;i<buf.length;i+=0x8000)s+=String.fromCharCode(...buf.subarray(i,i+0x8000));
  return btoa(s);
}
/** Source JPEG (≤ 5 MB) read in pieces — one IPC message is limited to 4 MB. */
async function source(wafer:number,record:number,kind:'color'|'gray'){
  const parts:Uint8Array<ArrayBuffer>[]=[];let offset:number|null=0;
  while(offset!==null){
    const r=(await desktop.request('cgm_read',{wafer,record,kind,offset}).promise).colorgray as {data:string;next:number|null};
    parts.push(b64Bytes(r.data));offset=r.next;
  }
  return createImageBitmap(new Blob(parts,{type:'image/jpeg'}),{imageOrientation:'from-image'});
}
/** Shrink-to-fit on a white 360×270 canvas (never enlarged), optional red cross at the fault. */
function thumb(img:ImageBitmap|OffscreenCanvas,marker?:{x:number;y:number;w:number;h:number}){
  const c=new OffscreenCanvas(TW,TH),g=c.getContext('2d')!;g.fillStyle='#fff';g.fillRect(0,0,TW,TH);
  const k=Math.min(1,TW/img.width,TH/img.height),w=Math.max(1,Math.round(img.width*k)),h=Math.max(1,Math.round(img.height*k));
  const ox=Math.floor((TW-w)/2),oy=Math.floor((TH-h)/2);g.imageSmoothingQuality='high';g.drawImage(img,ox,oy,w,h);
  if(marker){const x=ox+marker.x*w/marker.w,y=oy+marker.y*h/marker.h;g.strokeStyle='red';g.lineWidth=3;g.beginPath();
    g.moveTo(x-15,y);g.lineTo(x+15,y);g.moveTo(x,y-15);g.lineTo(x,y+15);g.stroke();}
  return c;
}
/** Shrink-to-fit (never enlarged, no padding) — 최종 목록 엑셀 사진(HTML xlJpeg 와 같은 크기 한도). */
function fit(img:ImageBitmap|OffscreenCanvas,mw:number,mh:number){
  const k=Math.min(1,mw/img.width,mh/img.height),c=new OffscreenCanvas(Math.max(1,Math.round(img.width*k)),Math.max(1,Math.round(img.height*k))),g=c.getContext('2d')!;
  g.imageSmoothingQuality='high';g.drawImage(img,0,0,c.width,c.height);return c;
}
/** Defect 빨간 네모 — Defect 를 가리지 않게 상자 바깥에(HTML cgDefBox 와 같은 규칙, Para #67). */
function defBox(g:OffscreenCanvasRenderingContext2D,x:number,y:number,hw:number,hh:number,size:number){
  const lw=Math.max(2,Math.round(size/300)),gap=Math.max(4,lw*2),mn=Math.max(8,size/60),ax=Math.max(hw+gap,mn),ay=Math.max(hh+gap,mn);
  g.save();g.filter='none';g.strokeStyle='#ff2d2d';g.lineWidth=lw;g.strokeRect(x-ax-lw/2,y-ay-lw/2,2*ax+lw,2*ay+lw);g.restore();
}
/** Gray Crop + 빨간 네모(HTML cgCropCanvas(d) 와 같은 그림). */
function cropMark(gray:ImageBitmap,r:Rec,c:{canvas:OffscreenCanvas;box:number[]}){
  const out=new OffscreenCanvas(c.canvas.width,c.canvas.height),o=out.getContext('2d')!;o.drawImage(c.canvas,0,0);
  const sx=gray.width/r.gw,sy=gray.height/r.gh,x=r.px*sx,y=r.py*sy,fx=r.out_w/r.crop_w,fy=r.out_h/r.crop_h,[bw,bh]=r.box||[4,4];
  defBox(o,(x-c.box[0])*fx,(y-c.box[1])*fy,Math.max(1,bw*sx)/2*fx,Math.max(1,bh*sy)/2*fy,Math.max(r.out_w,r.out_h));return out;
}
/** Gray 프레임 전체 + 노란 상자(Crop 범위) + 빨간 네모(HTML cgFrameCanvas 와 같은 그림). */
function frameMark(gray:ImageBitmap,r:Rec){
  const cv=new OffscreenCanvas(gray.width,gray.height),g=cv.getContext('2d')!;g.drawImage(gray,0,0);
  const sx=gray.width/r.gw,sy=gray.height/r.gh,x=r.px*sx,y=r.py*sy,lw=Math.max(2,gray.width/700),[bw,bh]=r.box||[4,4];
  g.strokeStyle='#ffd23f';g.lineWidth=lw;g.strokeRect(x-r.crop_w/2,y-r.crop_h/2,r.crop_w,r.crop_h);
  defBox(g,x,y,Math.max(1,bw*sx)/2,Math.max(1,bh*sy)/2,Math.max(gray.width,gray.height));return cv;
}
/** Gray crop centred on the fault, the color image's field of view, resized to the color image size. */
function crop(gray:ImageBitmap,r:Rec){
  const x=r.px*gray.width/r.gw,y=r.py*gray.height/r.gh,left=Math.round(x-r.crop_w/2),top=Math.round(y-r.crop_h/2);
  const raw=new OffscreenCanvas(r.crop_w,r.crop_h),g=raw.getContext('2d')!;g.fillStyle='#000';g.fillRect(0,0,r.crop_w,r.crop_h);
  const sl=Math.max(0,left),st=Math.max(0,top),sr=Math.min(gray.width,left+r.crop_w),sb=Math.min(gray.height,top+r.crop_h);
  if(sr>sl&&sb>st)g.drawImage(gray,sl,st,sr-sl,sb-st,sl-left,st-top,sr-sl,sb-st);
  const out=new OffscreenCanvas(r.out_w,r.out_h),o=out.getContext('2d')!;o.imageSmoothingQuality='high';o.filter='grayscale(1)';o.drawImage(raw,0,0,r.out_w,r.out_h);
  return {canvas:out,box:[left,top,left+r.crop_w,top+r.crop_h]};
}

export function ColorGray(){
  const [step,setStep]=useState(0),[busy,setBusy]=useState(false);
  const [root,setRoot]=useState(''),[wafers,setWafers]=useState<Wafer[]>(),[picked,setPicked]=useState<string[]>([]);
  const [defaultOut,setDefaultOut]=useState(''),[mode,setMode]=useState<'default'|'custom'>('default'),[custom,setCustom]=useState('');
  const [job,setJob]=useState<Job>(),[progress,setProgress]=useState({done:0,total:0,text:''}),[log,setLog]=useState<string[]>([]);
  const [results,setResults]=useState<(Finished&{name:string})[]>([]),[state,setState]=useState<'idle'|'running'|'complete'|'cancelled'|'error'>('idle');
  const stop=useRef(false),csvInput=useRef<HTMLInputElement>(null);
  const [csvInfo,setCsvInfo]=useState<CsvInfo|null>(null),[finalOut,setFinalOut]=useState<FinalOut|null>(null);
  const rel=(p:string)=>{const r=root.replace(/[\\/]+$/,'');return p.startsWith(r)?p.slice(r.length).replace(/^[\\/]+/,'')||p.split(/[\\/]/).pop()!:p;};
  const byId=new Map((wafers||[]).map(w=>[rel(w.path),w]));
  const addLog=(m:string)=>setLog(l=>[...l.slice(-249),`[${new Date().toLocaleTimeString('ko-KR',{hour12:false})}] ${m}`]);

  async function scan(){
    if(!root.trim())return notify('Lot 또는 Wafer 폴더를 입력하세요.','error');
    setBusy(true);setWafers(undefined);setPicked([]);setCsvInfo(null);
    try{const r=(await desktop.request('cgm_scan',{root:root.trim()}).promise).colorgray as {wafers:Wafer[];default_output:string;limit:number;diagnosis?:{missing:string[];files:number;folders:number;path_len:number}};
      setWafers(r.wafers);setDefaultOut(r.default_output);
      setPicked(r.wafers.map(w=>rel(w.path)));
      if(r.wafers.length){notify(`Wafer ${r.wafers.length}개를 찾았습니다.${r.wafers.length>=r.limit?` (최대 ${r.limit}개까지 찾습니다)`:''}`,'ok');setStep(1);}
      else{const d=r.diagnosis;
        notify('Wafer 폴더를 찾지 못했습니다. ColorImageGrabingInfo.ini · ScanResultImageList.txt · frameToChuckPlane.ini 가 있는 폴더를 찾습니다.'
          +(d?` 고른 폴더 바로 아래: 파일 ${d.files}개 · 폴더 ${d.folders}개${d.missing.length?` · 없는 파일 ${d.missing.join(', ')}`:''} (경로 ${d.path_len}자).`:''),'error');}
    }catch(e){fail(e);}finally{setBusy(false);}
  }
  async function browse(set:(p:string)=>void){const p=await pickFolder();if(p)set(p);}
  /** v14: 최종 목록 CSV(대규모 Defect 분석 5-3 [📄 최종 목록 CSV 저장]) → 그 Defect 만. 매칭 폴더가 상대 경로면 위 폴더 칸 = 그때 고른 폴더. */
  async function loadCsv(file:File){
    const text=await file.text();
    if(text.length>3_800_000)return notify('CSV 가 너무 큽니다(한 번에 4 MB 까지) — 5-3 에서 최종 목록을 나눠 저장하세요.','error');
    setBusy(true);setWafers(undefined);setPicked([]);setCsvInfo(null);
    try{const r=(await desktop.request('cgm_csv',{text,root:root.trim(),name:file.name}).promise).colorgray as
        {rows:number;wafers:Wafer[];missing:number;missing_examples:string[];need_root:boolean;default_output:string};
      setCsvInfo({name:file.name,rows:r.rows,missing:r.missing,examples:r.missing_examples,needRoot:r.need_root});
      setWafers(r.wafers);setDefaultOut(r.default_output);setPicked(r.wafers.map(w=>rel(w.path)));
      if(r.need_root&&!r.wafers.length)notify('CSV 의 매칭 폴더가 "고른 폴더부터"의 경로입니다. 위 [Lot / Wafer 폴더]에 그때 고른 폴더(예: 레시피 폴더)를 넣고 CSV 를 다시 고르세요.','error');
      else if(r.wafers.length){notify(`최종 목록 ${r.rows}줄 · 매칭 폴더 ${r.wafers.length}개${r.missing?` · 폴더를 못 찾은 줄 ${r.missing}개(최종 목록 엑셀에 이유와 함께 남음)`:''}`,r.missing?'info':'ok');setStep(1);}
      else notify('CSV 의 매칭 폴더를 하나도 찾지 못했습니다. 장비 공유를 탐색기로 먼저 연결했는지 확인하세요.','error');
    }catch(e){fail(e);}finally{setBusy(false);}
  }

  async function run(){
    const paths=picked.map(id=>byId.get(id)?.path).filter((p):p is string=>!!p);
    if(mode==='custom'&&!custom.trim())return notify('저장 위치를 고르세요.','error');
    setBusy(true);stop.current=false;setResults([]);setLog([]);setState('running');setFinalOut(null);
    let plan:Job;
    try{plan=((await desktop.request('cgm_start',{wafers:paths,output:mode==='custom'?custom.trim():''}).promise).colorgray as {job:Job}).job;}
    catch(e){setBusy(false);setState('idle');return fail(e);}
    setJob(plan);setStep(4);
    const total=plan.wafers.reduce((n,w)=>n+w.records.length,0);let done=0;
    setProgress({done:0,total,text:'준비'});addLog(`결과 폴더: ${plan.output}`);
    try{
      for(let wi=0;wi<plan.wafers.length;wi++){
        const w=plan.wafers[wi];addLog(`${w.name}: Color ${w.colors}장 중 매칭 ${w.records.length}장${w.failed?` · 매칭 실패 ${w.failed}장`:''}`);
        if(w.coord&&w.coord!=='그대로')addLog(`${w.name}: Fault 좌표를 wafer map 직사각형의 좌측 하단 (0,0) 기준(${w.coord})으로 맞췄습니다.`);
        if(w.failed&&w.diagnosis)addLog(`${w.name} 진단: ${diagText(w.diagnosis)}`);
        let grayName='',gray:ImageBitmap|undefined;
        for(let ri=0;ri<w.records.length;ri++){
          if(stop.current)break;
          const r=w.records[ri];
          setProgress({done,total,text:`[${wi+1}/${plan.wafers.length}] ${w.name} · ${ri+1}/${w.records.length} ${r.color}`});
          try{
            if(grayName!==r.gray){gray?.close();gray=await source(wi,ri,'gray');grayName=r.gray;}
            const color=await source(wi,ri,'color');
            const c=crop(gray!,r);
            const put=(kind:string,data:string,box?:number[])=>desktop.request('cgm_put',{wafer:wi,record:ri,kind,data,...(box?{box}:{})}).promise;
            await put('crop',await toB64(c.canvas,.95),c.box);
            await put('color_thumb',await toB64(thumb(color),.78));
            await put('gray_thumb',await toB64(thumb(gray!,{x:r.px,y:r.py,w:r.gw,h:r.gh}),.78));
            await put('crop_thumb',await toB64(thumb(c.canvas),.78));
            if(r.box){   // v14 최종 목록 엑셀 사진 3장(HTML 5-3 엑셀과 같은 그림 · 크기 한도)
              await put('color_view',await toB64(fit(color,960,720),.85));
              await put('crop_mark',await toB64(fit(cropMark(gray!,r,c),960,720),.85));
              await put('frame_mark',await toB64(fit(frameMark(gray!,r),1800,600),.85));
            }
            color.close();
          }catch(e){addLog(`실패 ${r.color}: ${errorText(e)}`);
            await desktop.request('cgm_fail',{wafer:wi,record:ri,reason:errorText(e)}).promise.catch(()=>undefined);}
          done++;
        }
        gray?.close();
        setProgress({done,total,text:`${w.name} Excel 만드는 중…`});
        const f=(await desktop.request('cgm_finish',{wafer:wi}).promise).colorgray as Finished;
        setResults(x=>[...x,{...f,name:w.name}]);addLog(`${w.name} 완료 — 성공 ${f.matched} · 실패 ${f.failed}`);
        if(stop.current)break;
      }
      if(plan.final){
        setProgress(p=>({...p,text:'최종 목록 엑셀 만드는 중…'}));
        const fo=(await desktop.request('cgm_final').promise).colorgray as FinalOut;
        setFinalOut(fo);addLog(`최종 목록 엑셀: ${fo.rows}줄 중 사진 ${fo.done}줄${fo.missing?` · 사진 없음 ${fo.missing}줄(이유 칸)`:''}`);
      }
      setProgress(p=>({...p,done:stop.current?p.done:total,text:stop.current?'취소됨':'완료'}));
      setState(stop.current?'cancelled':'complete');setStep(5);
      notify(stop.current?'작업을 취소했습니다. 처리한 이미지까지 Excel 로 저장했습니다.':'Color·Gray 매칭을 마쳤습니다.',stop.current?'info':'ok');
    }catch(e){setState('error');addLog('오류 '+errorText(e));fail(e);setStep(5);}
    finally{setBusy(false);}
  }
  async function restart(){
    await desktop.request('cgm_reset').promise.catch(()=>undefined);
    setStep(0);setWafers(undefined);setPicked([]);setJob(undefined);setResults([]);setLog([]);setState('idle');setMode('default');setCustom('');setCsvInfo(null);setFinalOut(null);
  }

  const outText=mode==='custom'?(custom||'(선택하지 않음)'):defaultOut;
  const pct=progress.total?Math.round(progress.done/progress.total*1000)/10:0;
  const canNext=step===0?!!wafers?.length:step===1?picked.length>0:step===2?(mode==='default'||!!custom.trim()):true;
  return <section className="panel">
    <div className="section-heading"><div><span className="step">IMAGE</span><h2>Color · Gray 매칭</h2></div>
      <span className="count">{wafers?`Wafer ${picked.length} / ${wafers.length}`:'원본 읽기 전용'}</span></div>
    <p className="hint">AOI Color 이미지마다 같은 위치의 Gray 스캔 프레임을 찾아, Color 시야만큼 Gray 를 잘라(Crop) 나란히 비교하는 Excel 을 만듭니다.
      원본 폴더는 읽기만 하고, 결과는 로컬 작업 폴더(또는 고른 로컬 폴더)에 저장합니다.</p>
    <Stepper labels={STEPS} current={step} onJump={i=>{if(!busy&&i<=3&&(i===0||wafers?.length))setStep(i);}}/>
    <div className="step-body">
    {step===0&&<>
      <p className="hint">Lot 폴더(여러 Wafer) 또는 Wafer 폴더 하나를 고르세요. 장비 공유 폴더는 탐색기(Win+R → <code>\\IP\c$</code>)로 먼저 연결해야 보입니다.
        Wafer 폴더 = <code>ColorImageGrabingInfo.ini</code> · <code>ScanResultImageList.txt</code> · <code>frameToChuckPlane.ini</code> 가 있는 폴더(하위 5단계까지, 최대 25개).</p>
      <div className="form-filter">
        <label className="field" style={{flex:1}}>Lot / Wafer 폴더<input aria-label="Lot 또는 Wafer 폴더" value={root} onChange={e=>setRoot(e.target.value)} placeholder="예: W:\AOI-9\Scanresult\2D@DEVICE\6412\LOT01"/></label>
        <button disabled={busy} onClick={()=>void browse(setRoot)}>📁 찾아보기…</button>
        <button className="primary" disabled={busy||!root.trim()} onClick={()=>void scan()}>{busy?'찾는 중…':'Wafer 찾기'}</button>
      </div>
      {busy&&<p className="hint" role="status"><span className="spinner" aria-hidden="true"/> 하위 폴더에서 Wafer 를 찾는 중입니다. 진행 상황은 오른쪽 아래 창에 표시됩니다.
        <button onClick={()=>void desktop.request('cgm_reset').promise.catch(()=>undefined)}>검색 취소</button></p>}
      <div className="cg-final" aria-label="최종 목록 CSV 로 고르기">
        <p className="hint"><b>또는 최종 목록 CSV 로 고르기</b> — [대규모 Defect 분석] 5-3 에서 ☑ 한 Defect 를 <b>📄 최종 목록 CSV 저장</b>으로 저장한 파일을 고르면,
          그 Defect 만 추출하고 결과 파일과 함께 <b>최종 목록 엑셀(Color · Gray Crop · Gray 프레임 사진 3장)</b>을 만듭니다.
          CSV 의 매칭 폴더가 전체 경로(프로그램에서 저장)면 위 폴더 칸은 비워 두세요. 브라우저로 따로 연 HTML 에서 [원본 폴더 경로] 없이 저장했다면 그때 고른 폴더를 위 칸에 넣으세요.</p>
        <input ref={csvInput} type="file" accept=".csv,text/csv" hidden aria-label="최종 목록 CSV 파일" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void loadCsv(f);}}/>
        <button disabled={busy} onClick={()=>csvInput.current?.click()}>📄 최종 목록 CSV 고르기…</button>
        {csvInfo&&<p className="hint" role="status"><b>{csvInfo.name}</b> — {csvInfo.rows}줄{csvInfo.missing?` · 매칭 폴더를 못 찾은 줄 ${csvInfo.missing}개 (예: ${csvInfo.examples.join(', ')})`:''}</p>}
      </div>
    </>}
    {step===1&&wafers&&<>
      <p className="hint">처리할 Wafer 를 고르세요. 기본은 전체 선택입니다.</p>
      <RowPick label="처리할 Wafer" columns={['Wafer','위치']} value={picked} onChange={setPicked}
        rows={wafers.map(w=>({id:rel(w.path),title:w.path,cells:[<b key="n">{w.name}</b>,<code key="p">{w.path}</code>]}))}/>
    </>}
    {step===2&&<>
      <p className="hint">결과(Excel · Crop 이미지 · 썸네일)는 이미지 수만큼 파일이 생기므로 <b>로컬 디스크</b>에만 저장합니다(OneDrive·네트워크·원본 폴더 안은 불가).</p>
      <div className="out-choice" role="radiogroup" aria-label="결과 저장 위치">
        <div className={'out-row'+(mode==='default'?' on':'')}>
          <button type="button" role="radio" aria-checked={mode==='default'} className={'out-pick'+(mode==='default'?' on':'')} onClick={()=>setMode('default')}>로컬 작업 폴더 (기본)</button>
          <code className="out-path" title={defaultOut}>{defaultOut}\{'{'}실행 시각{'}'}</code>
        </div>
        <div className={'out-row'+(mode==='custom'?' on':'')}>
          <button type="button" role="radio" aria-checked={mode==='custom'} className={'out-pick'+(mode==='custom'?' on':'')} onClick={()=>setMode('custom')}>다른 로컬 폴더</button>
          <input className="out-path" aria-label="다른 로컬 폴더 경로" placeholder="폴더 경로를 입력하거나 [찾아보기]" value={custom}
            onFocus={()=>setMode('custom')} onChange={e=>{setCustom(e.target.value);setMode('custom');}}/>
          <button type="button" onClick={()=>void browse(p=>{setCustom(p);setMode('custom');})}>📁 찾아보기…</button>
        </div>
      </div>
    </>}
    {step===3&&<>
      <table className="tbl watch-status" aria-label="실행 전 검토"><tbody>
        {csvInfo?<tr><th>최종 목록 CSV</th><td><b>{csvInfo.name}</b> — {csvInfo.rows}줄 (그 Defect 만 · 최종 목록 엑셀 포함)</td></tr>
          :<tr><th>선택 폴더</th><td><code>{root}</code></td></tr>}
        <tr><th>처리 Wafer</th><td>{picked.length}개 — {picked.slice(0,8).join(', ')}{picked.length>8?' …':''}</td></tr>
        <tr><th>결과 위치</th><td><code>{outText}</code>{mode==='default'&&' \\ 실행 시각 폴더'}</td></tr>
        <tr><th>Excel 링크</th><td>Crop 은 상대경로 · Color/Gray 는 원본 절대경로</td></tr></tbody></table>
      <div className="toolbar"><button className="primary" disabled={busy} onClick={()=>void run()}>▶ 처리 시작</button></div>
    </>}
    {step===4&&<>
      <p role="status" aria-live="polite"><b>{progress.text}</b></p>
      <div className="progress-bar" aria-label="처리 진행률" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><i style={{width:`${pct}%`}}/></div>
      <p className="hint">{progress.done} / {progress.total} 이미지 · {pct}% — 이 화면을 벗어나도 계속 처리합니다(다른 탭 이동 가능).</p>
      <pre className="log-box" aria-label="처리 기록">{log.join('\n')}</pre>
      <div className="toolbar"><button className="danger" disabled={!busy} onClick={()=>{stop.current=true;notify('현재 이미지까지 처리하고 멈춥니다.','info');}}>작업 취소</button></div>
    </>}
    {step===5&&<>
      <p><b className={state==='complete'?'st-on':'st-off'}>{state==='complete'?'완료':state==='cancelled'?'취소됨':'오류'}</b>{job&&<> · 결과 폴더</>}</p>
      {job&&<OpenPath label="결과 폴더" path={job.output} folder/>}
      {finalOut&&<p><b>최종 목록 엑셀</b> — {finalOut.rows}줄 중 사진 {finalOut.done}줄{finalOut.missing?` · 사진 없음 ${finalOut.missing}줄(엑셀의 '사진 없음 이유' 칸)`:''} <OpenPath label="" path={finalOut.workbook}/></p>}
      <table className="tbl" aria-label="Wafer별 결과"><thead><tr><th>Wafer</th><th>성공</th><th>실패</th><th>Excel</th></tr></thead>
        <tbody>{results.map(r=><tr key={r.workbook}><td><b>{r.name}</b></td><td>{r.matched}</td><td className={r.failed?'warn':''}>{r.failed}</td>
          <td><OpenPath label="" path={r.workbook}/>{r.failures_csv&&<OpenPath label="실패 목록" path={r.failures_csv}/>}</td></tr>)}</tbody></table>
      {log.length>0&&<details><summary>처리 기록</summary><pre className="log-box">{log.join('\n')}</pre></details>}
      <div className="toolbar"><button className="primary" onClick={()=>void restart()}>새 작업</button></div>
    </>}
    </div>
    {step<3&&<StepNav step={step} total={4} busy={busy} nextDisabled={!canNext} nextLabel="다음"
      onBack={()=>setStep(s=>Math.max(0,s-1))} onNext={()=>setStep(s=>s+1)}/>}
    {step===3&&<div className="stepnav"><button className="btn" disabled={busy} onClick={()=>setStep(2)}>◀ 이전</button><span className="stepcount">4 / {STEPS.length}</span><span/></div>}
  </section>;
}
