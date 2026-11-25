/* 자동 생성(frontend/vite.config.ts defectRun) — 원본 = frontend/public/defect/AOI_Contrast_Wizard_rev6.html. 이 파일은 고치지 말 것 */
(window.__dfxRun=window.__dfxRun||{})["AOI_Contrast_Wizard_rev6.html"]=function(document,window,location,localStorage,addEventListener,removeEventListener,self,globalThis,scrollTo,paraHost){

'use strict';
// ════════════════════════════════════════════════════════════════════════
// 1. 파서 (순수 함수 — window.__cw 로 시험에서 부른다)
// ════════════════════════════════════════════════════════════════════════
const REC = 152;   // Surface.flt 고정 레코드 크기(byte), little-endian
/** 기본 필드 정의 [이름, 형식, offset]. Surface.flt.md 에 같은 이름이 있으면 그 offset 을 쓴다. */
const FLT_FIELDS = [
  ['reclassify','int16',0],['orgReclassify','int16',2],['Type','int32',4],
  ['x','float64',8],['y','float64',16],['ActualX','float64',24],['ActualY','float64',32],
  ['id','int32',40],['resultID','int32',44],['frameIdx','int32',48],['xInFrame','float32',52],['yInFrame','float32',56],
  ['waferRegion','uint8',60],['zone','uint8',61],['recipe','uint8',62],
  ['BoxWidth','float64',64],['BoxHeight','float64',72],['area','float64',80],
  ['BlobBreadth','float64',88],['BlobLength','float64',96],['BlobFeretMax','float64',104],['BlobFeretMaxAngle','float64',112],['BlobFeretMin','float64',120],
  ['particlesNum','int32',128],['particlesArea','int32',132],['Contrast','float64',136],['taskID','int32',144]];
const TYPE_SIZE = {int8:1,uint8:1,byte:1,char:1,bool:1,int16:2,uint16:2,short:2,ushort:2,int32:4,uint32:4,int:4,uint:4,long:4,float32:4,float:4,single:4,float64:8,double:8,int64:8,uint64:8};
function normType(t){t=String(t||'').toLowerCase().replace(/^system\./,'');
  // Para #53: 실제 .md 는 Vartype 숫자(VARIANT 코드)를 쓴다: 2 int16 · 3 int32 · 4 float32 · 5 float64 · 16 int8 · 17 uint8 · 18 uint16 · 19 uint32 · 20 int64 · 21 uint64
  const vt={2:'int16',3:'int32',4:'float32',5:'float64',16:'int8',17:'uint8',18:'uint16',19:'uint32',20:'int64',21:'uint64',22:'int32',23:'uint32'};if(/^\d+$/.test(t))return vt[t]||t;
  return {byte:'uint8',char:'int8',bool:'uint8',short:'int16',ushort:'uint16',int:'int32',uint:'uint32',long:'int32',float:'float32',single:'float32',double:'float64'}[t]||t}
function readField(dv,o,t){switch(t){
  case 'int8':return dv.getInt8(o);case 'uint8':return dv.getUint8(o);case 'int16':return dv.getInt16(o,true);case 'uint16':return dv.getUint16(o,true);
  case 'int32':return dv.getInt32(o,true);case 'uint32':return dv.getUint32(o,true);case 'float32':return dv.getFloat32(o,true);case 'float64':return dv.getFloat64(o,true);
  case 'int64':return Number(dv.getBigInt64(o,true));case 'uint64':return Number(dv.getBigUint64(o,true));default:return null}}

/** *.md 필드 정의 XML 을 너그럽게 읽는다. name/type(/offset/size) 속성 또는 같은 이름의 자식 요소를 찾는다.
 *  offset 이 없으면 형식 크기를 차례로 더한다. 반환 {fields:[{name,type,offset}], recordSize} 또는 null. */
function parseMd(text){
  let doc;try{doc=new DOMParser().parseFromString(text,'application/xml')}catch(e){return null}
  if(!doc||doc.getElementsByTagName('parsererror').length)return null;
  const get=(el,k)=>{for(const a of el.attributes||[])if(a.name.toLowerCase()===k)return a.value;
    for(const c of el.children||[])if(c.tagName.toLowerCase()===k&&!c.children.length)return c.textContent.trim();return null};
  const fields=[];let cur=0,recordSize=null;
  for(const el of doc.getElementsByTagName('*')){
    const rs=get(el,'recordsize')||get(el,'recsize')||get(el,'size_of_record')||(el.tagName.toLowerCase()==='recordsize'?get(el,'size'):null);if(rs&&recordSize==null&&!get(el,'type'))recordSize=+rs||null;
    const name=get(el,'name'),type=normType(get(el,'type')||get(el,'datatype')||get(el,'vartype'));
    if(!name||!TYPE_SIZE[type])continue;
    const off=get(el,'offset');const o=off!=null&&off!==''?+off:cur;
    fields.push({name,type,offset:o});cur=o+TYPE_SIZE[type]}
  if(!fields.length)return null;
  return {fields,recordSize:recordSize||cur};
}
/** 기본 정의에 .md 의 offset/형식을 이름(대소문자 무시)으로 덮어쓴다. 다르면 경고를 돌려준다. */
function fltLayout(md){
  const lay=FLT_FIELDS.map(([n,t,o])=>({name:n,type:t,offset:o}));const warns=[];
  if(!md)return {lay,warns};
  const by=new Map(md.fields.map(f=>[f.name.toLowerCase(),f]));
  for(const f of lay){const m=by.get(f.name.toLowerCase());if(!m)continue;
    if(m.offset!==f.offset||m.type!==f.type){warns.push(`${f.name}: 기본 ${f.type}@${f.offset} → md ${m.type}@${m.offset}`);f.offset=m.offset;f.type=m.type}}
  return {lay,warns};
}
/** Para #74: Surface.flt 레코드 크기(byte). 종전에는 152 로 고정해 레코드가 다른 장비 · 레시피(실제: 136 byte)의 Slot 이 전부 '잘못된 Record Size' 로 빠졌다.
 *  지금: ① Surface.flt.md 의 RecordSize(없으면 필드 끝) ② 기본 152 — 파일 크기가 나누어떨어지는 첫 값. 둘 다 아니면 ① (오류 글에 그 값). */
function fltRec(md,bytes){const c=[];if(md&&md.recordSize>=8)c.push(md.recordSize);c.push(REC);
  for(const r of c)if(bytes>0&&bytes%r===0)return r;return c[0]}
/** 오류 글: 어느 크기로 나눴는지 · md 가 없으면 무엇을 두어야 하는지. */
function fltRecErr(r,md){return `잘못된 Record Size: ${r.bytes} byte 는 ${r.rec} 로 나누어떨어지지 않음(나머지 ${r.rem})`+
  (md?` — Surface.flt.md 레코드 ${md.recordSize} byte`:` — Surface.flt.md 없음(기본 ${REC} byte). 레코드 크기가 다른 장비면 Surface.flt.md 를 Slot 또는 Lot 폴더에 두십시오`)}
/** Surface.flt → Defect 배열. 레코드 크기(rec, 기본 152)로 나누어떨어지지 않으면 ok=false. */
function parseFlt(buf,lay,rec){
  lay=lay||fltLayout(null).lay;rec=rec||REC;
  const n=Math.floor(buf.byteLength/rec),rem=buf.byteLength%rec,dv=new DataView(buf),out=[];
  for(let i=0;i<n;i++){const d={i};for(const f of lay)if(f.offset+TYPE_SIZE[f.type]<=rec)d[f.name]=readField(dv,i*rec+f.offset,f.type);out.push(d)}
  return {defects:out,ok:rem===0&&buf.byteLength>0,rem,bytes:buf.byteLength,rec};
}
/** Step 5(대용량): Surface.flt → 열 배열(필요한 필드만, Defect 마다 객체를 만들지 않는다). [열 키, 필드 이름, 배열 형식] */
const COLS=[['x','x',Float64Array],['y','y',Float64Array],['ax','ActualX',Float64Array],['ay','ActualY',Float64Array],['id','id',Int32Array],['rid','resultID',Int32Array],['rec','recipe',Uint8Array],
  ['bw','BoxWidth',Float32Array],['bh','BoxHeight',Float32Array],['area','area',Float64Array],['w','BlobBreadth',Float64Array],['l','BlobLength',Float64Array],['c','Contrast',Float64Array],
  ['rc','reclassify',Int16Array],['orc','orgReclassify',Int16Array],['zn','zone',Uint8Array],['rg','waferRegion',Uint8Array],['ty','Type',Int32Array],
  ['fi','frameIdx',Int32Array],['xf','xInFrame',Float32Array],['yf','yInFrame',Float32Array]];   // v14.4.1(#89): 장비가 적은 Defect 의 프레임 · 픽셀(있으면 Gray 위치에 그대로 — geoHit)   // #73: 리뷰PC 정보(Zone · Region · 판정 비트)   // rev5: Classify(분류 코드 → ManReClassify.ini 이름)
function parseFltCols(buf,lay,rec){
  lay=lay||fltLayout(null).lay;rec=rec||REC;
  const n=Math.floor(buf.byteLength/rec),rem=buf.byteLength%rec,dv=new DataView(buf),by=new Map(lay.map(f=>[f.name,f])),C={n};
  for(const [k,name,T] of COLS){const a=C[k]=new T(n),f=by.get(name);if(!f||f.offset+TYPE_SIZE[f.type]>rec)continue;const o=f.offset,ty=f.type;for(let i=0;i<n;i++)a[i]=readField(dv,i*rec+o,ty)}
  return {cols:C,ok:rem===0&&buf.byteLength>0,rem,bytes:buf.byteLength,rec};
}
/** [section] key=value INI → [{name, kv:{소문자키:값}}] */
function parseIni(text){
  const out=[];let cur=null;
  for(const raw of String(text).split(/\r?\n/)){const line=raw.trim();if(!line||line[0]===';'||line[0]==='#')continue;
    if(line[0]==='['&&line.endsWith(']')){cur={name:line.slice(1,-1).trim(),kv:{}};out.push(cur);continue}
    const k=line.indexOf('=');if(k<0)continue;if(!cur){cur={name:'',kv:{}};out.push(cur)}
    cur.kv[line.slice(0,k).trim().toLowerCase().replace(/[^a-z0-9]/g,'')]=line.slice(k+1).trim()}
  return out;
}
const pick=(kv,keys)=>{for(const k of keys){const v=kv[k];if(v!=null&&v!=='')return v}return null};
const num=v=>{if(v==null||v==='')return null;const n=parseFloat(v);return isFinite(n)?n:null};
/** 글 파일 읽기(rev2, 2026-11-10): UTF-8(BOM 있어도) · UTF-16 LE/BE(BOM 또는 한 칸 걸러 0 인 모양) · 그 밖이면 EUC-KR(CP949).
 *  장비 ini 가 UTF-16 으로 저장돼 있으면 종전(File.text() = UTF-8 로만)에는 파일 이름 사이에 보이지 않는 글자가 끼어 'Color 파일 없음'이 났다. */
async function readText(f){const b=new Uint8Array(await f.arrayBuffer()),dec=(e,x)=>new TextDecoder(e).decode(x).replace(/\0/g,'');
  if(b[0]===0xFF&&b[1]===0xFE)return dec('utf-16le',b);if(b[0]===0xFE&&b[1]===0xFF)return dec('utf-16be',b);
  if(b[0]===0xEF&&b[1]===0xBB&&b[2]===0xBF)return dec('utf-8',b);
  const n=Math.min(b.length,512);let z0=0,z1=0;for(let i=0;i<n;i++)if(!b[i])(i&1?z1++:z0++);
  if(z1>n/5&&z0<n/20)return dec('utf-16le',b);if(z0>n/5&&z1<n/20)return dec('utf-16be',b);
  try{return new TextDecoder('utf-8',{fatal:true}).decode(b)}catch(e){try{return dec('euc-kr',b)}catch(x){return dec('utf-8',b)}}}
/** Color 사진 이름 = '{X}.{Y}.c.{번호}.jpeg'(실제 결과 폴더: 앞 두 숫자 = FaultX · FaultY 를 정수로, 2 µm 안). ColorImageGrabingInfo.ini 가 없거나 못 읽을 때 이 좌표로 연결한다. */
const CNAME_RE=/^(-?\d+(?:\.\d+)?)\.(-?\d+(?:\.\d+)?)\.c\.[^\\/]*\.(?:jpe?g|png|bmp)$/i;
function colorsFromNames(names){const out=[];for(const n of names){const m=CNAME_RE.exec(n);if(m)out.push({file:n,x:+m[1]+.5,y:+m[2]+.5,index:null,fromName:true})}return out}
/** ColorImageGrabingInfo.ini → Color 항목. 키 이름 변형을 받는다. */
function parseColors(text){
  return parseIni(text).filter(s=>s.name||Object.keys(s.kv).length).map(s=>{const kv=s.kv;
    return {file:pick(kv,['filename','imagename','file','name','image'])||s.name,
      index:num(pick(kv,['index','defectindex','defectidx','faultindex','defectid','id'])),
      x:num(pick(kv,['faultx','x','defectx','posx'])),y:num(pick(kv,['faulty','y','defecty','posy'])),
      recipe:num(pick(kv,['recipenumber','recipe'])),col:num(pick(kv,['col','diecol'])),row:num(pick(kv,['row','dierow'])),
      w:num(pick(kv,['imagesizex'])),h:num(pick(kv,['imagesizey'])),psx:num(pick(kv,['pixelsizex'])),psy:num(pick(kv,['pixelsizey'])),section:s.name}})
    .filter(c=>c.file);
}
/** ScanResultImageList.txt → [{file,x,y,recipe}] (colorgray.parse_frames 와 같음) */
function parseFrames(text){
  const out=[];
  for(const raw of String(text).split(/\r?\n/)){const p=raw.trim().split(/[,;\t]/).map(s=>s.trim());
    if(p.length<3||p[0].startsWith('Version='))continue;const x=parseFloat(p[1]),y=parseFloat(p[2]);if(!isFinite(x)||!isFinite(y))continue;
    const m=/\.t\.(\d+)\.jpe?g$/i.exec(p[0]);out.push({file:p[0].replace(/^"|"$/g,''),x,y,recipe:m?+m[1]:null})}
  return out;
}
/** frameToChuckPlane.ini → {inv, off} (colorgray.parse_transform 와 같음: Scan_X = a b ox, Scan_Y = c d oy) */
function parseTransform(text){
  const d={};
  for(const raw of String(text).split(/\r?\n/)){if(raw.trimStart().startsWith('['))continue;const line=raw.split(';')[0].trim();const k=line.indexOf('=');if(k<0)continue;
    const nums=line.slice(k+1).trim().split(/[\s,]+/).filter(Boolean).map(Number);if(nums.some(n=>!isFinite(n)))continue;
    const key=line.slice(0,k).toLowerCase().replace(/[^a-z0-9]/g,'');if(!(key in d))d[key]=nums}
  const sx=d.scanx,sy=d.scany;if(!sx||!sy||sx.length<3||sy.length<3)throw new Error('Scan_X · Scan_Y(숫자 3개) 줄이 없습니다');
  const a=sx[0],b=sx[1],c=sy[0],e=sy[1],det=a*e-b*c;if(!det)throw new Error('변환 행렬을 풀 수 없습니다');
  return {inv:[[e/det,-b/det],[-c/det,a/det]],off:[sx[2],sy[2]]};
}
/** ProductInfo.ini → Die 계산 메타데이터. 없으면 null. */
function parseProduct(text){
  const kv={};for(const s of parseIni(text))Object.assign(kv,s.kv);
  // v14.3.12(#82): Pitch = [Geometric] XDieIndex · YDieIndex 먼저(실제 결과 폴더 3장에서 Color 이미지 Col/Row 와 278/278 일치), 없으면 종전 키
  const px=num(pick(kv,['xdieindex','customerdiepitchx','diepitchx','pitchx'])),py=num(pick(kv,['ydieindex','customerdiepitchy','diepitchy','pitchy']));
  const cols=num(pick(kv,['cols','columns','diecols','numcols'])),rows=num(pick(kv,['rows','dierows','numrows']));
  if(!px||!py||!cols||!rows)return null;
  // 길이 단위 추정: ≤ 20 = inch, ≤ 1000 = mm, 그 위 = µm → µm
  const um=v=>v==null?null:v<=20?v*25400:v<=1000?v*1000:v;
  return {pitchX:px,pitchY:py,cols,rows,offX:num(pick(kv,['customerdieoffsetx','offsetx','dieoffsetx','mapshiftx']))||0,offY:num(pick(kv,['customerdieoffsety','offsety','dieoffsety','mapshifty']))||0,
    waferD:um(num(pick(kv,['waferdiameter','wafersize','wafersizemm','diameter','substratediameter','wafer']))),
    edge:(()=>{const v=num(pick(kv,['edgeexclusion','edgeexclusionmm','edgeexclude','edgeexcl']));return v==null?null:v<=20?v*1000:v})(),
    notch:num(pick(kv,['fnloc','notch','notchangle','notchlocation','notchdirection','flatangle','flatlocation'])),
    // Para #53: 실제 wafer 중심(장비 [Geometric] CenterX/CenterY, µm, Die 좌표와 같은 Wafer 좌표계). 없으면 null → s_DieLocation · 추정
    centerX:num(pick(kv,['centerx','wafercenterx'])),centerY:num(pick(kv,['centery','wafercentery'])),
    // v14.3.12: 웨이퍼 맵 범위 = [ExportData] cMin~cMax · rMin~rMax(장비 Col/Row), Flat Pos = [Geometric] Flat Pos(3 = Notch 아래, 소유자 확인)
    exp:(()=>{const e=['cmin','cmax','rmin','rmax'].map(k=>num(pick(kv,[k])));return e.every(v=>v!=null)&&e[1]>=e[0]&&e[3]>=e[2]?{cMin:e[0],cMax:e[1],rMin:e[2],rMax:e[3]}:null})(),
    flatPos:num(pick(kv,['flatpos']))};
}
/** 장비 Die 번호(Para #52 · #82 확인): Col = floor((X−OffX)/PitchX), Row = floor((Y−OffY)/PitchY) — ColorImageGrabingInfo Col/Row 와 같은 번호.
 *  Die 내부 = 그 Die 좌측 하단(장비 좌표)에서의 거리. 사람이 읽는 번호는 웨이퍼 맵 기준(mapDie — X = Col − cMin, Y = rMax − Row). */
function dieOf(x,y,p){
  if(!p||x==null||y==null)return null;
  const ix=Math.floor((x-p.offX)/p.pitchX),iy=Math.floor((y-p.offY)/p.pitchY);
  return {col:ix,row:iy,dx:x-p.offX-ix*p.pitchX,dy:y-p.offY-iy*p.pitchY,valid:ix>=0&&iy>=0};
}
/** Wafer2Table.ini [WAFER ALIGNMENT] Wafer2Table_X/Y = a b tx / c e ty(table = A·wafer + t) → table (0, 0) 이 되는 wafer 좌표 {x, y} µm(= wafer 중심). 없으면 null. */
function parseW2T(text){const g=k=>{const m=new RegExp('^\\s*'+k+'\\s*=([^\\r\\n]*)','im').exec(text);return m?m[1].trim().split(/\s+/).map(Number):null};
  const X=g('Wafer2Table_X'),Y=g('Wafer2Table_Y');if(!X||!Y||X.length<3||Y.length<3||[...X,...Y].some(v=>!isFinite(v)))return null;
  const [a,b,tx]=X,[c,e,ty]=Y,det=a*e-b*c;if(!det)return null;return {x:(-tx*e+b*ty)/det,y:(-a*ty+c*tx)/det}}
/** s_DieLocation.dat(+ .md) → 스캔한 Die 의 중심 좌표 [{x, y, sx, sy}] (Para #53: 실제 결과 폴더에서 확인 — 128 byte 레코드,
 *  x/y = Die 중심 Wafer 좌표 µm, DieSizeX/Y = Die 크기). 없거나 크기가 맞지 않으면 null. */
function parseDieLoc(buf,mdText){
  let rec=128,off={x:8,y:16,sx:116,sy:120};
  const m=mdText&&/RecordSize\s+Size="(\d+)"/.exec(mdText);if(m)rec=+m[1];
  if(mdText)for(const [k,n] of [['x','x'],['y','y'],['sx','DieSizeX'],['sy','DieSizeY']]){const r=new RegExp('Name="'+n+'"[^>]*Offset="(\\d+)"').exec(mdText);if(r)off[k]=+r[1]}
  if(!buf||!buf.byteLength||buf.byteLength%rec)return null;
  const dv=new DataView(buf),out=[];
  for(let i=0;i<buf.byteLength/rec;i++){const o=i*rec;out.push({x:dv.getFloat64(o+off.x,true),y:dv.getFloat64(o+off.y,true),
    sx:off.sx+4<=rec?dv.getFloat32(o+off.sx,true):null,sy:off.sy+4<=rec?dv.getFloat32(o+off.sy,true):null})}
  return out.filter(d=>isFinite(d.x)&&isFinite(d.y));
}
/** ScanLog / ProductionInfo 글에서 Surface defect 수를 찾는다(교차 검증, 참고). */
function surfaceCount(text){const k=/^\s*SurfaceDefects\s*=\s*(\d+)/im.exec(text);if(k)return +k[1];   // Para #53: ScanLog.ini [2D] SurfaceDefects=
  const m=/surface[^\r\n\d]{0,40}?(\d+)/i.exec(text);return m?+m[1]:null}

// ════════════════════════════════════════════════════════════════════════
// 2. 동일 Defect 1:1 매칭 — 격자(셀 = 허용오차) 최근접 검색 + 거리순 greedy, 중복 매칭 없음
// ════════════════════════════════════════════════════════════════════════
function matchSets(A,B,tol){
  const cell=Math.max(tol,1e-6),grid=new Map(),key=(i,j)=>i+','+j;
  B.forEach((b,k)=>{const g=key(Math.floor(b.X/cell),Math.floor(b.Y/cell));(grid.get(g)||grid.set(g,[]).get(g)).push(k)});
  const pairs=[];
  A.forEach((a,i)=>{const ci=Math.floor(a.X/cell),cj=Math.floor(a.Y/cell);
    for(let di=-1;di<=1;di++)for(let dj=-1;dj<=1;dj++){const l=grid.get(key(ci+di,cj+dj));if(!l)continue;
      for(const k of l){const d=Math.hypot(a.X-B[k].X,a.Y-B[k].Y);if(d<=tol)pairs.push([d,i,k])}}});
  pairs.sort((p,q)=>p[0]-q[0]);
  const ua=new Uint8Array(A.length),ub=new Uint8Array(B.length),keep=[];
  for(const [d,i,k] of pairs){if(ua[i]||ub[k])continue;ua[i]=ub[k]=1;keep.push({a:A[i],b:B[k],d})}
  return {keep,gone:A.filter((_,i)=>!ua[i]),added:B.filter((_,k)=>!ub[k])};
}
/** Para #57: Lot 별 비교 — 같은 Defect 는 같은 Slot(Wafer) 끼리만 짝짓는다(다른 Wafer 의 같은 좌표는 다른 Defect).
 *  양쪽이 Slot 1개씩이면 Slot 이름이 달라도 그대로 짝짓는다(Slot 폴더를 하나씩 고른 경우). */
const slotOf=x=>x.slot??(x.scan&&x.scan.slot)??'';
function matchBySlot(A,B,tol){const ga=new Map(),gb=new Map(),put=(m,x)=>{const k=slotOf(x);(m.get(k)||m.set(k,[]).get(k)).push(x)};
  A.forEach(x=>put(ga,x));B.forEach(x=>put(gb,x));if(ga.size<=1&&gb.size<=1)return matchSets(A,B,tol);
  const keep=[],gone=[],added=[];for(const k of new Set([...ga.keys(),...gb.keys()])){const r=matchSets(ga.get(k)||[],gb.get(k)||[],tol);keep.push(...r.keep);gone.push(...r.gone);added.push(...r.added)}
  return {keep,gone,added}}

// ════════════════════════════════════════════════════════════════════════
// 3. Gray 프레임 · 픽셀 찾기 — 기본(Step 1 ~ 4) · 대규모(Step 5) 공통 (v14.4.1, #89 — 소유자 "수정된 로직은 대규모, 기본 모드 둘다 동일하게")
//   모델 = Para 'Color · Gray 매칭'(colorgray.choose_frame): Gray 픽셀 p = M⁻¹ · (결함 − 프레임 좌표 − o)(frameToChuckPlane Scan_X · Scan_Y 의 M · o),
//   프레임 좌표 = 프레임 가운데(o = −M·(W/2, H/2)), 같은 레시피 프레임 중 p 가 프레임 안이고 가장자리에서 가장 먼 것.
//   #89 실제 Slot 3장: 프레임 크기 · 픽셀 크기는 레시피(배율)마다 다르다 — PI 3168×1024 · 0.7707 / x20 2848×1024 · 0.3853 / x5 3168×1024 · 1.5369 /
//   2D+3D 2048×2048 · 1.6899 µm. 종전 3168×1024 · 0.7708 고정은 PI 레시피에만 맞았다 → Slot 의 파일에서 읽는다:
//     크기 = 변환 offset → s_FrameData frameSize → 3168×1024, 픽셀 = 변환 → s_FrameData PixelSize → RecipesInfo.ini Scan2DPixelSize(공칭, 0.7708 의 출처) → 0.7698.
//   장비가 Defect 의 프레임 · 픽셀(Surface.flt frameIdx · xInFrame · yInFrame)을 적어 두었으면 그것을 그대로 쓴다(실제 74개: 그 값으로 다시 계산한 좌표 = Defect 좌표 ± 0.9 µm).
//   종전 기본 모드는 변환 파일이 없으면 프레임 좌표를 모서리로 본 '간단 모델'(0.7708, 약 1200 µm 어긋남) · 목록이 없으면 Gray 없음이었다 — 지금은 대규모와 같은 대체 계산.
// ════════════════════════════════════════════════════════════════════════
const GEO_W=3168,GEO_H=1024,GEO_PIX=0.7698455822,GEO_REC_TOL=5;   // 마지막 대체값(파일에 아무 값도 없을 때) · 장비 기록 프레임 고르기 허용(µm)
/** 변환 → 프레임 크기 {W, H}: 프레임 좌표(가운데) = 픽셀 (W/2, H/2) = −M⁻¹ · o. 값이 이상하면(예: offset 0) null. */
function tfSize(t){if(!t||t.err)return null;if(t.W>0&&t.H>0)return {W:t.W,H:t.H};
  const [[a,b],[c,d]]=t.inv,[ox,oy]=t.off,w=-2*(a*ox+b*oy),h=-2*(c*ox+d*oy),W=Math.round(w),H=Math.round(h);
  return W>=64&&H>=64&&W<=20000&&H<=20000&&Math.abs(w-W)<2&&Math.abs(h-H)<2?{W,H}:null}
/** 변환 → Gray 픽셀 크기(µm) = √|det M|. */
function tfPix(t){if(!t||t.err)return null;if(t.pix>0)return t.pix;const [[a,b],[c,d]]=t.inv,k=Math.abs(a*d-b*c);return k>0?1/Math.sqrt(k):null}
/** RecipesInfo.ini [Recipe-N] → {pix: Map(레시피 → Scan2DPixelSize µm — 장비 공칭값, 0.7708 의 출처, 변환 파일이 없을 때 · µm 환산 픽셀 sizePix), cpix: Map(레시피 → ColorPixelSize µm — Color 정보 파일이 없을 때 Crop 시야), name: Map(레시피 → Name)}. */
function parseRecipesInfo(text){const pix=new Map(),cpix=new Map(),name=new Map();for(const s of parseIni(text)){const r=/^recipe-?(\d+)$/i.exec(s.name);if(!r)continue;const p=num(s.kv.scan2dpixelsize),c=num(s.kv.colorpixelsize);
  if(p>0.05&&p<20)pix.set(+r[1],p);if(c>0.02&&c<20)cpix.set(+r[1],c);if(s.kv.name)name.set(+r[1],String(s.kv.name).trim())}return {pix,cpix,name}}
/** v14.4.1(소유자 2026-11-23): Surface.flt 크기 값(area · BlobBreadth · BlobLength · BoxWidth · BoxHeight)의 단위 = Slot 기준 픽셀 = RecipesInfo.ini 첫 레시피 Scan2DPixelSize(공칭).
 *  레시피마다 다르지 않다 — 실제 Slot(Recipe 1 x20 0.3859 · Recipe 2 x5 1.538): x5 로 찍은 Defect 의 Box · Area 가 x20 픽셀 기준(1.538 ÷ 0.3859 = 3.9855 배)으로 적혀 있었다.
 *  µm = 값 × 픽셀, µm² = 값 × 픽셀². 종전 = 0.7708 고정(PI 레시피만 맞음). RecipesInfo.ini 가 없으면 변환 파일 · s_FrameData 의 가장 작은 번호 레시피 픽셀, 그것도 없으면 0.7708(기본값).
 *  기준이 'Recipe 1' 인지 '가장 작은 픽셀' 인지는 미확인(그 Slot 에서는 둘 다 x20) — 바뀌면 여기만 고친다. */
function sizePix(s){const G=s&&(s.geo||s.cg);if(G&&G._sp)return G._sp;
  if(G&&G.rpix&&G.rpix.size){const r=Math.min(...G.rpix.keys());return G._sp={pix:G.rpix.get(r),r,name:G.rname&&G.rname.get(r)||'',from:''}}
  if(G&&G.fpix&&G.tfs){const ks=[...G.fpix.keys(),...G.tfs.keys()].filter(k=>k!=null);if(ks.length){const r=Math.min(...ks),p=geoPix(G,r);if(p>0.05&&p<20)return {pix:p,r,name:'',from:'RecipesInfo.ini 없음 → 사진 픽셀'}}}
  return {pix:PIX,r:null,name:'',from:'기본값'}}
const pixTxt=p=>`${+p.pix.toFixed(6)} µm (Slot 기준${p.r!=null?` · Recipe ${p.r}${p.name?' '+p.name:''}`:''}${p.from?' · '+p.from:''})`;
const um4=v=>v==null||v!==v?'-':String(+(+v).toFixed(4));
const um2=s=>{const u=sizePix(s).pix;return u*u};
/** 목록 위 한 줄(소유자 "µm 환산 픽셀 : 계수 이렇게만"): 계수가 하나면 그 값, Slot 마다 다르면 '값 (Slot n개)'. */
function pixLine(scans){const m=new Map();for(const s of new Set(scans)){if(!s)continue;const v=+sizePix(s).pix.toFixed(6);m.set(v,(m.get(v)||0)+1)}
  return m.size?'µm 환산 픽셀 : '+(m.size===1?String([...m.keys()][0]):[...m].map(([v,n])=>`${v} (Slot ${n}개)`).join(' · ')):''}
function pixLineSet(el,scans){if(!el)return;const t=pixLine(scans);el.textContent=t;el.hidden=!t}
/** Defect 박스 · GL 의 Box(Slot 기준 픽셀) → 그 Defect 를 찍은 Gray 사진 픽셀 배율(= µm 환산 픽셀 ÷ 찍은 레시피 픽셀). 종전 = 1(x5 Defect 가 4배 크게 그려짐). */
function boxK(d){const s=d&&d.scan,G=s&&(s.geo||s.cg);if(!G)return 1;const a=sizePix(s).pix,b=geoPix(G,d.recipe);return a>0&&b>0?a/b:1}
/** v14.4.1 [µm 로 보기](소유자 "목록 필터 width, area 는 체크박스로 µm 단위로 볼지 말지"): 켜면 목록 · 필터 · 정렬의 Area · Width = µm² · µm(값 × µm 환산 픽셀), 끄면 장비 값 그대로.
 *  한 곳을 바꾸면 모든 화면이 같이(기본 · 대규모 탭도 — storage 알림, 이 PC 에 기억 cw.um, 처음 = 켬). Length · Box 는 늘 장비 값. 리뷰PC 정보 · 사진 정보 칸은 늘 둘 다. */
const UM={on:true};try{UM.on=localStorage.getItem('cw.um')!=='0'}catch(e){}
const umK=s=>{const u=UM.on?sizePix(s).pix:1;return [u*u,u]};   // [Area 배율, Width 배율]
const umCells=(s,C,i)=>{const [a,w]=umK(s);return [fv(C.area[i]*a),fv(C.w[i]*w)]};
const fltUnit=k=>UM.on?(k==='a'?'µm²':'µm'):'';
const umCkHtml=()=>`<label class="umck" title="켜면 Area · Width 를 µm² · µm(장비 값 × µm 환산 픽셀)로 보고 거릅니다. 끄면 장비 값 그대로. 모든 목록이 같이 바뀝니다(Length · Box 는 늘 장비 값)"><input type="checkbox" data-um${UM.on?' checked':''}> µm 로 보기</label>`;
function umScans(){return [...(S.scans||[]),...(BIG.scans||[])]}
/** 열 제목(Step 2 쌍별 상세 표 · 5-1 · 5-3 목록). */
function umHeads(){document.querySelectorAll('[data-umh]').forEach(x=>x.textContent=x.dataset.umh==='a'?(UM.on?'Area (µm²)':'Area'):(UM.on?'Width (µm)':'Width'));
  for(const V of [VA,VC,...Object.values(PANELS).map(P=>P.V)])if(V)for(const c of V.cols)if(c[4])c[0]=c[4]==='a'?(UM.on?'Area (µm²)':'Area'):(UM.on?'Width (µm)':'Width')}
function umRefresh(){umHeads();if(S.cmp)renderTable();Object.values(PANELS).forEach(P=>{if(P.raw)applyPanel(P,true)});if(BIG.view)bigRefresh();if(VC.n)vtSet(VC,VC.n,true)}
/** 체크를 바꿀 때 필터 칸의 Area · Width 숫자: 계수가 하나면 새 단위로 바꿔 적고, Slot 마다 다르면 그대로 두고 알린다. */
function umSet(on,quiet){on=!!on;   // quiet = 다른 탭(기본 ↔ 대규모)에서 바꾼 것 — 알림 창 없이
  if(on===UM.on)return;const ks=new Set(umScans().map(s=>+sizePix(s).pix.toPrecision(12)));let filled=false;
  UM.on=on;try{localStorage.setItem('cw.um',on?'1':'0')}catch(e){}
  document.querySelectorAll('input[data-um]').forEach(x=>x.checked=on);document.querySelectorAll('[data-umu]').forEach(x=>x.textContent=fltUnit(x.dataset.umu));
  for(const b of document.querySelectorAll('.pflt,#bigFlt'))for(const k of ['a0','a1','w0','w1']){const el=b.querySelector(`[data-f="${k}"]`),t=el?el.value.trim():'';if(!t||!isFinite(+t))continue;filled=true;
    if(ks.size===1){const u=[...ks][0],f=k[0]==='a'?u*u:u;   // 사람이 적은 숫자로 되돌아가면 그 글 그대로(4.2 → 10.88… → 4.2)
      if(el.dataset.umo!=null&&el.dataset.umOn===(on?'1':'0')&&el.dataset.umTo===t)el.value=el.dataset.umo;
      else{const v=String(+(on?+t*f:+t/f).toPrecision(12));Object.assign(el.dataset,{umo:t,umOn:on?'0':'1',umTo:v});el.value=v}}}
  umRefresh();if(filled&&ks.size>1&&!quiet)alert(`Slot 마다 µm 환산 픽셀이 달라 Area · Width 필터 숫자는 그대로 두었습니다. 이제 이 숫자는 ${on?'µm² · µm':'장비 값'} 입니다.`)}
document.addEventListener('change',e=>{if(e.target&&e.target.matches&&e.target.matches('input[data-um]'))umSet(e.target.checked)},true);
window.addEventListener('storage',e=>{if(e.key==='cw.um')umSet(e.newValue!=='0',true)});
const geoFirst=m=>m&&m.size?m.values().next().value:null;
/** 레시피 r 의 프레임 크기 {W, H} · Gray 픽셀 크기(µm). */
function geoSize(G,r){return tfSize(cgTfFor(G.tfs,r))||G.fsize.get(r)||G.fsize.get(null)||geoFirst(G.fsize)||{W:GEO_W,H:GEO_H}}
function geoPix(G,r){const p=G?tfPix(cgTfFor(G.tfs,r)):null;return p>0.05&&p<20?p:G&&(G.fpix.get(r)||G.rpix.get(r)||geoFirst(G.fpix)||geoFirst(G.rpix))||GEO_PIX}
/** 좌표 (x, y) · 레시피 r → 프레임 고르기. {frame, px, py, n(후보 수), W, H, model} 또는 null. */
function geoChoose(G,x,y,r){const t=cgTfFor(G.tfs,r);if(!t||t.err||!G.frames.length)return null;const {W,H}=geoSize(G,r),[[a,b],[c,d]]=t.inv,[ox,oy]=t.off;let best=null,n=0;
  for(const f of cgPool(G.frames,r,G.pmemo||(G.pmemo=new Map()))){const tx=x-f.x-ox,ty=y-f.y-oy,px=a*tx+b*ty,py=c*tx+d*ty;
    if(px>=0&&px<W&&py>=0&&py<H){n++;const m=Math.min(px,W-px,py,H-py);if(!best||m>best.m)best={m,f,px,py}}}
  return best?{frame:best.f,px:best.px,py:best.py,n,W,H,model:t.model||'transform'}:null}
/** colorgray.frames_rect: 프레임 네 모서리를 변환 정방향으로 chuck 좌표에 놓은 직사각형 [x0, y0, x1, y1](좌표 기준 고르기용). */
function geoRect(G){let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
  for(const f of G.frames){const r=f.recipe!=null?f.recipe:1,t=cgTfFor(G.tfs,r);if(!t||t.err)continue;const [[a,b],[c,d]]=t.inv,det=a*d-b*c;if(!det)continue;
    const m=[[d/det,-b/det],[-c/det,a/det]],{W,H}=geoSize(G,r);
    for(const [px,py] of [[0,0],[W,0],[0,H],[W,H]]){const x=f.x+t.off[0]+m[0][0]*px+m[0][1]*py,y=f.y+t.off[1]+m[1][0]*px+m[1][1]*py;
      x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y)}}
  return x0<=x1?[x0,y0,x1,y1]:null}
/** 표본 pts([[x, y, recipe]]) 중 좌표 기준 mode 로 프레임을 찾은 수. */
function geoCount(G,pts,mode){let k=0;for(const [x,y,r] of pts){const [X,Y]=cgMap(mode,x,y,G.rect);if(geoChoose(G,X,Y,r))k++}return k}
/** 좌표 기준(CG.MODES) 고르기: '그대로'로 다 맞으면 끝, 아니면 가장 많이 맞는 것(동점 = 앞). Defect 좌표 표본으로(두 모드 같음). */
function geoPlan(G,pts){G.rect=geoRect(G);G.mode=0;G.ptsN=pts.length;G.planHits=0;if(!pts.length||!G.frames.length)return 0;
  let hits=geoCount(G,pts,0);if(G.rect&&hits<pts.length)for(let m=1;m<CG.MODES.length;m++){const k=geoCount(G,pts,m);if(k>hits){G.mode=m;hits=k}}
  G.planHits=hits;return hits}
/** 좌표 기준 · 장비 기록 확인용 Defect 표본(많으면 고르게 600개). */
function geoPtsCols(C){const n=C.n,st=Math.max(1,Math.ceil(n/600)),out=[];for(let i=0;i<n;i+=st)if(Number.isFinite(C.x[i])&&Number.isFinite(C.y[i]))out.push([C.x[i],C.y[i],C.rec[i]]);return out}
function geoPtsDefs(D){const n=D.length,st=Math.max(1,Math.ceil(n/600)),out=[];for(let i=0;i<n;i+=st){const d=D[i],x=d.X??d.x,y=d.Y??d.y;if(Number.isFinite(x)&&Number.isFinite(y))out.push([x,y,d.recipe])}return out}
/** 장비 프레임 기록(frameIdx · xInFrame · yInFrame)이 하나라도 있나. */
function geoHasRecCols(C){if(!C.fi)return false;for(let i=0;i<C.n;i++)if(C.fi[i]||C.xf[i]||C.yf[i])return true;return false}
const geoHasRecDefs=D=>D.some(d=>d.frameIdx||d.xInFrame||d.yInFrame);
/** 장비 기록 → {frame, px, py, ...}: s_FrameData 의 같은 레시피 · frameIdx 레코드(두 번 찍힌 프레임이면 그 픽셀이 Defect 좌표와 맞는 것, 5 µm 안) → 그 프레임의 Gray 사진. 못 찾으면 null(계산으로). */
function geoRecHit(G,x,y,r,fi,xf,yf){const R=G.fd;if(!R||!R.fi)return null;const t=cgTfFor(G.tfs,r);if(!t||t.err)return null;
  const {W,H}=geoSize(G,r),[[a,b],[c,d]]=t.inv,det=a*d-b*c;if(!det)return null;
  if(!R.byFi){R.byFi=new Map();for(let i=0;i<R.n;i++){const k=R.rc[i]+'|'+R.fi[i];(R.byFi.get(k)||R.byFi.set(k,[]).get(k)).push(i)}}
  const dx=xf-W/2,dy=yf-H/2,ex=(d*dx-b*dy)/det,ey=(-c*dx+a*dy)/det;let best=-1,bd=GEO_REC_TOL;
  for(const i of R.byFi.get(r+'|'+fi)||[]){const dd=Math.hypot(R.wx[i]+ex-x,R.wy[i]+ey-y);if(dd<bd){bd=dd;best=i}}
  if(best<0)return null;const fr=geoFrameOf(G,best);
  return fr?{frame:fr,px:xf,py:yf,n:1,W,H,model:'record',dd:bd}:null}
/** s_FrameData 레코드 i 의 Gray 사진: 프레임 목록에서 같은 자리(3 µm 안) → Gray 사진 이름의 Table 좌표(5 µm 안). */
function geoFrameOf(G,i){const R=G.fd,wx=R.wx[i],wy=R.wy[i],r=R.rc[i]>=0?R.rc[i]:null;let best=null,bd=3;
  for(const f of G.frames){if(f.recipe!=null&&r!=null&&f.recipe!==r)continue;const dd=Math.hypot(f.x-wx,f.y-wy);if(dd<bd){bd=dd;best=f}}
  if(best)return best;let b=null;bd=5;
  for(const g of G.gn&&!G.gn.err?G.gn:[]){if(g.recipe!=null&&r!=null&&g.recipe!==r)continue;const dd=Math.hypot(g.tx-R.tx[i],g.ty-R.ty[i]);if(dd<=bd){bd=dd;b=g}}
  return b?{file:b.file,x:wx,y:wy,recipe:b.recipe}:null}
/** Defect 하나의 Gray 위치(두 모드 공통): 장비 기록이 있으면 그것 → 없으면 좌표 기준을 적용한 Defect 좌표로 계산. 없으면 null(이유 = geoWhy). */
function geoHit(G,x,y,r,fi,xf,yf){if(!G||!G.frames||!G.frames.length)return null;
  if((fi||xf||yf)&&G.fd){const h=geoRecHit(G,x,y,r,fi,xf,yf);if(h)return h}
  const [X,Y]=cgMap(G.mode,x,y,G.rect);return geoChoose(G,X,Y,r)}
const geoWhy=G=>!G?'Gray 위치 자료를 읽지 않음':G.noGray?`Gray 없음 — ${G.noGray}`:!G.frames.length?'Gray 프레임 목록 없음':'매칭되는 Gray 프레임 없음(프레임 밖)';
/** 화면 · CSV 글: 계산 방법. */
const geoModel=h=>!h?'':h.model==='record'?'장비 기록(frameIdx · xInFrame)':h.model==='center'?'가운데 모델(변환 파일 없음)':'frameToChuckPlane';
/** Step 1 파일 목록(이름 → File) → 매칭 폴더 모양(geoLoad 가 읽는 get · names). */
function dirFromFiles(base,files){const m=new Map();for(const [k,f] of files)m.set(k,{name:f.name,path:base+'/'+f.name,file:async()=>f&&f.getFile?f.getFile():f});
  const get=async n=>m.get(lower(n))||null;return {path:base,get,peek:get,opt:get,listed:()=>true,names:async()=>m,subs:async()=>[],errs:()=>[]}}
/** Color 연결(rev2, 소유자 확정 2026-11-10: "Contrast 가 있는 Defect 는 좌표가 있고 Color 이미지 정보는 어떤 경우에도 있다 · 사진은 모두 Slot 폴더 안").
 *  스캔마다 colorModel 로 한 번 기준을 정한다 → Defect 마다
 *   ① 좌표: Color FaultX/FaultY 와 Defect 좌표(x/y 또는 ActualX/ActualY 중 더 잘 맞는 쪽 + 스캔 전체에서 일정한 어긋남을 보정)가 허용오차 안
 *   ② 번호: Color Index = Defect 번호 규칙(기록 순서 · id · resultID 중 Defect 마다 값이 다른 1:1 규칙만, 좌표가 있으면 보정 좌표와 맞는 수가 가장 많은 규칙)
 *   ③ 가장 가까운 Color 중 Defect 위치가 그 Color 사진 범위(ImageSize × PixelSize) 안에 드는 것('확인 필요')
 *  종전: ①은 보정 없이 5 µm, ②는 좌표가 50 µm 넘게 다르면 버리고, id 가 전부 1 이어도 'id' 규칙을 먼저 골라 —
 *  Color 좌표가 Defect 좌표와 일정하게 어긋난 자료에서 Gray 는 찾는데 Color 는 전부 못 찾았다(실제 결과 폴더를 100 µm 밀어 재현). */
const INDEX_RULES=[['id',d=>d.id],['id−1',d=>d.id-1],['id+1',d=>d.id+1],['resultID',d=>d.resultID],['resultID−1',d=>d.resultID-1],['resultID+1',d=>d.resultID+1],['기록 순서(0)',d=>d.i],['기록 순서(1)',d=>d.i+1]];
/** 가장 가까운 점 찾기(격자). 점이 묶음 밖 멀리 있으면 전부 훑는다. */
function makeCGrid(cs){let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;for(const c of cs){x0=Math.min(x0,c.x);x1=Math.max(x1,c.x);y0=Math.min(y0,c.y);y1=Math.max(y1,c.y)}
  const G=Math.max(20,Math.sqrt(Math.max(1,(x1-x0)*(y1-y0))/cs.length)*1.5),m=new Map(),K=(i,j)=>i+','+j;
  for(const c of cs){const k=K(Math.floor(c.x/G),Math.floor(c.y/G));(m.get(k)||m.set(k,[]).get(k)).push(c)}
  const brute=(x,y)=>{let b=null,bd=Infinity;for(const c of cs){const d=Math.hypot(c.x-x,c.y-y);if(d<bd){bd=d;b=c}}return b?{c:b,dd:bd}:null};
  return {nearest(x,y){if(!isFinite(x)||!isFinite(y))return null;if(x<x0-4*G||x>x1+4*G||y<y0-4*G||y>y1+4*G)return brute(x,y);
    const ci=Math.floor(x/G),cj=Math.floor(y/G),R=Math.ceil(Math.max(x1-x0,y1-y0)/G)+6;let b=null,bd=Infinity;
    const cell=(i,j)=>{const l=m.get(K(i,j));if(l)for(const c of l){const d=Math.hypot(c.x-x,c.y-y);if(d<bd){bd=d;b=c}}};
    for(let r=0;r<=R;r++){if(b&&(r-1)*G>bd)break;if(!r){cell(ci,cj);continue}
      for(let i=ci-r;i<=ci+r;i++){cell(i,cj-r);cell(i,cj+r)}for(let j=cj-r+1;j<=cj+r-1;j++){cell(ci-r,j);cell(ci+r,j)}}
    return b?{c:b,dd:bd}:null}}}
const median=a=>{if(!a.length)return 0;const s=[...a].sort((p,q)=>p-q),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2};
/** 스캔마다 Color 연결 기준: 좌표 기준(x/y 또는 ActualX/Y) · 일정한 어긋남(dx, dy = Color − Defect) · 번호 규칙. scan._cm 에 기억(Color 수 · 허용오차가 같을 때). */
function colorModel(scan,ctol){
  const key=ctol+'|'+scan.colors.length;if(scan._cm&&scan._cm.key===key)return scan._cm;
  const tol=Math.max(ctol,1),C=scan.cols;
  const defs=scan.defects?scan.defects.map(d=>({i:d.i,id:d.id,resultID:d.resultID,x:d.x??d.X,y:d.y??d.Y,ax:d.ActualX??d.x??d.X,ay:d.ActualY??d.y??d.Y}))
    :Array.from({length:C.n},(_,i)=>({i,id:C.id[i],resultID:C.rid[i],x:C.x[i],y:C.y[i],ax:C.ax[i],ay:C.ay[i]}));
  const n=defs.length,cs=scan.colors.filter(c=>c.x!=null&&c.y!=null&&isFinite(c.x)&&isFinite(c.y)),grid=cs.length?makeCGrid(cs):null;
  const P=(d,b)=>b==='act'?[d.ax,d.ay]:[d.x,d.y],bases=['xy'];if(defs.some(d=>Math.abs(d.ax-d.x)>1e-6||Math.abs(d.ay-d.y)>1e-6))bases.push('act');
  const count=(b,dx,dy)=>{if(!grid)return 0;let k=0;for(const d of defs){const [x,y]=P(d,b),r=grid.nearest(x+dx,y+dy);if(r&&r.dd<=tol)k++}return k};
  const M={key,basis:'xy',dx:0,dy:0,kind:'coord',direct:0,grid,n,colors:scan.colors.length,named:scan.colors.some(c=>c.fromName)};
  for(const b of bases){const k=count(b,0,0);if(k>M.direct){M.basis=b;M.direct=k}}
  // 번호 규칙 후보: Defect 마다 값이 다르고(1:1) 절반 넘게 Color Index 가 있는 규칙만(예: id 가 전부 1 이면 'id' 는 빠짐)
  const all=[];if(scan.colorByIndex.size)for(const [name,f] of INDEX_RULES){const vals=defs.map(f);if(new Set(vals).size<n)continue;
    const mapped=defs.filter(d=>scan.colorByIndex.has(f(d)));if(mapped.length)all.push({name,f,mapped})}
  const rules=all.filter(r=>r.mapped.length>=Math.max(1,n*.5));   // 어긋남 추정 · 좌표 없는 Color 에는 절반 넘게 이어지는 규칙만
  // 좌표로 절반도 안 맞으면: 일정한 어긋남 찾기 — ⓐ 번호 규칙 짝의 어긋남이 고르면 그것 ⓑ 없으면 좌표 차이 투표
  if(grid&&M.direct<n*.5){let best=null;
    for(const r of rules)for(const b of bases){const offs=[];for(const d of r.mapped){const c=scan.colorByIndex.get(r.f(d));if(c.x==null||c.y==null)continue;const [x,y]=P(d,b);offs.push([c.x-x,c.y-y])}
      if(offs.length<2)continue;const med=[median(offs.map(o=>o[0])),median(offs.map(o=>o[1]))],ok=offs.filter(o=>Math.hypot(o[0]-med[0],o[1]-med[1])<=Math.max(tol,2)).length;
      if(ok>=Math.max(2,offs.length*.8)&&(!best||ok>best.ok))best={b,med,ok}}
    if(!best){const step=Math.max(1,Math.floor(n/200)),cstep=Math.max(1,Math.floor(cs.length/4000)),Bin=Math.max(tol,2)*2,votes=new Map();let ns=0;
      for(const b of bases)for(let i=0;i<n;i+=step){ns++;const [x,y]=P(defs[i],b);for(let j=0;j<cs.length;j+=cstep){const ox=cs[j].x-x,oy=cs[j].y-y,k=b+'|'+Math.round(ox/Bin)+','+Math.round(oy/Bin);let v=votes.get(k);if(!v)votes.set(k,v={b,n:0,ox:[],oy:[]});v.n++;if(v.ox.length<500){v.ox.push(ox);v.oy.push(oy)}}}
      let top=null;for(const v of votes.values())if(!top||v.n>top.n)top=v;
      if(top&&top.n>=Math.max(3,ns/bases.length*.3))best={b:top.b,med:[median(top.ox),median(top.oy)],ok:top.n}}
    if(best){const k=count(best.b,best.med[0],best.med[1]);if(k>M.direct)Object.assign(M,{basis:best.b,dx:best.med[0],dy:best.med[1],kind:'offset',direct:k})}}
  // 번호 규칙 고르기: (보정한) 좌표와 맞는 수가 가장 많은 규칙. Color 에 좌표가 하나도 없으면 맞는 Index 수(같으면 '기록 순서' 먼저 — 실제 결과 폴더는 Index = Surface.flt 기록 순서)
  let rule=null;
  for(const r of grid?all:rules){let sc=0;if(grid){for(const d of r.mapped){const c=scan.colorByIndex.get(r.f(d));if(c.x==null||c.y==null)continue;const [x,y]=P(d,M.basis);if(Math.hypot(c.x-x-M.dx,c.y-y-M.dy)<=Math.max(tol,2))sc++}}
    else sc=r.mapped.length+(r.name.startsWith('기록')?.5:0);if(sc>0&&(!rule||sc>rule.sc))rule={...r,sc}}   // 같으면 앞 규칙(종전과 같음)
  M.rule=rule;scan._cm=M;
  scan.colorNote=`Color ${scan.colors.length}개${M.named?'(사진 이름의 좌표)':''} · 좌표 ${M.basis==='act'?'ActualX/Y':'x/y'}${M.kind==='offset'?` · 일정한 어긋남 ${Math.round(M.dx)}, ${Math.round(M.dy)} µm 보정`:''} · 좌표로 맞음 ${M.direct}/${n}${rule?` · 번호 규칙 ${rule.name}`:''}`;
  return M}
/** Color 사진 범위(µm, 반 폭 · 반 높이) — ImageSize × PixelSize, 없으면 실제 폴더 값(1380×1036 × 0.462 µm). */
const cHalf=c=>[(c.w||1380)*(c.psx||0.4624)/2,(c.h||1036)*(c.psy||0.4622)/2];
function linkColor(d,scan,ctol){
  const cs=scan.colors;if(!cs.length)return null;const M=colorModel(scan,ctol),tol=Math.max(ctol,1);
  const bx=M.basis==='act'?(d.ActualX??d.X):(d.x??d.X),by=M.basis==='act'?(d.ActualY??d.Y):(d.y??d.Y),X=bx+M.dx,Y=by+M.dy;
  const sh=(M.kind==='offset'?` · 어긋남 ${Math.round(M.dx)}, ${Math.round(M.dy)} µm 보정`:'')+(M.basis==='act'?' · ActualX/Y':'')+(M.named?' · 사진 이름의 좌표':'');
  const nb=M.grid?M.grid.nearest(X,Y):null;
  if(nb&&nb.dd<=tol)return {c:nb.c,how:`좌표(${nb.dd.toFixed(1)} µm${sh})`,dd:nb.dd};
  if(M.rule){const k=M.rule.f(d),c=scan.colorByIndex.get(k);if(c){const dd=c.x!=null&&c.y!=null?Math.hypot(c.x-X,c.y-Y):null;
    return {c,how:`Index ${k} (${M.rule.name}${dd!=null?` · 좌표 차 ${dd.toFixed(1)} µm`:' · 좌표 없음'}${sh})`,dd}}}
  if(nb){const [hw,hh]=cHalf(nb.c);if(Math.abs(nb.c.x-X)<=hw&&Math.abs(nb.c.y-Y)<=hh)return {c:nb.c,how:`가장 가까운 Color(${nb.dd.toFixed(1)} µm, 사진 범위 안 · 확인 필요${sh})`,dd:nb.dd,far:true}}
  return null}
/** Color 를 못 붙인 이유(화면 · CSV). */
function colorWhy(d,scan,ctol){if(!scan.colors.length)return 'ColorImageGrabingInfo.ini 도, Slot 폴더의 Color 사진 이름(X.Y.c.….jpeg)도 없음';
  const M=colorModel(scan,ctol),bx=M.basis==='act'?(d.ActualX??d.X):(d.x??d.X),by=M.basis==='act'?(d.ActualY??d.Y):(d.y??d.Y),nb=M.grid?M.grid.nearest(bx+M.dx,by+M.dy):null;
  return nb?`가장 가까운 Color ${cleanName(nb.c.file)} 도 ${nb.dd.toFixed(0)} µm 떨어져 사진 범위 밖 (${scan.colorNote})`:`Color 항목 ${scan.colors.length}개에 좌표 · 맞는 번호가 없음`}

// ════════════════════════════════════════════════════════════════════════
// 4. 상태
// ════════════════════════════════════════════════════════════════════════
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f1=v=>v==null||!isFinite(v)?'':(+v).toFixed(1),f2=v=>v==null||!isFinite(v)?'':(+v).toFixed(2);
/** 실제 값(#83) — Contrast · Area · Width · Length 를 반올림하지 않고 그대로 쓴다. 계산 잡음(1.2300000000000002)만 12 유효숫자로 없앤다. */
const exv=v=>+(+v).toPrecision(12),fv=v=>v==null||v===''||!isFinite(v)?'':String(exv(v));
const S={scans:[],rows:[],page:0,rv:0,rvList:[],overlay:{},pairs:[],pi:0};let scanSeq=0;
/** rev5(소유자 "사용자가 설정을 건들 일은 없어 아예 없애"): 결함 좌표 = x/y, Pixel Size 0.7708(Area µm² · Step 3 · 4 간단 모델), Color 연결 5 µm, 반전 · Offset 없음 — 종전 기본값. */
const PIX=0.7708,CTOL=5;
function opts(){return{tol:+$('#tol').value||0,pix:PIX,ctol:CTOL,coord:'xy',
  flipX:false,flipY:false,offX:0,offY:0,crop:Math.max(32,+$('#cropSz').value||160),ring:Math.max(1,+$('#ringW').value||6)}}
function sortedScans(){return [...S.scans].sort((a,b)=>(a.contrast??Infinity)-(b.contrast??Infinity)||a.seq-b.seq)}
const stepName=s=>s.step||s.name;

// ════════════════════════════════════════════════════════════════════════
// 5. 폴더 등록 — entries = [{path, file}] (path = 폴더 기준 상대 경로, '/' 구분)
// ════════════════════════════════════════════════════════════════════════
const baseName=p=>p.split(/[\\/]/).pop();
const lower=s=>s.toLowerCase();
// ── Para v14.1.8: 목록 검색 · ☑ 고르기(소유자 "모든 스텝 목록 위에 돋보기 검색 · 5-3 과 같이 ☑ · 전체 선택/해제 · 처음엔 모두 선택(옵션) · 필터로 고르면 목록이 자동으로 걸러짐") ──
//   검색 = 대소문자 무시, 띄어 쓴 여러 단어는 모두 들어 있어야(AND). Enter = 바로, 입력을 멈추면 0.3초 뒤(목록이 커도 계산은 한 번), Esc = 지움.
//   ☑ = 다음 단계 · CSV 로 가는 줄(5-1 → 5-2, 5-2 → 5-3). 필터 · 검색으로 안 보이는 줄은 ☑ 여도 가지 않고, 그 ☑/☐ 는 기억해 다시 보이면 그대로.
const LS={def:true,delay:300};try{LS.def=localStorage.getItem('cw.lsDef')!=='0'}catch(e){}
const qTerms=v=>lower(String(v||'')).split(/\s+/).filter(Boolean).slice(0,24);
const qAll=(T,txt)=>{for(const w of T)if(!txt.includes(w))return false;return true};
const LS_ICO='<svg class="ico" viewBox="0 0 16 16" aria-hidden="true"><circle cx="6.8" cy="6.8" r="4.6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10.3 10.3 14.2 14.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
const LS_DEF=()=>`<label class="lsdef" title="새로 만든 목록(Lot 등록 · 5-2 확인 · 비교)의 줄을 처음부터 ☑ 로 둡니다(이 PC 에 기억). 끄면 처음엔 ☐"><input type="checkbox" data-ls="def"${LS.def?' checked':''}> 처음엔 모두 ☑</label>`;
const lsHtml=(id,ph,pick,csv)=>`<div class="lsbar" id="${id}" role="search"><label class="lsq">${LS_ICO}<input type="search" placeholder="${esc(ph)}" aria-label="목록 검색"></label>`
  +(pick?`<span class="lspk"><span class="lsn" aria-live="polite">☑ 0 / 0개</span><button type="button" data-ls="all">전체 선택</button><button type="button" data-ls="none">전체 해제</button>${LS_DEF()}${csv?'<button type="button" data-ls="csv" disabled>CSV 저장</button>':''}</span>`:'')+'</div>';
document.addEventListener('change',e=>{const d=e.target;if(!d.matches||!d.matches('[data-ls="def"]'))return;LS.def=d.checked;try{localStorage.setItem('cw.lsDef',LS.def?'1':'0')}catch(x){}
  document.querySelectorAll('[data-ls="def"]').forEach(x=>x.checked=LS.def)});
/** 목록 위 줄 연결: o.onQ(단어 목록) · o.onAll(true|false). 돌려줌 .set(☑ 수, 보이는 수) = 개수 배지. */
function lsBind(id,o){const bar=document.getElementById(id),inp=bar.querySelector('input[type=search]'),q=bar.querySelector('.lsq');let tm=0,last='';
  const wait=()=>typeof o.delay==='function'?o.delay():LS.delay;   // 큰 목록(5-1 10만 줄 넘음)은 입력을 조금 더 기다림 — Enter 는 늘 바로
  const go=()=>{clearTimeout(tm);const v=inp.value.trim();q.classList.toggle('on',!!v);if(v===last)return;last=v;o.onQ(qTerms(v))};
  inp.addEventListener('keydown',e=>{if(e.key==='Enter'){go();e.preventDefault()}else if(e.key==='Escape'&&inp.value){inp.value='';go();e.preventDefault()}e.stopPropagation()});
  inp.addEventListener('input',()=>{clearTimeout(tm);tm=setTimeout(go,wait())});
  bar.addEventListener('click',e=>{const k=e.target.dataset&&e.target.dataset.ls;if((k==='all'||k==='none')&&o.onAll)o.onAll(k==='all');else if(k==='csv'&&o.onCsv)o.onCsv()});
  bar.querySelectorAll('[data-ls="def"]').forEach(x=>x.checked=LS.def);
  return {set(n,m){const b=bar.querySelector('.lsn');if(b){b.textContent=`☑ ${n.toLocaleString()} / ${m.toLocaleString()}개`;b.classList.toggle('on',n>0)}
    const c=bar.querySelector('[data-ls="csv"]');if(c){c.disabled=!n;c.textContent=n?`CSV 저장 (☑ ${n.toLocaleString()}개)`:'CSV 저장'}}}}
// ════════════════════════════════════════════════════════════════════════
// Para v14 프로그램 안(Defect 분석 탭)에서 열렸을 때 — 소유자 2026-11-15 "HTML 기능을 프로그램에 동일하게 · 초기 읽기 대폭 단축".
//   프로그램 엔진이 고른 폴더를 직접 읽어 준다(GET /api/fs/list · stat · file · walk, 읽기 전용 — 엔진에 쓰기 API 없음):
//   · 브라우저 '업로드'(폴더 전체 · 사진까지 목록 만들기, 50만 파일 ≈ 1시간)가 없다 — 5-1 은 종전 빠른 길(폴더 핸들)과 같이 필요한 폴더 · 파일만 그때그때.
//   · Windows Chromium(Edge · Chrome)이 폴더 핸들로 .ini 를 거부하는 규칙(파일 형식 정책 ini = DANGEROUS)과 무관(브라우저 핸들이 아니라 엔진).
//   · 전체 경로를 엔진이 알아 [원본 폴더 경로]를 적지 않아도 된다(pcPath).
//   파일 하나로 두 가지: file:// 로 열면 PARA = null → 종전 그대로. 프로그램이 http://127.0.0.1 에 ?t=토큰 으로 열면 PARA.
const PARA=(()=>{try{if(location.protocol!=='http:'||!/^(127\.0\.0\.1|localhost)$/.test(location.hostname))return null;
  const q=new URLSearchParams(location.search),t=q.get('t');if(!t)return null;
  const H={'X-Para-Token':t},E=encodeURIComponent,roots=new Map(),join=(a,b)=>a?a+'/'+b:b;
  const err=(st,what)=>new DOMException(`${what} (${st})`,st===404?'NotFoundError':st===403?'SecurityError':st===400?'TypeError':'NotReadableError');
  const api=async(path,what)=>{const r=await fetch(path,{headers:H,cache:'no-store'});if(!r.ok)throw err(r.status,what);return r};
  const url=(kind,R,rel)=>`/api/fs/${kind}?r=${E(R)}&p=${E(rel)}`;
  const fileH=(R,rel,name,size,mt)=>({kind:'file',name,size,lastModified:mt||0,path:rel,
    async getFile(){const b=await (await api(url('file',R,rel),rel)).blob();return new File([b],name,{lastModified:mt||0})}});
  const dirH=(R,rel,name)=>({kind:'directory',name,
    async *entries(){const j=await (await api(url('list',R,rel),rel||name)).json();for(const n of j.dirs)yield [n,dirH(R,join(rel,n),n)];for(const [n,sz,mt] of j.files)yield [n,fileH(R,join(rel,n),n,sz,mt)]},
    async getFileHandle(n){const s=await (await api(url('stat',R,join(rel,n)),n)).json();if(s.kind!=='file')throw new DOMException(n,'TypeMismatchError');return fileH(R,join(rel,n),s.name||n,s.size,s.mtime)}});
  // Step 1 ~ 4 의 파일(File 처럼 name · size · arrayBuffer · text · getFile) — 내용은 쓸 때만 엔진에서 읽는다(사진 내용은 보는 것만)
  const lazy=(R,rel,size,mt)=>{const name=rel.split('/').pop(),f=fileH(R,rel,name,size,mt);
    return {name,size,lastModified:mt||0,getFile:()=>f.getFile(),arrayBuffer:async()=>(await f.getFile()).arrayBuffer(),text:async()=>(await f.getFile()).text()}};
  return {mode:q.get('mode')||'',roots,
    /** 폴더 고르기 = 엔진이 Windows 고르기 창을 띄우고 그 폴더를 읽기 전용 뿌리로 등록. {id, name, path(전체 경로), handle} 또는 취소 null. */
    async pick(){const r=await fetch('/api/native',{method:'POST',headers:{...H,'Content-Type':'application/json'},body:JSON.stringify({command:'defect_pick',args:{}}),cache:'no-store'});
      if(!r.ok)throw err(r.status,'폴더 고르기');const R=(await r.json()).result;if(!R||!R.id)return null;roots.set(lower(R.name),R);return {...R,handle:dirH(R.id,'',R.name)}},
    /** Step 1 ~ 4: 고른 폴더 아래 파일 목록(이름 · 크기만, 엔진이 폴더마다 한 번 나열) → addEntries 항목. */
    async walk(R){const j=await (await api(`/api/fs/walk?r=${E(R.id)}`,R.name)).json();return {truncated:!!j.truncated,entries:j.files.map(([rel,sz,mt])=>({path:R.name+'/'+rel,file:lazy(R.id,rel,sz,mt)}))}}}}
  catch(e){return null}})();
/** 새 창 — 막히면(window.open = null, 소유자 v14 "Edge 앱 창에서 막히면 같은 창 전체 화면으로 대체 가능하게") 이 창 위에 전체 크기 칸(같은 출처 빈 문서)을 띄워
 *  같은 코드가 그 칸에 그린다(키 · 확대 · Space 그대로). [⛶ 전체 화면] · [✕ 닫기]. '같은 창에서 보기'를 켜 두면 처음부터 칸. */
const OVW=new Map();
const inWinPref=()=>{try{return localStorage.getItem('cw.inWin')==='1'}catch(e){return false}};
function winOpen(name,feats){let w=null;if(!inWinPref())try{w=window.open('',name,feats)}catch(e){w=null}return w||ovWin(name)}
function ovWin(name){let box=OVW.get(name);if(box&&name!=='_blank'&&box.isConnected){try{return box.querySelector('iframe').contentWindow}catch(e){}}
  if(box)box.remove();box=document.createElement('div');box.className='ovw';box.dataset.win=name;
  box.innerHTML='<div class="ovwb"><b>같은 창 보기</b><span>새 창 대신 이 창 안에 띄웠습니다(새 창이 막혔거나 \'같은 창에서 보기\'가 켜짐)</span><button type="button" data-fs>⛶ 전체 화면</button><button type="button" data-x>✕ 닫기</button></div><iframe title="같은 창 보기"></iframe>';
  document.body.append(box);OVW.set(name,box);
  box.querySelector('[data-x]').onclick=()=>{try{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{})}catch(e){}box.remove();OVW.delete(name)};
  box.querySelector('[data-fs]').onclick=()=>{try{if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else if(box.requestFullscreen)box.requestFullscreen().catch(()=>{})}catch(e){}};
  try{if(box.requestFullscreen)box.requestFullscreen().catch(()=>{})}catch(e){}   // 누른 직후라 전체 화면이 되면 좋고, 안 되면 창 크기 칸 그대로
  return box.querySelector('iframe').contentWindow}
/** Para #57: 폴더 인식 기준 = Lot 폴더 안 Wafer Slot 폴더(1~25개). Surface.flt 가 있는 폴더 = Slot, 그 바로 위 폴더 = Lot.
 *  Slot 폴더를 바로 고르면(위 폴더가 선택에 없음) 그 폴더 = Slot 1개짜리 Lot. Lot 1개 = 스캔 결과 1개(Step · Contrast AVG · 호기는 Lot 단위).
 *  Contrast AVG · Step 이름 = Lot 폴더 이름 → 그 위 폴더들 → Slot 폴더 이름 순으로 'CA27' 같은 이름을 찾는다. */
const CA_RE=/(?:contrast|avg|ca)[ _-]?(\d+(?:\.\d+)?)/i;
const natCmp=(a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true,sensitivity:'base'});
/** 로딩창(Para #59, Step 5 에서 확장). p = {title, done, total, unit, files, fileTotal, detail, indet, count, close, steps[], step, cancel(), reset}. null 이면 닫는다.
 *  아래 줄(#busyH)은 0.25초마다: 경과 · 마지막 진행(busy/throttle 이 마지막으로 불린 뒤) · 속도 · 남은 시간 · 화면 멈춤(타이머가 늦게 돈 만큼 = 브라우저가 계산하느라 멈춘 시간).
 *  '마지막 진행'이 3초를 넘으면 노란 글로 '응답 기다리는 중' — 렉인지 기다리는 중인지 사람이 알 수 있게. */
const BUSY={t0:0,last:0,tick:0,lag:0,lagAt:0,p:null,unlock:null,hidAt:0,away:0,awayAt:0};
function busy(p){const el=$('#busy');if(!el)return;const now=performance.now();if(!p){el.hidden=true;BUSY.p=null;bgUnlock();return}
  bgLock();
  if(el.hidden||p.reset){BUSY.t0=now;BUSY.lag=0;BUSY.tick=now}BUSY.last=now;BUSY.p=p;
  el.hidden=false;$('#busyT').textContent=p.title||'폴더 등록 중';
  const ind=!!p.indet||!p.total;$('#busyBar').classList.toggle('ind',ind);
  $('#busyN').textContent=ind?(p.count??'…'):`${p.done} / ${p.total} ${p.unit||''}`.trim();
  $('#busyBar').firstElementChild.style.width=ind?'':`${Math.round(100*p.done/p.total)}%`;
  $('#busyF').textContent=p.fileTotal?`파일 ${p.files} / ${p.fileTotal}개 (${Math.round(100*p.files/p.fileTotal)}%)`:(p.files||'');
  $('#busyD').textContent=p.detail||'';$('#busyX').hidden=!p.close;
  const S_=$('#busyS');S_.hidden=!p.steps;if(p.steps)S_.innerHTML=p.steps.map((t,i)=>`<li class="${i<p.step?'ok':i===p.step?'on':''}">${i<p.step?'✔':i===p.step?'▶':'·'} ${esc(t)}</li>`).join('');
  const c=$('#busyC');if(!p.cancel){c.hidden=true}else if(c.hidden){c.hidden=false;c.disabled=false;c.textContent='중지'}
  beat(now)}
const fmtSec=v=>v<60?`${v.toFixed(1)}초`:`${Math.floor(v/60)}분 ${Math.round(v%60)}초`;
function beat(now){const p=BUSY.p;if(!p)return;const el=$('#busyH'),t=(now-BUSY.t0)/1000,gap=(now-BUSY.last)/1000;
  let s=`경과 ${fmtSec(t)} · 마지막 진행 ${gap.toFixed(1)}초 전`;
  if(p.total&&p.done>0&&p.done<p.total&&t>1){const r=p.done/t;s+=` · ${r>=10?Math.round(r):r.toFixed(1)} ${p.unit||'개'}/초 · 남은 시간 약 ${fmtSec((p.total-p.done)/r)}`}
  const warn=gap>3;if(warn)s+=' — ⏳ 응답을 기다리는 중입니다(네트워크 드라이브 · 큰 파일). 이 숫자가 계속 커지기만 하면 [중지]를 누르십시오';
  if(BUSY.lag>700&&now-BUSY.lagAt<8000)s+=` · 화면이 ${(BUSY.lag/1000).toFixed(1)}초 멈췄었음(브라우저 계산)`;
  if(BUSY.away&&now-BUSY.awayAt<10000)s+=` · 다른 창에 있던 ${fmtSec(BUSY.away/1000)} 동안에도 계속 읽었습니다`;
  el.textContent=s;el.classList.toggle('warn',warn)}
setInterval(()=>{const now=performance.now();if(!BUSY.p||document.hidden){BUSY.tick=now;return}const lag=now-BUSY.tick-250;BUSY.tick=now;if(lag>700){BUSY.lag=lag;BUSY.lagAt=now}beat(now)},250);
$('#busyC').onclick=()=>{const p=BUSY.p;if(p&&p.cancel){p.cancel();$('#busyC').disabled=true;$('#busyC').textContent='중지하는 중… (지금 읽는 파일까지 끝내고 멈춤)'}};
// ── 다른 창 · 다른 작업 중에도 계속 불러오기(소유자 2026-11-13 "다른 창에 갔다 오면 끊기는 경우 — 계속 이어서 불러오게") ──────────────
//   원인: 불러오기는 Slot 마다 nextPaint(종전 setTimeout 0)로 한 번 쉰다. 탭이 숨으면 Chrome 이 이어지는 setTimeout 을 1초마다(5분 넘게 숨으면 1분마다)로 늦춘다
//   → Slot 하나에 1초 ~ 1분, 사실상 멈춤(돌아오면 다시 빨라짐). 오래 숨은 탭은 절전 · 메모리 절약으로 얼리거나 버릴 수도 있다.
//   고침: ① 숨은 동안은 MessageChannel 로 쉰다(타이머가 아니라 늦춰지지 않음). 쉬는 중에 숨어도 바로 MessageChannel 로 넘어간다.
//         ② 불러오는 동안(busy 창이 떠 있는 동안) Web Lock 을 잡는다 — Chrome 은 Web Lock 을 잡은 탭을 얼리거나 버리지 않으려 한다(최선, 보장 아님).
//         ③ 불러오는 동안 창 닫기 · 새로 고침은 브라우저 확인 창을 띄운다. ④ Slot 읽기가 일시 오류(DOMException: NotReadableError 등 — 네트워크 드라이브 다시 연결 중)면
//            1초 · 3초 뒤 두 번 더 읽는다(retryRead). '없음'(NotFoundError) · 막힘(#66 TypeError)은 다시 읽지 않는다.
const yieldMC=(()=>{let ch=null;const q=[];return ()=>new Promise(r=>{if(!ch){ch=new MessageChannel();ch.port1.onmessage=()=>{const f=q.shift();if(f)f()}}q.push(r);ch.port2.postMessage(0)})})();
const nextPaint=()=>document.hidden?yieldMC():new Promise(r=>{let done=false;const go=()=>{if(done)return;done=true;document.removeEventListener('visibilitychange',vis);r()},
  vis=()=>{if(document.hidden)yieldMC().then(go)};document.addEventListener('visibilitychange',vis);setTimeout(go,0)});
const waitMs=ms=>new Promise(r=>setTimeout(r,ms));
const transientErr=e=>!!e&&typeof DOMException!=='undefined'&&e instanceof DOMException&&!/^(NotFoundError|TypeMismatchError|SecurityError|NotAllowedError|AbortError)$/.test(e.name);
async function retryRead(fn,tries=3){for(let k=1;;k++){try{return await fn()}catch(e){if(k>=tries||!transientErr(e))throw e;BUSY.last=performance.now();await waitMs(k===1?1000:3000)}}}
function bgLock(){if(BUSY.unlock||!(navigator.locks&&navigator.locks.request))return;let rel;const held=new Promise(r=>rel=r);BUSY.unlock=rel;
  navigator.locks.request('aoi-contrast-wizard-loading',()=>held).catch(()=>{})}
function bgUnlock(){const f=BUSY.unlock;BUSY.unlock=null;if(f)f()}
document.addEventListener('visibilitychange',()=>{const now=performance.now();if(document.hidden){BUSY.hidAt=now;return}
  BUSY.tick=now;if(BUSY.p&&BUSY.hidAt&&now-BUSY.hidAt>2000){BUSY.away=now-BUSY.hidAt;BUSY.awayAt=now;beat(now)}BUSY.hidAt=0});
addEventListener('beforeunload',e=>{if(BUSY.p){e.preventDefault();e.returnValue=''}});
/** 폴더 인식(소유자 확정 2026-11-10: 레시피 폴더 / Setup 폴더 / Lot 폴더 / Slot 폴더(최대 25개)). entries = [{path}] (첫 마디 = 고른 폴더, '/' 구분).
 *  Slot = Surface.flt 가 있는 폴더(이름 = 그 폴더 이름), Lot = 그 바로 위 폴더 — 레시피 · Setup · Lot · Slot 어느 폴더를 골라도 같은 Lot 으로 묶인다.
 *   · 고른 폴더/Surface.flt → 고른 폴더 = Slot 1개짜리 Lot(Slot 폴더를 바로 고름)
 *   · 고른 폴더/X/Surface.flt → 고른 폴더 = Lot, X = Slot. 단 X 이름마다 다른 'CA27' 이 있고 고른 폴더 이름에는 없으면 X = Lot(Slot 1개)
 *  파일 주인 = 가장 가까운 위쪽 Slot 폴더. Slot 밖 위쪽 폴더(Lot · Setup · 레시피)에 있는 파일(ProductInfo · Wafer Map 등, 사진 제외)은 그 아래 Slot 들이 같이 쓴다(Slot 에 같은 이름이 있으면 Slot 것). */
function planUnits(entries){
  const dirOf=p=>p.slice(0,p.length-baseName(p).length),segs=d=>d.split('/').filter(Boolean);
  const fd=[...new Set(entries.filter(e=>lower(baseName(e.path))==='surface.flt').map(e=>dirOf(e.path)))];
  const bySel=new Map();for(const d of fd){const k=segs(d)[0]||'';(bySel.get(k)||bySel.set(k,[]).get(k)).push(d)}
  const units=[],U=new Map();
  for(const [sel,ds] of bySel){
    const d2=ds.filter(d=>segs(d).length===2),cas=new Set(d2.map(d=>{const m=CA_RE.exec(segs(d)[1]);return m?m[1]:null}));
    const childLots=d2.length>1&&!cas.has(null)&&cas.size===d2.length&&!CA_RE.test(sel);
    for(const d of ds){const s=segs(d),n=s.length,u=n===2&&childLots?{...unitOfPath(d),lotPath:s.join('/'),lotName:s[1],caNames:[s[1],sel]}:unitOfPath(d);
      Object.assign(u,{own:[],shared:[]});units.push(u);U.set(d,u)}}
  const memo=new Map(),owner=d=>{if(memo.has(d))return memo.get(d);let x=d,r=null;for(;;){if(U.has(x)){r=U.get(x);break}if(!x)break;x=x.replace(/[^/]*\/$/,'')}memo.set(d,r);return r};
  const under=new Map(),below=D=>{let l=under.get(D);if(!l)under.set(D,l=units.filter(u=>u.dir.startsWith(D)));return l};
  for(const e of entries){const D=dirOf(e.path),u=owner(D);if(u){u.own.push(e);continue}if(/\.(jpe?g|png|bmp)$/i.test(e.path))continue;for(const v of below(D))v.shared.push(e)}
  for(const u of units)u.files=u.own.concat(u.shared);
  units.sort((a,b)=>natCmp(a.lotPath,b.lotPath)||natCmp(a.slotName,b.slotName));
  // 화면 안내: 고른 폴더마다 Lot 몇 개로 보았는지
  const sum=[...bySel.keys()].map(sel=>{const L=[...new Set(units.filter(u=>u.sel===sel).map(u=>u.lotName))];return `폴더 '${sel}' → Lot ${L.length}개(${L.slice(0,8).join(', ')}${L.length>8?' …':''})`}).join(' · ');
  return {units,sum};
}
/** planUnits 의 Slot 정보를 스캔에 붙이고 Step 이름 · Contrast AVG 를 정한다(같은 Lot 이 이미 있으면 그 값). */
function applyUnit(w,u,known){w.lotPath=u.lotPath;w.lotName=u.lotName;w.slotName=u.slotName;w.slot=lower(u.slotName.trim());
  const prev=known.get(w.lotPath);
  if(prev){w.step=prev.step;w.contrast=prev.contrast;w.tool=prev.tool;return false}
  let step=w.lotName,ca=null;for(const n of u.caNames){const m=CA_RE.exec(n);if(m){ca=+m[1];step=n;break}}
  w.step=step;w.contrast=ca;known.set(w.lotPath,w);return true}
async function addEntries(entries){
  const msg=[],{units,sum}=planUnits(entries);
  if(!units.length){busy(null);showLoad([['err','고른 폴더에 Surface.flt 가 없습니다. Lot 폴더들이 들어 있는 폴더(또는 Lot 폴더)를 고르십시오.']]);return}
  const made=[],total=units.length,fileTotal=entries.length,t0=Date.now();let done=0,files=0;
  // Para #59: Slot 폴더 k / N 개, 파일 x / M 개를 실시간으로 보여 준다
  const tick=(r)=>busy({title:'폴더 등록 중',done,total,unit:'Slot 폴더',files,fileTotal,detail:r?`읽는 중: ${r.replace(/\/$/,'')}`:`경과 ${((Date.now()-t0)/1000).toFixed(1)}초`});
  try{
    for(const u of units){tick(u.dir);await nextPaint();
      try{const w=await retryRead(()=>buildScan(u.dir.replace(/\/$/,'')||'(선택 폴더)',u.files));w.unit=u;made.push(w)}catch(e){msg.push(['err',`${u.dir}: ${e.message}`])}
      done++;files=Math.min(fileTotal,files+u.own.length);tick(null)}
    files=fileTotal;tick(null);await nextPaint();
  }finally{busy(null)}
  const known=new Map(S.scans.map(w=>[w.lotPath,w])),newLots=new Map();
  for(const w of made){if(applyUnit(w,w.unit,known))newLots.set(w.lotPath,w);delete w.unit;
    for(const d of w.defects)d.slot=w.slot;
    S.scans.push(w)}
  // 다른 Lot 과 Step 이름이 같으면 Lot 경로로(구분되게)
  for(const w of newLots.values()){if(S.scans.some(x=>x.lotPath!==w.lotPath&&x.step===w.step))S.scans.filter(x=>x.lotPath===w.lotPath).forEach(x=>x.step=w.lotPath)}
  msg.unshift(['ok',sum]);
  for(const [path] of newLots){const ws=made.filter(w=>w.lotPath===path).sort((a,b)=>natCmp(a.slotName,b.slotName)),bad=ws.filter(w=>w.errors.length),wr=ws.filter(w=>w.warns.length);
    msg.push([bad.length?'err':(wr.length?'warn':'ok'),`Lot ${path}: Slot ${ws.length}개(${ws.map(w=>w.slotName).join(', ')}), Defect ${ws.reduce((a,w)=>a+w.defects.length,0)}개, 이미지 ${ws.reduce((a,w)=>a+w.images,0)}개 등록`
      +(bad.length?' — 제외할 Slot: '+bad.map(w=>`${w.slotName}(${w.errors.join(' / ')})`).join(', '):'')])}
  const added=made.filter(w=>!newLots.has(w.lotPath));if(added.length)msg.push(['ok',`기존 Lot 에 Slot ${added.length}개 추가: ${added.map(w=>w.lotPath+'/'+w.slotName).join(', ')}`]);
  showLoad(msg);renderScans();
}
/** 등록한 Wafer(Slot)를 Lot 으로 묶는다. Contrast AVG 오름차순. */
function lotsOf(){const m=new Map();for(const w of S.scans){let L=m.get(w.lotPath);if(!L)m.set(w.lotPath,L={path:w.lotPath,name:w.lotName,step:w.step,contrast:w.contrast,tool:w.tool,seq:w.seq,wafers:[]});L.wafers.push(w)}
  for(const L of m.values())L.wafers.sort((a,b)=>natCmp(a.slotName,b.slotName));
  return [...m.values()].sort((a,b)=>(a.contrast??Infinity)-(b.contrast??Infinity)||a.seq-b.seq)}
/** 보기 단위 고르기(Para #57): lot = Lot 별(모든 Slot), slot:<키> = 그 Slot 만. Step 2 · Step 3 두 곳이 같은 값. */
function renderUnit(){const L=lotsOf(),slots=new Map();for(const l of L)for(const w of l.wafers){const e=slots.get(w.slot)||{name:w.slotName,n:new Set()};e.n.add(l.path);slots.set(w.slot,e)}
  const cur=S.unit||'lot',html=`<option value="lot">Lot 별 (모든 Slot 합침)</option>`+[...slots].sort((a,b)=>natCmp(a[1].name,b[1].name)).map(([k,e])=>`<option value="slot:${esc(k)}">Slot 별 · ${esc(e.name)} (${e.n.size}/${L.length} Lot)</option>`).join('');
  $$('#unit,#unit3').forEach(el=>{el.innerHTML=html;el.value=cur;if(el.value!==cur){el.value='lot'}});S.unit=$('#unit').value||'lot'}
function setUnit(v){S.unit=v;$$('#unit,#unit3').forEach(el=>el.value=v);if(S.cmp)runCompare()}
/** 비교할 대상(스캔 = 집합): Lot 별이면 Lot 마다 가상 스캔(모든 Slot 의 Defect), Slot 별이면 Lot 마다 그 Slot 의 Wafer. 오류 Slot 은 뺀다. */
function compareViews(msg){const u=S.unit||'lot',L=lotsOf();S.lotViews=S.lotViews||new Map();
  if(u==='lot'){const out=[];for(const l of L){const ok=l.wafers.filter(w=>!w.errors.length);if(ok.length<l.wafers.length)msg.push(['warn',`Lot ${l.path}: 오류 Slot ${l.wafers.length-ok.length}개를 뺐습니다.`]);if(!ok.length)continue;
      let v=S.lotViews.get(l.path);if(!v){v={id:'L'+(++scanSeq),isLot:true};S.lotViews.set(l.path,v)}
      const first=k=>(ok.find(w=>w[k])||{})[k]||null;
      Object.assign(v,{lotPath:l.path,name:l.path,step:l.step,contrast:l.contrast,tool:l.tool,seq:l.seq,wafers:ok,defects:ok.flatMap(w=>w.defects),
        product:first('product'),dieLoc:first('dieLoc'),dieCheck:first('dieCheck')});out.push(v)}
    const all=new Set(out.flatMap(v=>v.wafers.map(w=>w.slot))),part=[...all].filter(k=>out.some(v=>!v.wafers.some(w=>w.slot===k)));
    if(out.length>1&&part.length&&!out.every(v=>v.wafers.length===1))msg.push(['warn',`모든 Lot 에 있지는 않은 Slot: ${part.length}개 — 그 Slot 의 Defect 는 없는 Lot 쪽과 짝이 없습니다.`]);
    return out}
  const k=u.slice(5),out=[];for(const l of L){const w=l.wafers.find(w=>w.slot===k&&!w.errors.length);if(w)out.push(w);else msg.push(['warn',`Lot ${l.path}: Slot ${k} 이 없거나 오류라 뺐습니다.`])}
  return out}
function showLoad(list){$('#loadMsg').innerHTML=list.map(([k,t])=>`<div class="msg ${k}">${esc(t)}</div>`).join('')}
async function buildScan(name,own,opt){
  const files=new Map();for(const e of own){const k=lower(baseName(e.path));if(!files.has(k))files.set(k,e.file)}
  const get=n=>files.get(lower(n));const text=async n=>{const f=get(n);return f?await readText(f):null};
  const s={id:++scanSeq,seq:scanSeq,name,files,warns:[],errors:[],step:baseName(name),tool:'',contrast:null,defects:[],colors:[],frames:[],transforms:new Map(),colorByIndex:new Map(),product:null,images:0};
  s.images=own.filter(e=>/\.(jpe?g|png|bmp)$/i.test(e.path)).length;
  // Contrast AVG 추정(폴더 이름의 'CA27', 'Contrast27', 'AVG27') — 사용자가 고친다
  const m=/(?:contrast|avg|ca)[ _-]?(\d+(?:\.\d+)?)/i.exec(baseName(name));if(m)s.contrast=+m[1];
  const mdText=await text('Surface.flt.md');const md=mdText?parseMd(mdText):null;
  if(mdText&&!md)s.warns.push('Surface.flt.md 를 읽지 못해 기본 필드 정의를 씁니다');
  const {lay,warns}=fltLayout(md);warns.forEach(w=>s.warns.push('md: '+w));
  const buf=await get('Surface.flt').arrayBuffer();const r=parseFlt(buf,lay,fltRec(md,buf.byteLength));
  if(!r.bytes)s.errors.push('빈 결과(Surface.flt 0 byte)');
  else if(!r.ok)s.errors.push(fltRecErr(r,md));
  else if(r.rec!==REC)s.warns.push(`Surface.flt 레코드 ${r.rec} byte(Surface.flt.md 기준, 기본 ${REC})`);
  s.defects=r.defects.map(d=>({...d,scan:s}));
  if(s.defects.length&&s.defects.every(d=>!d.frameIdx&&!d.xInFrame&&!d.yInFrame))s.warns.push('frameIdx/xInFrame/yInFrame 이 모두 0 — Wafer 좌표로 Gray 위치를 계산합니다');
  const ci=await text('ColorImageGrabingInfo.ini');if(ci){s.colors=parseColors(ci);for(const c of s.colors)if(c.index!=null&&!s.colorByIndex.has(c.index))s.colorByIndex.set(c.index,c)}else s.warns.push('ColorImageGrabingInfo.ini 없음');
  if(!s.colors.length){s.colors=colorsFromNames([...files.values()].map(f=>f.name));if(s.colors.length)s.warns.push(`Color 항목이 없어 Slot 폴더의 Color 사진 ${s.colors.length}장 이름(X.Y.c.….jpeg)의 좌표로 연결합니다`);else s.warns.push('Color 이미지 정보 없음(ini · 사진 이름 둘 다) — Color 연결 불가')}
  // v14.4.1(#89): Gray 위치 자료 = 대규모 모드와 같은 계산(geoLoad — 프레임 목록 · 변환 · 레시피별 프레임 크기 · 픽셀 크기 · 대체 계산 · 장비 프레임 기록).
  //   종전: 목록이 없으면 Gray 없음, 변환 파일이 없으면 간단 모델(모서리 기준 · 0.7708), 3168×1024 고정. Step 5 가 다시 읽을 때(opt.noGeo)는 s.cg 를 쓰므로 건너뛴다.
  if(!(opt&&opt.noGeo)){const G=s.geo=await geoLoad(dirFromFiles(name,files),geoPtsDefs(s.defects),geoHasRecDefs(s.defects)?'now':false);s.frames=G.frames;s.transforms=G.tfs;
    if(G.noGray)s.warns.push(`Gray 위치를 구할 수 없음 — ${G.noGray}`);else if(G.src.frames!==CG.SL)s.warns.push(`${CG.SL} 없음 — Gray 프레임 위치를 ${G.src.frames} 로 계산`);
    if(/모델/.test(G.src.tf||''))s.warns.push(G.src.tf);else if(G.usedHi)s.warns.push(`레시피 번호가 같은 변환 파일이 없는 Defect 는 ${G.src.tf} 의 큰 번호 파일로 계산`);
    for(const tf of new Set(G.tfs.values()))if(tf&&tf.err)s.warns.push(tf.err);
    if(G.mode)s.warns.push(`좌표 기준: ${CG.MODES[G.mode]}(프레임과 맞는 Defect 가 가장 많음)`)}
  if(get('s_FrameData.dat'))s.frameData=`s_FrameData.dat ${get('s_FrameData.dat').size} byte${get('s_FrameData.dat.md')?' + .md':''}${s.geo&&s.geo.fd?' (읽음: 프레임 위치 · 크기 · 장비 기록)':' (변환 파일 · 목록이 있어 안 읽음)'}`;
  const pi=await text('ProductInfo.ini');if(pi){s.product=parseProduct(pi);if(!s.product)s.warns.push('ProductInfo.ini 에 Die Pitch/Cols/Rows 없음 — Die 계산 불가')}else s.warns.push('ProductInfo.ini 없음 — Die 계산 불가');
  // v14.3.12: wafer 원 중심 = Wafer2Table.ini 역변환(wafer → table 변환에서 table (0, 0) 이 되는 wafer 좌표). 그림에만 씀.
  //  종전 Params_WaferInfo Center_X/Y 는 값이 없을 때 0 이라 중심을 (0, 0) 으로 잘못 읽었다(#82 — 맵이 1 ~ 2칸 밀린 원인) → 쓰지 않음.
  const w2=await text('Wafer2Table.ini');if(w2)s.w2t=parseW2T(w2);
  // Para #70: 리뷰PC 정보(Recipe 이름 · Zone 이름 · 판정 종류 이름 · 분류 이름) — 없어도 됨
  await rvLoad(s,text);
  // Para #53: 스캔한 Die 목록(s_DieLocation.dat) — wafer map 검증용
  if(get('s_DieLocation.dat'))s.dieLoc=parseDieLoc(await get('s_DieLocation.dat').arrayBuffer(),await text('s_DieLocation.dat.md'));
  // Para #53: id 가 모두 같으면(실제 자료는 전부 1) 화면 ID = 기록 순서(0부터, ColorImageGrabingInfo Index 와 같음)
  const ids=new Set(s.defects.map(d=>d.id));s.idByOrder=s.defects.length>1&&ids.size<s.defects.length;
  for(const d of s.defects)d.no=s.idByOrder?d.i:d.id;
  if(s.idByOrder)s.warns.push(`Surface.flt 의 id 가 고유하지 않음(${ids.size}종) — 표의 ID 는 기록 순서(0부터, Color Index 와 같음)`);
  // Para #53: Die 번호 검증 — Color 이미지의 장비 Col/Row 와 Fault 좌표로 계산한 Col/Row 비교
  if(s.product){let n=0,bad=0;for(const c of s.colors){if(c.col==null||c.row==null||c.x==null||c.y==null)continue;const d=dieOf(c.x,c.y,s.product);n++;if(d.col!==c.col||d.row!==c.row)bad++}
    s.dieCheck=n?{n,bad}:null;if(bad)s.warns.push(`Die 번호 검증: Color 이미지 Col/Row 와 계산이 ${bad}/${n}개 다름 — Die Pitch · Offset 확인 필요`)}
  // ScanLog 먼저(Para #53)
  for(const [k,f] of [...files].sort((a,b)=>/^scanlog/.test(b[0])-/^scanlog/.test(a[0])))if(/^(scanlog|productioninfo).*\.(txt|log|ini|csv|xml)$/i.test(k)){const c=surfaceCount(await readText(f));if(c!=null){s.crossCount={file:k,count:c};
    if(c!==s.defects.length)s.warns.push(`${k} 의 Surface defect 수 ${c} ≠ 파싱 ${s.defects.length}`);break}}
  return s;
}

// ════════════════════════════════════════════════════════════════════════
// 6. Step 1 표
// ════════════════════════════════════════════════════════════════════════
function renderScans(){
  const tb=$('#scanTbl tbody');
  tb.innerHTML=lotsOf().map(l=>{const ws=l.wafers,er=ws.flatMap(w=>w.errors.map(t=>w.slotName+': '+t)),wr=ws.flatMap(w=>w.warns.map(t=>w.slotName+': '+t));
    return `<tr data-id="${esc(l.path)}">
    <td><input data-k="step" value="${esc(l.step)}" style="width:140px"></td>
    <td><input data-k="contrast" type="number" step="0.1" value="${l.contrast??''}" placeholder="필수"></td>
    <td><input data-k="tool" value="${esc(l.tool)}" placeholder="예: AOI-3" style="width:90px"></td>
    <td title="${esc(l.path)}">${esc(l.path)}</td><td title="${esc(ws.map(w=>w.slotName).join(', '))}">${ws.length}개 <span class="muted">${esc(ws.slice(0,4).map(w=>w.slotName).join(', '))}${ws.length>4?' …':''}</span></td>
    <td class="num">${ws.reduce((a,w)=>a+w.defects.length,0)}</td><td>${esc(rcpSum(ws.map(w=>[w.defects.length,i=>rcpName(w.defects[i])])))}</td><td class="num">${ws.reduce((a,w)=>a+w.images,0)}</td>
    <td><details><summary>${er.length?`⛔ 오류 Slot ${ws.filter(w=>w.errors.length).length}`:wr.length?`⚠ ${wr.length}건`:'✔ 정상'}</summary>
      <div class="muted" style="white-space:normal;max-width:420px">${[...er,...wr].map(esc).join('<br>')||'문제 없음'}
      ${ws.map(w=>`<br>${esc(w.slotName)}: Defect ${w.defects.length} · Color ${w.colors.length} · Gray 프레임 ${w.frames.length} · 변환 ${w.transforms.size?'frameToChuckPlane':'없음'} · Die ${w.product?`${w.product.cols}×${w.product.rows}`:'계산 불가'}${w.crossCount?` · 교차 검증 ${esc(w.crossCount.file)} = ${w.crossCount.count}`:''}`).join('')}</div></details></td>
    <td><button data-del="${esc(l.path)}">삭제</button></td></tr>`}).join('')||'<tr><td colspan="10" class="muted">아직 없습니다.</td></tr>';
  renderUnit();
}
$('#scanTbl').addEventListener('change',e=>{const k=e.target.dataset.k;if(!k)return;const path=e.target.closest('tr').dataset.id,v=k==='contrast'?(e.target.value===''?null:+e.target.value):e.target.value;
  for(const w of S.scans)if(w.lotPath===path)w[k]=v;renderScans()});
$('#scanTbl').addEventListener('click',e=>{const id=e.target.dataset.del;if(id==null)return;S.scans=S.scans.filter(w=>w.lotPath!==id);renderScans()});
$$('#unit,#unit3').forEach(el=>el.addEventListener('change',e=>setUnit(e.target.value)));
// Para #59: 폴더를 고른 뒤 브라우저가 파일 목록을 만드는 동안은 개수를 알 수 없어 '목록 만드는 중' 만 보이고(닫기 가능), 목록이 오면 Slot 폴더 · 파일 개수로 바뀐다.
$('#addBtn').onclick=()=>{if(PARA)return void paraAdd1();busy({title:'폴더 고르는 중',indet:true,count:'…',files:'폴더를 고르면 브라우저가 파일 목록을 만듭니다. 큰 폴더는 시간이 걸립니다.',detail:'고르기를 취소했으면 [닫기]를 누르십시오.',close:true});$('#dirInput').click()};
$('#busyX').onclick=()=>busy(null);
$('#dirInput').addEventListener('cancel',()=>busy(null));
/** v14 Step 1: 엔진이 고른 폴더 아래 파일 목록(이름 · 크기)을 만들고, 내용은 쓸 때만 읽는다(사진은 보는 것만). */
async function paraAdd1(){let R;try{R=await PARA.pick()}catch(e){return showLoad([['err','폴더를 고르지 못했습니다: '+(e.message||e)]])}if(!R)return;
  busy({title:'폴더 등록 중',indet:true,count:'…',files:`프로그램이 폴더 목록을 만드는 중(이름만): ${R.path}`});await nextPaint();
  let W;try{W=await PARA.walk(R)}catch(e){busy(null);return showLoad([['err','폴더 목록을 만들지 못했습니다: '+(e.message||e)]])}
  showLoad([[W.truncated?'err':'warn',`파일 ${W.entries.length}개 읽는 중…${W.truncated?' — 파일이 너무 많아 일부만 받았습니다(더 아래 폴더를 고르십시오)':''}`]]);
  busy({title:'폴더 등록 중',indet:true,count:`파일 ${W.entries.length}개`,files:'Slot 폴더(Surface.flt) 찾는 중…'});await nextPaint();
  await addEntries(W.entries)}
$('#dirInput').onchange=async e=>{const fs=[...e.target.files];e.target.value='';if(!fs.length){busy(null);return}
  showLoad([['warn',`파일 ${fs.length}개 읽는 중…`]]);busy({title:'폴더 등록 중',indet:true,count:`파일 ${fs.length}개`,files:'Slot 폴더(Surface.flt) 찾는 중…'});await nextPaint();
  await addEntries(fs.map(f=>({path:f.webkitRelativePath||f.name,file:f})))};
// ════════════════════════════════════════════════════════════════════════
// 7. 비교
// ════════════════════════════════════════════════════════════════════════
function pts(s,o){return s.defects.map(d=>{const X=o.coord==='actual'?d.ActualX:d.x,Y=o.coord==='actual'?d.ActualY:d.y;d.X=X;d.Y=Y;return d}).filter(d=>isFinite(d.X)&&isFinite(d.Y))}
/** 쌍마다 이름 표기(Para #50 후속): 유지 · 소거 · 신규 대신 리스트(Step) 이름 */
function stLabel(st,c){c=c||S.cmp;const a=stepName(c.A),b=stepName(c.B);if(c.single)return a;return st==='keep'?`${a} ∩ ${b}`:st==='gone'?`${a} - ${b}`:`${b} - ${a}`}
/** 보기 5가지(집합 기호, 소유자 지시) + 합집합. 값 = 그 집합에 드는 내부 상태들. */
const VIEWS=[['all',['gone','keep','new']],['A',['gone','keep']],['B',['keep','new']],['gone',['gone']],['keep',['keep']],['new',['new']]];
function viewLabel(v,c){c=c||S.cmp;const a=stepName(c.A),b=stepName(c.B);if(c.single)return a;
  return {all:`${a} ∪ ${b}`,A:`${a} (전체)`,B:`${b} (전체)`}[v]||stLabel(v,c)}
const viewSet=v=>new Set((VIEWS.find(x=>x[0]===v)||VIEWS[0])[1]);
/** 등록한 리스트를 Contrast AVG 오름차순으로 놓고 모든 순서쌍(i ≠ j)을 비교한다. 3개 → 6쌍(Para #56). */
function runCompare(){
  const o=opts(),msg=[];
  S.unit=S.unit||$('#unit').value||'lot';const ss=compareViews(msg);
  if(ss.length<1){$('#cmpMsg').innerHTML=[...msg,['err',S.unit==='lot'?'Lot 을 1개 이상 등록하십시오.':'이 Slot 이 있는 Lot 이 없습니다. 보기 단위를 바꾸십시오.']].map(([k,t])=>`<div class="msg ${k}">${esc(t)}</div>`).join('');return false}
  if(ss.some(s=>s.contrast==null))msg.push(['warn','Contrast AVG 가 빈 Lot 이 있습니다. 정렬은 입력한 순서로 맨 뒤에 둡니다.']);
  // Para #57: Lot 별 = 그 Lot 의 모든 Slot Defect(같은 Defect 판정은 같은 Slot 끼리만, matchBySlot), Slot 별 = 그 Slot 만
  const P=new Map(ss.map(s=>[s,s.isLot?s.wafers.flatMap(w=>pts(w,o)):pts(s,o)])),prev=S.pairs[S.pi];
  // Para #55: wafer map · 벤다이어그램은 쌍이 아니라 등록한 스캔 전체로 그린다(같은 wafer)
  S.o=o;S.cmpScans=ss;S.allPts=[...P.values()].flat();S._mg=null;S.venn=buildVenn(ss,P,o,S.venn);
  // Para #56: 모든 순서쌍 A → B (i ≠ j). 3개 → 3×2 = 6쌍
  S.pairs=[];for(let i=0;i<ss.length;i++)for(let j=0;j<ss.length;j++){if(i===j)continue;const A=ss[i],B=ss[j];S.pairs.push({A,B,o,...matchBySlot(P.get(A),P.get(B),o.tol)})}
  // Para #70: Lot 1개 = 비교 쌍 없음 → 자기 자신 하나(single). Step 3 = 벤다이어그램 원 1개 · 그 Lot 의 모든 Defect, Step 4(Escape) = 비교 없음 안내.
  if(ss.length===1)S.pairs=[{A:ss[0],B:ss[0],o,single:true,keep:P.get(ss[0]).map(d=>({a:d,b:null,d:0})),gone:[],added:[]}];
  const k=prev?S.pairs.findIndex(c=>c.A===prev.A&&c.B===prev.B):-1;
  const rs=new Map(ss.map(s=>{const L=P.get(s);return [s,rcpSum([[L.length,i=>rcpName(L[i])]])]}));   // #73: Recipe 열
  $('#pairTbl tbody').innerHTML=S.pairs.map((c,i)=>{const n=c.keep.length+c.gone.length;
    if(c.single)return `<tr><td><b>${esc(stepName(c.A))}</b> <span class="muted">(Lot 1개 — 비교 없음)</span></td><td class="num">${n}</td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td class="num">-</td><td>${esc(rs.get(c.A))}</td><td></td></tr>`;
    return `<tr><td><b>${esc(stepName(c.A))} → ${esc(stepName(c.B))}</b></td><td class="num">${n}</td><td class="num">${c.keep.length+c.added.length}</td><td class="num">${c.keep.length}</td>
      <td class="num">${c.gone.length}</td><td class="num">${c.added.length}</td><td class="num">${n?(100*c.gone.length/n).toFixed(1)+'%':''}</td><td>${esc(rs.get(c.A))} → ${esc(rs.get(c.B))}</td><td><button data-pair="${i}">보기</button></td></tr>`}).join('');
  if(ss.length===1)msg.push(['ok',`${S.unit==='lot'?'Lot 별(모든 Slot)':'Slot 별 · '+(ss[0].slotName||'')} · Lot 1개(${stepName(ss[0])}, Defect ${S.pairs[0].keep.length}개) — 비교 없이 분석합니다. Step 3 벤다이어그램은 원 1개, Step 4(Escape)는 Lot 이 2개 이상일 때 나옵니다.`]);
  else msg.push(['ok',`${S.unit==='lot'?'Lot 별(모든 Slot)':'Slot 별 · '+(ss[0].slotName||'')} · 리스트 ${ss.length}개 → ${S.pairs.length}쌍 비교 (허용오차 ${o.tol} µm). `+S.pairs.map(c=>`${stepName(c.A)} → ${stepName(c.B)}: 없어짐 ${c.gone.length}`).join(' · ')]);
  $('#cmpMsg').innerHTML=msg.map(([k,t])=>`<div class="msg ${k}">${esc(t)}</div>`).join('');
  selectPair(k>=0?k:0);renderSetPick();if(S.venn.shown)refresh3();return true;
}
function selectPair(i){
  S.pi=Math.max(0,Math.min(S.pairs.length-1,i));const c=S.cmp=S.pairs[S.pi];
  S.rows=[...c.keep.map(k=>({st:'keep',d:k.a,b:k.b,dist:k.d})),...c.gone.map(d=>({st:'gone',d})),...c.added.map(d=>({st:'new',d}))];
  S.page=0;S.rv=0;S.rvList=S.rows.filter(x=>x.st==='gone');
  $$('.pairtabs').forEach(t=>t.innerHTML=S.pairs.map((p,j)=>`<button role="tab" data-pair="${j}" aria-pressed="${j===S.pi}">${esc(stepName(p.A))} → ${esc(stepName(p.B))} · 없어짐 ${p.gone.length}</button>`).join(''));
  const f=$('#fltSt'),fv=f.value||'all';f.innerHTML=VIEWS.filter(([v])=>!c.single||v==='all').map(([v])=>`<option value="${v}">${esc(viewLabel(v))}</option>`).join('');f.value=c.single?'all':fv;
  S._mg=null;renderKpis();renderTable();refresh4();mapStatus();
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-pair]');if(b&&S.pairs.length){selectPair(+b.dataset.pair);if(b.closest('#pairTbl'))go(4)}});
$('#runBtn').onclick=()=>{if(runCompare())go(3)};
/** Step 2 · 3 맵 상태 줄(v14.3.12 — 웨이퍼 맵 기준). */
function mapStatus(){const el=$('#mapSt');if(!S.cmp){el.textContent='';return}const g=mapGeom(),sc=S.cmpScans||[];
  if(!g.frames.length){el.textContent='ProductInfo.ini(Die Pitch · [ExportData])가 없어 웨이퍼 맵 번호를 정할 수 없습니다 — Defect 위치만 그립니다. · '+flatTag(g.flat).txt;return}
  let t=`웨이퍼 맵 기준 ${g.cols} × ${g.rows} 칸 — Die 번호 X 0~${g.cols-1}(왼쪽부터) · Y 0~${g.rows-1}(아래부터)`;
  t+=g.dies.size?` · Die ${g.dies.size}개(s_DieLocation) · Defect 점이 찍힌 Die = 연한 남색`:' · ⚠ s_DieLocation.dat 없음 — Die 를 그리지 않았습니다(번호는 [ExportData] 로 계산)';
  if(g.noLoc&&g.dies.size)t+=` · ⚠ s_DieLocation 없는 Slot ${g.noLoc}개`;
  if(g.outDie)t+=` · ⚠ Defect ${g.outDie}/${g.n}개가 맵 Die 밖`;
  const V=sc.map(x=>x.dieCheck).find(Boolean);if(V)t+=V.bad?` · ⚠ Die 번호가 Color 이미지 Col/Row 와 ${V.bad}/${V.n}개 다름`:` · Die 번호 확인: Color 이미지 Col/Row ${V.n}/${V.n} 일치`;
  t+=' · '+flatTag(g.flat).txt;
  if(g.noFrame)t+=` · ⚠ ProductInfo 없는 Slot ${g.noFrame}개(맵 번호 없음)`;
  if(g.warns.length)t+=' · ⚠ '+g.warns.slice(0,3).join(' · ')+(g.warns.length>3?` 외 ${g.warns.length-3}건`:'');
  if(S.unit==='lot'&&sc.some(v=>v.isLot&&v.wafers.length>1))t+=' · Lot 별: Slot 마다 자기 맵 번호로 맞춰 겹쳐 그림';
  el.textContent=t}
function renderKpis(){const c=S.cmp,n=c.keep.length+c.gone.length,a=stepName(c.A),b=stepName(c.B);
  $('#kpis').innerHTML=[[viewLabel('A'),`${n}`,'',`Contrast AVG ${c.A.contrast??'?'}`],[viewLabel('B'),`${c.keep.length+c.added.length}`,'',`Contrast AVG ${c.B.contrast??'?'}`],[stLabel('keep'),c.keep.length,'keep','둘 다 있음'],[stLabel('gone'),c.gone.length,'gone',`${b} 에서 없어짐`],[stLabel('new'),c.added.length,'new',`${b} 에서 새로 생김`],
    ['감소율',n?(100*(n-(c.keep.length+c.added.length))/n).toFixed(1)+'%':'-','',`없어진 비율 ${n?(100*c.gone.length/n).toFixed(1):'-'}%`]]
    .map(([t,v,k,s])=>`<div class="kpi ${k}"><span class="muted">${esc(t)}</span><b>${esc(v)}</b><span class="muted">${esc(s||'')}</span></div>`).join('')}

// ════════════════════════════════════════════════════════════════════════
// 8. 상세 표 · CSV
// ════════════════════════════════════════════════════════════════════════
function info(r){const d=r.d,s=d.scan,o=S.o,m=mapDie(d.X,d.Y,s),sp=sizePix(s),px2=sp.pix*sp.pix;   // v14.4.1: Area µm² = 값 × µm 환산 픽셀²(종전 0.7708²)
  // v14.3.12: Die = 웨이퍼 맵 번호 X, Y(왼쪽 · 아래부터 0). 장비 Col/Row(dieEq)는 마우스 · 상세 창에만. 맵 Die(s_DieLocation) 밖이면 표시.
  const out=m&&m.inDie===false,x={id:d.no??d.id,X:d.X,Y:d.Y,m,die:dieTxt(m)+(out?' · 맵 Die 밖':''),dieEq:dieEq(m),dieXY:m?`${m.dx.toFixed(0)}, ${m.dy.toFixed(0)}`:'',
    area:d.area*px2,areaRaw:d.area,width:d.BlobBreadth,widthUm:d.BlobBreadth*sp.pix,pix:sp,length:d.BlobLength,box:`${f1(d.BoxWidth)}×${f1(d.BoxHeight)}`,contrast:d.Contrast,step:stepName(s),slot:s.slotName||'',tool:s.tool,dieWarn:!m||m.x==null||out};
  // r.raw(Step 5): 비교 맥락이 없다
  return r.raw?{...x,st:r.label||'',cmpContrast:null}:{...x,st:r.label??stLabel(r.st),cmpContrast:r.b?r.b.Contrast:null}}
function filtered(){const f=viewSet($('#fltSt').value||'all'),T=S.dq||[];return S.rows.filter(r=>f.has(r.st)&&(!T.length||qAll(T,detText(r))))}
/** v14.1.8 쌍별 상세 표 검색 글: 모든 열 값 + 사진 이름 + O/X. */
function detText(r){if(!r.qt){const x=info(r),d=r.d,c=S.cmp?linkColor(d,d.scan,S.cmp.o.ctol):null,g=grayOf(d);
    r.qt=lower([x.st,x.id,f1(x.X),f1(x.Y),x.die,x.dieEq,fv(x.area),fv(x.areaRaw),fv(x.width),fv(x.widthUm),fv(x.length),x.box,fv(x.contrast),x.cmpContrast!=null?fv(x.cmpContrast):'',x.step,x.slot,x.tool,rcpName(d),c&&c.c&&c.c.file,g&&g.frame&&g.frame.file].filter(v=>v!=null&&v!=='').join(' '))}
  const ov=S.overlay[key(r.d)];return ov?r.qt+' '+lower(ov):r.qt}
function renderTable(){const rows=filtered(),P=200,pages=Math.max(1,Math.ceil(rows.length/P));S.page=Math.min(S.page,pages-1);
  $('#detTbl tbody').innerHTML=rows.slice(S.page*P,S.page*P+P).map((r,k)=>{const x=info(r),on=dOn(r);return `<tr data-k="${S.page*P+k}"${on?'':' class="off"'}><td class="pk" title="☑ = CSV 에 넣음">${on?'☑':'☐'}</td><td><span class="st ${r.st}">${x.st}</span></td><td class="num">${x.id}</td><td class="num">${f1(x.X)}</td><td class="num">${f1(x.Y)}</td>
    <td${x.dieWarn?' style="color:var(--err)"':''}>${x.die}</td><td class="num">${fv(UM.on?x.area:x.areaRaw)}</td><td class="num">${fv(UM.on?x.widthUm:x.width)}</td><td class="num">${fv(x.length)}</td><td>${x.box}</td><td class="num">${fv(x.contrast)}${x.cmpContrast!=null?' → '+fv(x.cmpContrast):''}</td><td>${esc(x.step)}</td><td>${esc(x.slot)}</td><td>${esc(x.tool)}</td><td>${esc(rcpName(r.d))}</td></tr>`}).join('');
  $('#pgInfo').textContent=`${S.page+1} / ${pages} 쪽 (${rows.length}행)`;const n=rows.reduce((a,r)=>a+(dOn(r)?1:0),0);DLS.set(n,rows.length);
  $('#csvBtn').disabled=!n;$('#csvBtn').textContent=n?`CSV 내보내기 (☑ ${n.toLocaleString()}개)`:'CSV 내보내기'}
/** v14.1.8 쌍별 상세 표 ☑(처음 = [처음엔 모두 ☑]) — 기억 = (Defect, 구분)마다. */
const dKey=r=>key(r.d)+'|'+r.st,dOn=r=>{const v=S.dpk&&S.dpk.get(dKey(r));return v===undefined?LS.def:v};
$('#fltSt').onchange=()=>{S.page=0;renderTable()};
const DLS=lsBind('detLs',{onQ:T=>{S.dq=T;S.page=0;renderTable()},onAll:v=>{S.dpk=S.dpk||new Map();for(const r of filtered())S.dpk.set(dKey(r),v);renderTable()}});$('#pgPrev').onclick=()=>{S.page=Math.max(0,S.page-1);renderTable()};$('#pgNext').onclick=()=>{S.page++;renderTable()};
$('#detTbl').addEventListener('click',e=>{const tr=e.target.closest('tr[data-k]');if(!tr)return;const r=filtered()[+tr.dataset.k];
  const tog=x=>{S.dpk=S.dpk||new Map();S.dpk.set(dKey(x),!dOn(x));renderTable()};
  if(e.target.closest('td.pk')){tog(r);return}photoWinOpen(listSrc(filtered(),+tr.dataset.k,tog,dOn))});   // v14.4.1(#89): 대규모와 같은 새 창(↑↓ = 표의 다음 줄, Space = ☑/☐)
function csvText(rows){rows=rows||S.rows;const q=v=>{v=v==null?'':String(v);return /[",\r\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
  const head=['구분','ID','resultID','WaferX','WaferY','Die','DieX','DieY','Area_um2','Area_px','Width','Length','BoxW','BoxH','Contrast','비교Contrast','Step','Slot','ContrastAVG','호기','Color이미지','Color연결','Gray프레임','GrayPX','GrayPY','Gray모델','ROI_mean','ROI_median','ROI_max','Ring_median','ROI_local_delta','위치확인','Recipe','Zone','Region','판정비트','분류코드','Zone이름','판정종류','분류','장비Col','장비Row'];
  const lines=[head];
  for(const r of rows){const x=info(r),d=r.d,g=grayOf(d),c=linkColor(d,d.scan,S.cmp.o.ctol),gl=d.gl||{};
    lines.push([x.st,x.id,d.resultID,f2(x.X),f2(x.Y),x.die,...(x.dieXY?x.dieXY.split(', '):['','']),fv(x.area),d.area,fv(x.width),fv(x.length),f2(d.BoxWidth),f2(d.BoxHeight),fv(d.Contrast),fv(x.cmpContrast),x.step,x.slot,d.scan.contrast,x.tool,
      c?c.c.file:'',c?c.how:'연결 실패',g.frame?g.frame.file:'',g.frame?f1(g.px):'',g.frame?f1(g.py):'',g.frame?g.model:g.reason,f2(gl.mean),f2(gl.median),gl.max??'',f2(gl.ring),f2(gl.delta),S.overlay[key(d)]||'',...(v=>[v.recipe,rawNum(v.zoneNo),v.region,rawNum(v.typeNo),rawNum(v.clsNo),v.zoneName,v.typeName,v.clsName])(rvInfo(d)),x.m?x.m.col:'',x.m?x.m.row:''])}
  return '﻿'+lines.map(l=>l.map(q).join(',')).join('\r\n')}
$('#csvBtn').onclick=async()=>{if(!S.cmp)return;await saveCsv([csvText(filtered().filter(dOn))],`Contrast_비교_${stepName(S.cmp.A)}_to_${stepName(S.cmp.B)}.csv`.replace(/[\\/:*?"<>|]/g,'_'),true)};

// ════════════════════════════════════════════════════════════════════════
// 9. 이미지 캐시(LRU) · Gray Crop · GL 측정
// ════════════════════════════════════════════════════════════════════════
const key=d=>d.scan.id+':'+d.i;
class LRU{constructor(n,drop){this.n=n;this.m=new Map;this.drop=drop}
  get(k){if(!this.m.has(k))return undefined;const v=this.m.get(k);this.m.delete(k);this.m.set(k,v);return v}
  set(k,v){this.m.delete(k);this.m.set(k,v);while(this.m.size>this.n){const [k0,v0]=this.m.entries().next().value;this.m.delete(k0);this.drop(v0)}}}
const urlCache=new LRU(80,p=>p.then(u=>u&&URL.revokeObjectURL(u)));                  // Color: object URL → 버리면 revokeObjectURL
const bmpCache=new LRU(16,p=>p.then(b=>b&&b.close&&b.close()).catch(()=>{}));          // Gray 프레임: ImageBitmap → 버리면 close
const cleanName=n=>baseName(String(n).replace(/^"|"$/g,''));
const FS={note:null};   // 긴 파일 일(Slot 목록 만들기 등)을 지금 열린 로딩창에 알린다
const TF_RE=/^frametochuckplane(?:\.(.+))?\.ini$/;
/** 스캔 폴더의 파일을 이름으로 찾는다 → {name, path(고른 폴더부터의 경로), get()} | null.
 *  순서: 등록 때 받은 목록(s.files = File 또는 핸들) → Slot 폴더 핸들에서 이름으로 바로(getFileHandle — 목록을 만들지 않아 빠름)
 *  → 그래도 없으면 그 Slot 폴더 목록을 한 번 만들어(하위 폴더 2단계까지, 대소문자 무시) 찾는다. noIdx = 없어도 되는 파일(목록을 만들지 않음). 읽기만 한다. */
function fileFind(s,name,noIdx){if(!name)return Promise.resolve(null);const b=cleanName(name),k=lower(b);
  const m=s.files&&s.files.get(k);
  if(m){const nm=m.name||b;return Promise.resolve({name:nm,path:(s.paths&&s.paths.get(k))||m.webkitRelativePath||(s.name?s.name+'/':'')+nm,get:()=>m.getFile?m.getFile():Promise.resolve(m)})}
  const d=s.dirs&&s.dirs[0];if(!d||s.full)return Promise.resolve(null);   // Step 1 방식으로 읽은 Slot 은 파일 목록이 전부다
  const fm=s.fmemo||(s.fmemo=new Map()),mk=k+(noIdx?'|n':'');if(fm.has(mk))return fm.get(mk);
  const p=(async()=>{try{const h=await d.getFileHandle(b);return {name:h.name,path:s.name+'/'+h.name,get:()=>h.getFile()}}catch(e){}
    if(noIdx)return null;const e=(await slotIndex(s)).get(k);return e?{name:e.h.name,path:e.path,get:()=>e.h.getFile()}:null})();
  fm.set(mk,p);return p}
async function fileGet(s,name){const f=await fileFind(s,name);return f?f.get():null}
/** Slot 폴더 파일 목록(하위 폴더 2단계까지) — 이름으로 바로 못 찾았을 때만 Slot 마다 한 번 만든다(사진이 많으면 시간이 걸려 로딩창에 개수를 알린다). */
function slotIndex(s){return s.idxP||(s.idxP=(async()=>{const m=new Map();let n=0;
  const walk=async(h,path,depth)=>{for await(const [name,c] of h.entries()){if(c.kind==='directory'){if(depth<2)await walk(c,path+name+'/',depth+1)}
    else{const k=lower(name);if(!m.has(k))m.set(k,{h:c,path:path+name});if(++n%300===0&&FS.note)FS.note(`Slot 파일 목록 만드는 중(이름으로 바로 못 찾은 파일이 있어서): ${s.name} · ${n.toLocaleString()}개`)}}};
  try{await walk(s.dirs[0],s.name+'/',0)}catch(e){s.warns.push('Slot 파일 목록 실패: '+e.message)}s.indexed=n;return m})())}
/** rev3(소유자 2026-11-10 "1 · 2 · 3 에서는 되는 Lot 이 5 에서 안 된다 — 방식이 다른 거 아니야?"): 5-2 · 5-3 에서 쓰는 Slot 은 **Step 1 과 똑같이** 읽는다.
 *  rev2 는 빠르게 하려고 Slot 안 목록을 만들지 않고 몇 파일만 이름으로 바로 찾아 따로 조합했다(Step 1 과 다른 길).
 *  지금: Slot 폴더 파일 전부(하위 폴더 포함 — 사진은 이름만, 내용은 볼 때) + 위쪽 폴더(Lot · Setup · 레시피)의 파일(사진 제외) → Step 1 의 buildScan 그대로 →
 *  결과(Color · Gray 목록 · 변환 · ProductInfo · Wafer Map · 파일 목록)를 이 Slot 에 옮겨 담는다. Slot 마다 한 번(s.fullP). 5-1 은 그대로 빠른 길(Surface.flt 만). */
const READY=Promise.resolve();
const IMG_RE=/\.(jpe?g|png|bmp)$/i;
const upFiles=new WeakMap();   // 위쪽 폴더 핸들 → 그 폴더 바로 안 파일(사진 제외) — Slot 마다 같은 Lot · Setup 폴더를 다시 나열하지 않게
async function dirOwnFiles(h){let p=upFiles.get(h);if(!p){p=(async()=>{const out=[];for await(const [name,c] of h.entries())if(c.kind==='file'&&!IMG_RE.test(name))out.push([name,await c.getFile()]);return out})();upFiles.set(h,p)}return p}
async function slotEntries(s){const out=[];let n=0;
  // Step 1(webkitdirectory)처럼 Slot 안 전부. 같은 이름이면 Slot 바로 안 파일이 먼저(폴더마다 파일 먼저, 하위 폴더는 나중)
  const walk=async(h,path,depth)=>{const subs=[];
    for await(const [name,c] of h.entries()){if(c.kind==='directory'){subs.push([name,c]);continue}
      out.push({path:path+name,file:IMG_RE.test(name)?c:await c.getFile()});if(++n%300===0&&FS.note)FS.note(`Slot 파일 목록 만드는 중(Step 1 과 같은 방식): ${s.name} · ${n.toLocaleString()}개`)}
    if(depth<4)for(const [name,c] of subs.sort((a,b)=>natCmp(a[0],b[0])))await walk(c,path+name+'/',depth+1)};
  await walk(s.dirs[0],s.name+'/',0);
  // 위쪽 폴더(가까운 것부터)의 파일 — Step 1 planUnits 와 같은 규칙(사진 제외, Slot 에 같은 이름이 있으면 Slot 것)
  let up=s.name.split('/').slice(0,-1);for(const h of s.chain){const base=up.join('/')+'/';for(const [name,f] of await dirOwnFiles(h))out.push({path:base+name,file:f});up=up.slice(0,-1)}
  return out}
function fullLoad(s){if(!s.light)return READY;return s.fullP||(s.fullP=(async()=>{
  const entries=s.dirs.length?await slotEntries(s):(s.entries||[]);
  FS.note&&FS.note(`Step 1 과 같은 방식으로 읽는 중: ${s.name} (파일 ${entries.length.toLocaleString()}개)`);
  const full=await buildScan(s.name,entries,{noGeo:true});   // Gray 위치는 s.cg(cgLoad · geoLoad — 같은 계산)
  Object.assign(s,{files:full.files,colors:full.colors,colorByIndex:full.colorByIndex,frames:full.frames,transforms:full.transforms,w2t:full.w2t,dieLoc:full.dieLoc,dieCheck:full.dieCheck,crossCount:full.crossCount,images:full.images});
  if(full.product)s.product=full.product;delete s._mf;   // v14.3.12: 맵 기준(mapFrame)을 s_DieLocation 까지 넣어 다시
  s.paths=new Map();for(const e of entries){const k=lower(baseName(e.path));if(!s.paths.has(k))s.paths.set(k,e.path)}
  s.fileCount=entries.length;s.upCount=entries.filter(e=>!e.path.startsWith(s.name+'/')).length;
  s.fmemo=null;s._cm=null;s.full=full;for(const w of full.warns)if(!s.warns.includes(w))s.warns.push(w);
  // rev4 안전장치: 5-1 이 모은 Defect 값 ↔ Step 1 방식으로 읽은 값. 다르면 Step 1 값으로 바꾼다(5-1 목록은 b5Pair 가 다시 거른다)
  s.mdStep1=s.paths.get('surface.flt.md')||'';
  const dif=colsDiff(s.cols,full.defects);
  if(dif){s.cols=colsFromDefs(full.defects);s.idByOrder=full.idByOrder;s.dc=null;s.reread=dif;
    s.warns.push(`5-1 값이 Step 1 방식으로 읽은 값과 달라 Step 1 값으로 바꿈(${dif.text}) — 5-1 md: ${s.mdPath||'없음'} · Step 1 md: ${s.mdStep1||'없음'}`)}
})().catch(e=>{s.warns.push('Slot 읽기 실패: '+e.message);s.full=s.full||{failed:true}}))}
function ensureImg(s){return fullLoad(s)}
/** rev4: 5-1 열 배열 ↔ Step 1 Defect 값(COLS 필드 전부). 같으면 null, 다르면 {n0, n1, fields:{필드: 다른 개수}, text}. */
function colsDiff(C,defs){const n1=defs.length,fields={};
  if(!C||C.n!==n1)return {n0:C?C.n:0,n1,fields,text:`Defect 수 ${C?C.n:0} → ${n1}`};
  for(const [k,name] of COLS){const a=C[k];let m=0;
    for(let i=0;i<n1;i++){const e=+(defs[i][name]??0),v=a[i];if(v===e||(v!==v&&e!==e))continue;if(!(Math.abs(v-e)<=1e-3*Math.max(1,Math.abs(e))))m++}
    if(m)fields[name]=m}
  return Object.keys(fields).length?{n0:C.n,n1,fields,text:Object.entries(fields).map(([k,v])=>`${k} ${v}개`).join(' · ')}:null}
/** Step 1 Defect 배열 → 5-1 열 배열(같은 COLS 형식). */
function colsFromDefs(defs){const n=defs.length,C={n};for(const [k,name,T] of COLS){const a=C[k]=new T(n);for(let i=0;i<n;i++)a[i]=+(defs[i][name]??0)}return C}
function colorUrl(d){return ensureImg(d.scan).then(()=>{const c=linkColor(d,d.scan,S.o.ctol);if(!c)return null;
  const k=d.scan.id+'|'+lower(cleanName(c.c.file));let p=urlCache.get(k);if(!p){p=fileGet(d.scan,c.c.file).then(f=>f?URL.createObjectURL(f):null).catch(()=>null);urlCache.set(k,p)}return p})}
function grayBmp(scan,frame){const k=scan.id+'|'+lower(cleanName(frame.file));let p=bmpCache.get(k);
  if(!p){p=fileGet(scan,frame.file).then(f=>f?createImageBitmap(f):null).catch(()=>null);bmpCache.set(k,p)}return p}
const grayMemo=new Map();   // 보정 값이 바뀌면 비운다
/** Defect 의 Gray 위치 = 대규모 모드와 같은 geoHit(v14.4.1 #89). {frame, px, py, n, W, H, model} 또는 {reason}. */
function grayOf(d){const k=key(d)+'|'+S.o.coord;let g=grayMemo.get(k);if(!g){const G=d.scan&&d.scan.geo,h=G?geoHit(G,d.X,d.Y,d.recipe,d.frameIdx,d.xInFrame,d.yInFrame):null;g=h||{reason:geoWhy(G)};grayMemo.set(k,g)}return g}
/** Gray Crop 캔버스(가운데 = 결함, Defect 박스 = BoxWidth×BoxHeight × boxK — v14.4.1 찍은 사진 픽셀로) + GL 측정. 범위 밖이면 이유 글을 돌려준다. */
async function grayCrop(d,size){
  const g=grayOf(d);if(!g.frame)return {reason:g.reason};
  const bmp=await grayBmp(d.scan,g.frame);if(!bmp)return {reason:`Gray 이미지 없음: ${g.frame.file}`};
  const o=S.o,sx=bmp.width/(g.W||GEO_W),sy=bmp.height/(g.H||GEO_H),cx=g.px*sx,cy=g.py*sy;   // 프레임 크기 = 그 레시피의 것(geoSize)
  if(cx<0||cy<0||cx>=bmp.width||cy>=bmp.height)return {reason:'좌표 변환 보정 필요'};
  const c=o.crop,cv=document.createElement('canvas');cv.width=cv.height=size||320;const x=cv.getContext('2d',{willReadFrequently:true});
  x.fillStyle='#000';x.fillRect(0,0,cv.width,cv.height);x.imageSmoothingEnabled=false;
  const sc=cv.width/c;x.drawImage(bmp,cx-c/2,cy-c/2,c,c,0,0,cv.width,cv.height);
  // GL 측정: 원 해상도 crop 에서(표시 배율 없이)
  const raw=document.createElement('canvas');raw.width=raw.height=c;const rx=raw.getContext('2d',{willReadFrequently:true});rx.drawImage(bmp,cx-c/2,cy-c/2,c,c,0,0,c,c);
  const bk=boxK(d),bw=Math.max(1,(d.BoxWidth||4)*bk*sx),bh=Math.max(1,(d.BoxHeight||4)*bk*sy);d.gl=measureGL(rx.getImageData(0,0,c,c),c/2,c/2,bw,bh,o.ring);
  x.strokeStyle='#ff2d2d';x.lineWidth=2;x.strokeRect(cv.width/2-bw*sc/2,cv.height/2-bh*sc/2,bw*sc,bh*sc);
  return {canvas:cv,g};
}
/** ROI mean/median/max, 주변 ring median, ROI−ring delta. 장비 Contrast 와 같다고 보지 않는다(Local Reference 추정). */
function measureGL(img,cx,cy,bw,bh,ring){
  const roi=[],rg=[],W=img.width,H=img.height,p=img.data;
  const x0=cx-bw/2,x1=cx+bw/2,y0=cy-bh/2,y1=cy+bh/2;
  for(let y=Math.max(0,Math.floor(y0-ring));y<Math.min(H,Math.ceil(y1+ring));y++)for(let x=Math.max(0,Math.floor(x0-ring));x<Math.min(W,Math.ceil(x1+ring));x++){
    const k=(y*W+x)*4,v=Math.round(.299*p[k]+.587*p[k+1]+.114*p[k+2]),inR=x+.5>=x0&&x+.5<=x1&&y+.5>=y0&&y+.5<=y1;(inR?roi:rg).push(v)}
  const med=a=>{if(!a.length)return null;const s=[...a].sort((u,v)=>u-v),m=s.length>>1;return s.length%2?s[m]:(s[m-1]+s[m])/2};
  const mean=roi.length?roi.reduce((u,v)=>u+v,0)/roi.length:null,ringMed=med(rg);
  return {mean,median:med(roi),max:roi.length?Math.max(...roi):null,ring:ringMed,delta:mean!=null&&ringMed!=null?mean-ringMed:null,n:roi.length}}

// ════════════════════════════════════════════════════════════════════════
// 10. Wafer Map (Canvas, requestAnimationFrame)
// ════════════════════════════════════════════════════════════════════════
const COL={keep:'--keep',gone:'--gone',new:'--new'};
/** v14.3.12(#82 후속, 소유자 2026-11-18 "사용자가 die 위치를 읽을 때는 웨이퍼 맵 기준 — 웨이퍼 맵 표시할 때는 웨이퍼 맵 기준으로 계산해서 표시해").
 *  종전(#50 ~ #69) 계산(중심 추정 · 네 모서리 원 규칙 · 샘플 맵 자리 맞추기 sampleFit · Notch 고르기)은 모두 지웠다.
 *  그림 · 번호 = Export Wafer Map(RowData)과 같게 — 실제 결과 폴더 3장 + Export 맵 2개로 확인:
 *   · RowData 첫 줄(맨 위) = 장비 Row 가장 작은 줄(rMin), 맨 왼쪽 칸 = 장비 Col 가장 작은 칸(cMin), 범위 = ProductInfo [ExportData] cMin~cMax · rMin~rMax(= s_DieLocation 범위).
 *   · 번호: X = Col − cMin(왼쪽 0 → 오른쪽), Y = rMax − Row(아래 0 → 위) — 'Wafer Map 수정하기' 탭 그림과 같은 읽는 법. 장비 Col/Row 는 마우스 · 상세 창에만.
 *   · 장비 Col = floor(X / XDieIndex), Row = floor(Y / YDieIndex)(dieOf — Color 이미지 Col/Row 와 278/278 일치).
 *   · Die = s_DieLocation.dat(장비가 스캔한 Die)만. 없으면 Die 를 그리지 않는다('300 mm 원 안' 규칙은 작은 die 에서 122칸 더 나와 쓰지 않음).
 *   · Defect 가 있는 Die = 그 지도에 찍힌 Defect 점이 들어 있는 Die — 다른 색(연한 남색, 소유자 2026-11-19 "간단하게 defect 위치가 있는 die 는 다른 색").
 *     v14.3.12 ~ 13 의 '불량 Die'(reclassify ≠ 0 · 리뷰 끝 · ScanLog BadDies 확인)는 지웠다 — 리뷰 전 Slot 에서 맞지 않았다.
 *   · wafer 원 = 300 mm, 중심 = Wafer2Table.ini 역변환 → ProductInfo CenterX/Y → Die 묶음 가운데(원은 그림일 뿐 — Die · 번호에는 안 씀).
 *   · Notch: Flat Pos 3 = 아래(소유자 확인). 다른 값은 미확인 — Notch 를 그리지 않고 오른쪽 위 태그로 알린다(태그 = Flat Pos · Notch 방향, 모든 wafer map).
 *  Lot 별(여러 Slot 겹쳐 그림): Slot 마다 자기 cMin · rMax 로 맵 좌표로 바꿔 겹친다(같은 device 라도 Slot 마다 장비 Row 가 1칸 다를 수 있음). */
const WAFER_R=150000;
function mapFrame(s){
  if(!s)return null;if(s._mf!==undefined)return s._mf;const p=s.product;if(!p)return s._mf=null;
  let cells=null,box=null;
  if(s.dieLoc&&s.dieLoc.length){cells=new Set();let c0=Infinity,c1=-Infinity,r0=Infinity,r1=-Infinity;
    for(const d of s.dieLoc){const q=dieOf(d.x,d.y,p);cells.add(q.col+','+q.row);if(q.col<c0)c0=q.col;if(q.col>c1)c1=q.col;if(q.row<r0)r0=q.row;if(q.row>r1)r1=q.row}
    box={cMin:c0,cMax:c1,rMin:r0,rMax:r1}}
  const ex=p.exp,warns=[];let f=null,src='';
  if(ex){f=ex;src='ProductInfo [ExportData]';
    if(box&&(box.cMin!==ex.cMin||box.cMax!==ex.cMax||box.rMin!==ex.rMin||box.rMax!==ex.rMax))warns.push(`[ExportData] Col ${ex.cMin}~${ex.cMax} · Row ${ex.rMin}~${ex.rMax} ≠ s_DieLocation Col ${box.cMin}~${box.cMax} · Row ${box.rMin}~${box.rMax}`)}
  else if(box){f=box;src='s_DieLocation 범위([ExportData] 없음)'}
  let cx=null,cy=null,csrc='';
  if(s.w2t){cx=s.w2t.x;cy=s.w2t.y;csrc='Wafer2Table'}
  else if(p.centerX&&p.centerY){cx=p.centerX;cy=p.centerY;csrc='ProductInfo'}
  else if(box){cx=(box.cMin+box.cMax+1)*p.pitchX/2+p.offX;cy=(box.rMin+box.rMax+1)*p.pitchY/2+p.offY;csrc='Die 묶음 가운데'}
  return s._mf={p,px:p.pitchX,py:p.pitchY,...(f||{}),ok:!!f,src,cells,cx,cy,csrc,flat:p.flatPos,warns};
}
/** Wafer 좌표(µm) → {x, y = 웨이퍼 맵 번호(없으면 null), col, row = 장비 번호, dx, dy = Die 안 위치(맵 방향, 그 Die 왼쪽 아래에서 µm), inDie}. */
function mapDie(X,Y,s){const f=mapFrame(s);if(!f||X==null||Y==null||!isFinite(X)||!isFinite(Y))return null;const q=dieOf(X,Y,f.p);if(!q)return null;
  const o={col:q.col,row:q.row,dx:q.dx,dy:f.py-q.dy,x:null,y:null,inDie:f.cells?f.cells.has(q.col+','+q.row):null};
  if(f.ok){o.x=q.col-f.cMin;o.y=f.rMax-q.row;if(o.inDie==null)o.inDie=q.col>=f.cMin&&q.col<=f.cMax&&q.row>=f.rMin&&q.row<=f.rMax}
  return o}
/** 화면 · 목록에 쓰는 Die 글 = 맵 번호 'X, Y'(맵 기준을 못 정하면 장비 번호를 이름 붙여). 장비 번호 글은 마우스 · 상세 창용. */
const dieTxt=m=>m?(m.x!=null?`${m.x}, ${m.y}`:`장비 Col ${m.col}, Row ${m.row}`):'-';
const dieEq=m=>m?`장비 Col ${m.col}, Row ${m.row}`:'';
/** 맵 그림 좌표(µm): 맵 왼쪽 아래 = (0, 0), 오른쪽 · 위쪽이 + (장비 Y 가 커지면 화면에서는 아래로). */
function toMap(X,Y,f){return f&&f.ok?[X-f.p.offX-f.cMin*f.px,(f.rMax+1)*f.py-(Y-f.p.offY)]:[X,-Y]}
const scanOfPt=it=>it&&(it.s||(it.d&&it.d.scan)||(it.q&&(it.q.s||(it.q.d&&it.q.d.scan))))||null;
const FLAT_DIR={3:'아래'};   // 소유자가 확인한 값만(2026-11-18: Flat Pos 3 = Notch 아래). 다른 값은 '미확인'.
function flatTag(vals){const v=[...vals].sort((a,b)=>a-b);if(!v.length)return {txt:'Flat Pos ? · Notch 미확인',down:false,ok:false};
  if(v.length>1)return {txt:`Flat Pos ${v.join(', ')} 섞임 · Notch 미확인`,down:false,ok:false};
  const d=FLAT_DIR[v[0]];return d?{txt:`Flat Pos ${v[0]} · Notch ↓ ${d}`,down:true,ok:true}:{txt:`Flat Pos ${v[0]} · Notch 미확인`,down:false,ok:false}}
/** 지금 비교의 맵(그릴 때마다 다시 세지 않게 기억 — runCompare · selectPair 에서 지움). */
function mapGeom(){if(S._mg)return S._mg;
  const ws=(S.cmpScans||[]).flatMap(v=>v.isLot?v.wafers:[v]),F=ws.map(w=>[w,mapFrame(w)]).filter(x=>x[1]&&x[1].ok),warns=[];
  const g={frames:F,dies:new Set(),px:null,py:null,cols:0,rows:0,cx:null,cy:null,flat:new Set(),warns,noLoc:0,noFrame:ws.length-F.length,outDie:0,n:0};
  for(const w of ws){const f=mapFrame(w);if(f&&f.flat!=null)g.flat.add(f.flat)}
  if(F.length){const f0=F[0][1];g.px=f0.px;g.py=f0.py;let ax=0,ay=0,an=0;const sizes=new Set();
    for(const [w,f] of F){const nm=w.slotName||w.name;
      if(Math.abs(f.px-g.px)>1||Math.abs(f.py-g.py)>1)warns.push(`${nm}: Die Pitch 가 다름`);
      g.cols=Math.max(g.cols,f.cMax-f.cMin+1);g.rows=Math.max(g.rows,f.rMax-f.rMin+1);sizes.add((f.cMax-f.cMin+1)+'×'+(f.rMax-f.rMin+1));
      if(f.cells)for(const k of f.cells){const [c,r]=k.split(',').map(Number);g.dies.add((c-f.cMin)+','+(f.rMax-r))}else g.noLoc++;
      if(f.cx!=null){const [mx,my]=toMap(f.cx,f.cy,f);ax+=mx;ay+=my;an++}
      for(const m of f.warns)warns.push(`${nm}: ${m}`)}
    if(sizes.size>1)warns.push(`Slot 마다 맵 크기가 다름(${[...sizes].join(', ')})`);
    if(an){g.cx=ax/an;g.cy=ay/an}else{g.cx=g.cols*g.px/2;g.cy=g.rows*g.py/2}}
  for(const d of S.allPts||[]){const m=mapDie(d.X,d.Y,d.scan);if(!m||m.x==null)continue;g.n++;if(g.dies.size&&!g.dies.has(m.x+','+m.y))g.outDie++}
  return S._mg=g}
/** 맵 그림 좌표 점들([mx, my]) → 그 점이 든 맵 Die 칸 'x,y' 모음(s_DieLocation Die 만). Defect 있는 Die 색칠용. */
const DIE_DEF_ALPHA=.22;
function ptDieKeys(xy,g){const out=new Set();if(!g||!g.px)return out;for(const [mx,my] of xy){const k=Math.floor(mx/g.px)+','+Math.floor(my/g.py);if(g.dies.has(k))out.add(k)}return out}
/** cv 에 wafer map 을 그린다: wafer 원 · Die(웨이퍼 맵 기준) · 맵 범위 · Notch · Flat Pos 태그 · Defect 점.
 *  opt.pts = [{X, Y(Wafer 좌표 µm), c(색 또는 '--변수'), r(반지름), ring(속 빈 원), q(누르면 돌려줄 것), s(그 점의 Slot — 없으면 q · d 에서)}], opt.hl = 강조, opt.on = 깜빡임 켜짐.
 *  다른 창(새 창 wafer map)의 canvas 에도 그린다 — 색은 이 문서의 CSS 변수에서 읽는다. 점 위치 목록 [x, y, q](화면 px)를 돌려준다. */
function paintMap(cv,opt){
  opt=opt||{};const r=cv.getBoundingClientRect(),dpr=(cv.ownerDocument.defaultView||window).devicePixelRatio||1;
  if(r.width<2||r.height<2)return null;   // 숨은 화면 — 보일 때 다시 그린다
  cv.width=r.width*dpr;cv.height=r.height*dpr;const x=cv.getContext('2d');x.setTransform(dpr,0,0,dpr,0,0);x.clearRect(0,0,r.width,r.height);
  if(!S.cmp)return null;
  const css=getComputedStyle(document.documentElement),cl=n=>css.getPropertyValue(n).trim(),col=c=>c&&c.startsWith('--')?cl(c):c;
  const g=mapGeom(),fr=new Map(g.frames),f0=g.frames.length?g.frames[0][1]:null;
  const pos=it=>{const s=scanOfPt(it);return toMap(it.X,it.Y,s?fr.get(s)||null:f0)};
  const pts=(opt.pts||[]).map(it=>[pos(it),it]);
  let vx0=Infinity,vy0=Infinity,vx1=-Infinity,vy1=-Infinity;
  if(g.px){vx0=Math.min(0,g.cx-WAFER_R);vy0=Math.min(0,g.cy-WAFER_R);vx1=Math.max(g.cols*g.px,g.cx+WAFER_R);vy1=Math.max(g.rows*g.py,g.cy+WAFER_R)}
  for(const [[X,Y]] of pts){if(X<vx0)vx0=X;if(Y<vy0)vy0=Y;if(X>vx1)vx1=X;if(Y>vy1)vy1=Y}
  if(!isFinite(vx0)){vx0=vy0=0;vx1=vy1=1}
  const pad=22,top=34,w=Math.max(vx1-vx0,1),h=Math.max(vy1-vy0,1),k=Math.max(1e-9,Math.min((r.width-2*pad)/w,(r.height-pad-top)/h)),ox=(r.width-w*k)/2,oy=top+(r.height-pad-top-h*k)/2;
  const PX=v=>ox+(v-vx0)*k,PY=v=>oy+h*k-(v-vy0)*k;
  const T=flatTag(g.flat);let hit=false;
  if(g.px){const R=WAFER_R*k,cx=PX(g.cx),cy=PY(g.cy);
    x.fillStyle=cl('--chip');x.globalAlpha=.55;x.beginPath();x.arc(cx,cy,R,0,7);x.fill();x.globalAlpha=1;
    // Die = s_DieLocation(웨이퍼 맵 칸). Defect 가 있는 Die(이 지도에 찍힌 점이 든 Die) = 다른 색(흰 바탕 위 연한 남색)
    const pw=g.px*k,ph=g.py*k,gp=pw>=6?.8:0,die=cl('--panel'),hasD=ptDieKeys(pts.map(q=>q[0]),g);hit=[...hasD].some(k2=>g.dies.has(k2));
    for(const key of g.dies){const [ix,iy]=key.split(',').map(Number),rx=PX(ix*g.px)+gp,ry=PY((iy+1)*g.py)+gp;x.fillStyle=die;x.fillRect(rx,ry,pw-2*gp,ph-2*gp);
      if(hasD.has(key)){x.fillStyle=cl('--navy');x.globalAlpha=DIE_DEF_ALPHA;x.fillRect(rx,ry,pw-2*gp,ph-2*gp);x.globalAlpha=1}}
    if(pw>=4&&g.dies.size){x.strokeStyle=cl('--sub');x.globalAlpha=.5;x.lineWidth=.8;x.beginPath();
      for(const key of g.dies){const [ix,iy]=key.split(',').map(Number);x.rect(PX(ix*g.px)+gp,PY((iy+1)*g.py)+gp,pw-2*gp,ph-2*gp)}x.stroke();x.globalAlpha=1}
    x.strokeStyle=cl('--sub');x.lineWidth=1.2;x.beginPath();x.arc(cx,cy,R,0,7);x.stroke();
    // 맵 범위(ROWCT × COLCT, 점선) · 왼쪽 아래 = X 0 · Y 0
    x.setLineDash([5,4]);x.strokeRect(PX(0),PY(g.rows*g.py),g.cols*g.px*k,g.rows*g.py*k);x.setLineDash([]);
    x.fillStyle=cl('--sub');x.font='11px sans-serif';x.fillText('(0,0)',PX(0)+3,PY(0)-4);
    if(!g.dies.size){x.fillStyle=cl('--err');x.font='bold 12px sans-serif';x.fillText('s_DieLocation.dat 없음 — Die 를 그리지 않음',8,r.height-8)}
    // Notch = Flat Pos 3 만 아래(소유자 확인). 다른 값은 그리지 않는다(태그로 '미확인').
    if(T.down){const ex=cx,ey=cy+R,d=Math.max(8,Math.min(16,R*.06)),wd=d*.75;
      x.beginPath();x.moveTo(ex-wd,ey+1.5);x.lineTo(ex,ey-d);x.lineTo(ex+wd,ey+1.5);x.closePath();x.fillStyle=cl('--panel');x.fill();
      x.strokeStyle=cl('--ink');x.lineWidth=1.4;x.beginPath();x.moveTo(ex-wd,ey);x.lineTo(ex,ey-d);x.lineTo(ex+wd,ey);x.stroke();
      x.fillStyle=cl('--ink');x.font='bold 11px sans-serif';x.textAlign='center';x.textBaseline='top';x.fillText('Notch',ex,Math.min(ey+3,r.height-13));x.textAlign='start';x.textBaseline='alphabetic'}}
  // 오른쪽 위 태그 = Flat Pos · Notch 방향(다른 값이 나오면 바로 보이게 — 소유자)
  x.font='bold 12px sans-serif';const tw=x.measureText(T.txt).width+18,th=22,tx=Math.max(4,r.width-tw-8),ty=6;
  x.fillStyle=T.ok?cl('--navy'):cl('--warnbg');x.beginPath();if(x.roundRect)x.roundRect(tx,ty,tw,th,11);else x.rect(tx,ty,tw,th);x.fill();
  if(!T.ok){x.strokeStyle=cl('--warn');x.lineWidth=1;x.stroke()}
  x.fillStyle=T.ok?'#fff':cl('--warn');x.textBaseline='middle';x.fillText(T.txt,tx+9,ty+th/2+.5);x.textBaseline='alphabetic';
  S.mapTag=T.txt;
  // 왼쪽 위 = Die 색 설명: □ Die(흰색) · ■ Defect 있는 Die(연한 남색). 오른쪽 위 Flat Pos 태그와 겹치면 안 그림
  if(g.dies.size){const items=[['Die',null]];if(hit)items.push(['Defect 있는 Die',DIE_DEF_ALPHA]);x.font='12px sans-serif';const sw=12;
    const need=items.reduce((a,[l])=>a+sw+14+x.measureText(l).width,0);
    if(8+need<tx-8){let lx=8;const ly=ty+th/2;x.textBaseline='middle';
      for(const [l,a] of items){x.fillStyle=cl('--panel');x.fillRect(lx,ly-sw/2,sw,sw);if(a){x.fillStyle=cl('--navy');x.globalAlpha=a;x.fillRect(lx,ly-sw/2,sw,sw);x.globalAlpha=1}
        x.strokeStyle=cl('--sub');x.lineWidth=.8;x.strokeRect(lx+.5,ly-sw/2+.5,sw-1,sw-1);x.fillStyle=cl('--ink');x.fillText(l,lx+sw+5,ly+.5);lx+=sw+14+x.measureText(l).width}
      x.textBaseline='alphabetic'}}
  const P=[];
  for(const [[X0,Y0],it] of pts){const X=PX(X0),Y=PY(Y0),rr=it.r||3;P.push([X,Y,it.q||it]);x.beginPath();x.arc(X,Y,rr,0,7);
    if(it.ring){x.strokeStyle=col(it.c);x.lineWidth=1.6;x.stroke()}else{x.fillStyle=col(it.c);x.fill()}}
  if(opt.hl){const [h0,h1]=pos(opt.hl),X=PX(h0),Y=PY(h1);
    if(opt.on){x.strokeStyle='#ff2d2d';x.lineWidth=3;x.beginPath();x.arc(X,Y,11,0,7);x.stroke();x.fillStyle='#ffd23f';x.beginPath();x.arc(X,Y,5.5,0,7);x.fill()}
    else{x.strokeStyle=cl('--ink');x.lineWidth=1.5;x.beginPath();x.arc(X,Y,7,0,7);x.stroke()}}
  return P;
}
addEventListener('resize',()=>{if(S.cmp)repaintAll()});
function hit(e,geo,cv){if(!geo||!cv)return null;const r=cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;let best=null,bd=64;
  for(const [X,Y,q] of geo){const dd=(X-mx)**2+(Y-my)**2;if(dd<=bd){bd=dd;best=q}}return best}
let tipFor=null;
/** wafer map 위 마우스 = 상세 + Color · Gray 미리 보기(Step 3 · 4 공용). geo() = 그 canvas 의 점 목록. */
function attachTip(cv,geo){
  cv.addEventListener('mousemove',e=>{const q=hit(e,geo(),cv),tip=$('#tip');if(!q||!q.d){tip.style.display='none';tipFor=null;return}
    tip.style.display='block';tip.style.left=Math.min(e.clientX+16,innerWidth-580)+'px';tip.style.top=Math.min(e.clientY+16,innerHeight-300)+'px';
    if(tipFor===q)return;tipFor=q;const x=info(q);
    tip.innerHTML=`<b>${esc(x.st)}</b> · <b>ID ${x.id}</b> · ${esc(x.step)} · Slot ${esc(x.slot||'-')} · 호기 ${esc(x.tool||'-')}<br>
      Wafer X/Y ${f1(x.X)}, ${f1(x.Y)} µm · Die(맵 X, Y) ${x.die}${x.dieEq?` · ${x.dieEq}`:''}${x.dieXY?` (Die 안 ${x.dieXY} µm)`:''}<br>Area ${fv(x.area)} µm² · Box ${x.box} px · Contrast(실제) ${fv(x.contrast)}${x.cmpContrast!=null?' → '+fv(x.cmpContrast):''}
      <div class="imgs"><img alt="Color"><canvas width="200" height="150"></canvas></div>`;
    colorUrl(q.d).then(u=>{if(tipFor!==q)return;const im=tip.querySelector('img');if(u)im.src=u;else im.alt='Color 없음'});
    grayCrop(q.d,300).then(r=>{if(tipFor!==q)return;const cv=tip.querySelector('canvas');if(r.canvas){cv.replaceWith(r.canvas);r.canvas.style.cssText='width:200px;height:150px;object-fit:contain'}
      else{const g=cv.getContext('2d');g.fillStyle='#000';g.fillRect(0,0,200,150);g.fillStyle='#ffd2d2';g.font='13px sans-serif';g.fillText(r.reason,8,78)}})});
  cv.addEventListener('mouseleave',()=>{$('#tip').style.display='none';tipFor=null});
}


// ════════════════════════════════════════════════════════════════════════
// 11. 리뷰 패널 (Para #55 — Step 3 · 4 공용): wafer map(깜빡임 · 새 창 실시간 연동) + 목록 + Color/Gray 사진 + 정보
//     항목 = {d(사진 · 정보에 쓰는 Defect), X, Y, c(점 색), label(구분), tag(목록 글), members([Defect] — 여러 스캔에 있는 같은 Defect)}
// ════════════════════════════════════════════════════════════════════════
/** 필터 · 정렬 줄(Step 3 · 4 리뷰 패널, Step 5 공용). 값 = Contrast(실제) · Area(µm²) · Width · Length 의 최소 ~ 최대(빈 칸 = 제한 없음).
 *  비교 = 실제 값 그대로(#83 — 반올림 안 함, 6.4749 처럼 소수 셋째 자리 이상도 정확히). 목록에도 실제 값을 쓰므로 보이는 값을 그대로 넣으면 그 Defect 가 들어온다. */
const FLT_KEYS=[['c','Contrast(실제)',''],['a','Area',''],['w','Width',''],['l','Length','']];   // Area · Width 단위 = [µm 로 보기](fltUnit)
const SORTS=[['','기본 순서'],['c-d','Contrast(실제) 큰 순'],['c-a','Contrast(실제) 작은 순'],['a-d','Area 큰 순'],['a-a','Area 작은 순'],['w-d','Width 큰 순'],['w-a','Width 작은 순'],['l-d','Length 큰 순'],['l-a','Length 작은 순'],['r-a','Recipe 순'],['r-d','Recipe 이름 역순']];
const fltRngHtml=()=>FLT_KEYS.map(([k,t,u])=>`<label class="rng"><b>${t}</b> <input type="number" step="any" data-f="${k}0" placeholder="최소" aria-label="${t} 최소"> ~ <input type="number" step="any" data-f="${k}1" placeholder="최대" aria-label="${t} 최대">${k==='a'||k==='w'?` <span data-umu="${k}">${fltUnit(k)}</span>`:u?' '+u:''}</label>`).join('')+umCkHtml();
const fltRcpHtml=(b=true)=>`<label>${b?'<b>Recipe</b> ':''}<select data-f="rcp" aria-label="Recipe"><option value="">전체</option></select></label>`;
/** Zone 고르기(#83 후속): 값 = Surface.flt zone 번호 + Zones.ini 이름('3 (Bump)'), 리뷰PC 정보의 Zone 과 같은 글. */
const fltZnHtml=(b=true)=>`<label>${b?'<b>Zone</b> ':''}<select data-f="zn" aria-label="Zone"><option value="">전체</option></select></label>`;
const fltSortHtml=(b=true)=>`<label>${b?'<b>정렬</b> ':''}<select data-f="sort" aria-label="정렬">${SORTS.map(([v,n])=>`<option value="${v}">${n}</option>`).join('')}</select></label>`;
const fltClrHtml=()=>'<button data-f="clear">필터 지우기</button>';
function fltHtml(){return fltRngHtml()+fltRcpHtml()+fltZnHtml()+fltSortHtml()+fltClrHtml()}
function readFlt(box){const v=k=>{const el=box.querySelector(`[data-f="${k}"]`),t=el?el.value.trim():'';return t===''||!isFinite(+t)?null:+t},f={sort:box.querySelector('[data-f="sort"]').value,on:false};
  for(const [k] of FLT_KEYS){f[k+'0']=v(k+'0');f[k+'1']=v(k+'1');if(f[k+'0']!=null||f[k+'1']!=null)f.on=true}
  const rc=box.querySelector('[data-f="rcp"]');f.rcp=rc?rc.value:'';if(f.rcp)f.on=true;
  const zn=box.querySelector('[data-f="zn"]');f.zn=zn?zn.value:'';if(f.zn)f.on=true;return f}
const inR=(v,lo,hi)=>{if(lo==null&&hi==null)return true;v=exv(v);return (lo==null||v>=lo)&&(hi==null||v<=hi)};   // 값이 없으면(NaN) 범위를 건 필터에서 빠진다
const fltPass=(f,c,a,w,l)=>inR(c,f.c0,f.c1)&&inR(a,f.a0,f.a1)&&inR(w,f.w0,f.w1)&&inR(l,f.l0,f.l1);
/** Zone 글(#83 후속) = 번호 + 그 Slot Zones.ini 이름. 번호가 없으면 '-'. */
const zoneLbl=(z,s)=>{const r=s&&s.rv,n=r&&r.zones&&z!=null?r.zones.get(z):null;return withName(z,n)};
/** 필터 줄 입력 → fn(0.2초 모아서). [필터 지우기] = 범위만 비운다(정렬은 그대로). */
function fltBind(box,fn){let t=0;const run=()=>{clearTimeout(t);t=setTimeout(fn,200)};box.addEventListener('input',run);box.addEventListener('change',run);
  box.addEventListener('click',e=>{if(e.target.dataset.f!=='clear')return;box.querySelectorAll('input[data-f],select[data-f="rcp"],select[data-f="zn"]').forEach(el=>el.value='');clearTimeout(t);fn()})}
/** 값 범위 막대(Para para-skin.js — 소유자 2026-11-24 양방향 막대 + 숫자 칸)의 양 끝 = 그 필터 칸이 거르는 자료의 실제 최소 · 최대(지금 [µm 로 보기] 단위).
 *  필터 계산은 바꾸지 않는다(막대는 숫자 칸에 값을 적을 뿐). 키(c · a · w · l)마다 [최소, 최대], 자료가 없으면 null. 자료 · 단위가 같으면 다시 세지 않는다. */
function fltSpan(box){if(!box)return null;const big=box.id==='bigFlt',P=big?null:Object.values(PANELS).find(p=>p.el&&p.el('Flt')===box),src=big?bigSources():P&&P.raw;
  const key=big?src.map(s=>s.id+':'+s.cols.n).join('|'):src;if(box.__spanK===key&&box.__spanU===UM.on)return box.__span;
  const R={c:[Infinity,-Infinity],a:[Infinity,-Infinity],w:[Infinity,-Infinity],l:[Infinity,-Infinity]},put=(r,v)=>{if(v<r[0])r[0]=v;if(v>r[1])r[1]=v};   // NaN 은 비교에서 빠짐
  if(big)for(const s of src){const C=s.cols,[uA,uW]=umK(s);for(let i=0;i<C.n;i++){put(R.c,C.c[i]);put(R.a,C.area[i]*uA);put(R.w,C.w[i]*uW);put(R.l,C.l[i])}}
  else if(src)for(const it of src){const d=it.d,[uA,uW]=umK(d.scan);put(R.c,+d.Contrast);put(R.a,d.area*uA);put(R.w,d.BlobBreadth*uW);put(R.l,+d.BlobLength)}
  for(const k in R)if(!(R[k][0]<=R[k][1])||!isFinite(R[k][0])||!isFinite(R[k][1]))R[k]=null;else R[k]=R[k].map(exv);
  box.__spanK=key;box.__spanU=UM.on;return box.__span=R}
const RH=30,PANELS={};let blinkOn=true;
/** 2026-11-25 기본 모드 목록 열 = 대규모 5-1 · 5-2 목록 열(+ 구분 = 벤다이어그램 영역 · A → B 쌍 · O/X). Area · Width 제목 = [µm 로 보기](umHeads). */
const PCOLS=[['☑',46,'pk',null],['#',56,'num',null],['구분',150,'',null],['사진',150,'s',null],['Lot',140,'',null],['Slot',110,'',null],['ID',62,'num',null],
  ['장비 스캔 분류',140,'',null],['리뷰 결과',140,'',null],['Recipe',120,'','r'],['Contrast(실제)',112,'num','c'],['Area (µm²)',92,'num','a','a'],['Width (µm)',72,'num','w','w'],['Length',68,'num','l'],
  ['Box W×H',96,'',null],['Wafer X',96,'num',null],['Wafer Y',96,'num',null],['Die (맵 X, Y)',120,'',null],['흑백 GL (원)',100,'num','g'],['Color 이미지',220,'',null],['Gray 프레임 (픽셀)',260,'',null]];
/** 사진 상태(대규모 5-2 · 5-3 의 '보기'와 같은 4가지) = Color 이미지 연결 · Gray 프레임 유무. 한 번 구해 둔다. */
function panelPh(it){if(it.ph)return it.ph;const d=it.d,c=S.cmp?linkColor(d,d.scan,S.cmp.o.ctol):null,g=grayOf(d),gf=g&&g.frame;
  return it.ph={c,g,st:c&&gf?'ok':c?'color':gf?'gray':'none'}}
/** 분류 이름(대규모 clsFirst · clsName 과 같은 규칙): 1 = 장비 스캔 분류(orgReclassify, 0 이면 reclassify), 2 = 리뷰 결과(reclassify). */
const panelCls=(d,g)=>{const code=g===1?(d.orgReclassify||d.reclassify):d.reclassify,r=d.scan&&d.scan.rv;return codeName(code,r&&r.cls)||`#${code}`};
const PH_LAB={ok:'Color·Gray 매칭 완료',color:'Color 만',gray:'흑백(Gray) 만',none:'둘 다 없음'};
/** 필터 카드 = 대규모 5-1 필터와 같은 줄(.fgrid): 사진 · 장비 스캔 분류 · 리뷰 결과 · 값 범위 · Recipe · Zone · 정렬. */
function panelFltHtml(pre){
  return `<div class="card fgrid pflt" id="${pre}Flt" style="margin:12px 0 0" role="group" aria-label="목록 필터 · 정렬">
    <div class="frow"><span class="fh">사진</span><div class="fb"><span class="c5stF" title="사진 상태로 골라 보기(여러 개 켜면 모두 보임 — 대규모 5-3 보기와 같음)">${Object.entries(PH_LAB).map(([k,t])=>`<label><input type="checkbox" data-pst="${k}" checked> ${t} <i data-pn="${k}"></i></label>`).join('')}</span></div></div>
    <div data-pclsbox></div>
    <div class="frow"><span class="fh">값 범위</span><div class="fb frng">${fltRngHtml()}</div></div>
    <div class="frow"><span class="fh">Recipe</span><div class="fb">${fltRcpHtml(false)}</div></div>
    <div class="frow"><span class="fh">Zone</span><div class="fb">${fltZnHtml(false)}</div></div>
    <div class="frow"><span class="fh">정렬</span><div class="fb">${fltSortHtml(false)}</div></div>
    <div class="fact">${fltClrHtml()}</div><span class="muted">필터에 맞는 Defect 만 목록 · 사진에 나옵니다(맞지 않는 것은 지도에 회색 원).</span></div>`}
/** 분류 · 사진 칸의 개수 = 지금 목록(필터 전) 기준. 분류 칸 = 대규모 5-1 과 같은 모양(fChip). */
function panelFacet(P){const box=P.el('Flt'),c1=new Map(),c2=new Map(),n={ok:0,color:0,gray:0,none:0};
  for(const it of P.raw){const a=panelCls(it.d,1),b=panelCls(it.d,2);c1.set(a,(c1.get(a)||0)+1);c2.set(b,(c2.get(b)||0)+1);n[panelPh(it).st]++}
  box.querySelectorAll('[data-pn]').forEach(x=>x.textContent=`(${(n[x.dataset.pn]||0).toLocaleString()})`);
  const grp=(g,t,cnt,off)=>{const ks=[...new Set([...cnt.keys(),...off])].sort(natCmp);return `<div class="frow"><span class="fh">${t}</span><div class="fb">`+(ks.length?`<div class="chipgrid">${ks.map(k=>fChip('data-pcls'+g,k,k,cnt.get(k),off.has(k))).join('')}</div>`
    +(ks.length>1?`<div class="fx"><button type="button" data-pclsall="${g}">${off.size?'모두 켜기':'모두 끄기'}</button></div>`:''):'<span class="muted">비교를 실행하면 나옵니다</span>')+'</div></div>'};
  const h=grp(1,'장비 스캔 분류',c1,P.clsOff1)+grp(2,'리뷰 결과',c2,P.clsOff2),el=box.querySelector('[data-pclsbox]');if(el.__h!==h){el.innerHTML=h;el.__h=h}}
/** 표 한 줄(대규모 VA · VB 와 같은 값 · 글). */
function panelRow(P,k){const it=P.items[k];if(!it)return [];const d=it.d,s=d.scan,ph=panelPh(it),[uA,uW]=umK(s),ov=S.overlay[key(d)],g=ph.g,gf=g&&g.frame;
  return [pOn(P,it)?'☑':'☐',k+1,(it.tag||it.label||'')+(ov?' · '+ov:''),PH_LAB[ph.st],s.lotName||s.name||'',s.slotName||'',d.no??d.id,panelCls(d,1),panelCls(d,2),rcpName(d),fv(d.Contrast),fv(d.area*uA),fv(d.BlobBreadth*uW),fv(d.BlobLength),
    `${f1(d.BoxWidth)}×${f1(d.BoxHeight)}`,f1(it.X),f1(it.Y),dieTxt(mapDie(d.X,d.Y,s)),d.glv!=null?d.glv.toFixed(1):d.glErr?'못 잼':'',ph.c&&ph.c.c?ph.c.c.file:'-',gf?`${gf.file} (${f1(g.px)}, ${f1(g.py)})`:(g&&g.reason)||'-']}
/** 열 제목 정렬 = 정렬 칸(data-f="sort")과 같은 값 — 같은 열을 다시 누르면 반대로(대규모 sortClick 과 같음). */
function panelSort(P,k){const sel=P.el('Flt').querySelector('[data-f="sort"]');
  if(k==='g'){P.gsort=P.gsort==='d'?'a':'d';sel.value='';applyPanel(P,true);return}   // 흑백 GL 열(5-3 과 같이 큰 순 먼저)
  P.gsort='';const [sk,sd]=(sel.value||'').split('-');sel.value=k+'-'+(k===sk?(sd==='d'?'a':'d'):(/^[cawl]$/.test(k)?'d':'a'));applyPanel(P,true)}
// ── 2026-11-25(소유자 "Defect Map 에도 5-3 기능 넣어"): 최종 목록 · 흑백 GL — 대규모 5-3 과 같은 규칙 · 같은 파일 형식 ─────────────────
//   최종 목록 = 이 목록(필터 · 검색 · GL 범위)에 보이고 ☑ 인 줄. 엑셀 = XL_COLS(+ [원본 이미지로 저장] = xlCols(true)), CSV = FL_HEAD(Para [Color·Gray 매칭] 이 읽는 최종 목록 CSV),
//   zip = color/ · gray/ · gray crop/(원본 바이트 · Crop PNG). 흑백 GL = 최종 목록(☑) 중 흑백 사진이 있는 Defect, 반지름 = 5-3 과 같은 값(GLC.r). 값은 Defect(d.glp · d.glv)에 둔다.
const pFin=P=>P.items.filter(it=>pOn(P,it));
function panelFinHtml(pre){
  return `<div class="card c5stbox pfin" id="${pre}Fin" style="margin:12px 0 0" role="group" aria-label="최종 목록 · 흑백 GL">
    <div class="row c5pickrow"><b>최종 목록</b><span class="c5pick" id="${pre}FinN">☑ 0개</span>
      <button class="pri" id="${pre}Xlsx" disabled>💾 최종 목록 엑셀 저장 (사진 포함)</button><button id="${pre}FlCsv" disabled>📄 최종 목록 CSV 저장</button><button id="${pre}Zip" disabled>🗂 최종 목록 사진 파일.zip 저장</button>
      <label title="켜면 Color 열 = Color 원본 파일, Gray 프레임 뒤에 흑백 원본 2열(5-3 과 같음)"><input type="checkbox" data-xlorig> 원본 이미지로 저장</label></div>
    <div class="row"><b>흑백 GL (원) 측정</b><label>반지름 <input type="number" data-glr min="0.5" step="0.5" style="width:76px" aria-label="흑백 GL 반지름 px"> px</label>
      <button id="${pre}Gl" disabled>흑백 GL 측정 (☑ 만)</button>
      <label>GL 범위 <input type="number" data-glo min="0" max="255" step="any" placeholder="0" style="width:70px" aria-label="GL 최소"> ~ <input type="number" data-ghi min="0" max="255" step="any" placeholder="255" style="width:70px" aria-label="GL 최대"></label>
      <span class="muted" id="${pre}GlSt"></span></div>
    <div class="muted" id="${pre}FinSt"></div></div>`}
/** GL 범위 칸 → [lo, hi] 또는 null(비었으면 · 0 ~ 255 면 걸지 않음). 범위를 걸면 아직 안 잰 Defect 는 목록에서 빠진다(5-3 과 같음). */
function panelGlRange(P){const b=P.el('Fin');if(!b)return null;const v=k=>{const t=b.querySelector(`[data-${k}]`).value.trim();return t===''||!isFinite(+t)?null:+t};
  let lo=v('glo'),hi=v('ghi');if(lo==null&&hi==null)return null;lo=lo??0;hi=hi??255;if(lo>hi)[lo,hi]=[hi,lo];return lo<=0&&hi>=255?null:[lo,hi]}
function pFinInfo(P){const n=pFin(P).length,ng=pFin(P).filter(it=>panelPh(it).g&&panelPh(it).g.frame).length,b=k=>P.el(k);if(!b('Fin'))return;
  b('FinN').textContent=`☑ ${n.toLocaleString()} / ${P.items.length.toLocaleString()}개`;b('FinN').classList.toggle('on',n>0);
  for(const k of ['Xlsx','FlCsv','Zip'])b(k).disabled=!n;b('Gl').disabled=!ng;
  b('Xlsx').textContent=n?`💾 최종 목록 엑셀 저장 (☑ ${n.toLocaleString()}개 · 사진 포함)`:'💾 최종 목록 엑셀 저장 (사진 포함)';b('Gl').textContent=`흑백 GL 측정 (☑ 만${ng?` · ${ng.toLocaleString()}개`:''})`;
  const o=b('Fin').querySelector('[data-xlorig]');if(o)o.checked=XLO.on;const r=b('Fin').querySelector('[data-glr]');if(r&&document.activeElement!==r)r.value=GLC.r}
/** 파일 → 원본 사진(xlOrig 와 같은 규칙: JPEG · PNG 는 바이트 그대로, 그 밖은 같은 픽셀 PNG). */
async function fileOrig(f){if(!f)return null;try{const data=new Uint8Array(await f.arrayBuffer()),bm=await createImageBitmap(f),w=bm.width,h=bm.height;
    const ext=data[0]===0xff&&data[1]===0xd8?'jpeg':data[0]===0x89&&data[1]===0x50&&data[2]===0x4e&&data[3]===0x47?'png':'';
    if(ext){bm.close&&bm.close();return {data,w,h,ext,orig:true}}
    const cv=document.createElement('canvas');cv.width=w;cv.height=h;cv.getContext('2d').drawImage(bm,0,0);bm.close&&bm.close();
    const pb=await new Promise(r=>cv.toBlob(r,'image/png'));return {data:new Uint8Array(await pb.arrayBuffer()),w,h,ext:'png',orig:true}}catch(e){return null}}
const baseFile=async(s,name)=>{try{return await fileGet(s,name)}catch(e){return null}};
/** 한 줄의 사진(xlPhotos 와 같은 그림 — 칸 자료 = baseView, 새 창과 같음). */
async function baseXlPhotos(it,orig){const d=it.d,s=d.scan,v=baseView(it,0,0,null),o={c:null,g:null,f:null,gl:null,err:[]};
  if(v.c){const b=await v.c.bmp();if(b)o.c=await xlJpeg(b,960,720);else o.err.push(`Color 파일 없음: ${v.c.name}`)}else o.err.push(v.cwhy||'Color 없음');
  if(v.g){const b=await v.g.bmp();
    if(b){const k=cgCropCanvas(b,v.g.hit,v.g.crop,null,d);o.gl=cgGL(k,b,d);if(!d.glp){d.glp=glProfile(b,v.g.hit);d.glv=glMean(d)}o.g=await xlJpeg(k.canvas,960,720);o.f=await xlJpeg(cgFrameCanvas(b,v.g.hit,v.g.crop,null,d),1800,600);
      if(orig)o.go=await cropPng(k.raw)}
    else o.err.push(`Gray 파일 없음: ${v.g.name}`)}
  else o.err.push(v.gwhy);
  if(orig){if(v.c){o.co=await fileOrig(await baseFile(s,v.c.name));if(o.co)o.c=o.co;else o.err.push('Color 원본 못 읽음 — 줄인 사진')}if(v.g)o.fo=await fileOrig(await baseFile(s,v.g.name))}
  return o}
/** 엑셀 · CSV 한 줄(xlRow0 · flRow 와 같은 열 차례). '5-1 #' 칸 = 이 목록의 순서 번호. */
function baseFinCells(P,it){const d=it.d,s=d.scan,x=info({d,label:it.label||it.tag||''}),v=baseView(it,0,0,null),ph=panelPh(it),die=dieOf(d.X,d.Y,s.product),m=mapDie(d.X,d.Y,s),n=v=>Number.isFinite(v)?+v.toFixed(3):'',
    cn=v.c?v.c.name:'',gn=v.g?v.g.name:'',rv=(r=>[rawNum(r.zoneNo),r.region,rawNum(r.typeNo),rawNum(r.clsNo),r.zoneName,r.typeName])(rvInfo(d));
  return {no:P.items.indexOf(it)+1,lot:s.lotName||s.name||'',slot:s.slotName||'',id:d.no??d.id,k1:panelCls(d,1),k2:panelCls(d,2),rcp:rcpName(d),c:n(+d.Contrast),st:ST5[ph.st]||ph.st,area:n(x.area),w:n(+d.BlobBreadth),l:n(+d.BlobLength),
    bw:n(+d.BoxWidth),bh:n(+d.BoxHeight),X:n(d.X),Y:n(d.Y),die:die?`${die.col}, ${die.row}`:'-',map:m&&m.x!=null?`${m.x}, ${m.y}`:'-',cn,cp:cn?pcPath(v.c.path):'',gn,gp:gn?pcPath(v.g.path):'',g:v.g,dir:s.name||'',rv}}
function baseXlRow(P,it,o,orig){const c=baseFinCells(P,it),d=it.d,n=v=>Number.isFinite(v)?+v.toFixed(3):'';
  const R=[c.no,c.lot,c.slot,c.id,c.k1,c.k2,c.rcp,c.c,o.c?null:'(Color 사진 없음)',o.g?null:'(Gray 사진 없음)',o.f?null:'(Gray 사진 없음)',c.st,c.area,c.w,c.l,`${f1(d.BoxWidth)}×${f1(d.BoxHeight)}`,c.X,c.Y,c.die,c.map,
    o.gl?n(o.gl.delta):'',o.gl?n(o.gl.mean):'',c.cn,c.cp,c.gn,c.gp,o.err.join(' · '),c.dir,d.glv!=null?+d.glv.toFixed(2):'',d.glp?`${GLC.r} px · ${glCount(d)}픽셀`:'',...c.rv];
  if(orig)R.splice(XL_OI,0,o.go?null:'(원본 없음)',o.fo?null:'(원본 없음)');return R}
function baseFlRow(P,it){const c=baseFinCells(P,it),d=it.d,n=v=>Number.isFinite(v)?+v.toFixed(3):'',cs=c.g?c.g.crop:null;
  return [c.no,c.lot,c.slot,c.id,c.k1,c.k2,c.rcp,c.c,c.st,c.area,c.w,c.l,c.bw,c.bh,c.X,c.Y,c.die,c.map,d.glv!=null?+d.glv.toFixed(2):'',c.cn,c.cp,c.gn,c.gp,
    c.g?n(c.g.hit.px):'',c.g?n(c.g.hit.py):'',cs?cs.cw:'',cs?cs.ch:'',c.dir?pcPath(c.dir):'',c.dir,c.dir,...c.rv]}
async function baseSaveCsv(P){const L=pFin(P);if(!L.length)return;
  const parts=['\ufeff'+FL_HEAD.map(csvQ).join(',')+'\r\n',...L.map(it=>baseFlRow(P,it).map(csvQ).join(',')+'\r\n')];
  const msg=await saveCsv(parts,`최종목록_DefectMap_${stamp()}.csv`,true);P.el('FinSt').textContent=msg?`${msg} (Defect ${L.length}개)`:'저장 취소';return msg}
async function baseSaveXlsx(P){const L=pFin(P);if(!L.length)return;
  const name=`최종목록_DefectMap_${stamp()}.xlsx`,h=await pickSave(name,[{description:'Excel',accept:{'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':['.xlsx']}}]);if(h===false)return;
  BIG.stop=false;const orig=XLO.on,COLS=xlCols(orig),cancel=()=>{BIG.stop=true},total=L.length,rows=[],pics=[],STEPS=['① Defect 마다 사진 읽기 · 그리기(Color · Gray Crop · Gray 프레임)','② 엑셀 파일 만들기 · 저장'];let done=0,cur='',msg;
  const pr=throttle(()=>busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:0,done,total,unit:'Defect',files:`사진 ${pics.length}장`,detail:cur,cancel}),80);
  busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  try{for(const it of L){if(BIG.stop)break;cur=`${stepName(it.d.scan)} · ID ${it.d.no??it.d.id}`;pr();
      const o=await baseXlPhotos(it,orig),ri=rows.length+1;rows.push(baseXlRow(P,it,o,orig));COLS.forEach(([,,k],ci)=>{if(k&&o[k])pics.push({row:ri,col:ci,...o[k]})});done++;pr()}
    if(BIG.stop){msg=`중지 — 저장하지 않았습니다 (${done} / ${total} 개 준비)`;return msg}
    busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:1,done:total,total,unit:'Defect',files:`사진 ${pics.length}장`,detail:'xlsx 묶는 중',cancel});await nextPaint();
    const blob=xlsxBlob('최종 목록',COLS,rows,pics);
    if(h){const w=await h.createWritable();await w.write(blob);await w.close();msg=`저장: ${h.name} (Defect ${rows.length}개 · 사진 ${pics.length}장 · ${(blob.size/1048576).toFixed(1)} MB)`}
    else{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),5000);msg=`다운로드 폴더에 저장: ${name} (Defect ${rows.length}개 · 사진 ${pics.length}장)`}
  }catch(e){msg=`저장 실패: ${(e&&e.message)||e}`}
  finally{busy(null);P.el('FinSt').textContent=msg||'';applyPanel(P,true)}
  return msg}
async function baseSaveZip(P){const L=pFin(P);if(!L.length)return;
  const name=`최종목록_DefectMap_사진_${stamp()}.zip`,h=await pickSave(name,[{description:'ZIP',accept:{'application/zip':['.zip']}}]);if(h===false)return;
  BIG.stop=false;const cancel=()=>{BIG.stop=true},total=L.length,files=[],U={keys:new Set(),names:new Set()},cnt={color:0,gray:0,crop:0},miss=[],STEPS=['① Defect 마다 원본 사진 읽기(color · gray 복사, gray crop 자르기)','② zip 파일 만들기 · 저장'];let done=0,msg;
  busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  const pr=throttle(()=>busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:0,done,total,unit:'Defect',files:`파일 ${files.length}개`,detail:'',cancel}),80);
  try{for(const it of L){if(BIG.stop)break;const d=it.d,s=d.scan,v=baseView(it,0,0,null),sk=s.id;pr();
      if(v.c){const key=sk+'|'+lower(v.c.name);if(!U.keys.has('color/\u0000'+key)){const f=await baseFile(s,v.c.name);if(f){files.push([zipName(U,'color/',f.name||v.c.name,key),new Uint8Array(await f.arrayBuffer())]);cnt.color++}else miss.push(`Color ${v.c.name}`)}}
      if(v.g){const key=sk+'|'+lower(v.g.name);
        if(!U.keys.has('gray/\u0000'+key)){const f=await baseFile(s,v.g.name);if(f){files.push([zipName(U,'gray/',f.name||v.g.name,key),new Uint8Array(await f.arrayBuffer())]);cnt.gray++}else miss.push(`Gray ${v.g.name}`)}
        const bm=await v.g.bmp();
        if(bm){const k=cgCropCanvas(bm,v.g.hit,v.g.crop,null,null),c=await cropPng(k.raw),dot=v.g.name.lastIndexOf('.'),nm=(dot>0?v.g.name.slice(0,dot):v.g.name)+'.png',zn=zipName(U,'gray crop/',nm,key+'|'+v.g.hit.px+','+v.g.hit.py);
          if(zn){files.push([zn,c.data]);cnt.crop++}}}
      done++;pr()}
    if(BIG.stop){msg=`중지 — 저장하지 않았습니다 (${done} / ${total} 개 준비)`;return msg}
    if(!files.length){msg='저장할 사진 파일이 없습니다 (☑ Defect 의 원본 사진을 읽지 못함)';return msg}
    busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:1,done:total,total,unit:'Defect',files:`파일 ${files.length}개`,detail:'zip 묶는 중',cancel});await nextPaint();
    const blob=zipStore(files,'application/zip'),sum=`Defect ${total}개 · color ${cnt.color} · gray ${cnt.gray} · gray crop ${cnt.crop}개 · ${(blob.size/1048576).toFixed(1)} MB${miss.length?` · 못 읽음 ${miss.length}개`:''}`;
    if(h){const w=await h.createWritable();await w.write(blob);await w.close();msg=`저장: ${h.name} (${sum})`}
    else{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),5000);msg=`다운로드 폴더에 저장: ${name} (${sum})`}
  }catch(e){msg=`저장 실패: ${(e&&e.message)||e}`}
  finally{busy(null);P.el('FinSt').textContent=msg||''}
  return msg}
/** 흑백 GL 측정(glRun 과 같은 계산): ☑ 중 흑백 사진이 있고 아직 안 잰 Defect, 같은 Gray 프레임은 한 번만 읽는다. */
async function baseGlRun(P){const T=pFin(P).filter(it=>{const g=panelPh(it).g;return g&&g.frame}),L=T.filter(it=>!it.d.glp);
  if(!L.length){P.el('GlSt').textContent=T.length?'새로 잴 Defect 가 없습니다(☑ 의 흑백 사진은 모두 잼).':'☑ 에 흑백 사진이 있는 Defect 가 없습니다.';return}
  const G=new Map();for(const it of L){const g=panelPh(it).g,k=it.d.scan.id+'|'+lower(cleanName(g.frame.file));let e=G.get(k);if(!e)G.set(k,e={s:it.d.scan,frame:g.frame,ps:[]});e.ps.push({d:it.d,hit:g})}
  const F=[...G.values()],total=L.length,t0=performance.now(),STEPS=['① Gray 프레임 읽기 · 디코딩(같은 프레임은 한 번)','② 원 안 픽셀 평균(반지름 0.5 px 단계마다 기억)'];
  BIG.stop=false;let done=0,bad=0;const cancel=()=>{BIG.stop=true};
  const pr=throttle(()=>busy({title:'흑백 GL 측정',steps:STEPS,step:0,done,total,unit:'Defect',files:`Gray 프레임 ${F.length.toLocaleString()}장 · 못 잰 것 ${bad}`,detail:'',cancel}),80);
  busy({title:'흑백 GL 측정',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  try{for(let j=0;j<F.length;j++){if(BIG.stop)break;const f=F[j];pr();if(F[j+1])grayBmp(F[j+1].s,F[j+1].frame);
      const b=await grayBmp(f.s,f.frame);
      for(const {d,hit} of f.ps){if(b){d.glp=glProfile(b,hit);d.glv=glMean(d);d.glErr=null}else{d.glErr='흑백 사진 못 읽음';bad++}done++}
      pr();if(j%8===7)await nextPaint()}}
  finally{busy(null)}
  P.el('GlSt').textContent=`${BIG.stop?'중지 — ':''}☑ 측정 ${done.toLocaleString()}/${total.toLocaleString()}개 · 못 잰 것 ${bad} · ${((performance.now()-t0)/1000).toFixed(1)}초`;
  if(!P.gsort&&!P.el('Flt').querySelector('[data-f="sort"]').value)P.gsort='d';applyPanel(P,true)}
/** Step 3 새 창 왼쪽 = 벤다이어그램(클릭 = 영역 더하기/빼기, 빈 곳 = 고른 집합 전체). */
function mountVennSide(P,box){const doc=box.ownerDocument;box.innerHTML='<div class="cap">벤다이어그램 · 영역 클릭 = 더하기 · 다시 클릭 = 빼기 · 빈 곳 = 고른 집합 전체</div><canvas aria-label="벤다이어그램" style="cursor:pointer"></canvas>';
  const cv=box.querySelector('canvas');P.pop.vcv=cv;const at=e=>{const r=cv.getBoundingClientRect(),G=S.venn&&S.venn.popGeo;return G?vennMaskAt((e.clientX-r.left)*G.dpr,(e.clientY-r.top)*G.dpr,G):0};
  cv.addEventListener('click',e=>{if(S.venn&&S.venn.popGeo)pickRegion(at(e))});
  cv.addEventListener('mousemove',e=>{const m=at(e);cv.title=m?`${regLabel(m)} · Defect ${S.venn.counts.get(m)||0}개`:'빈 곳 클릭 = 고른 집합 전체'})}
/** Step 4 새 창 왼쪽 = A → B 간략 지도 2개(점 클릭 = 그 Defect). */
function mountEscSide(P,box){box.innerHTML='<div class="cap" data-k="a"></div><canvas aria-label="A 간략 지도"></canvas><div class="cap" data-k="b"></div><canvas aria-label="B 간략 지도"></canvas>';
  const cs=box.querySelectorAll('canvas');P.pop.es=[...cs];P.pop.esCap=[...box.querySelectorAll('.cap')];
  P.pop.es.forEach((cv,i)=>cv.addEventListener('click',e=>{const it=hit(e,P.pop.esGeo&&P.pop.esGeo[i],cv);if(it)panelPick(P,it)}))}
function makePanel(pre,mapHost,lowHost,o){
  mapHost.innerHTML=`<div class="card" style="margin:0;height:100%"><div class="row"><h3 style="margin:0">Wafer map</h3>
    <label><input type="checkbox" id="${pre}All" checked> ${esc(o.allLabel)}</label>
    <button id="${pre}Pop" title="다른 모니터에 크게 띄웁니다. 이 화면과 실시간으로 같이 움직입니다">⧉ 새 창으로 크게 보기</button></div>
    <canvas id="${pre}Map" class="bigmap" aria-label="Wafer map (깜빡이는 점 = 보고 있는 Defect)"></canvas><div class="row legend" id="${pre}Lg"></div></div>`;
  lowHost.innerHTML=`${panelFltHtml(pre)}${panelFinHtml(pre)}<div class="review"><div>${lsHtml(pre+'Ls','검색 — 모든 열 값 · 사진 파일 이름 (여러 단어 = 모두 포함)',true,true)}<div class="muted" id="${pre}Cnt"></div><div class="pixln" id="${pre}Pix" hidden></div><div id="${pre}List" class="biglist pvt" tabindex="0" aria-label="Defect 목록 (열 제목 = 정렬, ↑↓ 또는 J/K 이동, Space = ☑, Enter · 더블 클릭 = 새 창)"></div>
    <p class="muted">목록 열 = 대규모 5-1 · 5-2 목록과 같음(+ 구분 = 영역 · 쌍). 열 제목을 누르면 그 값으로 정렬합니다. ↑ ↓ 또는 J K 로 이동합니다. 더블 클릭 또는 Enter 로 새 창(큰 화면)을 엽니다.${o.mark?' O = 위치 맞음, X = 벗어남.':''}</p></div>
    <div><div class="rvimgs"><figure id="${pre}Color"><figcaption>Color</figcaption></figure><figure id="${pre}Gray"><figcaption>Gray Crop</figcaption></figure></div>
    <div class="card" style="margin:8px 0 0"><div class="row memb" id="${pre}Mem"></div>
    ${o.mark?`<div class="row"><button data-mark="맞음">위치 맞음 (O)</button><button data-mark="벗어남">벗어남 (X)</button><span id="modelSt" class="muted"></span></div>`:''}
    <div class="muted" style="margin-top:6px">리뷰PC 정보 <span title="Surface.flt 와 Slot 의 Zones.ini · EquipmentClassifications.ini · ManReClassify.ini · WaferInfo.ini 로 만듭니다. 값 = Surface.flt 한 줄 그대로(단위 환산 없음, #71)">ⓘ</span></div><pre class="rvbox" id="${pre}Rv"></pre>
    <dl class="kv" id="${pre}Info"></dl></div></div></div>`;
  const P={pre,o,items:[],bg:[],raw:[],rawBg:[],cntBase:'',sel:0,geo:null,pop:null,popGeo:null,tok:0,title:'',q:[],el:k=>document.getElementById(pre+k)};
  fltBind(P.el('Flt'),()=>applyPanel(P,true));   // v14.1.8 검색 · ☑ · ☑ CSV
  P.pk=new Map();P.ls=lsBind(pre+'Ls',{onQ:T=>{P.q=T;applyPanel(P,true)},onAll:v=>{for(const it of P.items)P.pk.set(key(it.d),v);panelPkPaint(P)},
    onCsv:async()=>{const L=P.items.filter(it=>pOn(P,it));if(!L.length||!S.cmp)return;await saveCsv([csvText(L.map(it=>({d:it.d,label:it.label||it.tag||'',st:it.st})))],`Defect_목록_Step${o.step}_${stamp()}.csv`,true)}});
  // 2026-11-25(소유자 "기본 · 대규모 차이는 wafer map 유무만, 이미지 관련 필터와 리스트 모두 동일"): 목록 = 대규모와 같은 표(makeVT · 같은 열),
  // 필터 = 같은 줄(사진 · 장비 스캔 분류 · 리뷰 결과 · 값 범위 · Recipe · Zone · 정렬). ☑ 칸 누르기 = ☑/☐, 줄 누르기 = 보기, 더블 클릭 · Enter = 새 창.
  const L=P.el('List');P.clsOff1=new Set();P.clsOff2=new Set();P.gsort='';
  P.V=makeVT(L,PCOLS.map(c=>c.slice()),{row:k=>panelRow(P,k),cls:k=>{const it=P.items[k];return it?'st-'+panelPh(it).st+(pOn(P,it)?'':' off'):''},
    onSel:k=>{P.sel=k;showPanel(P)},onEnter:k=>{if(k!=null)P.sel=k;const q=P.items[P.sel];if(q)photoWinOpen(baseSrc(P))},onSpace:k=>panelTog(P,k),
    sort:()=>P.gsort?'g-'+P.gsort:P.el('Flt').querySelector('[data-f="sort"]').value,onSort:k=>panelSort(P,k)});
  {const FN=P.el('Fin');P.el('Xlsx').onclick=()=>baseSaveXlsx(P);P.el('FlCsv').onclick=()=>baseSaveCsv(P);P.el('Zip').onclick=()=>baseSaveZip(P);P.el('Gl').onclick=()=>baseGlRun(P);
    FN.querySelector('[data-xlorig]').addEventListener('change',e=>xlOrigSet(e.target.checked));
    FN.querySelector('[data-glr]').addEventListener('change',e=>{glSetR(e.target.value);for(const Q of Object.values(PANELS))for(const it of Q.raw||[])if(it.d.glp)it.d.glv=glMean(it.d);Object.values(PANELS).forEach(Q=>Q.raw&&applyPanel(Q,true))});
    let gt=0;FN.addEventListener('input',e=>{if(e.target.matches('[data-glo],[data-ghi]')){clearTimeout(gt);gt=setTimeout(()=>applyPanel(P,true),250)}})}
  L.addEventListener('click',e=>{const c=e.target.closest('.br>span.pk');if(!c)return;e.stopPropagation();panelTog(P,+c.parentNode.dataset.k)},true);
  const FB=P.el('Flt');
  FB.addEventListener('change',e=>{const d=e.target.dataset||{},g=d.pcls1!=null?1:d.pcls2!=null?2:0;if(!g)return;const off=P['clsOff'+g],k=d['pcls'+g];if(e.target.checked)off.delete(k);else off.add(k)});
  FB.addEventListener('click',e=>{const t=e.target,g=t.dataset&&t.dataset.pclsall;
    if(g){const off=P['clsOff'+g];if(off.size)off.clear();else FB.querySelectorAll(`[data-pcls${g}]`).forEach(x=>off.add(x.dataset['pcls'+g]));applyPanel(P,true);return}
    if(t.dataset&&t.dataset.f==='clear'){P.clsOff1.clear();P.clsOff2.clear();FB.querySelectorAll('[data-pst]').forEach(x=>x.checked=true);applyPanel(P,true)}});   // 범위 칸은 fltBind 가 비움
  P.el('All').addEventListener('change',()=>paintPanel(P));
  P.el('Pop').onclick=()=>popMap(P);
  P.el('Map').addEventListener('click',e=>{const q=hit(e,P.geo,P.el('Map'));if(q)panelPick(P,q)});
  attachTip(P.el('Map'),()=>P.geo);
  P.el('Mem').addEventListener('click',e=>{const b=e.target.closest('[data-mem]');const it=P.items[P.sel];if(!b||!it)return;it.d=it.members[+b.dataset.mem];showPanel(P)});
  lowHost.addEventListener('click',e=>{const b=e.target.closest('[data-mark]');if(b)mark(P,b.dataset.mark)});
  PANELS[pre]=P;return P;
}
/** v14.1.8: Step 3 · 4 목록 줄의 검색 글 — 목록 · 정보 칸의 값(구분 · ID · 좌표 · Die · Area · Width · Length · Box · Contrast · Step · Slot · 호기 · Recipe) + 사진 이름(+ O/X 는 매번). */
function panelText(it){const d=it.d;if(!it.qt){const x=info({d,label:it.label||it.tag||''}),c=S.cmp?linkColor(d,d.scan,S.cmp.o.ctol):null,g=grayOf(d);
    it.qt=lower([it.tag,it.label,x.id,f1(x.X),f1(x.Y),x.die,fv(x.area),fv(x.areaRaw),fv(x.width),fv(x.widthUm),fv(x.length),x.box,fv(x.contrast),x.step,x.slot,x.tool,rcpName(d),c&&c.c&&c.c.file,g&&g.frame&&g.frame.file].filter(v=>v!=null&&v!=='').join(' '))}
  const ov=S.overlay[key(d)];return ov?it.qt+' '+lower(ov):it.qt}
/** 목록 · 지도 자료를 바꾼다. keep = 보고 있던 항목을 유지(같은 항목이 새 목록에 있으면). */
function setPanel(P,items,bg,cnt,keep){P.raw=items;P.rawBg=bg;P.cntBase=cnt;applyPanel(P,keep)}
/** 목록 필터(Contrast(실제) · Area µm² · Width · Length 범위) · 정렬을 적용해 목록 · 지도를 다시 만든다. 필터가 비어 있고 정렬이 '기본 순서'면 받은 그대로. */
/** Para #70: Recipe 고르기 칸 = 지금 목록(필터 전)의 Recipe 이름 + 개수. 고른 값은 목록에 없어도 남긴다. */
function rcpOptions(P){const sel=P.el('Flt').querySelector('[data-f="rcp"]');if(!sel)return;const n=new Map();for(const it of P.raw){const k=rcpName(it.d);n.set(k,(n.get(k)||0)+1)}
  const v=sel.value,ks=[...n.keys()].sort((a,b)=>a.localeCompare(b,'ko',{numeric:true}));if(v&&!n.has(v))ks.push(v);
  sel.innerHTML='<option value="">전체</option>'+ks.map(k=>`<option value="${esc(k)}">${esc(k)} (${n.get(k)||0})</option>`).join('');sel.value=v}
/** #83 후속: Zone 고르기 칸 = 지금 목록(필터 전)의 Zone + 개수(Recipe 칸과 같은 방식). */
function znOptions(P){const sel=P.el('Flt').querySelector('[data-f="zn"]');if(!sel)return;const n=new Map();for(const it of P.raw){const k=zoneLbl(it.d.zone,it.d.scan);n.set(k,(n.get(k)||0)+1)}
  const v=sel.value,ks=[...n.keys()].sort((a,b)=>a.localeCompare(b,'ko',{numeric:true}));if(v&&!n.has(v))ks.push(v);
  sel.innerHTML='<option value="">전체</option>'+ks.map(k=>`<option value="${esc(k)}">${esc(k)} (${n.get(k)||0})</option>`).join('');sel.value=v}
function applyPanel(P,keep){
  rcpOptions(P);znOptions(P);
  const f=readFlt(P.el('Flt')),cur=keep?P.items[P.sel]:null,T=P.q||[];let items=P.raw,bg=P.rawBg;   // v14.4.1: Area · Width = [µm 로 보기] 단위
  panelFacet(P);const pst=new Set([...P.el('Flt').querySelectorAll('[data-pst]')].filter(x=>x.checked).map(x=>x.dataset.pst)),off1=P.clsOff1,off2=P.clsOff2;
  if(pst.size<4||off1.size||off2.size)f.on=true;   // 2026-11-25: 사진 상태 · 분류도 필터(대규모와 같음)
  const glr=panelGlRange(P);if(glr)f.on=true;   // 흑백 GL 범위(5-3 과 같음 — 안 잰 Defect 는 빠짐)
  const fp=it=>{const [a,w]=umK(it.d.scan);return fltPass(f,it.d.Contrast,it.d.area*a,it.d.BlobBreadth*w,it.d.BlobLength)&&pst.has(panelPh(it).st)&&!off1.has(panelCls(it.d,1))&&!off2.has(panelCls(it.d,2))&&(!glr||(it.d.glv!=null&&it.d.glv>=glr[0]&&it.d.glv<=glr[1]))};
  if(f.on||T.length){const out=[];items=[];for(const it of P.raw)((!f.on||fp(it)&&(!f.rcp||rcpName(it.d)===f.rcp)&&(!f.zn||zoneLbl(it.d.zone,it.d.scan)===f.zn))&&(!T.length||qAll(T,panelText(it)))?items:out).push(it);
    bg=bg.concat(out.map(it=>({X:it.X,Y:it.Y,c:'#9aa3b2',r:2.4,ring:true,q:it})))}
  if(f.sort&&f.sort[0]==='r'){const sg=f.sort==='r-d'?-1:1;items=items.map((it,i)=>[rcpName(it.d),i,it]).sort((a,b)=>sg*a[0].localeCompare(b[0],'ko',{numeric:true})||a[1]-b[1]).map(x=>x[2])}
  else if(f.sort){const [sk,sd]=f.sort.split('-'),sg=sd==='d'?-1:1,bad=sd==='d'?-Infinity:Infinity,val=it=>{const d=it.d,v=sk==='c'?d.Contrast:sk==='a'?d.area*umK(d.scan)[0]:sk==='w'?d.BlobBreadth*umK(d.scan)[1]:d.BlobLength;return v===v&&v!=null?v:bad};
    items=items.map((it,i)=>[val(it),i,it]).sort((a,b)=>sg*(a[0]-b[0])||a[1]-b[1]).map(x=>x[2])}
  if(P.gsort){const sg=P.gsort==='d'?-1:1,bad=P.gsort==='d'?-Infinity:Infinity;items=items.map((it,i)=>[it.d.glv!=null?it.d.glv:bad,i,it]).sort((a,b)=>sg*(a[0]-b[0])||a[1]-b[1]).map(x=>x[2])}
  P.items=items;P.bg=bg;const k=cur?items.indexOf(cur):-1;P.sel=k>=0?k:0;
  const cnt=P.cntBase+(f.on||T.length?` · ${f.on?'필터':''}${f.on&&T.length?' · ':''}${T.length?`검색 '${T.join(' ')}'`:''}에 맞는 것 ${items.length} / ${P.raw.length}개${f.rcp?` (Recipe ${f.rcp})`:''}${f.zn?` (Zone ${f.zn})`:''}`:'')+(f.sort?` · 정렬: ${SORTS.find(x=>x[0]===f.sort)[1]}`:'');
  P.el('Cnt').textContent=cnt;pixLineSet(P.el('Pix'),P.raw.map(it=>it.d.scan));P.V.sel=P.sel;vtSet(P.V,items.length,k>=0);
  P.ls.set(items.reduce((a,it)=>a+(pOn(P,it)?1:0),0),items.length);pFinInfo(P);paintPanelList(P);showPanel(P)}
/** v14.1.8 Step 3 · 4 ☑(처음 = [처음엔 모두 ☑]): ☐ = 목록에서 흐리게 · 지도에 회색 원 · ↑↓ 로 건너뜀 · CSV 에서 뺌. 기억 = Defect 마다(필터 · 검색 · 영역을 바꿔도). */
const pOn=(P,it)=>{const v=P.pk.get(key(it.d));return v===undefined?LS.def:v};
function panelTog(P,k){const it=P.items[k];if(!it)return;P.pk.set(key(it.d),!pOn(P,it));panelPkPaint(P)}
function panelPkPaint(P){paintPanelList(P);paintPanel(P);P.ls.set(P.items.reduce((a,it)=>a+(pOn(P,it)?1:0),0),P.items.length);pFinInfo(P)}
/** ↑↓: ☑ 줄만 차례로(☐ 는 건너뜀). 더 없으면 그대로. */
function panelStep(P,dir){for(let k=P.sel+dir;k>=0&&k<P.items.length;k+=dir)if(pOn(P,P.items[k]))return k;return P.sel}
function paintPanelList(P){P.V.sel=P.sel;vtPaint(P.V)}
/** 지도에 그릴 점: '전체' 체크 = 배경 점(bg) + 목록 점, 아니면 목록 점만. 목록 점이 위에 그려진다. */
function panelPts(P){const off=[],on=[];for(const it of P.items)(pOn(P,it)?on:off).push(it);   // v14.1.8: ☐ = 회색 원(☑ 가 위에)
  return (P.el('All').checked?P.bg:[]).concat(off.map(it=>({X:it.X,Y:it.Y,c:'#9aa3b2',r:2.4,ring:true,q:it})),on.map(it=>({X:it.X,Y:it.Y,c:it.c,r:3.6,q:it})))}
function paintPanel(P){if(!S.cmp)return;const hl=P.items[P.sel],opt={pts:panelPts(P),hl,on:blinkOn};
  P.geo=paintMap(P.el('Map'),opt);
  if(P.pop&&!P.pop.w.closed){P.popGeo=paintMap(P.pop.cv,opt);
    P.pop.hd.textContent=`${P.title} · ${P.el('Cnt').textContent}${hl?` · 보고 있는 Defect: ${hl.label||''} ID ${hl.d.no??hl.d.id} (${f1(hl.X)}, ${f1(hl.Y)})`:''}`}}
/** 새 창 wafer map: 같은 그림을 그 창의 canvas 에도 그린다(깜빡임 · 목록 이동 · 영역 바꾸기가 바로 반영). 그 창에서 점을 누르면 이 화면이 그 Defect 로 간다. */
function popMap(P){
  if(P.pop&&!P.pop.w.closed){P.pop.w.focus();return}
  const w=winOpen('cw_map_'+P.pre,'width=1100,height=1000');
  const css=getComputedStyle(document.documentElement),cl=n=>css.getPropertyValue(n).trim(),doc=w.document;doc.title='Wafer map · '+P.title;
  doc.head.innerHTML=`<meta charset="utf-8"><style>html,body{height:100%;margin:0}body{background:${cl('--bg')};color:${cl('--ink')};font:13px "Malgun Gothic","Segoe UI",sans-serif;display:flex;flex-direction:column}
    .hd{padding:6px 10px;flex:none}canvas{flex:1;min-height:0;width:100%;display:block;background:${cl('--panel')}}</style>`;
  // Para #56: 새 창 = 왼쪽 벤다이어그램(Step 3) 또는 A → B 간략 지도 2개(Step 4) + 오른쪽 wafer map. 둘 다 이 화면과 실시간 연동.
  doc.head.insertAdjacentHTML('beforeend','<style>.bd{flex:1;min-height:0;display:flex;gap:8px;padding:0 8px 8px}.sd{flex:0 0 38%;min-width:0;display:flex;flex-direction:column;gap:6px}.sd canvas{flex:1;min-height:0;border:1px solid '+cl('--line')+';border-radius:8px}.sd .cap{flex:none;font-size:12px;color:'+cl('--sub')+'}.mp{flex:1;min-width:0;display:flex}.mp canvas{border:1px solid '+cl('--line')+';border-radius:8px}</style>');
  doc.body.innerHTML='<div class="hd"></div><div class="bd">'+(P.o.side?'<div class="sd"></div>':'')+'<div class="mp"><canvas aria-label="Wafer map"></canvas></div></div>';
  P.pop={w,cv:doc.querySelector('.mp canvas'),hd:doc.querySelector('.hd')};
  if(P.o.side)P.o.side.mount(P,doc.querySelector('.sd'));
  w.addEventListener('resize',()=>{paintPanel(P);sidePaint(P)});
  P.pop.cv.addEventListener('click',e=>{const q=hit(e,P.popGeo,P.pop.cv);if(q)panelPick(P,q)});
  w.addEventListener('keydown',e=>panelKey(P,e));
  setTimeout(()=>{paintPanel(P);sidePaint(P)},50)}
/** 새 창 왼쪽(벤다이어그램 · 간략 지도) 다시 그리기 — 깜빡일 때마다가 아니라 자료 · 선택이 바뀔 때만 */
function sidePaint(P){if(!P.pop||P.pop.w.closed)return;if(P===P3)drawVenn();else if(P===P4)paintEsc()}
function panelPick(P,q){const k=P.items.indexOf(q);if(k>=0){P.sel=k;showPanel(P);return}if(P.o.pickOther&&P.o.pickOther(q))return;if(q.d)photoWinOpen(listSrc([q],0))}
function panelKey(P,e){if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;const k=e.key.toLowerCase();
  if(k==='arrowdown'||k==='j'){P.sel=panelStep(P,1);showPanel(P);e.preventDefault()}else if(k==='arrowup'||k==='k'){P.sel=panelStep(P,-1);showPanel(P);e.preventDefault()}
  else if(k===' '){panelTog(P,P.sel);e.preventDefault()}
  else if(k==='enter'){const q=P.items[P.sel];if(q)photoWinOpen(baseSrc(P));e.preventDefault()}else if(P.o.mark&&k==='o')mark(P,'맞음');else if(P.o.mark&&k==='x')mark(P,'벗어남')}
async function showPanel(P){
  const L=P.items;
  if(!L.length){if(P.o.onShow)P.o.onShow();paintPanel(P);P.el('Color').innerHTML=`<figcaption>Color</figcaption><div class="ph">${esc(P.o.empty)}</div>`;P.el('Gray').innerHTML='<figcaption>Gray Crop</figcaption>';P.el('Info').innerHTML='';P.el('Rv').textContent='';P.el('Mem').innerHTML='';return}
  P.sel=Math.max(0,Math.min(L.length-1,P.sel));const q=L[P.sel],tk=++P.tok;if(P.o.onShow)P.o.onShow();
  vtGo(P.V,P.sel,true);paintPanelList(P);blinkOn=true;paintPanel(P);
  if(PW.src&&PW.src.key===P&&PW.w&&!PW.w.closed)photoWinShow();   // v14.4.1(#89): 새 창이 이 목록이면 같이 넘어감(대규모 photoWinFollow 와 같음)
  P.el('Mem').innerHTML=q.members&&q.members.length>1?'<span class="muted">사진 · 정보 스캔:</span>'+q.members.map((m,i)=>`<button data-mem="${i}" aria-pressed="${m===q.d}">${esc(stepName(m.scan))}${m.scan.slotName?' · '+esc(m.scan.slotName):''}</button>`).join(''):'';
  const x=info(q),c=linkColor(q.d,q.d.scan,S.o.ctol),g=grayOf(q.d);
  const fill=()=>{P.el('Info').innerHTML=kvHtml([['구분',x.st],...infoRows(q.d,x,c?`${c.c.file} · ${c.how}`:'연결 실패',grayText(g))])};fill();P.el('Rv').textContent=rvText(q.d);
  const cf=P.el('Color');cf.innerHTML='<figcaption>Color</figcaption>';const u=await colorUrl(q.d);if(tk!==P.tok)return;
  if(u){const im=new Image();im.src=u;im.alt='Color';cf.append(im)}else cf.insertAdjacentHTML('beforeend','<div class="ph">Color 이미지 연결 실패</div>');
  const gf=P.el('Gray');gf.innerHTML='<figcaption>Gray Crop</figcaption>';const r=await grayCrop(q.d,420);if(tk!==P.tok)return;
  if(r.canvas)gf.append(r.canvas);else gf.insertAdjacentHTML('beforeend',`<div class="ph">${esc(r.reason)}</div>`);fill();
  // 앞뒤 8개 미리 로딩(LRU 가 넘치는 것을 정리)
  for(let k=1;k<=8;k++)for(const j of [P.sel+k,P.sel-k]){const n=L[j];if(!n)continue;colorUrl(n.d);const gg=grayOf(n.d);if(gg.frame&&k<=4)grayBmp(n.d.scan,gg.frame)}
}
/** 사진 정보 표의 줄(Step 3 · 4 리뷰 패널, Step 5 공용). color · gray = 그 줄에 적을 글. */
function infoRows(d,x,color,gray){const gl=d.gl;return [['ID / resultID',`${x.id} / ${d.resultID}`],['Step · Slot · 호기',`${x.step} · CA ${d.scan.contrast??'?'} · Slot ${x.slot||'-'} · ${x.tool||'-'}`],['Wafer X/Y',`${f1(x.X)}, ${f1(x.Y)} µm`],['Die (맵 X, Y)',x.die+(x.dieEq?` · ${x.dieEq}`:'')+(x.dieXY?` · Die 안 ${x.dieXY} µm`:'')],
  ['Area (µm²)',`${fv(x.area)} µm² (값 ${rawNum(d.area)})`],['Width (µm)',`${fv(x.widthUm)} µm (값 ${rawNum(d.BlobBreadth)})`],['Length',fv(x.length)],['µm 환산 픽셀',pixTxt(x.pix)+' — Width · Area 에 곱함'],['Box W×H',x.box+' px'],['Contrast(실제)',fv(x.contrast)],['Color',color],['Gray',gray],
  ['GL(Local 추정)',gl?`ROI mean ${f1(gl.mean)} · median ${f1(gl.median)} · max ${gl.max} · ring median ${f1(gl.ring)} · ROI−local ${f1(gl.delta)}`:'-']]}
const grayText=g=>g.frame?`${g.frame.file} · (${f1(g.px)}, ${f1(g.py)}) · ${g.W}×${g.H} · ${geoModel(g)}`:g.reason;
const kvHtml=rows=>rows.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
// ── Para #70: 리뷰PC Defect 정보 ────────────────────────────────────────────
//   사진 제외.zip 조사: Surface.flt 한 줄에 area · BlobBreadth · BlobLength · BoxWidth · BoxHeight(모두 Gray 픽셀) · recipe · zone · waferRegion · Type(판정 비트) · reclassify 가 있다.
//   이름은 Slot 의 글 파일: Recipe = WaferInfo.ini [Recipe] Name(없으면 Params_WaferInfo.ini RecipeName), Zone = Zones.ini [ALGName], 맨 위 'Surface' = Zones.ini [ALG],
//   판정 종류 = EquipmentClassifications.ini [SURFACE] '비트=이름'(1024 = Long dark defect), 분류 = ManReClassify.ini [General](0 = Accept).
//   #71(소유자 "지금 방식 말고 Surface.flt 한 줄의 값을 그대로"): 값 = Surface.flt 그대로(µm 환산 안 함), Recipe · Zone · Region 번호 · 판정 비트 · 분류 코드도 숫자 그대로. 이름 파일이 있으면 숫자 뒤 괄호.
/** EquipmentClassifications.ini [SURFACE] '비트=이름 ; 기호' → Map(비트 → 이름). -1(내부용) · 0 은 뺀다. */
function parseEqCls(text){const m=new Map();let sec='';
  for(const raw of String(text).split(/\r\n|\r|\n/)){const l=raw.trim();if(!l||l[0]===';')continue;const h=/^\[(.+)\]$/.exec(l);if(h){sec=lower(h[1]).trim();continue}
    if(sec!=='surface')continue;const q=/^(-?\d+)\s*=\s*([^;]*)/.exec(l);if(!q||+q[1]<=0)continue;const n=q[2].trim();if(n)m.set(+q[1],n)}
  return m}
/** Zones.ini [ALGName] · [ALG] → {zones: Map(번호 → Zone 이름), algs: Map(번호 → 알고리즘 이름)} */
function parseZones(text){const zones=new Map(),algs=new Map();let sec='';
  for(const raw of String(text).split(/\r\n|\r|\n/)){const l=raw.trim();if(!l||l[0]===';')continue;const h=/^\[(.+)\]$/.exec(l);if(h){sec=lower(h[1]).trim();continue}
    const q=/^(\d+)\s*=\s*(.*)$/.exec(l);if(!q)continue;if(sec==='algname')zones.set(+q[1],q[2].trim());else if(sec==='alg')algs.set(+q[1],q[2].trim())}
  return {zones,algs}}
async function rvLoad(s,text){const r={recipe:'',zones:new Map(),algs:new Map(),types:new Map(),cls:null};
  try{const wi=await text('WaferInfo.ini');if(wi){const sec=parseIni(wi).find(x=>lower(x.name)==='recipe');if(sec&&sec.kv.name)r.recipe=sec.kv.name}
    if(!r.recipe){const pw=await text('Params_WaferInfo.ini');if(pw)for(const x of parseIni(pw))if(x.kv.recipename){r.recipe=x.kv.recipename;break}}
    const zt=await text('Zones.ini');if(zt)Object.assign(r,parseZones(zt));
    const et=await text('EquipmentClassifications.ini');if(et)r.types=parseEqCls(et);
    const mt=await text('ManReClassify.ini');if(mt)r.cls=parseManRe(mt)}
  catch(e){s.warns.push('리뷰 정보 파일을 읽지 못함: '+(e.message||e))}
  s.rv=r}
/** #71: 리뷰PC 정보 = Surface.flt 한 줄의 값 그대로(픽셀 → µm 환산 없음, 번호 · 비트 · 코드도 숫자 그대로). 이름 파일에 있으면 숫자 뒤 괄호로만 덧붙인다. */
function rawNum(x){if(x==null||x!==x)return '-';return Number.isInteger(x)?String(x):String(+x.toFixed(4))}
/** Recipe = Surface.flt recipe 번호 그대로. 0 이고 Slot 의 Recipe 이름(WaferInfo.ini)이 있으면 '0 (이름)'. */
/** #73: Recipe 요약(표 칸) — groups = [[개수, i → Recipe 글]], 결과 '0 (PI_Bubble) 353 · 1 20'(많은 순). */
function rcpSum(groups){const m=new Map();for(const [n,f] of groups)for(let i=0;i<n;i++){const k=f(i);m.set(k,(m.get(k)||0)+1)}
  return m.size?[...m].sort((a,b)=>b[1]-a[1]||String(a[0]).localeCompare(String(b[0]),'ko',{numeric:true})).map(([k,n])=>`${k} ${n.toLocaleString()}`).join(' · '):'-'}
function rcpName(d){const k=d.recipe,r=d.scan&&d.scan.rv,n=r&&r.recipe;if(k==null||k!==k)return '-';return k===0&&n?`0 (${n})`:String(k)}
/** 판정 비트 이름(EquipmentClassifications.ini). 이름이 없으면 ''. */
function typeName(d){const t=d.Type>>>0;if(d.Type==null||!t)return '';const r=d.scan&&d.scan.rv,out=[];
  if(r&&r.types)for(const [b,n] of r.types)if((b&(b-1))===0&&(t&b)>>>0===b)out.push(n);return out.join(', ')}
const withName=(v,n)=>v==null||v!==v?'-':n?`${v} (${n})`:String(v);
function rvInfo(d){const s=d.scan||{},r=s.rv||{},die=d.X!=null&&s.product?mapDie(d.X,d.Y,s):null,cl=codeName(d.reclassify,r.cls),zn=r.zones&&r.zones.get(d.zone);
  return {alg:(r.algs&&r.algs.get(d.zone))||'Surface',area:d.area,width:d.BlobBreadth,length:d.BlobLength,bw:d.BoxWidth,bh:d.BoxHeight,
    recipe:rcpName(d),recipeNo:d.recipe,col:die?die.col:null,row:die?die.row:null,mx:die?die.x:null,my:die?die.y:null,
    clsNo:d.reclassify,clsName:cl||'',cls:withName(d.reclassify,cl),typeNo:d.Type==null?null:d.Type>>>0,typeName:typeName(d),type:withName(d.Type==null?null:d.Type>>>0,typeName(d)),
    zoneNo:d.zone,zoneName:zn||'',zone:withName(d.zone,zn),region:d.waferRegion==null?'-':String(d.waferRegion)}}
/** 리뷰PC 와 같은 순서로 Surface.flt 값을 그대로(단위 환산 없음). */
function rvText(d){const v=rvInfo(d),sp=sizePix(d.scan);   // v14.4.1: Area · Width 뒤 괄호 = µm(소유자), 한 줄 띄우고 µm 환산 픽셀
  return [v.alg,`Area:${rawNum(v.area)} (${um4(v.area*sp.pix*sp.pix)} µm²)`,`Width:${rawNum(v.width)} (${um4(v.width*sp.pix)} µm)`,`Length:${rawNum(v.length)}`,`Box Width:${rawNum(v.bw)}`,`Box Height:${rawNum(v.bh)}`,'',`µm 환산 픽셀: ${pixTxt(sp)}`,'',`Recipe: ${v.recipe}`,`Col: ${v.col??'-'} Row: ${v.row??'-'}`,`맵 X: ${v.mx??'-'} Y: ${v.my??'-'}`,
    '--------------------',`분류: ${v.cls}`,`판정 비트: ${v.type}`,'',`Zone: ${v.zone}`,`Region: ${v.region}`].join('\n')}
// 깜빡임 0.45초: 보이는 Step 의 패널 + 새 창이 열린 패널(다른 Step 으로 가도 새 창은 계속 움직인다)
setInterval(()=>{const on=Object.values(PANELS).filter(P=>P.items.length&&($('#step'+P.o.step).classList.contains('on')||(P.pop&&!P.pop.w.closed)));
  if(!on.length)return;blinkOn=!blinkOn;on.forEach(paintPanel)},450);
document.addEventListener('keydown',e=>{if($('#step5').classList.contains('on'))return vtKey(curVT(),e);const P=Object.values(PANELS).find(P=>$('#step'+P.o.step).classList.contains('on'));if(P)panelKey(P,e)});
function modelState(){const el=$('#modelSt');if(!el)return;const v=Object.values(S.overlay),ok=v.filter(x=>x==='맞음').length,ng=v.filter(x=>x==='벗어남').length;
  el.textContent=`좌표 모델: ${ok>=10&&!ng?'확인됨':'미확정'} (맞음 ${ok}/10, 벗어남 ${ng})${ng?' — 벗어난 샘플이 있어 확정하지 않습니다. Step 2 에서 보정하십시오':''}`}
function mark(P,v){const q=P.items[P.sel];if(!q)return;S.overlay[key(q.d)]=v;modelState();paintPanelList(P)}

// ════════════════════════════════════════════════════════════════════════
// 12. Step 3 — 스캔 결과 = 집합, 벤다이어그램(Para #55)
//     같은 Defect 묶음: Contrast AVG 오름차순으로 스캔을 차례로 matchSets(같은 허용오차) → 묶음마다 어느 스캔에 있는지 = mask(비트 k = k번째 스캔).
//     벤다이어그램은 늘 모든 스캔으로 그리고, 고른 집합(sel)과 관련된 영역(mask & sel ≠ 0)만 색, 나머지는 옅은 회색 + 경계선.
// ════════════════════════════════════════════════════════════════════════
function buildVenn(ss,P,o,prev){
  const cl=[];
  ss.forEach((s,k)=>{const pts=P.get(s);
    const m=matchBySlot(cl,pts,o.tol);
    for(const {a,b} of m.keep){a.mask|=1<<k;a.mem.push(b)}
    for(const d of m.added)cl.push({X:d.X,Y:d.Y,slot:slotOf(d),mask:1<<k,mem:[d]})});
  const counts=new Map();for(const c of cl)counts.set(c.mask,(counts.get(c.mask)||0)+1);
  // 집합 선택 · 결과를 눌렀는지는 다시 비교해도 유지(스캔이 같으면)
  const sel=new Set(),was=prev?new Set([...prev.sel].map(j=>prev.scans[j])):null;ss.forEach((s,k)=>{if(!was||was.has(s))sel.add(k)});
  for(const c of cl){c.item={d:c.mem[0],X:c.X,Y:c.Y,members:c.mem,mask:c.mask}}
  return {scans:ss,cl,counts,sel,regs:new Set(),shown:!!(prev&&prev.shown)};
}
const REG_PAL=['#2f6fed','#e5383b','#0fa3a3','#d4a106','#8e44ad','#e67e22','#2e9e4f','#c2185b','#5d6d7e','#00838f','#7cb342','#8d6e63','#3949ab','#f06292','#00a37a'];
const regColor=m=>REG_PAL[(m-1)%REG_PAL.length];
const selMask=()=>[...S.venn.sel].reduce((a,k)=>a|1<<k,0);
const related=m=>(m&selMask())!==0;
/** 영역 이름(집합 기호): 들어 있는 스캔 ∩ … - 들어 있지 않은 스캔. 예) CA20 ∩ CA27 - CA30 */
function regLabel(m){const V=S.venn,n=k=>stepName(V.scans[k]),ins=[],outs=[];V.scans.forEach((_,k)=>(m>>k&1?ins:outs).push(n(k)));
  return ins.join(' ∩ ')+(outs.length?' - '+(outs.length>1?'('+outs.join(' ∪ ')+')':outs[0]):'')}
// 벤다이어그램 모양(단위 좌표, [cx, cy, rx, ry, 회전]). 4개 = 타원 4개(15개 영역이 모두 생기게 수치로 찾은 배치). 5개 이상은 그림 대신 영역 표.
const VENN_SHAPES={1:[[0,0,.7,.7,0]],2:[[-.38,0,.62,.62,0],[.38,0,.62,.62,0]],3:[[-.34,.2,.58,.58,0],[.34,.2,.58,.58,0],[0,-.38,.58,.58,0]],
  4:[[-.006,-.177,1.091,.571,.506],[-.362,.077,1.091,.571,.506],[.362,.077,1.091,.571,-.506],[.006,-.177,1.091,.571,-.506]]};
function inEll(e,x,y){const c=Math.cos(e.r),s=Math.sin(e.r),dx=x-e.cx,dy=y-e.cy,u=dx*c+dy*s,v=-dx*s+dy*c;return (u/e.rx)**2+(v/e.ry)**2<=1}
function vennMaskAt(x,y,G){G=G||(S.venn&&S.venn.geo);if(!G)return 0;let m=0;G.E.forEach((e,k)=>{if(inEll(e,x,y))m|=1<<k});return m}
/** 벤다이어그램을 cv 에 그리고 클릭 판정용 geo 를 돌려준다(Para #56: 이 화면 + wafer map 새 창 둘 다). */
function drawVennOn(cv){const V=S.venn;if(!V||!cv)return null;const r=cv.getBoundingClientRect(),dpr=(cv.ownerDocument.defaultView||window).devicePixelRatio||1;if(r.width<2)return null;
  const W=Math.round(r.width*dpr),H=Math.round(r.height*dpr);cv.width=W;cv.height=H;const x=cv.getContext('2d');x.setTransform(1,0,0,1,0,0);x.clearRect(0,0,W,H);
  const css=getComputedStyle(document.documentElement),cl=n=>css.getPropertyValue(n).trim(),N=V.scans.length,sh=VENN_SHAPES[N];
  if(!sh){x.fillStyle=cl('--sub');x.font=`${13*dpr}px sans-serif`;x.fillText(`스캔 ${N}개 — 벤다이어그램은 4개까지 그립니다. 영역 표에서 고르십시오.`,12*dpr,26*dpr);return null}
  let bx0=Infinity,by0=Infinity,bx1=-Infinity,by1=-Infinity;for(const [cx,cy,rx,ry] of sh){const e=Math.max(rx,ry);bx0=Math.min(bx0,cx-e);bx1=Math.max(bx1,cx+e);by0=Math.min(by0,cy-e);by1=Math.max(by1,cy+e)}
  const pad=30*dpr,k=Math.min((W-2*pad)/(bx1-bx0),(H-2*pad)/(by1-by0)),ox=W/2-(bx0+bx1)/2*k,oy=H/2+(by0+by1)/2*k;
  const E=sh.map(([cx,cy,rx,ry,rot])=>({cx:ox+cx*k,cy:oy-cy*k,rx:rx*k,ry:ry*k,r:-rot})),geo={E,dpr};
  // 영역 칠하기: 픽셀마다 어느 타원 안인지(mask) → 색. 고른 영역이 있으면 그 영역은 진하게, 관련 영역은 옅게.
  const hex=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)),rgba=new Map(),sm=selMask(),gray=[150,160,175];
  for(let m=1;m<1<<N;m++){const rel=(m&sm)!==0,on=V.regs.size?V.regs.has(m):rel;rgba.set(m,rel?[...hex(regColor(m)),on?220:80]:[...gray,28])}
  const img=x.createImageData(W,H),D=img.data,acc=new Map(),step=3;
  for(let py=0;py<H;py++)for(let px=0;px<W;px++){let m=0;for(let i=0;i<N;i++)if(inEll(E[i],px,py))m|=1<<i;if(!m)continue;const c=rgba.get(m),o=(py*W+px)*4;D[o]=c[0];D[o+1]=c[1];D[o+2]=c[2];D[o+3]=c[3];
    if(px%step===0&&py%step===0){let a=acc.get(m);if(!a)acc.set(m,a={sx:0,sy:0,n:0,p:[]});a.sx+=px;a.sy+=py;a.n++;a.p.push(px,py)}}
  x.putImageData(img,0,0);
  // 경계선: 고른 집합 = 진하게, 나머지 = 옅은 회색
  E.forEach((e,i)=>{const on=V.sel.has(i);x.beginPath();x.ellipse(e.cx,e.cy,e.rx,e.ry,e.r,0,7);x.strokeStyle=on?cl('--ink'):cl('--sub');x.globalAlpha=on?1:.45;x.lineWidth=(on?2:1)*dpr;x.stroke();x.globalAlpha=1});
  // 영역마다 Defect 수(영역 무게중심에 가장 가까운 그 영역 안 점)
  x.textAlign='center';x.textBaseline='middle';
  for(const [m,a] of acc){const gx=a.sx/a.n,gy=a.sy/a.n;let bx=a.p[0],by=a.p[1],bd=Infinity;for(let i=0;i<a.p.length;i+=2){const d=(a.p[i]-gx)**2+(a.p[i+1]-gy)**2;if(d<bd){bd=d;bx=a.p[i];by=a.p[i+1]}}
    const n=V.counts.get(m)||0,rel=(m&sm)!==0;x.font=`${(rel?'bold ':'')}${13*dpr}px sans-serif`;x.fillStyle=rel?cl('--ink'):cl('--sub');x.fillText(String(n),bx,by)}
  // 집합 이름: 타원 바깥쪽(전체 가운데에서 먼 쪽)
  const gcx=E.reduce((a,e)=>a+e.cx,0)/N,gcy=E.reduce((a,e)=>a+e.cy,0)/N;
  E.forEach((e,i)=>{let dx=e.cx-gcx,dy=e.cy-gcy;const L=Math.hypot(dx,dy);if(L<1e-6){dx=N===4?(i<2?-1:1):0;dy=-1}else{dx/=L;dy/=L}
    const R=Math.max(e.rx,e.ry)*(N===4?.78:.92),tx=Math.min(W-40*dpr,Math.max(40*dpr,e.cx+dx*R)),ty=Math.min(H-10*dpr,Math.max(10*dpr,e.cy+dy*R+(N===4?0:-6*dpr)));
    const t=`${stepName(V.scans[i])} (${V.scans[i].contrast??'?'})`;x.font=`bold ${12*dpr}px sans-serif`;const w=x.measureText(t).width+10*dpr;
    x.fillStyle=cl('--panel');x.globalAlpha=.9;x.fillRect(tx-w/2,ty-9*dpr,w,18*dpr);x.globalAlpha=1;x.fillStyle=V.sel.has(i)?cl('--ink'):cl('--sub');x.fillText(t,tx,ty)});
  x.textAlign='start';x.textBaseline='alphabetic';return geo;
}
function drawVenn(){const V=S.venn;if(!V)return;V.geo=drawVennOn($('#venn'));const pp=P3.pop;if(pp&&!pp.w.closed&&pp.vcv)V.popGeo=drawVennOn(pp.vcv)}
function renderSetPick(){const V=S.venn;if(!V)return;
  $('#setPick').innerHTML=V.scans.map((s,k)=>`<label><input type="checkbox" data-set="${k}"${V.sel.has(k)?' checked':''}> ${esc(stepName(s))} <span class="muted">CA ${s.contrast??'?'} · ${s.defects.length}</span></label>`).join('')}
$('#setPick').addEventListener('change',e=>{const k=e.target.dataset.set;if(k==null)return;const V=S.venn;e.target.checked?V.sel.add(+k):V.sel.delete(+k);
  V.regs=new Set([...V.regs].filter(related));if(V.shown)refresh3()});
$('#vennBtn').onclick=()=>{if(!S.venn)return;if(!S.venn.sel.size){$('#vennNote').textContent='집합을 1개 이상 고르십시오.';return}S.venn.shown=true;refresh3()};
function renderRegTbl(){const V=S.venn,N=V.scans.length,ms=[...V.counts.keys()].sort((a,b)=>bits(b)-bits(a)||a-b);
  $('#regTbl').innerHTML=`<table><thead><tr><th>영역</th>${V.scans.map(s=>`<th>${esc(stepName(s))}</th>`).join('')}<th class="num">Defect</th></tr></thead><tbody>`+
    ms.map(m=>{const rel=related(m);return `<tr data-reg="${m}" class="${V.regs.has(m)?'on':''}"${rel?'':' style="opacity:.55"'}><td><i class="chip" style="background:${rel?regColor(m):'#b8bfcc'}"></i>${esc(regLabel(m))}</td>`+
      V.scans.map((_,k)=>`<td>${m>>k&1?'●':'○'}</td>`).join('')+`<td class="num">${V.counts.get(m)}</td></tr>`}).join('')+'</tbody></table>'}
const bits=m=>{let n=0;for(;m;m&=m-1)n++;return n};
/** Para #56: 영역 클릭 = 더하기, 이미 고른 영역 클릭 = 빼기(Ctrl 없이), 빈 곳(m=0) = 고른 집합 전체로 돌아가기. */
function pickRegion(m){const V=S.venn;if(!m)V.regs=new Set();else V.regs.has(m)?V.regs.delete(m):V.regs.add(m);refresh3()}
$('#regTbl').addEventListener('click',e=>{const tr=e.target.closest('tr[data-reg]');if(tr)pickRegion(+tr.dataset.reg)});
$('#venn').addEventListener('click',e=>{if(!S.venn||!S.venn.geo)return;const r=e.currentTarget.getBoundingClientRect(),d=S.venn.geo.dpr;pickRegion(vennMaskAt((e.clientX-r.left)*d,(e.clientY-r.top)*d))});
$('#venn').addEventListener('mousemove',e=>{if(!S.venn||!S.venn.geo)return;const r=e.currentTarget.getBoundingClientRect(),d=S.venn.geo.dpr,m=vennMaskAt((e.clientX-r.left)*d,(e.clientY-r.top)*d);
  e.currentTarget.title=m?`${regLabel(m)} · Defect ${S.venn.counts.get(m)||0}개`:'빈 곳 클릭 = 고른 집합 전체'});
/** Step 3 다시 그리기: 벤다이어그램 · 영역 표 · wafer map · 목록. 목록 = 고른 영역(없으면 고른 집합과 관련된 모든 영역). */
function refresh3(){const V=S.venn;if(!V||!V.shown)return;$('#vennArea').hidden=false;
  if(!V.sel.size){$('#vennNote').textContent='집합을 1개 이상 고르십시오.';}
  else $('#vennNote').textContent=`고른 집합: ${[...V.sel].sort().map(k=>stepName(V.scans[k])).join(', ')} · 관련 영역 ${[...V.counts.keys()].filter(related).length}개 · 같은 Defect = 허용오차 ${S.o.tol} µm 안(Step 2)`;
  drawVenn();renderRegTbl();
  const want=m=>V.regs.size?V.regs.has(m):related(m),items=[],bg=[];
  for(const c of V.cl){const it=c.item;it.c=related(c.mask)?regColor(c.mask):'#9aa3b2';it.label=regLabel(c.mask);it.tag=V.scans.map((s,k)=>c.mask>>k&1?stepName(s):null).filter(Boolean).join('·');
    if(want(c.mask))items.push(it);else bg.push({X:c.X,Y:c.Y,s:c.mem[0]&&c.mem[0].scan,c:it.c,r:related(c.mask)?2.6:2.2,q:it})}
  const what=V.regs.size?[...V.regs].map(regLabel).join(' + '):'고른 집합 전체('+([...V.sel].sort().map(k=>stepName(V.scans[k])).join(' ∪ ')||'-')+')';
  P3.title=what;
  $('#p3Lg').innerHTML=(V.regs.size?[...V.regs]:[...V.counts.keys()].filter(related)).map(m=>`<span><i style="background:${regColor(m)}"></i>${esc(regLabel(m))}</span>`).join('')+
    '<span><i style="background:#9aa3b2"></i>고른 집합과 관계없는 영역</span><span class="muted">깜빡이는 점 = 보고 있는 Defect · 점 클릭 = 그 Defect(다른 영역이면 그 영역으로)</span>';
  setPanel(P3,items,bg,`${what} · Defect ${items.length}개`,true);mapStatus()}
const P3=makePanel('p3',$('#p3map'),$('#p3low'),{step:3,allLabel:'다른 영역 Defect 도 표시',empty:'이 영역에 Defect 가 없습니다',
  side:{mount:mountVennSide},
  pickOther:q=>{if(q.mask==null)return false;const V=S.venn;if(!V.regs.size)V.regs=new Set([...V.counts.keys()].filter(related));V.regs.add(q.mask);refresh3();const k=P3.items.indexOf(q);if(k>=0){P3.sel=k;showPanel(P3)}return true}});

// ════════════════════════════════════════════════════════════════════════
// 13. Step 4 — A → B 에서 Escape 된(없어진) Defect: 간략 wafer map 2개 + Step 3 과 같은 리뷰 패널
// ════════════════════════════════════════════════════════════════════════
const P4=makePanel('p4',$('#p4map'),$('#p4low'),{step:4,mark:true,allLabel:'A ∪ B 의 다른 Defect 도 표시',empty:'Escape Defect 가 없습니다',side:{mount:mountEscSide},onShow:()=>paintEsc()});
function refresh4(){const c=S.cmp;if(!c)return;const a=stepName(c.A),b=stepName(c.B);
  const items=c._items||(c._items=c.gone.map(d=>({d,X:d.X,Y:d.Y,c:'--gone',label:stLabel('gone',c)})));
  const bg=[...c.keep.map(k=>({X:k.a.X,Y:k.a.Y,c:'--keep',r:2.6,q:{d:k.a,b:k.b,label:stLabel('keep',c)}})),...c.added.map(d=>({X:d.X,Y:d.Y,c:'--new',r:2.6,q:{d,label:stLabel('new',c)}}))];
  P4.o.empty=c.single?`Lot 이 1개(${a})라 A → B 비교(Escape Defect)가 없습니다. Step 3 에서 이 Lot 의 Defect 를 보십시오.`:'Escape Defect 가 없습니다';
  P4.title=c.single?`${a} · 비교 없음(Lot 1개)`:`${a} → ${b} · ${stLabel('gone',c)}`;
  $('#p4Lg').innerHTML=['gone','keep','new'].map(st=>`<span><i style="background:var(${COL[st]})"></i>${esc(stLabel(st,c))}</span>`).join('')+'<span class="muted">깜빡이는 점 = 보고 있는 Defect · 점 클릭 = 그 Defect 로 이동</span>';
  $('#esAt').textContent=`A = ${a} (전체 ${c.keep.length+c.gone.length}) · 빨강 = B 에서 없어진 ${c.gone.length}개`;
  $('#esBt').textContent=`B = ${b} (전체 ${c.keep.length+c.added.length}) · 빨간 원 = 없어진 자리`;
  setPanel(P4,items,bg,`${a} → ${b} Escape Defect (${stLabel('gone',c)}) ${items.length}개`,true);modelState();paintEsc()}
/** 간략 그림: A = A 의 Defect(회색) + 없어진 것(빨강 점), B = B 의 Defect(회색) + 없어진 자리(빨간 원). 점을 누르면 그 Defect 로 간다. */
function paintEsc(){const c=S.cmp,pp=P4.pop&&!P4.pop.w.closed?P4.pop:null;if(!c||(!$('#step4').classList.contains('on')&&!pp))return;const g='#9aa3b2',hl=P4.items[P4.sel];
  const A=[...c.keep.map(k=>({X:k.a.X,Y:k.a.Y,s:k.a.scan,c:g,r:1.8})),...P4.items.map(it=>({X:it.X,Y:it.Y,c:'--gone',r:3,q:it}))];
  const B=[...c.keep.map(k=>k.b||k.a).map(b=>({X:b.X,Y:b.Y,s:b.scan,c:g,r:1.8})),...c.added.map(d=>({X:d.X,Y:d.Y,s:d.scan,c:g,r:1.8})),...P4.items.map(it=>({X:it.X,Y:it.Y,c:'--gone',r:3.4,ring:true,q:it}))];
  if($('#step4').classList.contains('on'))S.esGeo=[paintMap($('#esA'),{pts:A,hl,on:true}),paintMap($('#esB'),{pts:B,hl,on:true})];
  if(pp&&pp.es){pp.esGeo=[paintMap(pp.es[0],{pts:A,hl,on:true}),paintMap(pp.es[1],{pts:B,hl,on:true})];pp.esCap[0].textContent=$('#esAt').textContent;pp.esCap[1].textContent=$('#esBt').textContent}}
['#esA','#esB'].forEach((q,i)=>$(q).addEventListener('click',e=>{const it=hit(e,S.esGeo&&S.esGeo[i],$(q));if(it)panelPick(P4,it)}));
function repaintAll(){if(!S.cmp)return;Object.values(PANELS).forEach(paintPanel);if($('#step3').classList.contains('on'))drawVenn();paintEsc()}

// ════════════════════════════════════════════════════════════════════════
// 15-0. rev5: Color · Gray 매칭 = Para 프로그램 'Color · Gray 매칭'(param_manager/colorgray.py, v12.9.30) 그대로 — Step 5 전용
//   소유자(2026-11-10): "프로그램에 있는 기능을 최우선으로 사용" · "설정은 아예 없애" · "결과는 목록으로, 새 창에서 큰 화면으로 사진들만".
//   · 매칭 폴더(프로그램의 Wafer 폴더) = ColorImageGrabingInfo.ini 가 바로 안에 있는 폴더(v14.4.1 #89: 없으면 목록 · 변환 파일이 있는 폴더 → Slot 폴더, Color = 사진 이름) —
//     Slot 바로 안 → Slot 하위 폴더 중 그 파일이 있는 첫 폴더(이름 순, 4단계까지) → 그 아래 Slot 이 이 Slot 하나뿐인 위쪽 폴더(이름은 대소문자 무시, cgLoad 설명). 목록 · 변환 파일이 없을 때의 대신 계산도 cgLoad 설명.
//     그 폴더 파일만 쓴다(여러 Slot 이 같이 있는 위쪽 폴더 것은 안 씀 — rev1 때 위쪽 폴더 파일로 좌표가 전부 어긋났다).
//   · Color 항목마다(choose_frame): Fault 좌표(FaultX/FaultY, 없으면 X/Y) · RecipeNumber(없으면 1) → 같은 레시피 프레임(없으면 레시피 번호 없는 프레임 → 전체) 중
//     Gray 픽셀 p = M⁻¹ · (Fault − 프레임 좌표 − offset) 이 프레임(레시피마다 크기 — geoSize) 안이고 가장자리에서 가장 먼 프레임. 변환 파일 = 그 레시피 번호 → 공통 → 이름 순 첫 번째.
//     v14.4.1(#89): 이 계산은 3절 geo*(두 모드 공통)로 옮겼다. Defect 의 Gray 위치는 늘 Defect 좌표(또는 장비 기록)로 — Color Fault 좌표는 Color 항목의 검색 글에만.
//   · 좌표 기준(COORD_MODES): '그대로'로 다 맞으면 끝, 아니면 프레임들이 덮는 직사각형의 좌측 하단 원점 해석 3가지 중 가장 많이 맞는 것(동점 = 앞, 매칭 폴더마다 하나).
//   · Crop(ColorGray.tsx crop) = Fault 가운데 Color 시야(ImageSize × PixelSize ÷ 0.769644 µm)만큼 잘라(밖 = 검정) Color 크기로 늘림 · 흑백.
//   · Defect(Surface.flt) → Color 항목(HTML 만 필요, 프로그램은 Color 항목만 다룸): ① Index = 기록 순서이고 좌표 5 µm 안(실제 결과 폴더 353/353)
//     ② 5 µm 안 가장 가까운 Color. Color 항목이 없는 Defect 는 같은 계산을 Defect 좌표 · recipe 로 해 Gray 만 찾는다('Defect 좌표').
//   프로그램 계산을 바꾸면 여기도 같이(시험 tools/test_contrast_wizard_rev5.mjs 가 실제 결과 폴더로 colorgray.py 결과와 비교).
// ════════════════════════════════════════════════════════════════════════
const CG={GW:3168,GH:1024,GP:0.769644115336745,MODES:['그대로','좌측 하단 원점','좌측 하단 원점 · Y 반전','Y 반전'],
  CI:'ColorImageGrabingInfo.ini',SL:'ScanResultImageList.txt',TF:'frameToChuckPlane.ini',TF_RE:/^frametochuckplane(\..+)?\.ini$/i,TOL:5};
const CG_HOW=['','Index = 기록 순서','좌표 (5 µm 안)','Index (Color 좌표 없음)','Color 사진 이름 좌표(일정한 어긋남 보정 · 기본 모드와 같음)'];
/** Python float() 처럼: 숫자 글자만(빈 칸 · 글자 = NaN). */
const pyFloat=v=>{if(v==null)return NaN;const t=String(v).trim();return /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(t)?+t:NaN};
/** Python round(): .5 는 짝수 쪽. */
const pyRound=v=>{const f=Math.floor(v),d=v-f;return d>0.5?f+1:d<0.5?f:(f%2?f+1:f)};
/** Color 항목의 값(이름이 정확히 같은 것 → 대소문자만 다른 것). */
const cgGet=(c,k)=>{if(Object.prototype.hasOwnProperty.call(c,k))return c[k];const l=k.toLowerCase();for(const x of Object.keys(c))if(x.toLowerCase()===l)return c[x]};
/** colorgray.parse_colors: [파일] 섹션마다 key=value(앞뒤 공백 제거). */
function cgColors(text){const rows=[];let cur=null;
  for(const raw of String(text).split(/\r\n|\r|\n/)){const line=raw.trim();
    if(line.startsWith('[')&&line.endsWith(']')){if(cur)rows.push(cur);cur={file:line.slice(1,-1)}}
    else if(cur&&line.includes('=')){const k=line.indexOf('=');cur[line.slice(0,k).trim()]=line.slice(k+1).trim()}}
  if(cur)rows.push(cur);return rows}
/** colorgray.fault_xy: FaultX/FaultY(없으면 X/Y). 숫자가 아니면 NaN. */
const cgFault=c=>{const v=(a,b)=>{const x=cgGet(c,a);return pyFloat(x!==undefined?x:cgGet(c,b))};return [v('FaultX','X'),v('FaultY','Y')]};
/** colorgray: int(float(RecipeNumber or 1)). 숫자가 아니면 NaN. */
const cgRecipe=c=>{const v=cgGet(c,'RecipeNumber'),n=pyFloat(v===undefined||v===''?'1':v);return Number.isFinite(n)?Math.trunc(n):NaN};
/** Defect 연결용 Color 번호(Index · DefectIndex …, 정수만). */
const cgIndex=c=>{for(const k of ['Index','DefectIndex','DefectIdx','FaultIndex']){const v=cgGet(c,k);if(v!==undefined){const n=pyFloat(v);if(Number.isInteger(n))return n}}return null};
/** colorgray.parse_frames: '파일, x, y'(구분자 , ; 탭), Version= 줄 · 숫자 아닌 줄 건너뜀, 이름의 .t.<번호>.jpg = 레시피. */
function cgFrames(text){const rows=[];
  for(const raw of String(text).split(/\r\n|\r|\n/)){const p=raw.trim().split(/[,;\t]/).map(x=>x.trim());
    if(p.length<3||p[0].startsWith('Version='))continue;const x=pyFloat(p[1]),y=pyFloat(p[2]);if(!Number.isFinite(x)||!Number.isFinite(y))continue;
    const m=/\.t\.(\d+)\.jpe?g$/i.exec(p[0]);rows.push({file:p[0],x,y,recipe:m?+m[1]:null})}
  return rows}
/** colorgray.transform_files 의 키: frameToChuckPlane.ini = null(공통), .<번호>.ini = 번호, 그 밖 = 글자. 변환 파일이 아니면 undefined. */
function cgTfKey(name){const low=lower(name);if(!CG.TF_RE.test(low))return undefined;const mid=low.slice(17,-4).replace(/^\.+|\.+$/g,'');return /^\d+$/.test(mid)?+mid:(mid||null)}
/** colorgray.transform_for: 그 레시피 → 공통 → 이름 순 첫 번째. */
function cgTfFor(tfs,r){if(tfs.has(r))return tfs.get(r);if(tfs.has(null))return tfs.get(null);
  const ks=[...tfs.keys()].sort((a,b)=>{const x=String(a),y=String(b);return x<y?-1:x>y?1:0});return ks.length?tfs.get(ks[0]):null}
/** colorgray.map_xy */
const cgMap=(mode,x,y,r)=>!mode||!r?[x,y]:mode===1?[r[0]+x,r[1]+y]:mode===2?[r[0]+x,r[3]-y]:[x,r[1]+r[3]-y];
/** choose_frame 의 후보 프레임: 같은 레시피 → 레시피 번호 없는 것 → 전체(레시피마다 한 번). */
function cgPool(frames,r,memo){let p=memo.get(r);if(!p){const same=frames.filter(f=>f.recipe===r);p=same.length?same:frames.filter(f=>f.recipe==null);if(!p.length)p=frames;memo.set(r,p)}return p}
/** colorgray.crop_size: {cw, ch(잘라 낼 Gray 픽셀), ow, oh(Color 크기 = 늘릴 크기)}. 값이 숫자가 아니면 null.
 *  gp = 그 레시피의 Gray 픽셀 크기(µm, geoPix — v14.4.1 #89: 종전 0.769644 고정은 x5 · 2D+3D 레시피에서 Color 시야를 2배 넘게 크게 잘랐다). 없으면 종전 값. */
function cgCropSize(c,gp,cp){const g=(k,d)=>{const v=cgGet(c,k);return pyFloat(v===undefined?d:v)},P=gp>0?gp:CG.GP,C0=cp>0?cp:0.4674;   // cp = RecipesInfo ColorPixelSize(Color 항목에 PixelSize 가 없을 때 — 사진 이름 Color)
  const ow=Math.trunc(g('ImageSizeX',1380)),oh=Math.trunc(g('ImageSizeY',1036)),sx=g('PixelSizeX',C0),sy=g('PixelSizeY',C0);
  if(![ow,oh,sx,sy].every(Number.isFinite))return null;return {cw:Math.max(1,pyRound(ow*sx/P)),ch:Math.max(1,pyRound(oh*sy/P)),ow,oh}}
/** Color 항목마다 Gray 위치(5-1 의 검색 글 · 개수). 좌표 기준 g.mode 는 geoPlan(Defect 좌표 표본)이 정했다. 변환 파일 오류는 던진다(프로그램: 그 Wafer 전체 실패). */
function cgPlan(g){
  for(const c of g.colors){const r=cgRecipe(c),t=cgTfFor(g.tfs,Number.isFinite(r)?r:1);if(t&&t.err)throw new Error(t.err)}
  let hits=0;const recs=g.colors.map(c=>{const [fx,fy]=cgFault(c),r=cgRecipe(c);if(!Number.isFinite(fx)||!Number.isFinite(fy)||!Number.isFinite(r))return {c,why:'좌표 값을 읽을 수 없음'};
    const [x,y]=cgMap(g.mode,fx,fy,g.rect),h=geoChoose(g,x,y,r),cs=cgCropSize(c,geoPix(g,r),g.rcpix&&g.rcpix.get(r));
    if(!h)return {c,fx,fy,r,crop:cs,why:geoWhy(g)};hits++;
    return {c,fx,fy,r,...h,crop:cs,why:cs?'':'Color ImageSize · PixelSize 값을 읽을 수 없음'}});
  return {mode:g.mode,rect:g.rect,hits,recs}}
/** Defect → Color 항목(s.cg.link[i] = Color 번호 | -1, s.cg.how[i] = CG_HOW 번호). */
function cgLink(s){const g=s.cg,C=s.cols,n=C.n,link=new Int32Array(n).fill(-1),how=new Uint8Array(n),T=CG.TOL;
  // v14.4.1(#89): Color 정보 파일이 없어 Color 가 사진 이름이면 기본 모드와 같은 연결(colorModel · linkColor — 사진 이름 좌표는 Fault 와 수 µm 일정하게 어긋날 수 있어 그 어긋남을 보정)
  if(g.colors.length&&g.colors[0].fromName){const K=new Map(g.colors.map((c,k)=>[c._nc,k])),sc={colors:g.colors.map(c=>c._nc),colorByIndex:new Map(),cols:C};let nXY=0;
    for(let i=0;i<n;i++){const r=linkColor({i,id:C.id[i],resultID:C.rid[i],x:C.x[i],y:C.y[i],ActualX:C.ax[i],ActualY:C.ay[i],X:C.x[i],Y:C.y[i]},sc,T);if(r){link[i]=K.get(r.c);how[i]=4;nXY++}}
    g.colorNote=sc.colorNote||'';Object.assign(g,{link,how,nIdx:0,nXY});return}
  const byIdx=new Map(),fx=[],fy=[],grid=new Map(),K=(i,j)=>i+','+j;
  g.colors.forEach((c,k)=>{const ix=cgIndex(c);if(ix!=null&&!byIdx.has(ix))byIdx.set(ix,k);const [x,y]=cgFault(c);fx[k]=x;fy[k]=y;
    if(Number.isFinite(x)&&Number.isFinite(y)){const q=K(Math.floor(x/T),Math.floor(y/T));(grid.get(q)||grid.set(q,[]).get(q)).push(k)}});
  const near=(x,y)=>{if(!Number.isFinite(x)||!Number.isFinite(y))return -1;const ci=Math.floor(x/T),cj=Math.floor(y/T);let b=-1,bd=Infinity;
    for(let di=-1;di<=1;di++)for(let dj=-1;dj<=1;dj++){const l=grid.get(K(ci+di,cj+dj));if(l)for(const k of l){const d=Math.hypot(fx[k]-x,fy[k]-y);if(d<=T&&d<bd){bd=d;b=k}}}return b};
  let nIdx=0,nXY=0;
  for(let i=0;i<n;i++){const P=[[C.x[i],C.y[i]],[C.ax[i],C.ay[i]]],k=byIdx.get(i);
    if(k!=null){if(!Number.isFinite(fx[k])||!Number.isFinite(fy[k])){link[i]=k;how[i]=3;nIdx++;continue}
      if(P.some(([x,y])=>Math.hypot(fx[k]-x,fy[k]-y)<=T)){link[i]=k;how[i]=1;nIdx++;continue}}
    for(const [x,y] of P){const b=near(x,y);if(b>=0){link[i]=b;how[i]=2;nXY++;break}}}
  Object.assign(g,{link,how,nIdx,nXY})}
/** Defect 의 Gray 위치(v14.4.1 #89: 늘 Defect 좌표 · 장비 기록으로 — 기본 모드 grayOf 와 같은 geoHit. 종전 = Color 가 붙은 Defect 는 Color Fault 좌표로, 실제 자료에서 둘은 같다). */
function cgDefGray(s,i){const g=s.cg,m=g.dmemo||(g.dmemo=new Map());if(m.has(i))return m.get(i);
  const C=s.cols,res=geoHit(g,C.x[i],C.y[i],C.rec[i],C.fi?C.fi[i]:0,C.xf?C.xf[i]:0,C.yf?C.yf[i]:0);
  m.set(i,res);return res}
/** Defect 하나의 매칭 → {ci(Color 번호 | -1), c(Color 항목), how, hit({frame, px, py, n, W, H, model} | null), from('defect' | 'record'), crop, why}. */
function cgOf(s,i){const g=s.cg;if(!g||!g.plan)return {ci:-1,c:null,how:0,hit:null,from:'',crop:null,why:!g?'매칭 파일을 읽지 않음':g.err||`매칭 파일 없음: ${g.missing.join(', ')}${g.path?` (${g.path})`:''}`};
  const r=s.cols.rec[i],k=g.link[i],h=cgDefGray(s,i),gp=geoPix(g,r),cp=g.rcpix&&g.rcpix.get(r),from=h&&h.model==='record'?'record':'defect',gw=h?'':geoWhy(g);
  if(k>=0){const rec=g.plan.recs[k],cs=cgCropSize(rec.c,gp,cp);return {ci:k,c:rec.c,how:g.how[i],hit:h,from,crop:cs||cgCropSize({},gp,cp),why:h?(cs?'':'Color ImageSize · PixelSize 값을 읽을 수 없음'):gw}}
  return {ci:-1,c:null,how:0,hit:h,from,crop:cgCropSize({},gp,cp),why:gw}}
// ── rev5: Classify(결함 종류) — 소유자 "classify 열 · 필터 · 정렬(B R Other, B R Surface Dark …)" ─────────────────
//   Surface.flt reclassify = 현재 분류 코드, orgReclassify = 리뷰 전 코드 = 장비 스캔 분류(0 = 리뷰에서 안 바뀜) → ManReClassify.ini [General] '코드=이름,Good/Defect,…'
//   (Para param_manager/manreclassify.py 와 같은 형식, 줄 맨 앞 ; 만 주석). 실제 결과 폴더: 29 = B R Surface Dark 334 · 28 = B R Other 19.
//   소유자 Slot 29126432EWE3 은 reclassify 0(Accept) · orgReclassify 28 · 29 → 장비 스캔 분류 B R Other · 리뷰 결과 Accept. ManReClassify.ini = 매칭 폴더 → Slot → 위쪽 폴더.
function parseManRe(text){const m=new Map();let sec='';
  for(const raw of String(text).split(/\r\n|\r|\n/)){const l=raw.trim();if(!l||l.startsWith(';'))continue;const h=/^\[(.+)\]$/.exec(l);if(h){sec=lower(h[1]);continue}
    if(sec!=='general')continue;const q=/^(-?\d+)\s*=\s*(.*)$/.exec(l);if(!q)continue;const f=q[2].split(',');m.set(+q[1],{name:(f[0]||'').trim()||`#${q[1]}`,status:(f[1]||'').trim()})}
  return m}
async function clsLoad(s,dir){let f=null,t=null;
  try{if(dir)f=await (dir.opt||dir.get)('ManReClassify.ini');if(!f)f=await fileFind(s,'ManReClassify.ini',true);
    if(f)t=await readText(await (f.file?f.file():f.get()));else if(s.chain&&s.chain.length)t=await chainText(s,'ManReClassify.ini');
    s.cls=t?{names:parseManRe(t),src:f?(f.path||f.name):'위쪽 폴더'}:null;if(!t)s.warns.push('ManReClassify.ini 없음 — Classify 는 코드 번호(#29 …)로 표시')}
  catch(e){s.cls=null;s.warns.push('ManReClassify.ini 를 읽지 못함: '+(e.message||e))}}
/** #73: Step 5 Slot 의 리뷰PC 이름 파일(WaferInfo · Zones · EquipmentClassifications · ManReClassify) — Step 1 rvLoad 와 같음. 찾는 순서 = clsLoad(매칭 폴더 → Slot → 위쪽 폴더). 없어도 됨. */
async function rv5Load(s,dir){
  const text=async n=>{try{let f=dir?await (dir.opt||dir.get)(n):null;if(!f)f=await fileFind(s,n,true);if(f)return readText(await (f.file?f.file():f.get()));return s.chain&&s.chain.length?await chainText(s,n):null}catch(e){return null}};
  await rvLoad(s,text)}
/** #73: Step 5 Recipe 칸 = Surface.flt recipe 번호 그대로(0 이고 WaferInfo 이름이 있으면 '0 (이름)') — Step 1 ~ 4 rcpName 과 같은 글. */
const rcp5=(s,i)=>{const k=s.cols.rec[i],n=s.rv&&s.rv.recipe;return k===0&&n?`0 (${n})`:String(k)};
/** #73: CSV 끝 열(Step 3 CSV 와 같은 순서): Recipe · Zone · Region · 판정비트 · 분류코드 · Zone이름 · 판정종류. */
const RV5_HEAD=['Recipe','Zone','Region','판정비트','분류코드','Zone이름','판정종류'];
const rv5Cells=(s,i)=>{const v=rvInfo(bigDef(s,i));return [v.recipe,rawNum(v.zoneNo),v.region,rawNum(v.typeNo),rawNum(v.clsNo),v.zoneName,v.typeName]};
/** 소유자 2026-11-25: Defect 코드 → 이름(Desc) 표(0 = Good, 나머지 = Defect). 화면 · 목록 · CSV · 엑셀 · 필터의 분류 이름은 이 표가 먼저,
    표에 없는 코드는 종전대로(Slot 의 ManReClassify.ini 이름 → 없으면 #코드). Para param_manager/wafermap.py DEFECT_CODES 와 같은 표(tests/test_defect_codes.py). */
const DEFECT_DESC=new Map([[0,'Accept'],[1,'Undersized Bump'],[2,'Missing Bump'],[3,'Metal Residue'],[4,'Bridged Bumps'],[7,'Irregular Bump'],[9,'Over Sized Bump'],[14,'Damaged Bump'],[22,'Passivation Scratch'],[23,'Passivation Damage'],[31,'Foreign Material'],[94,'Others'],[91,'Incoming Passivation Damaged - Metal Defect'],[92,'Passivation Defect'],[41,'Discolored'],[13,'Unfocused'],[90,'Coplanarity'],[93,'Incoming FM'],[42,'Height'],[40,'Crack'],[28,'B R Other'],[29,'B R Surface Dark'],[30,'B R Bump Missing'],[60,'B R Big Bump'],[50,'B R Bump Small'],[51,'B R Height LSL'],[52,'B R Height USL'],[53,'B R Cop'],[54,'B R Surface Bright'],[55,'B R Damage Bump'],[71,'CMP TSV breaking'],[72,'CMP FM under passivation'],[73,'CMP FM on passivation'],[74,'CMP TSV original defect'],[75,'CMP Bent Via defect'],[76,'CMP Scratch'],[77,'CMP Passivation peeled off'],[78,'CMP Crack'],[79,'CMP Discolor TSV'],[80,'CMP Unreveal TSV'],[81,'CMP Other'],[82,'Cu missing'],[83,'PTN reveal'],[84,'Cu short'],[85,'Cu shape'],[86,'Cu Smear'],[87,'FM on Cu'],[88,'Other']]);
const codeName=(code,m)=>{if(code==null||code!==code)return null;const t=DEFECT_DESC.get(+code);if(t)return t;const x=m&&m.get(code);return x?x.name:null};
const clsOf=(s,code)=>codeName(code,s.cls&&s.cls.names)||`#${code}`;
/** 소유자 "분류 2열 — 각각 AND 필터": 장비 스캔 분류(종전 '첫번째 분류') = 리뷰 전 코드(orgReclassify, 0 = 리뷰에서 안 바뀜 → 지금 코드),
 *  리뷰 결과(종전 '재분류') = 지금 코드(reclassify). Para v14.1.5 소유자 "첫번째 분류 → 장비 스캔 분류, 재분류 → 리뷰 결과 — 모든 곳에서".
 *  실제 자료: 리뷰에서 안 바뀐 Defect 는 org 0(두 열이 같음), 29126432EWE3 은 장비 스캔 B R Other · Surface Dark → 리뷰 결과 Accept. */
const clsFirst=(s,i)=>{const C=s.cols;return clsOf(s,C.orc[i]||C.rc[i])};
const clsName=(s,i)=>clsOf(s,s.cols.rc[i]);   // 리뷰 결과(지금 분류)
/** 한 줄 글(새 창 머리): 같으면 하나, 다르면 '장비 스캔 분류 → 리뷰 결과'. */
const clsText=(s,i)=>{const a=clsFirst(s,i),b=clsName(s,i);return a===b?a:`${a} → ${b}`};
/** 5-1 목록 칸. */
function cgShort(s,i){const g=s.cg;if(!g||!g.plan)return g&&!g.err?'✖ 매칭 파일 없음':'✖ 매칭 파일 오류';const r=cgOf(s,i);
  return r.c&&r.hit?'Color · Gray':r.c?'Color 만':r.hit?'Gray 만':'✖ 매칭 없음'}
/** 폴더 하나(읽기 전용 핸들): get(이름) = 이름으로 바로(목록 안 만듦), names() = 이름 목록 한 번(사진 내용은 안 읽음 · 실패해도 멈추지 않음 — Map.err), subs() = 하위 폴더. */
function cgDirH(h,path){let N=null;const fo=f=>f?{name:f.name,path:path+'/'+f.name,file:()=>f.getFile()}:null;return {path,
  get:async n=>fo(await dirFind(h,n)),peek:async n=>fo(await dirFile(h,n)),listed:()=>listMemo.has(h),
  opt:async n=>fo(listMemo.has(h)?await dirFind(h,n):await dirFile(h,n)),   // 없어도 되는 파일: 목록이 이미 있으면 목록에서, 없으면 이름으로만(5-1 에서 사진 많은 Slot 목록을 새로 만들지 않게)
  names:()=>N||(N=dirList(h).then(L=>{const m=new Map();for(const [k,e] of L.files)m.set(k,{name:e.name,path:path+'/'+e.name,file:()=>e.h.getFile()});if(L.err)m.err=L.err;return m})),
  subs:()=>dirSubs(h).then(l=>l.map(([n,c])=>cgDirH(c,path+'/'+n)),()=>[]),errs:()=>dirErrs.get(h)||[]}}
/** 폴더 하나(webkitdirectory 파일 목록): base 아래 파일을 폴더별로 묶는다. */
function cgDirsFromList(base,files){const by=new Map();
  for(const e of files){if(!e.path.startsWith(base+'/'))continue;const nm=baseName(e.path),d=e.path.slice(0,e.path.length-nm.length-1);let m=by.get(d);if(!m)by.set(d,m=new Map());
    if(!m.has(lower(nm)))m.set(lower(nm),{name:nm,path:e.path,file:()=>{const f=e.file||e.handle;return f&&f.getFile?f.getFile():Promise.resolve(f)}})}
  const mk=d=>({path:d,get:async n=>(by.get(d)||new Map()).get(lower(n))||null,peek:async n=>(by.get(d)||new Map()).get(lower(n))||null,opt:async n=>(by.get(d)||new Map()).get(lower(n))||null,listed:()=>true,errs:()=>[],names:async()=>by.get(d)||new Map(),
    subs:async()=>[...by.keys()].filter(x=>x.startsWith(d+'/')&&!x.slice(d.length+1).includes('/')).sort(natCmp).map(mk)});
  for(const d of [...by.keys()])for(let p=d;p.length>base.length;p=p.slice(0,p.lastIndexOf('/')))if(!by.has(p))by.set(p,new Map());   // 파일 없는 중간 폴더
  return mk(base)}
/** 5-1: Slot 의 매칭 폴더 · 매칭 파일 읽기 → 프로그램 계산(cgPlan) → Defect 연결(cgLink). 사진 · 다른 파일 내용은 열지 않는다. 결과 s.cg(src = 무엇으로 계산했는지).
 *  소유자 확정(2026-11-10): ScanResultImageList.txt 는 없을 수 있음 · 변환 파일이 frameToChuckPlane.1.ini · .2.ini 둘이면 .2 기준(그 레시피 번호 파일이 없을 때).
 *  v14.4.1(#89, 소유자): ColorImageGrabingInfo.ini 도 없을 수 있다 → Color = 사진 이름, Gray = Defect 좌표(geoLoad · geoHit — 기본 모드와 같은 계산).
 *  · Gray 프레임 목록: ScanResultImageList.txt(프로그램) → 없으면 Gray 사진 이름(X.Y.t.jpeg = 프레임 가운데 Table 좌표) + s_FrameData.dat(프레임마다 잰 TablePos · WaferPos)
 *    → 그것도 없으면 이름 + Wafer2Table.ini(Table → Wafer). 실제 결과 폴더: 이름 + s_FrameData ≤ 0.13 px, 이름 + Wafer2Table ≤ 2.6 px(#89 실제 Slot 최대 9 µm) — v14.4.1 에서 순서 바꿈.
 *  · 변환: frameToChuckPlane.ini 가 있으면 프로그램(레시피 번호 파일 → 공통) / 번호 파일만 있으면 그 레시피 번호 파일 → 없으면 가장 큰 번호(.1 · .2 → .2, 소유자) /
 *    하나도 없으면 레시피마다 가운데 모델(목록 좌표 = 프레임 가운데 — 실제 변환 파일로 확인, 픽셀 = s_FrameData → RecipesInfo → 0.7698 µm, 크기 = s_FrameData → 3168×1024).
 *  · 계산은 geoLoad(3절과 함께 — 기본 모드 buildScan 도 같은 함수). */
const CG_TF_NUM=[0,1,2,3,4,5,6,7,8,9],CG_PIX=0.7698455822;
/** s_FrameData.dat(+ .md) → {n, tx, ty(TablePos), wx, wy(WaferPos = 프레임 가운데 Wafer 좌표), fi(frameIdx), rc(recipe), size(레시피 → {W, H}), pixs(레시피 → PixelSizeX), pix}.
 *  없거나 크기가 맞지 않으면 null. 수 ~ 수십 MB 라 필요할 때만(목록 · 변환 파일이 없을 때, 장비 프레임 기록이 있을 때) 읽는다. md 가 없으면 실제 결과 폴더의 배치(192 byte). */
async function cgFrameData(d){const f=await d.get('s_FrameData.dat');if(!f)return null;
  const mf=await d.get('s_FrameData.dat.md'),md=mf?parseMd(await readText(await mf.file())):null,by=new Map((md?md.fields:[]).map(x=>[lower(x.name),x]));
  const DEF={tableposx:[88,'float64'],tableposy:[96,'float64'],waferposx:[72,'float64'],waferposy:[80,'float64'],pixelsizex:[120,'float64'],frameidx:[60,'int32'],recipe:[58,'uint8'],framesizex:[108,'int32'],framesizey:[112,'int32']};
  const fld=k=>{const x=by.get(k);return x?[x.offset,x.type]:DEF[k]},rec=md&&md.recordSize||192;
  const buf=await (await f.file()).arrayBuffer();if(!buf.byteLength||buf.byteLength%rec)return null;
  const n=buf.byteLength/rec,dv=new DataView(buf),o={tx:fld('tableposx'),ty:fld('tableposy'),wx:fld('waferposx'),wy:fld('waferposy'),px:fld('pixelsizex'),fi:fld('frameidx'),rc:fld('recipe'),fw:fld('framesizex'),fh:fld('framesizey')};
  const ok=k=>o[k]&&o[k][0]+(TYPE_SIZE[o[k][1]]||8)<=rec,rd=(b,k)=>readField(dv,b+o[k][0],o[k][1]);
  const R={n,tx:new Float64Array(n),ty:new Float64Array(n),wx:new Float64Array(n),wy:new Float64Array(n),fi:ok('fi')?new Int32Array(n):null,rc:new Int16Array(n).fill(-1),size:new Map(),pixs:new Map()};
  for(let i=0;i<n;i++){const b=i*rec;R.tx[i]=rd(b,'tx');R.ty[i]=rd(b,'ty');R.wx[i]=rd(b,'wx');R.wy[i]=rd(b,'wy');if(R.fi)R.fi[i]=rd(b,'fi');if(ok('rc'))R.rc[i]=rd(b,'rc');
    const r=R.rc[i]>=0?R.rc[i]:null;
    if(!R.size.has(r)&&ok('fw')&&ok('fh')){const W=rd(b,'fw'),H=rd(b,'fh');if(W>=64&&H>=64&&W<=20000&&H<=20000)R.size.set(r,{W,H})}
    if(!R.pixs.has(r)&&ok('px')){const p=rd(b,'px');if(p>0.05&&p<20)R.pixs.set(r,p)}}
  R.pix=geoFirst(R.pixs);return R}
/** G 에 s_FrameData 를 한 번만 읽어 둔다(없으면 false). 레시피마다 프레임 크기 · 픽셀 크기도 G 에. */
async function geoFd(G,d){if(G.fd===null){let R=null;try{R=await cgFrameData(d)}catch(e){R=null}G.fd=R||false;if(R){for(const [r,v] of R.size)G.fsize.set(r,v);for(const [r,v] of R.pixs)G.fpix.set(r,v)}}return G.fd||null}
/** 매칭 폴더의 Gray 사진 이름(X.Y.t[.레시피].jpeg — X, Y = 프레임 가운데 Table 좌표, 정수) 목록(한 번만). 목록 실패면 .err. */
async function geoGrayNames(d,G){if(G.gn)return G.gn;const nm=await d.names(),L=[];if(nm.err){L.err=nm.err;return G.gn=L}
  const re=/^(-?\d+)\.(-?\d+)\.t(?:\.(\d+))?\.jpe?g$/i;for(const e of nm.values()){const m=re.exec(e.name);if(m)L.push({file:e.name,tx:+m[1],ty:+m[2],recipe:m[3]!=null?+m[3]:null})}return G.gn=L}
/** s_FrameData 에서 TablePos 가 (tx, ty) 에 가장 가까운 레코드(tol µm 안, 같으면 나중 것 — 실제 자료: 목록 좌표 = 나중 레코드). 없으면 −1. */
function geoFdNear(R,tx,ty,tol){const Z=10,K=(i,j)=>i+','+j;if(!R.grid){R.grid=new Map();for(let i=0;i<R.n;i++){const k=K(Math.floor(R.tx[i]/Z),Math.floor(R.ty[i]/Z));(R.grid.get(k)||R.grid.set(k,[]).get(k)).push(i)}}
  let b=-1,bd=tol;const ci=Math.floor(tx/Z),cj=Math.floor(ty/Z);
  for(let di=-1;di<=1;di++)for(let dj=-1;dj<=1;dj++)for(const i of R.grid.get(K(ci+di,cj+dj))||[]){const dd=Math.hypot(R.tx[i]-tx,R.ty[i]-ty);if(dd<=bd){bd=dd;b=i}}return b}
/** ScanResultImageList.txt 가 없을 때 Gray 프레임 목록: Gray 사진 이름 → s_FrameData.dat 의 그 프레임 잰 위치(WaferPos) → 없으면 Wafer2Table.ini 로 이름의 Table 좌표를 Wafer 로.
 *  v14.4.1(#89) 순서 바꿈(종전 Wafer2Table 먼저): 이름은 정수 · 명령 위치라 목록과 수 µm 다르다(#89 실제 Slot: Y 가운데 5.2 · 최대 9.1 µm), s_FrameData 는 목록과 ≤ 0.13 px(rev5 실제 결과 폴더). */
async function geoFramesFromNames(d,G){const L=await geoGrayNames(d,G);if(L.err)return {frames:[],why:'매칭 폴더 목록 실패: '+L.err};if(!L.length)return {frames:[],why:'Gray 사진(X.Y.t.jpeg)이 없음'};
  const R=await geoFd(G,d);let w=null;const w2=await d.get('Wafer2Table.ini');
  if(w2){const t=await readText(await w2.file()),X=/Wafer2Table_X\s*=\s*(\S+)\s+(\S+)\s+(\S+)/i.exec(t),Y=/Wafer2Table_Y\s*=\s*(\S+)\s+(\S+)\s+(\S+)/i.exec(t);
    if(X&&Y){const [a,b,c0]=X.slice(1).map(Number),[c,e,c1]=Y.slice(1).map(Number),det=a*e-b*c;if(det&&[a,b,c0,c,e,c1].every(Number.isFinite))w=f=>[(e*(f.tx-c0)-b*(f.ty-c1))/det,(-c*(f.tx-c0)+a*(f.ty-c1))/det]}}
  const fr=[];let nf=0,nw=0;
  for(const f of L){const b=R?geoFdNear(R,f.tx,f.ty,5):-1;if(b>=0){fr.push({file:f.file,x:R.wx[b],y:R.wy[b],recipe:f.recipe});nf++;continue}
    if(w){const [x,y]=w(f);fr.push({file:f.file,x,y,recipe:f.recipe});nw++}}
  if(!fr.length)return {frames:[],why:R||w?'Gray 사진 이름이 s_FrameData.dat · Wafer2Table.ini 와 맞지 않음':'Wafer2Table.ini · s_FrameData.dat 가 없음'};
  return {frames:fr,src:nf&&nw?`Gray 사진 이름 + s_FrameData.dat ${nf} · Wafer2Table.ini ${nw}`:nf?'Gray 사진 이름 + s_FrameData.dat':'Gray 사진 이름 + Wafer2Table.ini'}}
/** 두 모드 공통(v14.4.1, #89): 매칭 폴더 d(get · peek · opt · names · listed — cgDirH · cgDirsFromList · dirFromFiles)의 파일로 Gray 위치 자료 G 를 만든다. 사진 내용은 읽지 않는다.
 *  pts = Defect 좌표 표본 [[x, y, recipe]](좌표 기준 · 번호 파일 점검), rec = 장비 프레임 기록이 있음('now' = 지금 s_FrameData 를 읽음, 'later' = geoLoadFd 를 나중에(5-1 은 빠르게)).
 *  · 프레임 목록: ScanResultImageList.txt → Gray 사진 이름 + s_FrameData.dat → 이름 + Wafer2Table.ini (geoFramesFromNames)
 *  · 변환: frameToChuckPlane.ini(+ 레시피 번호 파일) → 번호 파일만이면 그 레시피 번호 파일, 없으면 큰 번호(소유자 ".1 · .2 → .2") →
 *    하나도 없으면 레시피마다 가운데 모델(픽셀 = s_FrameData → RecipesInfo.ini → 0.7698, 크기 = s_FrameData → 3168×1024)
 *  · 좌표 기준(CG.MODES) = geoPlan(Defect 좌표). */
async function geoLoad(d,pts,rec){
  const G={frames:[],tfs:new Map(),tfNames:[],tfAlt:[],src:{},fsize:new Map(),fpix:new Map(),rpix:new Map(),rcpix:new Map(),fd:null,gn:null,mode:0,rect:null,noGray:'',usedHi:false,pmemo:null,recPending:false};
  try{const ri=await (d.opt||d.get)('RecipesInfo.ini');if(ri){const R=parseRecipesInfo(await readText(await ri.file()));G.rpix=R.pix;G.rcpix=R.cpix;G.rname=R.name}}catch(e){}
  const sl=await d.get(CG.SL);
  if(sl){G.frames=cgFrames(await readText(await sl.file()));G.src.frames=CG.SL}
  else{const r=await geoFramesFromNames(d,G);G.frames=r.frames;G.src.frames=r.src||'';if(!G.frames.length){G.noGray=r.why;G.src.frames=`Gray 없음(${r.why})`}}
  const tf=await d.get(CG.TF),num=new Map();
  if(d.listed()){const nm=await d.names();for(const [k,v] of nm){const key=cgTfKey(k);if(typeof key==='number'&&!num.has(key))num.set(key,v)}}
  if(!num.size)await Promise.all(CG_TF_NUM.map(async r=>{const f=await d.peek(`frameToChuckPlane.${r}.ini`);if(f)num.set(r,f)}));
  if(!tf&&!num.size){const nm=await d.names();for(const [k,v] of [...nm].sort((a,b)=>a[0]<b[0]?-1:1)){const key=cgTfKey(k);if(typeof key==='number'&&!num.has(key))num.set(key,v);else if(key&&!num.has(key))num.set(key,v)}}
  const parse=async f=>{try{return parseTransform(await readText(await f.file()))}catch(e){return {err:`${f.name}: ${e.message}`}}};
  if(tf){G.tfs.set(null,await parse(tf));G.tfNames.push(tf.name);for(const [k,f] of num){G.tfs.set(k,await parse(f));G.tfNames.push(f.name)}G.src.tf=tf.name+(num.size?' + 레시피 번호 파일':'')}
  else if(num.size){   // 번호 파일만: 레시피 번호가 같은 파일(프로그램 · 소유자 예 29126432EWE3 = Color · Gray 사진이 레시피 1 · 2) → 없으면 가장 큰 번호(.1 · .2 → .2, 소유자)
    const ks=[...num.keys()].sort((a,b)=>typeof a==='number'&&typeof b==='number'?a-b:String(a)<String(b)?-1:1),hi=ks.filter(k=>typeof k==='number').pop()??ks[ks.length-1];
    const P=new Map();for(const k of ks)P.set(k,await parse(num.get(k)));for(const k of ks)G.tfs.set(k,P.get(k));G.tfs.set(null,P.get(hi));G.tfNames.push(...ks.map(k=>num.get(k).name));
    const same=ks.every(k=>JSON.stringify(P.get(k))===JSON.stringify(P.get(hi)));
    G.src.tf=num.size>1?`${ks.map(k=>num.get(k).name).join(' · ')}(레시피 번호가 같은 파일, 없으면 큰 번호 ${num.get(hi).name}${same?' — 내용 모두 같음':''})`:num.get(hi).name;
    G.usedHi=pts.some(p=>!num.has(p[2]));   // 레시피 번호 파일이 없는 Defect 가 있어 큰 번호를 씀(소유자 기준) — 알림에 표시
    if(!same)for(const k of ks)if(k!==hi)G.tfAlt.push({name:num.get(k).name,t:P.get(k)})}
  else{await geoFd(G,d);const rs=new Set([null,...pts.map(p=>p[2]),...G.frames.map(f=>f.recipe),...G.rpix.keys(),...G.fpix.keys()]);
    for(const r of rs){const p=G.fpix.get(r)||G.rpix.get(r)||geoFirst(G.fpix)||geoFirst(G.rpix)||GEO_PIX,z=G.fsize.get(r)||G.fsize.get(null)||geoFirst(G.fsize)||{W:GEO_W,H:GEO_H};
      G.tfs.set(r,{inv:[[1/p,0],[0,1/p]],off:[-p*z.W/2,-p*z.H/2],W:z.W,H:z.H,pix:p,model:'center'})}
    const t0=G.tfs.get(null);G.src.tf=`변환 파일 없음 → 가운데 모델(목록 좌표 = 프레임 가운데, 픽셀 ${+t0.pix.toFixed(6)} µm${G.fpix.size?'(s_FrameData)':G.rpix.size?'(RecipesInfo.ini)':''} · ${t0.W}×${t0.H})`;G.tfNames.push('(가운데 모델)')}
  if(rec==='now')await geoLoadFd(G,d);else if(rec)G.recPending=true;
  geoPlan(G,pts);
  for(const a of G.tfAlt){a.hits=a.t.err?null:geoCount({...G,tfs:new Map([[null,a.t]]),pmemo:null},pts,G.mode)}   // 점검용: 다른 번호 파일이면 Defect 표본 몇 개가 맞는지
  return G}
/** 장비 프레임 기록을 쓰려고 s_FrameData · Gray 사진 이름을 읽는다(5-2 에서 Slot 마다 한 번 — 5-1 은 빠르게). */
async function geoLoadFd(G,d){await geoFd(G,d);if(G.fd)await geoGrayNames(d,G);G.recPending=false;G.dmemo=null}
/** Color 정보 파일(ColorImageGrabingInfo.ini)이 없을 때 Color 항목 = Slot 폴더의 Color 사진 이름 '{X}.{Y}.c.{번호}[.{레시피}].jpeg'(기본 모드 colorsFromNames 와 같은 좌표 +0.5 µm, 2 µm 안). */
async function cgColorsFromNames(d){const nm=await d.names(),out=[];if(nm.err)return out;
  for(const e of nm.values()){const m=CNAME_RE.exec(e.name);if(!m)continue;const r=/\.c\.-?\d+\.(\d+)\.(?:jpe?g|png|bmp)$/i.exec(e.name);
    out.push({file:e.name,FaultX:String(+m[1]+.5),FaultY:String(+m[2]+.5),...(r?{RecipeNumber:r[1]}:{}),fromName:true,_nc:{file:e.name,x:+m[1]+.5,y:+m[2]+.5,index:null,fromName:true}})}
  return out.sort((a,b)=>natCmp(a.file,b.file))}
/** ColorImageGrabingInfo.ini 를 못 찾았을 때 화면에 보일 까닭(프로그램 #48 의 diagnosis 처럼): 폴더 파일 수 · 비슷한 이름 · 이름으로 묻기 오류 · 찾아본 폴더 · 경로 길이. */
async function cgDiag(d,look){const nm=await d.names(),L=[...nm.values()].map(e=>e.name),er=d.errs?d.errs():[];
  const like=L.filter(n=>/color|grab|imageinfo/i.test(n)&&!/\.(jpe?g|png|bmp)$/i.test(n)).slice(0,4),ini=L.filter(n=>/\.ini$/i.test(n)).slice(0,6);
  const full=pcBaseSet()?pcPath(d.path+'/'+CG.CI):'',len=full.length;
  return [nm.err?`Slot 폴더 목록 오류(${nm.err})`:`Slot 폴더 파일 ${L.length.toLocaleString()}개 중 이 이름(대소문자 무시) 없음`,
    like.length?`비슷한 이름: ${like.join(', ')}`:ini.length?`.ini 파일: ${ini.join(', ')}`:'',er.length?`이름으로 묻기 오류: ${er.slice(0,2).join(' · ')}${er.some(t=>/not allowed/i.test(t))?' — 브라우저가 이 이름(.ini)을 막음: [폴더 추가]를 다시 눌러 파일 목록 방식으로 고르십시오':''}`:'',
    `하위 폴더 ${look.subs}개${look.ups.length?` · 위쪽 폴더 ${look.ups.length}개`:''}도 찾아봄`,look.shared||'',
    len?`전체 경로 ${len}자${len>=250?'(Windows 260자 제한에 가까움 — 더 짧은 경로로 옮겨 보십시오)':''}`:''].filter(Boolean).join(' · ')}
const cgMiss=g=>!g?'안 읽음':g.err||('없음: '+g.missing.join(', ')+(g.diag?' — '+g.diag:''));
async function cgLoad(s,root,up){const g=s.cg={missing:[],colors:[],frames:[],tfs:new Map(),tfNames:[],tfAlt:[],dir:null,path:root.path,src:{},at:'slot'};
  try{
    // 소유자 "ColorImageGrabingInfo.ini 파일 자체를 못 찾는다": 종전 rev5 는 이름으로 한 번만 물었다(대소문자 · 일시 오류에 약함, 위쪽 폴더 안 봄 — Step 1 은 목록에서 대소문자 무시로 찾음).
    // 지금: 이름으로 바로 → 없으면 폴더 목록(대소문자 무시, 프로그램 #48 과 같음). 찾는 곳: Slot 폴더 → 하위 폴더(4단계, 다른 Slot 빼고) → 이 Slot 하나만 있는 위쪽 폴더.
    // v14.4.1(#89, 소유자 "대규모 모드가 Color 정보 파일 없이 흑백도 찾게끔"): ColorImageGrabingInfo.ini 는 이제 없어도 된다 — 종전에는 여기서 멈춰 Gray 도 '매칭 파일 없음'이었다.
    //   없으면 Color = Color 사진 이름(X.Y.c.….jpeg, 기본 모드와 같음), Gray = Defect 좌표 · 장비 기록(두 모드 공통 geoLoad · geoHit — Gray 에는 Color 가 필요 없다).
    //   매칭 폴더 = ColorImageGrabingInfo.ini 가 있는 폴더(종전 순서) → 없으면 같은 순서로 ScanResultImageList.txt · frameToChuckPlane.ini 가 있는 폴더 → Slot 폴더.
    const has=async d=>{const [ci,sl,tf]=await Promise.all([d.get(CG.CI),d.get(CG.SL),d.get(CG.TF)]);return {d,ci,any:!!(ci||sl||tf)}};
    let hit=await has(root),alt=hit.any?hit:null;const look={subs:0,ups:[],shared:''};
    if(!hit.ci){   // 하위 폴더 중 ColorImageGrabingInfo.ini 가 있는 첫 폴더(프로그램 discover 처럼). Surface.flt 가 있는 하위 폴더 = 다른 Slot 이라 빌려 쓰지 않는다(그 아래도 안 봄)
      const q=[[root,0]];let found=null;
      while(q.length&&!found){const [d,dep]=q.shift();if(dep>=4)continue;
        for(const sd of await d.subs()){look.subs++;if(await sd.get('Surface.flt'))continue;const h=await has(sd);if(h.ci){found=h;break}if(!alt&&h.any)alt=h;q.push([sd,dep+1])}}
      if(found){hit=found;g.at='sub'}}
    if(!hit.ci)for(const u of up||[]){   // 위쪽 폴더(가까운 것부터, 고른 폴더까지): 그 아래 Slot 이 이 Slot 하나일 때만 — 여러 Slot 이 같이 쓰는 파일은 Index(기록 순서)가 맞지 않아 쓰지 않는다
      look.ups.push(u.d.path);const h=await has(u.d);if(!h.ci)continue;
      if(u.n===1){hit=h;g.at='up'}else look.shared=`위쪽 폴더 ${u.d.path} 에 있지만 그 아래 Slot 이 ${u.n}개라 쓰지 않음`;break}
    if(!hit.ci&&alt&&alt.d!==root){hit=alt;g.at='sub'}
    g.dir=hit.d;g.path=hit.d.path;
    let colorSrc=CG.CI;
    if(hit.ci){if(g.at==='up')s.warns.push(`${CG.CI} 가 Slot 폴더가 아니라 위쪽 폴더에 있어 그 폴더를 매칭 폴더로 씀: ${g.path} (그 아래 Slot 은 이것 하나)`);
      g.colors=cgColors(await readText(await hit.ci.file()))}
    else{g.missing.push(CG.CI);g.diag=await cgDiag(root,look);g.colors=await cgColorsFromNames(hit.d);colorSrc=g.colors.length?`Color 사진 이름 ${g.colors.length}장`:'없음';
      s.warns.push(`${CG.CI} 없음 — ${g.colors.length?`Color 는 Slot 폴더의 Color 사진 ${g.colors.length}장 이름(X.Y.c.….jpeg)의 좌표로 연결`:'Color 연결 불가(사진 이름도 없음)'} · Gray 는 Defect 좌표로 찾음 (${g.path}) — ${g.diag}`)}
    // Gray 위치 자료(두 모드 공통): 프레임 목록 · 변환 · 레시피별 프레임 크기 · 픽셀 크기 · 좌표 기준. 장비 프레임 기록은 5-2 에서(geoLoadFd)
    Object.assign(g,await geoLoad(hit.d,geoPtsCols(s.cols),geoHasRecCols(s.cols)?'later':false));g.src.color=colorSrc;
    if(g.noGray){const why=/X\.Y\.t\.jpeg/.test(g.noGray)?`Gray 사진 없음 — 이 Slot 에는 Gray 프레임 사진(X.Y.t.jpeg) · ${CG.SL} 가 없음(Color 만)`:`Gray 위치를 못 구함 — ${CG.SL} 가 없고 대신할 것도 없음(${g.noGray}, Color 만)`;
      g.plan={mode:0,rect:null,hits:0,recs:g.colors.map(c=>{const [fx,fy]=cgFault(c);return {c,fx,fy,r:cgRecipe(c),why}})};cgLink(s);s.warns.push(why);return}
    g.plan=cgPlan(g);cgLink(s);
  }catch(e){const full=pcBaseSet()?pcPath(g.path+'/'+CG.CI):'';
    g.err=`매칭 파일을 읽지 못함(${g.path}): ${e&&e.name&&e.name!=='Error'?e.name+' ':''}${(e&&e.message)||e}${full.length>=250?` — 전체 경로 ${full.length}자(Windows 260자 제한에 가까움)`:''}`;g.plan=null;s.warns.push(g.err)}}

// ════════════════════════════════════════════════════════════════════════
// 15. Step 5 — 대용량 Defect 조회 (소유자 세션 지시 2026-11-10, 3단계로 다시 만듦)
//     폴더 구조: 레시피 폴더 / Setup 폴더 / Lot 폴더 / Slot 폴더(최대 25개, Surface.flt 가 있는 폴더).
//     5-1 Contrast 모으기 · 걸러내기: 레시피 폴더를 고르면 폴더만 훑어 Slot 을 찾고(Slot 안 사진 목록은 만들지 않음) Surface.flt 만 읽어 열 배열로 →
//         Contrast(실제) · Area · Width · Length · Lot · Slot 필터 + 정렬 → 조사할 Defect 를 줄인다.
//     5-2 사진 짝짓기 · CSV: 걸러낸 Defect 마다 Color 이미지(ColorImageGrabingInfo)와 Gray 프레임 + 픽셀 좌표(ScanResultImageList · frameToChuckPlane)를 짝짓고
//         파일이 실제로 있는지 확인 → 경로가 든 CSV 저장. 사진 픽셀은 아직 읽지 않는다.
//     5-3 사진 정밀 조사: 짝지은 Defect 만 Color 원본 + Gray Crop(빨간 박스 · GL 측정)을 띄운다(리스트 / 격자 구조 — v14.1.6 이름). Step 3 · 4 와 같은 계산(grayCrop · linkColor · locateGray).
//     모든 긴 작업은 로딩창(busy)에 단계 · 개수 · 지금 읽는 파일 · 경과 · 마지막 진행 · 속도 · 남은 시간 · 화면 멈춤을 보여 주고 [중지] 할 수 있다.
// ════════════════════════════════════════════════════════════════════════
const BIG={scans:[],view:null,sort:'c-d',stop:false,pairs:null,stale:false,q:[],stage:1,clsOff1:new Set(),clsOff2:new Set(),lotOff:new Set()};   // lotOff = 뺀 Lot 폴더 경로(소유자 "5-1 에서 필터로 제외할 Lot 고를 수 있게")
//   // 끈 이름: 1 = 장비 스캔 분류, 2 = 리뷰 결과(둘 다 맞아야 = AND)
const BRH=26,BHH=28,BIG_MAX=1000000;   // 표에 그리는 줄 수 한도(브라우저 요소 높이 한도) — 넘으면 필터로 줄이라고 알린다
const bigMsg=list=>{$('#bigMsg').innerHTML=list.map(([k,t])=>`<div class="msg ${k}">${esc(t)}</div>`).join('')};
const kb=n=>n>=1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
/** 진행 표시: 호출할 때마다 '마지막 진행' 시각은 갱신하고, 화면은 ms 에 한 번만 다시 그린다. */
function throttle(fn,ms){let t=0;return()=>{const n=performance.now();BUSY.last=n;if(n-t<ms)return;t=n;fn()}}
/** n 개씩 동시에 처리(중지하면 새 일을 시작하지 않음). */
async function pool(items,n,fn){let i=0;const w=async()=>{while(i<items.length&&!BIG.stop){const it=items[i++];await fn(it)}};
  await Promise.all(Array.from({length:Math.max(1,Math.min(n,items.length))},w))}
/** 사진 · 새 창 · Color/Gray 연결에 쓰는 Defect 객체. 열 배열에서 그때 만든다(조금만 기억). */
function bigDef(s,i){const act=S.o.coord==='actual';let d;
  if(s.defects)d=s.defects[i];
  else{const M=s.dc||(s.dc=new Map());d=M.get(i);
    if(!d){if(M.size>400)M.clear();const C=s.cols;d={i,x:C.x[i],y:C.y[i],ActualX:C.ax[i],ActualY:C.ay[i],id:C.id[i],resultID:C.rid[i],recipe:C.rec[i],BoxWidth:C.bw[i],BoxHeight:C.bh[i],area:C.area[i],BlobBreadth:C.w[i],BlobLength:C.l[i],Contrast:C.c[i],reclassify:C.rc[i],orgReclassify:C.orc[i],zone:C.zn[i],waferRegion:C.rg[i],Type:C.ty[i],frameIdx:C.fi[i],xInFrame:C.xf[i],yInFrame:C.yf[i],scan:s,slot:s.slot};
      d.no=s.idByOrder?i:d.id;M.set(i,d)}}
  d.X=act?d.ActualX:d.x;d.Y=act?d.ActualY:d.y;return d}

// ── 5-1: 폴더 훑기 · Surface.flt 읽기 ─────────────────────────────────────
/** 폴더 핸들(읽기 전용)을 n 개씩 동시에 훑는다. 폴더마다 Surface.flt 를 이름으로 바로 찾아(getFileHandle) 있으면 Slot — 그 안은 더 보지 않는다(사진 목록을 만들지 않아 빠르다).
 *  없으면 그 폴더의 하위 폴더만 이어서 본다(깊이 7까지). onProg(폴더 수, Slot 수, 지금 경로). */
async function walkFast(root,par,onProg){
  const q=[{h:root,path:root.name+'/',depth:0,chain:[]}],slots=[],errs=[];let dirs=0,active=0;
  // rev5: Surface.flt 가 있어도 매칭 파일(ColorImageGrabingInfo.ini)이 바로 안에 없으면 그 아래도 본다 — 위쪽 폴더(Lot 등)에 Surface.flt 가 있어도
  //       실제 Slot 이 빠지지 않게(Step 1 planUnits 와 같음). 보통 Slot(매칭 파일이 바로 안)은 종전처럼 안을 나열하지 않는다(사진 수천 장이어도 빠름).
  const visit=async it=>{dirs++;onProg(dirs,slots.length,it.path);
    let flt=null;try{flt=await it.h.getFileHandle('Surface.flt')}catch(e){}
    if(flt){slots.push({...it,flt});if(await dirFile(it.h,CG.CI))return}
    if(it.depth>=7)return;
    let L=await dirList(it.h);   // 목록 오류(네트워크 드라이브 일시 오류)는 1초 · 3초 뒤 두 번 더 — 폴더 아래 Slot 이 통째로 빠지지 않게
    for(let k=0;k<2&&L.err&&!L.dirs.length&&!L.files.size&&!BIG.stop;k++){await waitMs(k?3000:1000);listMemo.delete(it.h);L=await dirList(it.h)}
    if(L.err&&!L.dirs.length&&!L.files.size)throw new Error(L.err);
    const f2=L.files.get('surface.flt');if(!flt&&f2)slots.push({...it,flt:f2.h});
    if((flt||f2)&&L.files.has(lower(CG.CI)))return;   // 매칭 파일이 목록에는 있음(이름 대소문자가 다르거나 이름으로 묻기가 실패) → 이 폴더가 Slot, 아래는 안 봄
    for(const [name,c] of L.dirs)q.push({h:c,path:it.path+name+'/',depth:it.depth+1,chain:[it.h,...it.chain]})};
  await new Promise(res=>{const next=()=>{
      while(!BIG.stop&&active<par&&q.length){const it=q.shift();active++;
        visit(it).catch(e=>errs.push(`${it.path}: ${e.message}`)).then(()=>{active--;next()})}
      if(!active&&(!q.length||BIG.stop))res()};next()});
  slots.sort((a,b)=>natCmp(a.path,b.path));return {slots,dirs,errs};
}
/** Slot 이름 규칙(Step 1 planUnits 와 같음): Slot = Surface.flt 가 있는 폴더, Lot = 그 바로 위 폴더(레시피/Setup/Lot/Slot 이면 Lot 폴더). */
function unitOfPath(p){const s=p.split('/').filter(Boolean),n=s.length,lot=n>1?s.slice(0,-1):s;
  return {dir:p,sel:s[0]||'',lotPath:lot.join('/'),lotName:lot[lot.length-1]||p,slotName:s[n-1]||p,caNames:[lot[lot.length-1],...(n>1?[s[n-1]]:[]),...lot.slice(0,-1).reverse()].filter(Boolean)}}
function newLight(name){return {id:++scanSeq,seq:scanSeq,name,light:true,files:new Map(),paths:null,dirs:[],chain:[],warns:[],errors:[],step:baseName(name),tool:'',contrast:null,colors:[],frames:[],transforms:new Map(),colorByIndex:new Map(),product:null,images:0,fltBytes:0}}
/** 위쪽 폴더(Lot · Setup · 레시피)에서 파일 하나 찾기 — 폴더 · 이름마다 한 번만 묻는다. */
const dirMemo=new WeakMap();
const dirErrs=new WeakMap(),NOTFOUND=new Set(['NotFoundError','TypeMismatchError']);
/** 소유자 #66: 회사 PC Chrome 은 폴더 핸들(showDirectoryPicker)로 .ini 를 막았다 — getFileHandle('ColorImageGrabingInfo.ini') = TypeError 'Name is not allowed.',
 *  폴더 목록(entries)에도 .ini 가 하나도 안 나옴(Slot 파일 39개 중 .ini 0). Step 1 ~ 4 의 <input webkitdirectory> 는 같은 파일을 받는다(그래서 1 ~ 4 는 됨).
 *  → 이름이 막힌 것을 알아보면(TypeError = 이름 거부, '없음'이 아님) 5-1 을 파일 목록 방식으로 바꾼다. 이 PC 에 기억('cw.bigList'). */
const fsaBlocked=e=>!!e&&e.name==='TypeError'&&/not allowed|not valid|invalid/i.test(e.message||'');
let FSA_BLOCK='';
const useList=()=>{if(PARA)return false;try{return localStorage.getItem('cw.bigList')==='1'}catch(e){return false}};   // 폴더 → 이름으로 묻다 난 '없음' 아닌 오류(못 찾을 때 진단에 보임)
function dirFile(h,name){let m=dirMemo.get(h);if(!m)dirMemo.set(h,m=new Map());const k=lower(name);
  if(!m.has(k)){const ask=()=>h.getFileHandle(name);   // '없음' 이 아닌 오류(네트워크 드라이브 일시 오류 등)는 한 번 더 묻는다 — 실패를 '없음'으로 기억해 버리지 않게
    m.set(k,ask().catch(e=>e&&NOTFOUND.has(e.name)?null:fsaBlocked(e)?Promise.reject(e):new Promise(r=>setTimeout(r,150)).then(ask))
      .catch(e=>{if(fsaBlocked(e)&&!FSA_BLOCK)FSA_BLOCK=`${name}: ${e.message}`;if(!(e&&NOTFOUND.has(e.name))){let L=dirErrs.get(h);if(!L)dirErrs.set(h,L=[]);L.push(`${name}: ${((e&&e.name)||'')+' '+((e&&e.message)||e)}`.trim())}return null}))}
  return m.get(k)}
/** 폴더 목록 한 번(프로그램 colorgray.file_names 와 같음 — 이슈 #48 "이름으로 하나씩 묻지 않고 목록 1번, 대소문자 무시"). 사진 내용은 안 읽는다.
 *  {files: Map(소문자 → {name, h}), dirs: [[이름, 핸들]] 이름 순, err}. 핸들마다 한 번(5-1 · 5-2 가 같이 씀). */
const listMemo=new WeakMap();
function dirList(h){let p=listMemo.get(h);
  if(!p){p=(async()=>{const files=new Map(),dirs=[];let err='';
      try{for await(const [n,c] of h.entries()){if(c.kind==='directory')dirs.push([n,c]);else{const k=lower(n);if(!files.has(k))files.set(k,{name:n,h:c})}}}
      catch(e){err=`${(e&&e.name)||''} ${(e&&e.message)||e}`.trim()}
      dirs.sort((a,b)=>natCmp(a[0],b[0]));return {files,dirs,err}})();listMemo.set(h,p)}
  return p}
/** 파일 찾기: 이름으로 바로(빠름, 목록 안 만듦) → 없으면 폴더 목록에서 대소문자 무시(NAS 대소문자 · 이름으로 묻기 실패 — Step 1 · 프로그램과 같은 결과). */
async function dirFind(h,name){const f=await dirFile(h,name);if(f)return f;const L=await dirList(h),e=L.files.get(lower(name));return e?e.h:null}
async function chainText(s,name){for(const h of s.chain){const f=await dirFile(h,name);if(f)return readText(await f.getFile())}return null}
/** Surface.flt(+ .md) · ProductInfo.ini 만 읽어 열 배열로. md · ProductInfo 는 있을 때만(Slot → 위쪽 폴더 순). */
async function finishLight(s,mdText,buf,piText){
  const md=mdText?parseMd(mdText):null;if(mdText&&!md)s.warns.push('Surface.flt.md 를 읽지 못해 기본 필드 정의를 씁니다');
  const {lay,warns}=fltLayout(md);warns.forEach(w=>s.warns.push('md: '+w));
  const r=parseFltCols(buf,lay,fltRec(md,buf.byteLength));s.fltBytes=buf.byteLength;
  if(!r.bytes)s.errors.push('빈 결과(Surface.flt 0 byte)');
  else if(!r.ok)s.errors.push(fltRecErr(r,md));
  else if(r.rec!==REC)s.warns.push(`Surface.flt 레코드 ${r.rec} byte(Surface.flt.md 기준, 기본 ${REC})`);
  s.cols=r.cols;s.idByOrder=r.cols.n>1&&new Set(r.cols.id).size<r.cols.n;
  if(piText)s.product=parseProduct(piText);if(!s.product)s.warns.push('ProductInfo.ini 없음 또는 Die Pitch 없음 — Die 계산 불가');
  return s}
/** rev4(소유자 "둘 다 적용해"): rev3 까지 5-1 은 Surface.flt.md 를 Slot 바로 안에서만 찾아, md 가 Lot 폴더 · Slot 하위 폴더에 있고 그 배치가 기본과 다르면
 *  좌표 · Contrast 를 틀리게 읽었다(Step 1 은 맞게 읽음 — 재현: x · y 자리를 바꾼 md 를 Lot 폴더에 두면 5-1 좌표 353개 전부 틀림 · Color 연결 0).
 *  지금: Step 1 과 같은 순서 — ① Slot 바로 안 ② Slot 하위 폴더(이름 순 · 깊이 우선 · 4단계까지 = Step 1 의 Slot 파일 순서) ③ 위쪽 폴더(가까운 것부터).
 *  ①에 있으면 Slot 안 목록을 만들지 않는다(빠른 길 그대로). ①에 없을 때만 하위 폴더 이름을 보려고 그 Slot 폴더 목록을 한 번 만든다(폴더마다 기억). */
const MD_AT={slot:'Slot 안',sub:'Slot 하위 폴더',up:'위쪽 폴더',none:'없음(기본 배치)'};
const mdWhere=(s,p)=>!p?'none':p.startsWith(s.name+'/')?(p.slice(s.name.length+1).includes('/')?'sub':'slot'):'up';
let MDSUB=0;
function dirSubs(h){return dirList(h).then(L=>{if(L.err&&!L.dirs.length&&!L.files.size)throw new Error(L.err);return L.dirs})}
async function findLikeStep1(s,name){
  const top=await fileFind(s,name,true);if(top)return {...top,at:'slot'};
  const d=s.dirs&&s.dirs[0];
  if(d){MDSUB++;const walk=async(h,path,depth)=>{if(depth>=4)return null;
      for(const [n,c] of await dirSubs(h)){const p=path+n+'/',f=await dirFile(c,name);if(f)return {name:f.name,path:p+f.name,get:()=>f.getFile(),at:'sub'};const r=await walk(c,p,depth+1);if(r)return r}return null};
    const r=await walk(d,s.name+'/',0);if(r)return r}
  let up=s.name.split('/').slice(0,-1);
  for(const h of s.chain){const f=await dirFile(h,name);if(f)return {name:f.name,path:up.join('/')+'/'+f.name,get:()=>f.getFile(),at:'up'};up=up.slice(0,-1)}
  return null}
async function readLight(sl){const s=newLight(sl.path.replace(/\/$/,''));s.dirs=[sl.h];s.chain=sl.chain;
  const md=await findLikeStep1(s,'Surface.flt.md'),f=await sl.flt.getFile(),buf=await f.arrayBuffer();s.mdAt=md?md.at:'none';s.mdPath=md?md.path:'';
  const pi=await fileFind(s,'ProductInfo.ini',true);
  await finishLight(s,md?await readText(await md.get()):null,buf,pi?await readText(await pi.get()):await chainText(s,'ProductInfo.ini'));
  const seg=s.name.split('/');await cgLoad(s,cgDirH(sl.h,s.name),(sl.chain||[]).map((h,k)=>({d:cgDirH(h,seg.slice(0,seg.length-1-k).join('/')),n:sl.under?sl.under[k]:0})));
  await clsLoad(s,s.cg&&s.cg.dir);await rv5Load(s,s.cg&&s.cg.dir);return s}
/** <input webkitdirectory> 로 고른 경우(폴더 핸들을 못 쓰는 브라우저): 브라우저가 만든 파일 목록에서. */
async function buildLight(name,own){const s=newLight(name);s.paths=new Map();s.entries=own.files;
  for(const e of own.files){const k=lower(baseName(e.path));if(/\.(jpe?g|png|bmp)$/.test(k))s.images++;if(!s.files.has(k)){s.files.set(k,e.file||e.handle);s.paths.set(k,e.path)}}
  const text=async n=>{const f=await fileFind(s,n,true);return f?readText(await f.get()):null};
  const flt=await fileFind(s,'Surface.flt',true),md=await fileFind(s,'Surface.flt.md',true);s.mdPath=md?md.path:'';s.mdAt=mdWhere(s,s.mdPath);   // 파일 목록 순서 = Step 1(planUnits)
  await finishLight(s,md?await readText(await md.get()):null,await (await flt.get()).arrayBuffer(),await text('ProductInfo.ini'));
  await cgLoad(s,cgDirsFromList(name,own.files),(own.up||[]).map(u=>({d:cgDirsFromList(u.path,u.files),n:u.n})));await clsLoad(s,s.cg&&s.cg.dir);await rv5Load(s,s.cg&&s.cg.dir);return s}
/** 읽은 Slot 들을 목록에 넣는다(같은 Slot 폴더를 다시 고르면 바꿔 넣음). 이름 = unitOfPath / planUnits. */
function addMade(made,units,head){
  made.sort((a,b)=>natCmp(a.name,b.name));
  const fresh=new Set(made.map(w=>w.name));BIG.scans=BIG.scans.filter(w=>!fresh.has(w.name));
  const known=new Map(BIG.scans.map(w=>[w.lotPath,w]));
  for(const w of made){applyUnit(w,units.get(w.name)||unitOfPath(w.name),known);BIG.scans.push(w)}
  const bad=made.filter(w=>w.errors.length),nd=made.reduce((a,w)=>a+w.cols.n,0);
  const lots=[...new Set(made.map(w=>w.lotPath))];
  const msg=[[bad.length?'warn':'ok',`${head} → Lot ${lots.length}개(${lots.slice(0,6).map(p=>baseName(p)).join(', ')}${lots.length>6?' …':''}) · Slot ${made.length}개 · Defect ${nd.toLocaleString()}개`
    +(bad.length?` — 제외한 Slot ${bad.length}개: `+bad.slice(0,6).map(w=>`${w.name}(${w.errors.join(' / ')})`).join(', ')+(bad.length>6?' …':''):'')]];
  const mc={slot:0,sub:0,up:0,none:0};for(const w of made)mc[w.mdAt||'none']++;
  if(made.length&&mc.slot<made.length)msg.push([mc.none?'warn':'ok','Surface.flt.md 위치(Step 1 과 같은 순서로 찾음): '+Object.entries(mc).filter(([,v])=>v).map(([k,v])=>`${MD_AT[k]} ${v}`).join(' · ')
    +(mc.none?' — md 가 없는 Slot 은 기본 필드 배치로 읽었습니다(5-2 에서 Step 1 방식으로 다시 읽어 값을 비교합니다)':'')]);
  // rev5: 5-1 에서 끝낸 Color · Gray 매칭(Para 프로그램 계산) 요약
  const cs={n:0,miss:[],col:0,hit:0,def:0,link:0,modes:[]};
  for(const w of made){if(w.errors.length)continue;cs.n++;const g=w.cg;
    if(!g||!g.plan){cs.miss.push(`${w.slotName||w.name}(${cgMiss(g)})`);continue}
    cs.col+=g.colors.length;cs.hit+=g.plan.hits;cs.def+=w.cols.n;cs.link+=g.nIdx+g.nXY;if(g.plan.mode)cs.modes.push(`${w.slotName||w.name} ${CG.MODES[g.plan.mode]}`)}
  const altTf=g=>/모델/.test(g.src.tf||'')||!!g.usedHi;
  const alt=made.filter(w=>w.cg&&w.cg.plan&&!w.cg.noGray&&w.cg.src&&(w.cg.src.frames!==CG.SL||altTf(w.cg))).map(w=>`${w.slotName||w.name}: ${[w.cg.src.frames!==CG.SL?w.cg.src.frames:'',altTf(w.cg)?w.cg.src.tf:''].filter(Boolean).join(' · ')}`);
  const ng=made.filter(w=>w.cg&&w.cg.noGray).map(w=>w.slotName||w.name);
  const noCi=made.filter(w=>w.cg&&w.cg.plan&&w.cg.missing&&w.cg.missing.includes(CG.CI)).map(w=>w.slotName||w.name);   // v14.4.1(#89): Color 정보 파일 없이도 Gray 를 찾음
  if(noCi.length)msg.push(['warn',`${CG.CI} 가 없는 Slot ${noCi.length}개 — Color 는 Color 사진 이름(X.Y.c.….jpeg)의 좌표로 연결, Gray 는 Defect 좌표로 찾음: `+noCi.slice(0,6).join(', ')+(noCi.length>6?' …':'')]);
  if(ng.length)msg.push(['warn',`Gray 사진이 없는 Slot ${ng.length}개(Color 사진만 저장됨 — Color 는 보여 주고 Gray 는 '없음'): `+ng.slice(0,6).join(', ')+(ng.length>6?' …':'')]);
  if(alt.length)msg.push(['warn',`프로그램 파일 대신 계산한 Slot ${alt.length}개(ScanResultImageList.txt 없음 → Gray 사진 이름 · 변환 파일 번호 여러 개 → 큰 번호 · 변환 파일 없음 → 가운데 모델): `+alt.slice(0,4).join(' / ')+(alt.length>4?' …':'')]);
  if(cs.n)msg.push([cs.miss.length?'warn':'ok',`Color · Gray 매칭(사진은 아직 안 읽음): Color 항목 ${cs.col.toLocaleString()}개 중 Gray 위치 ${cs.hit.toLocaleString()}개 · Defect ${cs.def.toLocaleString()}개 중 Color 연결 ${cs.link.toLocaleString()}개`
    +(cs.modes.length?` · 좌표 기준이 '그대로'가 아닌 Slot: ${cs.modes.slice(0,4).join(', ')}${cs.modes.length>4?' …':''}`:'')
    +(cs.miss.length?` — 매칭 파일이 없는 Slot ${cs.miss.length}개: ${cs.miss.slice(0,4).join(' / ')}${cs.miss.length>4?' …':''}`:'')]);
  BIG.pairs=null;THUMB.clear();bigLots();bigRefresh();b5tabs();return msg}
const STEPS_A=['① 폴더 훑기 — Slot 폴더(= Surface.flt 가 있는 폴더) 찾기, Slot 안 사진 목록은 만들지 않음','② Slot 마다 Surface.flt + 매칭 파일 읽기 · Color · Gray 매칭 계산(사진은 안 읽음)','③ 목록 · 필터 만들기'];
/** 5-1: 폴더 핸들로(빠른 길). */
async function bigPickHandle(root){
  BIG.stop=false;S.o=opts();MDSUB=0;const par=+$('#bigPar').value||4,t0=performance.now(),cancel=()=>{BIG.stop=true};
  let dirs=0,ns=0,cur=root.name;
  busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:0,indet:true,count:'폴더 0개',files:`동시에 ${par}개 폴더씩`,detail:root.name,cancel,reset:true});
  const p1=throttle(()=>busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:0,indet:true,count:`폴더 ${dirs}개 훑음 · Slot ${ns}개 찾음`,files:`동시에 ${par}개 폴더씩`,detail:'훑는 중: '+cur,cancel}),100);
  let W;try{W=await walkFast(root,par,(d,n,p)=>{dirs=d;ns=n;cur=p;p1()})}catch(e){busy(null);bigMsg([['err','폴더를 읽지 못했습니다: '+e.message]]);return}
  {const cnt=new Map();for(const sl of W.slots)for(const h of sl.chain)cnt.set(h,(cnt.get(h)||0)+1);for(const sl of W.slots)sl.under=sl.chain.map(h=>cnt.get(h)||0)}   // 위쪽 폴더마다 그 아래 Slot 수
  if(W.slots.length&&!BIG.stop){   // #66: 이 브라우저가 폴더 핸들로 .ini 를 막는지 첫 Slot 에서 한 번 본다(막으면 매칭 파일 · ProductInfo.ini 를 못 읽어 모든 Slot 이 '매칭 파일 없음')
    const sl=W.slots[0];let blk='';try{await sl.h.getFileHandle(CG.CI)}catch(e){if(fsaBlocked(e))blk=`${CG.CI}: ${e.message}`}
    if(blk||FSA_BLOCK){bigToList(blk||FSA_BLOCK);return}}
  if(!W.slots.length){busy(null);bigMsg([['err',`'${root.name}' 아래에서 Surface.flt 가 있는 폴더를 찾지 못했습니다(폴더 ${W.dirs}개 훑음)${BIG.stop?' — 중지됨':''}. 레시피 폴더(그 아래 Setup · Lot · Slot)를 고르십시오.`]]);return}
  const made=[],errs=[...W.errs],total=W.slots.length;let done=0,nd=0,bytes=0;cur='';
  const p2=throttle(()=>busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:1,done,total,unit:'Slot',files:`Defect ${nd.toLocaleString()}개 · Surface.flt ${kb(bytes)} 읽음 · 폴더 ${W.dirs}개 훑음${MDSUB?` · Surface.flt.md 가 Slot 바로 안에 없어 하위 폴더까지 찾은 Slot ${MDSUB}개`:''}`,detail:'읽는 중: '+cur,cancel}),80);
  await pool(W.slots,par,async sl=>{cur=sl.path;p2();
    try{const s=await retryRead(()=>readLight(sl));made.push(s);nd+=s.cols.n;bytes+=s.fltBytes}catch(e){errs.push(`${sl.path}: ${e.message}`)}done++;p2()});
  busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:2,indet:true,count:`Defect ${nd.toLocaleString()}개`,detail:'목록 · 필터 만드는 중'});await nextPaint();
  try{const msg=addMade(made,new Map(),`폴더 '${root.name}'`);msg[0][1]+=` (${((performance.now()-t0)/1000).toFixed(1)}초, 폴더 ${W.dirs}개 훑음, 사진은 읽지 않음)`;
    if(BIG.stop)msg.push(['warn',`중지했습니다 — Slot ${total}개 중 ${done}개만 읽었습니다.`]);
    if(errs.length)msg.push(['err',`읽지 못한 폴더 ${errs.length}개: `+errs.slice(0,5).join(' · ')+(errs.length>5?' …':'')]);bigMsg(msg)}
  finally{busy(null)}
}
/** 5-1: 파일 목록으로(webkitdirectory · 시험). entries = [{path, file}]. */
async function addBigEntries(entries){
  const {units,sum}=planUnits(entries);
  if(!units.length){busy(null);bigMsg([['err','고른 폴더에 Surface.flt 가 없습니다. 레시피 폴더(그 아래 Setup · Lot · Slot)를 고르십시오.']]);return}
  BIG.stop=false;S.o=opts();const total=units.length,t0=performance.now(),made=[],U=new Map(),cancel=()=>{BIG.stop=true};let done=0,nd=0,cur='';
  // 위쪽 폴더마다 그 아래 Slot 수 — 한 번에 센다(종전 Slot 마다 전체 Slot 을 다시 셈 = Slot 수의 제곱: 5,000개 3초 · 15,000개 29초)
  const under=new Map();for(const v of units){const sg=v.dir.split('/').filter(Boolean);for(let k=sg.length;k>=1;k--){const D=sg.slice(0,k).join('/');under.set(D,(under.get(D)||0)+1)}}
  const p2=throttle(()=>busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:1,done,total,unit:'Slot',files:`Defect ${nd.toLocaleString()}개`,detail:'읽는 중: '+cur,cancel}),80);
  busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:1,done,total,unit:'Slot',files:'',detail:'',cancel,reset:true});
  try{for(const u of units){if(BIG.stop)break;cur=u.dir;p2();await nextPaint();
      const seg=u.dir.split('/').filter(Boolean),up=[],byDir=new Map();   // 위쪽 폴더(가까운 것부터): 그 폴더 파일 · 그 아래 Slot 수
      for(const e of u.shared){const d=e.path.slice(0,e.path.length-baseName(e.path).length);let L=byDir.get(d);if(!L)byDir.set(d,L=[]);L.push(e)}
      for(let k=seg.length-1;k>=1;k--){const D=seg.slice(0,k).join('/');up.push({path:D,files:byDir.get(D+'/')||[],n:under.get(D)||0})}
      try{const s=await retryRead(()=>buildLight(u.dir.replace(/\/$/,'')||'(선택 폴더)',{files:u.files,up}));made.push(s);U.set(s.name,u);nd+=s.cols.n}catch(e){}
      done++;p2()}
    busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:2,indet:true,count:`Defect ${nd.toLocaleString()}개`,detail:'목록 · 필터 만드는 중'});await nextPaint();
    const msg=addMade(made,U,sum.replace(/ → Lot.*$/,''));msg[0][1]+=` (${((performance.now()-t0)/1000).toFixed(1)}초, 사진은 읽지 않음)`;bigMsg(msg)}
  finally{busy(null)}
}
function bigSources(){return BIG.scans.filter(s=>!s.errors.length)}
/** 등록 Lot 표 + Lot · Slot 고르기 */
function bigLots(){
  const m=new Map();for(const w of BIG.scans){let L=m.get(w.lotPath);if(!L)m.set(w.lotPath,L={path:w.lotPath,step:w.step,contrast:w.contrast,ws:[]});L.ws.push(w)}
  const L=[...m.values()];
  $('#bigSum').textContent=`등록한 Lot ${L.length}개 · Slot ${BIG.scans.length}개 · Defect ${BIG.scans.reduce((a,w)=>a+w.cols.n,0).toLocaleString()}개`;
  $('#bigTbl tbody').innerHTML=L.map(l=>{const er=l.ws.filter(w=>w.errors.length),wr=l.ws.flatMap(w=>w.warns.map(t=>w.slotName+': '+t));
    return `<tr><td title="${esc(l.path)}">${esc(baseName(l.path))}</td><td class="muted" title="${esc(l.path)}">${esc(l.path)}</td><td class="num">${l.ws.length}</td><td class="num">${l.ws.reduce((a,w)=>a+w.cols.n,0).toLocaleString()}</td><td>${esc(rcpSum(l.ws.map(w=>[w.cols.n,i=>rcp5(w,i)])))}</td>
      <td title="${esc([...er.map(w=>w.slotName+': '+w.errors.join(' / ')),...wr].join('\n'))}">${er.length?`⛔ 오류 Slot ${er.length}`:wr.length?`⚠ ${wr.length}건`:'✔ 정상'}</td><td><button data-bigdel="${esc(l.path)}">빼기</button></td></tr>`}).join('')||'<tr><td colspan="7" class="muted">아직 없습니다.</td></tr>';
  const src=bigSources(),lots=new Map(),slots=new Map();for(const s of src){lots.set(s.lotPath,s.lotName||baseName(s.lotPath));slots.set(s.slot,s.slotName||s.slot)}
  const fillSel=(el,mp)=>{const cur=el.value;el.innerHTML='<option value="">전체</option>'+[...mp].sort((a,b)=>natCmp(a[1],b[1])).map(([k,n])=>`<option value="${esc(k)}">${esc(n)}</option>`).join('');el.value=cur;if(el.value!==cur)el.value=''};
  fillSel($('#bigLot'),lots);fillSel($('#bigSlot'),slots);
  // Lot 제외 · 분류 필터 2묶음(소유자): 칸(종류 · 순서)은 등록한 전체로 정하고, 괄호 개수는 bigRefresh → bigFacetFill(Para v14.1.4: 다른 필터를 따름)
  {const tot=new Map(),c1=new Map(),c2=new Map();for(const s of src){tot.set(s.lotPath,(tot.get(s.lotPath)||0)+s.cols.n);for(let i=0;i<s.cols.n;i++){const a=clsFirst(s,i),b=clsName(s,i);c1.set(a,(c1.get(a)||0)+1);c2.set(b,(c2.get(b)||0)+1)}}
    const ord=m=>[...m].sort((a,b)=>b[1]-a[1]||natCmp(a[0],b[0])).map(x=>x[0]);
    BIG.facet={lots:[...tot.keys()].sort((a,b)=>natCmp(lots.get(a)||'',lots.get(b)||'')),lotName:lots,c1:ord(c1),c2:ord(c2)}}
  // #73: Recipe 고르기(종전 5-1 은 빈 칸이었다) — Para #75: 개수는 bigRefresh → bigRcpFill(필터에 맞는 것만)
}
/** Para v14.1.5(소유자 "필터 제목 · 행 간격 구분 · 하위 목록은 간격에 맞춰 · Lot 제외는 다른 줄"): 칸 하나 = 체크 · 이름(길면 …) · 개수(오른쪽), 칸들은 같은 너비 격자(.chipgrid). */
const fChip=(attr,k,name,n,off,title)=>`<label class="clsck${off?' off':''}" title="${esc(title||name)}"><input type="checkbox" ${attr}="${esc(k)}"${off?'':' checked'}> <span class="nm">${esc(name)}</span> <span class="muted">${(n||0).toLocaleString()}</span></label>`;
/** Para v14.1.4: Lot 제외 · 장비 스캔 분류 · 리뷰 결과 칸의 개수 = 자기 묶음을 뺀 다른 필터(Lot · Slot 고르기, 나머지 체크, Recipe, Contrast · Area · Width · Length)에 맞는 Defect 수.
 *  칸(종류)은 0개여도 남겨 다시 켤 수 있게 한다. V = bigBuild() 결과(nLot · n1 · n2). */
function bigFacetFill(V){const F=BIG.facet;if(!F)return;const off=BIG.lotOff,L=F.lots,nOff=L.filter(k=>off.has(k)).length;
  $('#bigLotOff').innerHTML=L.length?`<div class="chipgrid">${L.map(k=>fChip('data-lotoff',k,F.lotName.get(k)||baseName(k),V.nLot.get(k),off.has(k),k)).join('')}</div>`
    +(L.length>1?`<div class="fx"><button type="button" data-lotall="1">${nOff?'모두 켜기':'모두 끄기'}</button></div>`:''):'<span class="muted">Lot 없음</span>';
  $('#bigLotSum').textContent=nOff?`${nOff}개 제외 / 전체 ${L.length}개`:`제외 없음 (전체 ${L.length}개)`;$('#bigLotBox').classList.toggle('has',!!nOff);
  const grp=(g,t,ks,cnt,off)=>`<div class="frow"><span class="fh">${t}</span><div class="fb">`+(ks.length?`<div class="chipgrid">${ks.map(k=>fChip('data-cls'+g,k,k,cnt.get(k),off.has(k))).join('')}</div>`
    +(ks.length>1?`<div class="fx"><button type="button" data-clsall="${g}">${off.size?'모두 켜기':'모두 끄기'}</button></div>`:''):'<span class="muted">Lot 을 등록하면 나옵니다</span>')+'</div></div>';
  $('#bigCls').innerHTML=grp(1,'장비 스캔 분류',F.c1,V.n1,BIG.clsOff1)+grp(2,'리뷰 결과',F.c2,V.n2,BIG.clsOff2)}
/** Para #75: 5-1 Recipe 고르기 = Recipe 이름 + 개수. 개수 = Recipe 를 뺀 다른 필터(Lot · Slot · Lot 제외 · 분류 · Contrast · Area · Width · Length)에 맞는 Defect 수.
 *  필터를 걸면 그에 맞게 줄고, 고른 값은 0개가 되어도 남긴다(종전 #73 은 등록한 전체 수였다). */
function bigRcpFill(n){const sel=$('#bigFlt [data-f="rcp"]');if(!sel)return;
  const v=sel.value,ks=[...n.keys()].sort(natCmp);if(v&&!n.has(v))ks.push(v);
  sel.innerHTML='<option value="">전체</option>'+ks.map(k=>`<option value="${esc(k)}">${esc(k)} (${(n.get(k)||0).toLocaleString()})</option>`).join('');sel.value=v}
/** #83 후속: 5-1 Zone 고르기 = Zone + 개수(Zone 을 뺀 다른 필터에 맞는 Defect 수, Recipe 칸과 같은 방식). */
function bigZnFill(n){const sel=$('#bigFlt [data-f="zn"]');if(!sel)return;
  const v=sel.value,ks=[...n.keys()].sort(natCmp);if(v&&!n.has(v))ks.push(v);
  sel.innerHTML='<option value="">전체</option>'+ks.map(k=>`<option value="${esc(k)}">${esc(k)} (${(n.get(k)||0).toLocaleString()})</option>`).join('');sel.value=v}
/** 필터 → 정렬 → 보기(V). 줄 = (스캔 번호 gs, 스캔 안 순서 gi), ord = 화면 순서. */
/** noQ = 5-1 검색을 빼고 계산해서 돌려주기만(BIG.view 는 그대로) — 5-2 · 5-3 필터(bigRankOf)용. */
function bigBuild(noQ){
  const o=S.o=opts(),f=readFlt($('#bigFlt')),src=bigSources(),lot=$('#bigLot').value,slot=$('#bigSlot').value,act=o.coord==='actual';
  let N=0;for(const s of src)N+=s.cols.n;
  const [sk,sd]=BIG.sort?BIG.sort.split('-'):['',''],gs=new Int32Array(N),gi=new Int32Array(N),kv=sk?new Float64Array(N):null,bad=sd==='d'?-Infinity:Infinity;let m=0;
  const rank=key=>new Map([...new Set(src.map(key))].sort(natCmp).map((n,i)=>[n,i])),rl=sk==='lot'?rank(s=>s.lotPath):null,rs=sk==='slot'?rank(s=>s.slotName||''):null;
  const kf=sk==='k1'?clsFirst:sk==='k2'?clsName:sk==='r'?rcp5:null,rk=kf?(()=>{const set=new Set();for(const s of src)for(let i=0;i<s.cols.n;i++)set.add(kf(s,i));return new Map([...set].sort(natCmp).map((n,j)=>[n,j]))})():null;
  const off1=BIG.clsOff1.size?BIG.clsOff1:null,off2=BIG.clsOff2.size?BIG.clsOff2:null;
  const lotOff=BIG.lotOff,rc=new Map(),znc=new Map(),nLot=new Map(),n1=new Map(),n2=new Map(),add=(m,k)=>m.set(k,(m.get(k)||0)+1);   // v14.1.4: 칸마다 '자기 묶음을 뺀' 개수
  // v14.1.8 검색: 글(Lot · Slot, 분류 이름, Recipe)마다 맞는 단어를 한 번만 세어 둔다 → 줄마다는 비트 OR 몇 번(30만 줄도 가볍게)
  const T=noQ?[]:BIG.q||[],full=(1<<T.length)-1,qc=new Map(),qm=x=>{let v=qc.get(x);if(v===undefined){v=0;const y=lower(String(x));for(let j=0;j<T.length;j++)if(y.includes(T[j]))v|=1<<j;qc.set(x,v)}return v};let np=0;
  const tn=T.reduce((a,w,j)=>/^[-\d.,×]+$/.test(w)&&/\d/.test(w)?a|1<<j:a,0);   // 숫자 단어(글자 없음)일 때만 숫자 열 글을 만든다(30만 줄)
  src.forEach((s,si)=>{if(lot&&s.lotPath!==lot)return;if(slot&&s.slot!==slot)return;const C=s.cols,n=C.n,lon=!lotOff.has(s.lotPath),nm=s.rv&&s.rv.recipe,lp=s.lotPath;
    if(!s.pk||s.pk.length!==n)s.pk=new Uint8Array(n).fill(LS.def?1:0);const pk=s.pk,qb=T.length?qm(`${s.lotName||baseName(s.lotPath)} ${s.slotName||''}`):0;   // v14.1.8 ☑(처음 = [처음엔 모두 ☑])
    const cg=s.cg,lk=T.length&&cg&&cg.plan&&cg.link?cg.link:null,recs=lk?cg.plan.recs:null;   // 사진 파일 이름 = Color 연결(5-1 에서 이미 계산) — 연결 없는 Defect 의 Gray 프레임은 5-2 에서
    const sv=sk==='lot'?rl.get(s.lotPath):sk==='slot'?rs.get(s.slotName||''):null;
    const zcache=new Map(),zl=i=>{const z=C.zn?C.zn[i]:null;let v=zcache.get(z);if(v===undefined)zcache.set(z,v=zoneLbl(z,s));return v};   // #83 후속 Zone 글(Slot 마다 이름표가 다를 수 있다)
    const ka=sk==='id'?(s.idByOrder?null:C.id):sk==='c'?C.c:sk==='w'?C.w:sk==='l'?C.l:sk==='a'?C.area:sk==='x'?(act?C.ax:C.x):sk==='y'?(act?C.ay:C.y):null;
    const [uA,uW]=umK(s),ku=sk==='a'?uA:sk==='w'?uW:1,u1=sizePix(s).pix;   // v14.4.1: Area · Width = [µm 로 보기] 단위(Slot 마다 µm 환산 픽셀)
    for(let i=0;i<n;i++){if(f.on&&!fltPass(f,C.c[i],C.area[i]*uA,C.w[i]*uW,C.l[i]))continue;
      const k1=clsFirst(s,i),k2=clsName(s,i),p1=!(off1&&off1.has(k1)),p2=!(off2&&off2.has(k2)),r=C.rec[i],rl=r===0&&nm?`0 (${nm})`:String(r),pr=!f.rcp||rl===f.rcp,zk=zl(i),pz=!f.zn||zk===f.zn;   // 글 = rcp5 와 같음
      if(T.length){let w=qb|qm(k1)|qm(k2)|qm(rl);   // 검색 = 다른 필터와 같이
        if(w!==full&&(tn&~w)){const X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product),
            ns=`${s.idByOrder?i:C.id[i]} ${fv(C.c[i])} ${fv(C.area[i]*u1*u1)} ${fv(C.area[i])} ${fv(C.w[i])} ${fv(C.w[i]*u1)} ${fv(C.l[i])} ${f1(C.bw[i])}×${f1(C.bh[i])} ${f1(X)} ${f1(Y)}${die?` ${die.col}, ${die.row}`:''}${(m=>m&&m.x!=null?` ${m.x}, ${m.y}`:'')(mapDie(X,Y,s))}`;
          for(let j=0;j<T.length;j++)if(!(w>>j&1)&&ns.includes(T[j]))w|=1<<j}
        if(w!==full&&lk){const ck=lk[i];if(ck>=0){const rec=recs[ck];w|=(rec.c&&rec.c.file?qm(rec.c.file):0)|(rec.frame&&rec.frame.file?qm(rec.frame.file):0)}}
        if(w!==full)continue}
      if(p1&&p2&&pr&&pz)add(nLot,lp);if(!lon)continue;
      if(p2&&pr&&pz)add(n1,k1);if(p1&&pr&&pz)add(n2,k2);if(!p1||!p2)continue;if(pz)add(rc,rl);if(pr)add(znc,zk);   // Para #75: Recipe · Zone = 다른 필터 기준
      if(!pr||!pz)continue;gs[m]=si;gi[m]=i;if(kv){const v=sv!=null?sv:rk?rk.get(kf(s,i)):ka?ka[i]*ku:i;kv[m]=v===v?v:bad}np+=pk[i];m++}});
  const ord=new Int32Array(m);for(let i=0;i<m;i++)ord[i]=i;
  if(kv){const sg=sd==='d'?-1:1;ord.sort((p,q)=>sg*(kv[p]-kv[q])||p-q)}
  const V={src,gs,gi,ord,m,total:N,f,rc,zn:znc,nLot,n1,n2,np,q:T};if(!noQ)BIG.view=V;return V;
}
const bigAt=k=>{const V=BIG.view,j=V.ord[k];return {s:V.src[V.gs[j]],i:V.gi[j]}};

// ── 가상 스크롤 표(5-1 · 5-2 · 5-3 목록 공용) ────────────────────────────
/** cols = [[제목, 폭px, class, 정렬 키]], o.row(k) → 칸 배열, o.cls(k) → 줄 class, o.onSel(k), o.onEnter(k), o.onSort(키), o.sort() → '키-a|d' */
function makeVT(box,cols,o){const V={box,cols,o,n:0,sel:0};
  box.style.setProperty('--bgc',cols.map(c=>c[1]+'px').join(' '));box.style.setProperty('--bgw',cols.reduce((a,c)=>a+c[1],0)+'px');
  box.addEventListener('scroll',()=>vtPaint(V));
  box.addEventListener('click',e=>{const h=e.target.closest('[data-sort]');if(h){o.onSort&&o.onSort(h.dataset.sort);return}const r=e.target.closest('.br');if(r)vtGo(V,+r.dataset.k)});
  // 첫 클릭이 줄을 다시 그리면 dblclick 대상이 목록 상자가 될 수 있다 → 그때는 고른 줄
  box.addEventListener('dblclick',e=>{if(e.target.closest('.bh')||!V.n)return;const r=e.target.closest('.br');if(r)vtGo(V,+r.dataset.k,true);o.onEnter&&o.onEnter(V.sel)});
  return V}
function vtSet(V,n,keep){V.n=Math.min(n,BIG_MAX);const [sk,sd]=(V.o.sort&&V.o.sort()||'').split('-'),w=V.cols.reduce((a,c)=>a+c[1],0);
  V.box.innerHTML=`<div class="bh" role="row">${V.cols.map(([t,,cls,k])=>`<span class="${cls}"${k?` data-sort="${k}" title="누르면 이 값으로 정렬"`:''}>${esc(t)}${k&&k===sk?(sd==='d'?' ▼':' ▲'):''}</span>`).join('')}</div><div style="height:${V.n*BRH}px;width:${w}px"></div>`;
  if(!keep){V.sel=0;V.box.scrollTop=0}V.sel=Math.max(0,Math.min(V.n-1,V.sel));vtPaint(V)}
function vtPaint(V){const box=V.box,top=box.scrollTop,h=box.clientHeight||600,s=Math.max(0,Math.floor(top/BRH)-8),e=Math.min(V.n,Math.ceil((top+h)/BRH)+8);
  box.querySelectorAll('.br').forEach(x=>x.remove());const fr=document.createDocumentFragment();
  for(let k=s;k<e;k++){const cells=V.o.row(k),el=document.createElement('div');el.className='br'+(k===V.sel?' sel':'')+(V.o.cls?' '+V.o.cls(k):'');el.style.top=BHH+k*BRH+'px';el.dataset.k=k;
    el.innerHTML=cells.map((v,j)=>`<span class="${V.cols[j][2]}" title="${esc(v)}">${esc(v)}</span>`).join('');fr.append(el)}
  box.append(fr)}
function vtGo(V,k,quiet){if(!V.n)return;k=Math.max(0,Math.min(V.n-1,k));const ch=k!==V.sel;V.sel=k;const box=V.box,vh=box.clientHeight-BHH;
  const top=box.scrollTop;if(k*BRH<top)box.scrollTop=k*BRH;else if((k+1)*BRH>top+vh)box.scrollTop=(k+1)*BRH-vh;
  // 스크롤이 그대로면 줄을 다시 만들지 않고 표시만 바꾼다(줄을 갈아 끼우면 브라우저가 더블 클릭을 알아채지 못한다)
  if(box.scrollTop===top&&box.querySelector(`.br[data-k="${k}"]`))box.querySelectorAll('.br').forEach(el=>el.classList.toggle('sel',+el.dataset.k===k));else vtPaint(V);
  if(ch&&!quiet&&V.o.onSel)V.o.onSel(k)}
function vtKey(V,e){if(!V||/INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName))return;const k=e.key.toLowerCase();if(!V.n)return;
  const page=Math.max(1,Math.floor((V.box.clientHeight-BHH)/BRH)-1),mv={arrowdown:1,arrowright:1,j:1,arrowup:-1,arrowleft:-1,k:-1,pagedown:page,pageup:-page}[k];   // rev5: ←→ 도 이전 · 다음(소유자)
  if(mv){vtGo(V,V.sel+mv);e.preventDefault()}else if(k==='home'||k==='end'){vtGo(V,k==='home'?0:V.n-1);e.preventDefault()}
  else if(k==='enter'&&V.o.onEnter){V.o.onEnter(V.sel);e.preventDefault()}
  else if(k===' '&&V.o.onSpace){V.o.onSpace(V.sel);e.preventDefault()}}
const sortClick=k=>{const [sk,sd]=BIG.sort?BIG.sort.split('-'):['',''];return k+'-'+(k===sk?(sd==='d'?'a':'d'):(/^[cawl]$/.test(k)?'d':'a'))};

// ── 5-1 목록 ───────────────────────────────────────────────────────────
const VA=makeVT($('#bigList'),[['☑',46,'pk',null],['#',64,'num',null],['Lot',150,'','lot'],['Slot',120,'','slot'],['ID',66,'num','id'],['장비 스캔 분류',150,'','k1'],['리뷰 결과',150,'','k2'],['Recipe',130,'','r'],['Contrast(실제)',124,'num','c'],['Area (µm²)',92,'num','a','a'],['Width (µm)',68,'num','w','w'],['Length',68,'num','l'],
  ['Box W×H',96,'',null],['Wafer X',100,'num','x'],['Wafer Y',100,'num','y'],['Die (맵 X, Y)',120,'',null],['Color · Gray 매칭',120,'',null]],{
  sort:()=>BIG.sort,onSort:k=>{BIG.sort=sortClick(k);bigRefresh()},
  row:k=>{const o=S.o,act=o.coord==='actual',{s,i}=bigAt(k),C=s.cols,X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product);
    return [s.pk[i]?'☑':'☐',k+1,s.lotName||baseName(s.lotPath),s.slotName||'',s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),fv(C.c[i]),...umCells(s,C,i),fv(C.l[i]),`${f1(C.bw[i])}×${f1(C.bh[i])}`,f1(X),f1(Y),dieTxt(mapDie(X,Y,s)),cgShort(s,i)]},
  cls:k=>{const {s,i}=bigAt(k);return s.pk[i]?'':'off'},onSpace:k=>bigPick(k)});
/** v14.1.8 5-1 ☑: 줄 하나 바꾸기 · 보이는 줄 모두(전체 선택 / 전체 해제 — 안 보이는 줄은 그대로). */
function bigPick(k){const V=BIG.view;if(!V||k<0||k>=V.m)return;const {s,i}=bigAt(k),v=s.pk[i]^1;s.pk[i]=v;V.np+=v?1:-1;vtPaint(VA);bigPickInfo()}
function bigPickAll(v){const V=BIG.view;if(!V)return;for(let k=0;k<V.m;k++){const j=V.ord[k];V.src[V.gs[j]].pk[V.gi[j]]=v?1:0}V.np=v?V.m:0;vtPaint(VA);bigPickInfo()}
function bigPickInfo(){const V=BIG.view,n=V?V.np:0,m=V?V.m:0;LSA.set(n,m);$('#toB2').disabled=!n;$('#bigCsv').disabled=!n;
  $('#bigCsv').textContent=n?`목록 CSV (☑ ${n.toLocaleString()}개)`:'목록 CSV';
  $('#toB2').textContent=n?`다음: ☑ ${n.toLocaleString()}개 결과 목록 · 사진 확인 →`:m?'다음: ☑ 한 Defect 가 없습니다':'다음: 결과 목록 · 사진 확인 →'}
const LSA=lsBind('bigLs',{onQ:T=>{BIG.q=T;bigRefresh()},onAll:bigPickAll,delay:()=>BIG.view&&BIG.view.total>100000?700:LS.delay});
$('#bigList').addEventListener('click',e=>{const c=e.target.closest('.br>span.pk');if(c)bigPick(+c.parentNode.dataset.k)});
function bigRefresh(){
  const t0=performance.now(),V=bigBuild();vtSet(VA,V.m);pixLineSet($('#bigPix'),V.src);
  bigRcpFill(V.rc);bigZnFill(V.zn);bigFacetFill(V);   // Para #75 · v14.1.4
  const sel=$('#bigFlt [data-f="sort"]');sel.value=BIG.sort;if(sel.value!==BIG.sort)sel.value='';
  $('#bigCnt').textContent=V.total?`Defect ${V.m.toLocaleString()}개`+(V.m<V.total?` (전체 ${V.total.toLocaleString()}개 중 필터 · 검색 · Lot · Slot 에 맞는 것)`:'')+(V.q.length?` · 검색 '${V.q.join(' ')}'`:'')+` · Slot ${V.src.length}개 · ${Math.round(performance.now()-t0)} ms`
    +(V.m>BIG_MAX?` · ⚠ 표에는 앞 ${BIG_MAX.toLocaleString()}줄만 그립니다(CSV · 매칭은 전부).`:''):'레시피 폴더를 고르면 Defect 목록이 여기에 나옵니다.';
  bigPickInfo();
  if(BIG.pairs){b5Refresh();if(BIG.stage===3)c5Refresh(true)}   // 소유자 2026-11-24: 필터는 5-1 · 5-2 · 5-3 같은 값 — 어느 단계에서 바꿔도 지금 목록에 바로
}
/** 대규모 5-2 · 5-3 필터(소유자 2026-11-24 "5-1 · 2 · 3 모두 필터가 있어야 하고 단계가 바뀌어도 유지"): 5-1 필터 카드 한 벌이 지금 단계 목록 위로 따라가고(b5go),
 *  5-2 · 5-3 목록은 5-1 에서 넘어온 Defect 중 그 필터(Lot · Slot · Lot 제외 · 분류 · 값 범위 · Recipe · Zone)에 맞는 것만, 5-1 정렬 순서로 보인다.
 *  계산 = 5-1 목록과 같은 bigBuild(검색만 단계마다 따로) → (Slot, 줄) 마다 5-1 순서 번호, 맞지 않으면 -1. */
function bigRankOf(){const V=BIG.q&&BIG.q.length?bigBuild(true):BIG.view;if(!V)return null;const R=new Map();
  for(let k=0;k<V.m;k++){const j=V.ord[k],s=V.src[V.gs[j]];let a=R.get(s);if(!a)R.set(s,a=new Int32Array(s.cols.n).fill(-1));a[V.gi[j]]=k}return R}
/** 5-1 목록 CSV(사진 정보 없음) — 보이는 줄 중 ☑ 한 것만(v14.1.8). */
function bigCsv(){const V=BIG.view;if(!V)return null;const o=S.o,act=o.coord==='actual';
  const parts=['\ufeff'+['순서','Lot','Lot경로','Slot','ID','resultID','WaferX','WaferY','DieCol','DieRow','Die맵X','Die맵Y','Area_um2','Area_px','Width','Length','BoxW','BoxH','Contrast','장비스캔분류','리뷰결과',...RV5_HEAD].join(',')+'\r\n'];let buf=[];
  for(let k=0;k<V.m;k++){const {s,i}=bigAt(k);if(!s.pk[i])continue;const C=s.cols,X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product);   // v14.1.8: ☑ 한 줄만
    buf.push([k+1,csvQ(s.lotName),csvQ(s.lotPath),csvQ(s.slotName||''),s.idByOrder?i:C.id[i],C.rid[i],f2(X),f2(Y),die?die.col:'',die?die.row:'',...(m=>m&&m.x!=null?[m.x,m.y]:['',''])(mapDie(X,Y,s)),fv(C.area[i]*um2(s)),C.area[i],fv(C.w[i]),fv(C.l[i]),f2(C.bw[i]),f2(C.bh[i]),fv(C.c[i]),csvQ(clsFirst(s,i)),csvQ(clsName(s,i)),...rv5Cells(s,i).map(csvQ)].join(','));
    if(buf.length>=20000){parts.push(buf.join('\r\n')+'\r\n');buf=[]}}
  if(buf.length)parts.push(buf.join('\r\n')+'\r\n');return parts}
const csvQ=v=>{v=v==null?'':String(v);return /[",\r\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
/** 저장 위치 고르기(showSaveFilePicker) — 사람이 누른 직후에만 열 수 있다. 고른 파일 핸들, 취소 = false, 이 브라우저에 없음 = null. */
async function pickSave(name,types){if(!window.showSaveFilePicker)return null;
  try{return await window.showSaveFilePicker({suggestedName:name,types:types||[{description:'CSV',accept:{'text/csv':['.csv']}}]})}catch(e){return e&&e.name==='AbortError'?false:null}}
/** CSV 저장: 미리 고른 핸들 → (pick 이면) 지금 위치 고르기 → 둘 다 없으면 다운로드 폴더(file:// 페이지에서는 브라우저가 이름을 'download' 로 바꿀 수 있다). 원본 폴더에는 쓰지 않는다. */
async function saveCsv(parts,name,pick,handle){const blob=new Blob(parts,{type:'text/csv'});let h=handle||null;
  if(!h&&pick){h=await pickSave(name);if(h===false)return null}
  if(h){const w=await h.createWritable();await w.write(blob);await w.close();return `저장: ${h.name}`}
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),5000);
  return `다운로드 폴더에 저장: ${name} (이름이 'download' 로 바뀌어 있으면 끝에 .csv 를 붙이십시오)`}
const stamp=()=>{const d=new Date(),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}${z(d.getMonth()+1)}${z(d.getDate())}_${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}`};

// ── 5-2: 사진 짝짓기 · CSV ──────────────────────────────────────────────
const ST5={ok:'Color·Gray 매칭 완료',color:'Color 만 (Gray 없음)',gray:'Gray 만 (Color 없음)',none:'둘 다 없음',skip:'확인 안 함 (중지)'};
const STEPS_B=['① Slot 마다 매칭 폴더의 파일 이름 목록 (사진 내용 · 다른 파일은 열지 않음)','② Defect 마다 Color · Gray 사진 파일이 있는지 이름으로 확인','③ 결과 목록 · CSV 만들기'];
/** [다음] · [짝짓기 다시 하기]: (자동 저장이면) 저장 위치를 먼저 고르고 — 고르기 창은 누른 직후에만 열린다 — 짝짓기를 돌린 뒤 그 파일에 쓴다. */
async function b5Start(go2){const V=BIG.view;if(!V||!V.np)return;
  if(V.np>50000&&!confirm(`Defect ${V.np.toLocaleString()}개를 매칭합니다. 오래 걸릴 수 있습니다. 5-1 에서 필터로 더 줄이면 빠릅니다. 계속할까요?`))return;
  let save=null;if($('#b5auto').checked){const h=await pickSave(csvName());save=h===false?null:{h}}
  if(go2)b5go(2);await b5Pair(save)}
/** save = {h: 파일 핸들 | null(다운로드 폴더)} 이면 끝난 뒤 CSV 저장, null 이면 저장 안 함.
 *  rev5: 짝(매칭)은 5-1 에서 Para 프로그램 계산으로 끝났다. 여기서는 Slot 마다 매칭 폴더의 파일 이름 목록을 한 번 만들어(사진 내용은 안 읽음) 사진 파일이 있는지만 본다.
 *  rev3 · rev4 는 Slot(하위 4단계) · 위쪽 폴더의 사진 아닌 파일을 전부 열어(getFile) 하나만 실패해도 그 아래 Slot 이 모두 0 이 됐다 — 이제 다른 파일은 열지 않는다. */
async function b5Pair(save){
  const V=BIG.view;if(!V||!V.np)return;
  BIG.stop=false;THUMB.clear();const par=+$('#bigPar').value||4,t0=performance.now(),cancel=()=>{BIG.stop=true};
  const cnt={ok:0,color:0,gray:0,none:0},hows=new Map();let ds=0,di=0,cur='',step=0;
  const items=[];for(let k=0;k<V.m;k++){const j=V.ord[k],s=V.src[V.gs[j]],i=V.gi[j];if(s.pk[i])items.push({k,s,i,st:'skip',r:null,c:null,g:null,cerr:'중지로 확인 안 함',gerr:''})}   // v14.1.8: 보이는 ☑ 줄만
  const N=items.length;
  const bySlot=new Map();for(const p of items)(bySlot.get(p.s)||bySlot.set(p.s,[]).get(p.s)).push(p);const slots=[...bySlot.keys()];
  const show=()=>busy({title:'5-2 결과 목록 · 사진 확인',steps:STEPS_B,step,done:step?di:ds,total:step?N:Math.max(1,slots.length),unit:step?'Defect':'Slot',
    files:`Slot ${ds} / ${slots.length} · Color·Gray 매칭 완료 ${cnt.ok} · Color 만 ${cnt.color} · Gray 만 ${cnt.gray} · 둘 다 없음 ${cnt.none}`,detail:cur,cancel});
  const pr=throttle(show,80);
  busy({title:'5-2 결과 목록 · 사진 확인',steps:STEPS_B,step:0,done:0,total:Math.max(1,slots.length),unit:'Slot',files:'',detail:'',cancel,reset:true});
  try{
    await pool(slots,par,async s=>{const g=s.cg,st=s.pst={n:0,cl:0,cf:0,gl:0,gf:0};let names=null;
      if(g&&g.dir){cur=`매칭 폴더 이름 목록(사진 내용은 안 읽음): ${g.path}`;pr();names=await g.dir.names()}
      if(g&&g.dir&&g.recPending){cur=`장비 프레임 기록(s_FrameData.dat) 읽는 중: ${g.path}`;pr();await geoLoadFd(g,g.dir)}   // v14.4.1(#89): frameIdx · xInFrame 이 있는 Defect = 장비가 적은 프레임 · 픽셀
      ds++;pr();
      const find=async n=>{const b=cleanName(n||'');if(!b||!g||!g.dir)return null;if(names&&!names.err)return names.get(lower(b))||null;return g.dir.get(b)};
      for(const p of bySlot.get(s)){if(BIG.stop)return;step=1;const r=p.r=cgOf(s,p.i);cur=`사진 확인: ${s.name} · ID ${s.idByOrder?p.i:s.cols.id[p.i]}`;
        const cf=r.c?await find(r.c.file):null,gf=r.hit?await find(r.hit.frame.file):null;
        p.c=r.c&&cf?{file:cf.name,path:cf.path,how:CG_HOW[r.how]}:null;
        p.cerr=!g||!g.plan?r.why:!r.c?(g.missing&&g.missing.includes(CG.CI)?'Color 없음(ColorImageGrabingInfo.ini 가 없고 Color 사진 이름에도 이 Defect 가 없음)':'Color 항목 없음(ColorImageGrabingInfo.ini 에 이 Defect 가 없음)'):!cf?`Color 파일 없음: ${cleanName(r.c.file)} (${g.path})`:'';
        p.g=r.hit&&gf?{file:gf.name,path:gf.path,px:r.hit.px,py:r.hit.py,n:r.hit.n,from:r.from,W:r.hit.W,H:r.hit.H,model:r.hit.model}:null;
        p.gerr=!g||!g.plan?'':!r.hit?`Gray: ${r.why||'매칭되는 Gray 프레임 없음'}`:!gf?`Gray 파일 없음: ${cleanName(r.hit.frame.file)} (${g.path})`:'';
        if(r.c){const h=CG_HOW[r.how];hows.set(h,(hows.get(h)||0)+1)}
        st.n++;if(r.c)st.cl++;if(cf)st.cf++;if(r.hit)st.gl++;if(gf)st.gf++;
        p.st=p.c&&p.g?'ok':p.c?'color':p.g?'gray':'none';cnt[p.st]++;di++;pr()}});
    step=2;cur='결과 목록 만드는 중';show();await nextPaint();
    {const wp=new Map((BIG.pairs||[]).map(p=>[p.s.id+'|'+p.i,!!p.pick]));for(const p of items){const v=wp.get(p.s.id+'|'+p.i);p.pick=v===undefined?LS.def:v}}   // v14.1.8 5-3 ☑: 처음 = 옵션(소유자 "전체 선택을 기본으로"), 다시 확인해도 남김
    {const w2=new Map((BIG.pairs||[]).map(p=>[p.s.id+'|'+p.i,p.on2]));for(const p of items){const v=w2.get(p.s.id+'|'+p.i);p.on2=v===undefined?LS.def:v}}   // v14.1.8 5-2 ☑: 다시 확인해도 남김, 새 줄 = 옵션
    {const old=new Map((BIG.pairs||[]).filter(p=>p.glp).map(p=>[p.s.id+'|'+p.i,p.glp]));if(old.size)for(const p of items){const g=old.get(p.s.id+'|'+p.i);if(g){p.glp=g;p.glv=glMean(p)}}}   // rev6 GL 측정값도 남김   // #68 최종 목록 ☑ 는 다시 확인해도 남김
    BIG.pairs=items;b5SlotTbl(slots);
    const sec=((performance.now()-t0)/1000).toFixed(1),skip=N-di;
    $('#b5pairSt').innerHTML=`<div class="msg ${skip?'warn':'ok'}">${esc(`Defect ${N.toLocaleString()}개 확인 끝 (${sec}초): Color·Gray 매칭 완료 ${cnt.ok} · Color 만 ${cnt.color} · Gray 만 ${cnt.gray} · 둘 다 없음 ${cnt.none}`+(skip?` · 중지로 확인 안 함 ${skip}`:''))}</div>`;
    if(hows.size)$('#b5pairSt').insertAdjacentHTML('beforeend',`<div class="msg ok">${esc('Color 연결: '+[...hows].map(([k,v])=>`${k} ${v.toLocaleString()}`).join(' · ')+' · Gray = frameToChuckPlane 변환')}</div>`);
    const modes=slots.filter(s=>s.cg&&s.cg.plan&&s.cg.plan.mode).map(s=>`${s.slotName||s.name}: ${CG.MODES[s.cg.plan.mode]}`);
    if(modes.length)$('#b5pairSt').insertAdjacentHTML('beforeend',`<div class="msg warn">${esc("좌표 기준이 '그대로'가 아닌 Slot(프로그램과 같이 가장 많이 맞는 기준을 씀): "+modes.slice(0,6).join(' / ')+(modes.length>6?' …':''))}</div>`);
    const miss=slots.filter(s=>!s.cg||!s.cg.plan).map(s=>`${s.slotName||s.name}(${cgMiss(s.cg)})`);
    if(miss.length)$('#b5pairSt').insertAdjacentHTML('beforeend',`<div class="msg err">${esc('매칭 파일이 없어 매칭하지 못한 Slot: '+miss.slice(0,6).join(' / ')+(miss.length>6?' …':''))}</div>`);
    b5Refresh();b5tabs();
    if(save&&!skip){const r=await saveCsv(pairCsv(),csvName(),false,save.h);$('#b5pairSt').insertAdjacentHTML('beforeend',`<div class="msg ok">CSV ${esc(r)}</div>`)}
    else if(save&&skip)$('#b5pairSt').insertAdjacentHTML('beforeend','<div class="msg warn">중지해서 CSV 를 자동 저장하지 않았습니다. 지금까지 결과를 저장하려면 [CSV 저장]을 누르십시오.</div>');
  }finally{FS.note=null;busy(null)}
}
/** Slot 별 결과: 매칭 폴더 · 세 파일 · 연결 수 — 덜 붙은 Slot 은 노란 줄(상자 자동 펼침). */
function b5SlotTbl(slots){const rows=slots.filter(s=>s.pst).sort((a,b)=>natCmp(a.lotPath,b.lotPath)||natCmp(a.slotName||'',b.slotName||'')).map(s=>{const st=s.pst,g=s.cg||{},pc=(a,b)=>b?`${a} (${Math.round(100*a/b)}%)`:'0',bad=!g.plan||st.cf<st.n||st.gf<st.n;
    return `<tr${bad?' style="background:var(--warnbg)"':''}><td>${esc(s.lotName||'')}</td><td>${esc(s.slotName||'')}</td><td class="num">${st.n}</td><td class="num">${(g.colors||[]).length}</td><td class="num">${pc(st.cl,st.n)}</td><td class="num">${pc(st.cf,st.n)}</td>
      <td class="num">${(g.frames||[]).length}${g.src&&g.src.frames&&g.src.frames!==CG.SL?`<br><span class="muted">${esc(g.src.frames)}</span>`:''}</td><td>${esc((g.src&&g.src.tf)||(g.tfNames||[]).join(' · ')||'없음')}</td><td class="num">${pc(st.gl,st.n)}</td><td class="num">${pc(st.gf,st.n)}</td><td>${g.plan?esc(CG.MODES[g.plan.mode]):'-'}</td>
      <td class="muted" style="white-space:normal;min-width:240px">${esc([g.path?`매칭 폴더 ${g.path}`:'',g.err||'',g.missing&&g.missing.length?'없음: '+g.missing.join(', '):'',...(g.noGray?[]:g.tfAlt||[]).map(a=>`${a.name} 이면 Gray 위치 ${a.hits==null?'계산 못 함':a.hits+' / '+(g.ptsN||0)}(Defect 표본)`),...s.warns.filter(w=>!/id 가 고유하지|frameIdx\/xInFrame|매칭 파일/.test(w))].filter(Boolean).join(' / '))}</td></tr>`});
  $('#b5slotTbl tbody').innerHTML=rows.join('')||'<tr><td colspan="12" class="muted">없음</td></tr>';
  $('#b5slotBox').open=slots.some(s=>s.pst&&(!s.cg||!s.cg.plan||s.pst.cf<s.pst.n||s.pst.gf<s.pst.n))}
const csvName=()=>`Defect_매칭_${(BIG.scans[0]&&BIG.scans[0].name.split('/')[0])||'목록'}_${stamp()}.csv`.replace(/[\\/:*?"<>|]/g,'_');
/** 고른 폴더부터의 경로('RCP/SETUP1/…/x.jpeg') → PC 전체 경로(소유자 "사진 파일명뿐만 아니라 전체 경로도"). [원본 폴더 경로(PC)] = 고른 폴더 자체
 *  (마지막 폴더 이름이 고른 폴더 이름과 같으면 그 위를 씀) 또는 그 상위 폴더. 비었으면 고른 폴더 이름부터 그대로. 드라이브 · UNC 경로면 \ 로. */
function pcPath(rel){if(!rel)return '';
  if(PARA){const seg=rel.split('/')[0],R=PARA.roots.get(lower(seg));if(R){const b=String(R.path).replace(/[\\/]+$/,''),win=/\\|^[A-Za-z]:/.test(b),rest=rel.slice(seg.length).replace(/^\/+/,'');
      return rest?(win?b+'\\'+rest.replace(/\//g,'\\'):b+'/'+rest):b}}   // v14: 고른 폴더의 전체 경로(엔진) + 그 아래
const base=(($('#bigBase')||{}).value||'').trim().replace(/^"|"$/g,'').replace(/[\\/]+$/,'');if(!base)return rel;
  const win=/\\|^[A-Za-z]:/.test(base),root=rel.split('/')[0],segs=base.split(/[\\/]/),last=segs[segs.length-1];
  const b=segs.length>1&&root&&lower(last)===lower(root)?base.slice(0,base.length-last.length).replace(/[\\/]+$/,''):base;
  return win?b+'\\'+rel.replace(/\//g,'\\'):b+'/'+rel}
const pcBaseSet=()=>!!(PARA&&PARA.roots.size)||!!(($('#bigBase')||{}).value||'').trim();
/** 결과 CSV. 경로 = 고른 폴더 이름부터의 상대 경로(브라우저는 전체 경로를 알려 주지 않음) — [원본 폴더 경로]를 적으면 그 앞에 붙인다. */
function pairCsv(L){const o=S.o,full=pcPath;   // L = 줄 목록(없으면 전체 — 확인 직후 자동 저장)
  const head=['순서','상태','Lot','Lot경로','Slot','ID','resultID','장비스캔분류','리뷰결과','Contrast','Area_um2','Area_px','Width','Length','BoxW','BoxH','WaferX','WaferY','DieCol','DieRow','Die맵X','Die맵Y',
    'Color이미지','Color경로','Color연결','FaultX','FaultY','Gray프레임','Gray경로','GrayPX(3168x1024기준)','GrayPY(3168x1024기준)','후보프레임','Gray계산','좌표기준','CropW','CropH','매칭폴더','Gray프레임목록','변환','이유',...RV5_HEAD,'Gray프레임크기'];   // v14.4.1(#89): 프레임 크기는 레시피마다 다름 — GrayPX/PY 는 그 프레임 픽셀(열 이름은 종전 그대로, 크기 열 추가)
  const parts=['\ufeff'+head.join(',')+'\r\n'];let buf=[];
  for(const p of L||BIG.pairs||[]){const s=p.s,i=p.i,C=s.cols,X=C.x[i],Y=C.y[i],die=dieOf(X,Y,s.product),r=p.r,g=s.cg||{},cs=r&&r.hit&&r.crop,fc=r&&r.c?cgFault(r.c):null;
    buf.push([p.k+1,csvQ(ST5[p.st]),csvQ(s.lotName),csvQ(s.lotPath),csvQ(s.slotName||''),s.idByOrder?i:C.id[i],C.rid[i],csvQ(clsFirst(s,i)),csvQ(clsName(s,i)),fv(C.c[i]),fv(C.area[i]*um2(s)),C.area[i],fv(C.w[i]),fv(C.l[i]),f2(C.bw[i]),f2(C.bh[i]),f2(X),f2(Y),die?die.col:'',die?die.row:'',...(m=>m&&m.x!=null?[m.x,m.y]:['',''])(mapDie(X,Y,s)),
      csvQ(p.c?p.c.file:''),csvQ(p.c?full(p.c.path):''),csvQ(p.c?p.c.how:''),fc?f2(fc[0]):'',fc?f2(fc[1]):'',
      csvQ(p.g?p.g.file:''),csvQ(p.g?full(p.g.path):''),p.g?f1(p.g.px):'',p.g?f1(p.g.py):'',p.g?p.g.n:'',p.g?(p.g.from==='record'?'장비 기록':'Defect 좌표'):'',g.plan?csvQ(CG.MODES[g.plan.mode]):'',cs?cs.cw:'',cs?cs.ch:'',csvQ(g.path?full(g.path):''),csvQ(g.src&&g.src.frames||''),csvQ(g.src&&g.src.tf||''),csvQ([p.cerr,p.gerr].filter(Boolean).join(' / ')),...rv5Cells(s,i).map(csvQ),p.g&&p.g.W?`${p.g.W}x${p.g.H}`:''].join(','));
    if(buf.length>=20000){parts.push(buf.join('\r\n')+'\r\n');buf=[]}}
  if(buf.length)parts.push(buf.join('\r\n')+'\r\n');return parts}
const B5={items:[],q:[]};
/** v14.1.8: 5-2 · 5-3 줄의 검색 글(한 번 만들어 둠). */
const b5Text=p=>{if(!p.qt){const s=p.s,C=s.cols,i=p.i,o=S.o||{},u=sizePix(s).pix,act=o.coord==='actual',X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product);
    p.qt=lower([p.k+1,ST5[p.st],s.lotName,s.slotName,s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),fv(C.c[i]),fv(C.area[i]*u*u),fv(C.area[i]),fv(C.w[i]),fv(C.w[i]*u),fv(C.l[i]),`${f1(C.bw[i])}×${f1(C.bh[i])}`,f1(X),f1(Y),die?`${die.col}, ${die.row}`:'',dieTxt(mapDie(X,Y,s)),
      p.c&&p.c.file,p.c&&p.c.how,p.c&&pcPath(p.c.path),p.g&&`${p.g.file} (${f1(p.g.px)}, ${f1(p.g.py)})`,p.g&&pcPath(p.g.path),p.cerr,p.gerr].filter(x=>x!=null&&x!=='').join(' '))}
  return p.glv!=null?p.qt+' '+f1(p.glv):p.qt};
/** 5-3 으로 가는 줄 = 5-2 에서 보이는(보기 · 검색) ☑ 줄, 확인 안 함은 빼고. */
const c5Pool=()=>BIG.pairs?B5.items.filter(p=>p.on2&&p.st!=='skip'):[];
const VB=makeVT($('#b5list'),[['☑',46,'pk',null],['5-1 #',64,'num',null],['상태',150,'s',null],['Lot',140,'',null],['Slot',110,'',null],['ID',62,'num',null],['장비 스캔 분류',140,'',null],['리뷰 결과',140,'',null],['Recipe',120,'',null],['Contrast(실제)',112,'num',null],['Color 이미지',230,'',null],['Gray 프레임 (픽셀)',280,'',null],['Color 연결',150,'',null],['이유',360,'',null],['Color 전체 경로',520,'',null],['Gray 전체 경로',520,'',null]],{
  row:k=>{const p=B5.items[k],s=p.s,C=s.cols,i=p.i;return [p.on2?'☑':'☐',p.k+1,ST5[p.st],s.lotName,s.slotName||'',s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),fv(C.c[i]),p.c?p.c.file:'-',p.g?`${p.g.file} (${f1(p.g.px)}, ${f1(p.g.py)})${p.g.from==='defect'?' · Defect 좌표':''}`:'-',p.c?p.c.how:'-',[p.cerr,p.gerr].filter(Boolean).join(' / '),
    p.c?pcPath(p.c.path):'-',p.g?pcPath(p.g.path):'-']},
  cls:k=>'st-'+B5.items[k].st+(B5.items[k].on2?'':' off'),onSel:()=>photoWinFollow(VB),onEnter:()=>photoWin(VB,B5.items),onSpace:k=>b5Pick(k)});
function b5Pick(k){const p=B5.items[k];if(!p)return;p.on2=!p.on2;vtPaint(VB);b5PickInfo()}
function b5PickAll(v){B5.items.forEach(p=>p.on2=v);vtPaint(VB);b5PickInfo()}
function b5PickInfo(){const n=B5.items.reduce((a,p)=>a+(p.on2?1:0),0),f=c5Pool().length;LSB.set(n,B5.items.length);
  $('#b5csv').disabled=!n;$('#b5csv').textContent=n?`CSV 저장 (☑ ${n.toLocaleString()}개 · 위치 고르기)`:'CSV 저장 (위치 고르기)';
  $('#toB3').disabled=!f;$('#toB3').textContent=f?`다음: ☑ ${f.toLocaleString()}개 사진 정밀 조사 →`:'다음: 사진 정밀 조사 →';b5tabs()}
const LSB=lsBind('b5Ls',{onQ:T=>{B5.q=T;b5Refresh()},onAll:b5PickAll});
$('#b5list').addEventListener('click',e=>{const c=e.target.closest('.br>span.pk');if(c)b5Pick(+c.parentNode.dataset.k)});
function b5Refresh(){const P=BIG.pairs||[],f=$('#b5show').value,T=B5.q,R=bigRankOf(),rk=p=>{const a=R&&R.get(p.s);return R?a?a[p.i]:-1:p.k};
  const F=[];for(const p of P){const r=rk(p);if(r>=0)F.push([r,p])}F.sort((a,b)=>a[0]-b[0]);   // 필터(5-1 과 같은 값) → 5-1 정렬 순서
  const nt=$('#bigFltNote');nt.hidden=BIG.stage===1||!P.length;nt.textContent=`5-1 에서 넘어온 Defect ${P.length.toLocaleString()}개 중 필터에 맞는 것 ${F.length.toLocaleString()}개 · 범위를 넓혀 더하려면 5-1 에서 [다음]을 다시 누르십시오`;
  B5.items=F.map(x=>x[1]).filter(p=>(!f||p.st===f)&&(!T.length||qAll(T,b5Text(p))));vtSet(VB,B5.items.length);pixLineSet($('#b5Pix'),B5.items.map(p=>p.s));
  const c={ok:0,color:0,gray:0,none:0,skip:0};for(const p of P)c[p.st]++;
  $('#b5sum').innerHTML=P.length?[['ok','Color·Gray 매칭 완료','keep'],['color','Color 만','new'],['gray','Gray 만','new'],['none','둘 다 없음','gone']].concat(c.skip?[['skip','확인 안 함','']]:[])
    .map(([k,t,cl])=>`<div class="kpi ${cl}"><span class="muted">${t}</span><b>${c[k].toLocaleString()}</b></div>`).join(''):'';
  $('#b5win').disabled=!B5.items.length;b5PickInfo();
  if(PW.V===VB){PW.items=B5.items;photoWinFollow(VB)}}

// ── rev5: 사진 새 창(큰 화면 · 사진만) ─────────────────────────────────────
//   소유자: "결과물은 html 에서 목록으로 쭉 보면 되고 새 창에서 큰 화면으로 사진들만". 창 하나(이름 cw_photo)를 다시 쓰고, 목록(5-2 · 5-3)에서 고른 줄을 따라간다.
//   위 = Color 원본 | Gray Crop(Color 시야 — 프로그램과 같은 Crop), 아래 = Gray 프레임 전체(Defect 박스, 노란 상자 = Crop 범위).
//   새 창에서 ↑↓ ←→ · PageUp/PageDown · Home/End = 목록 이동(목록도 같이 움직임).
//   확대(Para #67 소유자 "확대가 1번밖에 안 돼"): 사진 누르기 = 누른 곳을 2배씩(창 맞춤 → … 원래 픽셀의 16배까지, 끝에서 누르면 창 맞춤),
//   Shift + 누르기 · 오른쪽 누르기 = 2배씩 작게, 마우스 휠 = 조금씩, 끌기 = 옮기기, Esc · 0 = 모든 사진 창 맞춤. 사진을 바꾸면 창 맞춤으로 돌아간다.
const PW={w:null,V:null,items:[],tok:0,src:null,ring:null};
const PZ_MAX=16;   // 사진 확대 끝 = 원래 픽셀의 16배
/** 새 창 사진 확대(pwZoom): el = canvas(.im 안). 배율 z = 창 맞춤 크기의 몇 배(1 = 창 맞춤). 누른 점(ax, ay 화면 좌표)이 확대 뒤에도 같은 자리에 오게 스크롤한다. */
function pwFit(el){const im=el.parentNode;return Math.min(1,im.clientWidth/el.width||1,im.clientHeight/el.height||1)}
function pwSet(el,z,ax,ay){const im=el.parentNode,doc=el.ownerDocument,fit=pwFit(el),zmax=Math.max(1,PZ_MAX/fit);z=Math.max(1,Math.min(zmax,z));
  const r0=el.getBoundingClientRect();if(ax==null){ax=r0.left+r0.width/2;ay=r0.top+r0.height/2}
  const fxp=r0.width?(ax-r0.left)/r0.width:.5,fyp=r0.height?(ay-r0.top)/r0.height:.5;el._z=z;
  if(z<=1.0001){el._z=1;im.classList.remove('full');el.style.width=el.style.height=''}
  else{im.classList.add('full');el.style.width=Math.round(el.width*fit*z)+'px';el.style.height=Math.round(el.height*fit*z)+'px';
    const r1=el.getBoundingClientRect();im.scrollLeft+=r1.left+fxp*r1.width-ax;im.scrollTop+=r1.top+fyp*r1.height-ay}
  const f=im.parentNode,zb=f&&f.querySelector('.zb');if(zb){const pct=Math.round(fit*el._z*100);zb.textContent=el._z>1?`확대 ×${el._z>=10?Math.round(el._z):+el._z.toFixed(1)} · 원래 크기의 ${pct}%`:'';zb.hidden=el._z<=1}
  return el._z}
/** 확대 · 위치 고정(소유자 "가운데만 크롭해서 볼 수 있게 — 확대 배율과 위치를 고정해 놓고 보면 될 것 같다, 고정 체크박스").
 *  켜면 칸마다(fc Color · fx Gray Crop · ff Gray 프레임) 배율 z 와 보는 곳(칸 가운데가 사진의 어디인지, 사진 비율 0 ~ 1)을 기억하고 다음 Defect 에 그대로 쓴다.
 *  보는 곳은 기준점(el._anchor)에서 떨어진 만큼 — Color · Crop 은 기준점 (0, 0) = 사진의 같은 자리, 프레임은 기준점 = Defect 자리(Defect 마다 프레임 안 위치가 달라서 Defect 를 따라감).
 *  기억은 사람이 확대 · 축소 · 끌기 · Esc 할 때만 고친다(사진을 바꿀 때 생기는 스크롤로는 안 고침). 이 PC 에 기억(localStorage cw.pwLock · cw.pwLockV). */
const PWL={on:false,v:{}};try{PWL.on=localStorage.getItem('cw.pwLock')==='1';PWL.v=JSON.parse(localStorage.getItem('cw.pwLockV')||'{}')||{}}catch(e){}
/** Para v14.1.5 새 창 [Defect 박스](v14.4.1 이름 — 종전 '빨간 네모')(소유자 "흑백 이미지의 빨간 네모 Defect 표시 on, off — 새 창으로 크게 보기에서"): Gray Crop · Gray 프레임의 Defect 박스만(노란 Crop 상자 · 측정 원은 그대로).
 *  끄고 켜면 지금 사진을 그 자리에서 다시 그린다(확대 · 보는 곳 그대로). 5-3 칸 · 격자 · 엑셀 사진은 늘 Defect 박스를 그린다. 이 PC 에 기억(cw.pwBox). */
const PWB={on:true};try{PWB.on=localStorage.getItem('cw.pwBox')!=='0'}catch(e){}
const pwLegend=ring=>`${PWB.on?'Defect 박스 = 장비가 잡은 Defect 범위(Box W×H)':'Defect 박스 끔'} · 노란 상자 = Crop 범위${(ring===undefined?(PW.ring?PW.ring():GLC.show):ring)?' · 하늘색 점선 = 측정 원':''}`;
/** 새 창 사진을 그 자리에서 다시 그림(Defect 박스 · 측정 원을 바꿨을 때) — 캔버스는 그대로라 확대 · 스크롤이 유지된다. */
function pwRedraw(){const w=PW.w,doc=w&&!w.closed?pwDoc(w):null;if(!doc)return;
  doc.querySelectorAll('.im>canvas').forEach(c=>{try{c._redraw&&c._redraw()}catch(e){}});
  const lg=doc.querySelector('#ff .lg');if(lg)lg.textContent='· '+pwLegend();const b=doc.getElementById('pwBox');if(b){b.checked=PWB.on;b.parentNode.classList.toggle('on',PWB.on)}}
function pwBoxSet(on){PWB.on=!!on;try{localStorage.setItem('cw.pwBox',PWB.on?'1':'0')}catch(e){}pwRedraw()}
function pwLockSave(){try{localStorage.setItem('cw.pwLock',PWL.on?'1':'0');localStorage.setItem('cw.pwLockV',JSON.stringify(PWL.v))}catch(e){}}
/** 칸 가운데가 사진의 어디인지(사진 비율). */
function pwCenter(el){const im=el.parentNode,r=el.getBoundingClientRect(),b=im.getBoundingClientRect();return [r.width?(b.left+b.width/2-r.left)/r.width:.5,r.height?(b.top+b.height/2-r.top)/r.height:.5]}
function pwRemember(el){if(!PWL.on||!el._pid||!el.isConnected)return;const a=el._anchor||[0,0],[cx,cy]=pwCenter(el);
  PWL.v[el._pid]={z:el._z||1,dx:cx-a[0],dy:cy-a[1]};pwLockSave();pwBadge(el)}
/** 고정이 켜져 있으면 기억한 배율 · 보는 곳을 새 사진에 적용(칸에 붙인 뒤 부름). */
function pwApply(el){const v=PWL.on&&PWL.v[el._pid];if(!v)return pwBadge(el);pwSet(el,v.z);
  if(el._z>1){const a=el._anchor||[0,0],im=el.parentNode,r=el.getBoundingClientRect(),b=im.getBoundingClientRect(),fx=Math.max(0,Math.min(1,a[0]+v.dx)),fy=Math.max(0,Math.min(1,a[1]+v.dy));
    im.scrollLeft+=r.left+fx*r.width-(b.left+b.width/2);im.scrollTop+=r.top+fy*r.height-(b.top+b.height/2)}
  pwBadge(el)}
function pwBadge(el){const f=el.parentNode&&el.parentNode.parentNode,zb=f&&f.querySelector('.zb');if(!zb)return;
  if(PWL.on&&!/고정/.test(zb.textContent)){zb.textContent=(el._z>1?zb.textContent+' · ':'')+'🔒 고정';zb.hidden=false}}
function pwZoom(el){el._z=1;let dn=null,moved=false;   // 끌기 = 포인터 잡기(setPointerCapture) — 창 문서에 이벤트를 쌓지 않는다
  el.addEventListener('pointerdown',e=>{if(e.button!==0)return;dn={x:e.clientX,y:e.clientY,sl:el.parentNode.scrollLeft,st:el.parentNode.scrollTop};moved=false;try{el.setPointerCapture(e.pointerId)}catch(x){}e.preventDefault()});
  el.addEventListener('pointermove',e=>{if(!dn)return;const dx=e.clientX-dn.x,dy=e.clientY-dn.y;if(Math.abs(dx)+Math.abs(dy)>4)moved=true;
    if(moved&&el._z>1){el.parentNode.scrollLeft=dn.sl-dx;el.parentNode.scrollTop=dn.st-dy;el.parentNode.classList.add('drag')}});
  const up=()=>{if(dn){el.parentNode&&el.parentNode.classList.remove('drag');if(moved)pwRemember(el)}dn=null};el.addEventListener('pointerup',up);el.addEventListener('pointercancel',up);
  el.addEventListener('click',e=>{if(moved){moved=false;return}const zmax=Math.max(1,PZ_MAX/pwFit(el));
    if(e.shiftKey)pwSet(el,el._z/2,e.clientX,e.clientY);else pwSet(el,el._z>=zmax-1e-6?1:el._z*2,e.clientX,e.clientY);pwRemember(el)});
  el.addEventListener('contextmenu',e=>{e.preventDefault();pwSet(el,el._z/2,e.clientX,e.clientY);pwRemember(el)});
  el.addEventListener('wheel',e=>{e.preventDefault();pwSet(el,el._z*(e.deltaY<0?1.25:0.8),e.clientX,e.clientY);pwRemember(el)},{passive:false});
  return el}
const cgBmpCache=new LRU(24,p=>p.then(b=>b&&b.close&&b.close()).catch(()=>{}));
/** 매칭 폴더의 사진 하나 → ImageBitmap(최근 24장 기억). 못 읽으면 null 이고 기억하지 않는다(다시 누르면 다시 읽음). */
function cgBitmap(s,file){const g=s.cg,b=cleanName(file||'');if(!g||!g.dir||!b)return Promise.resolve(null);const k=s.id+'|'+lower(b);let p=cgBmpCache.get(k);
  if(!p){p=(async()=>{const nm=await g.dir.names(),e=nm&&!nm.err?nm.get(lower(b)):await g.dir.get(b);return e?createImageBitmap(await e.file()):null})().catch(()=>null);
    cgBmpCache.set(k,p);p.then(x=>{if(!x&&cgBmpCache.m.get(k)===p)cgBmpCache.m.delete(k)})}
  return p}
/** Defect 박스(v14.4.1 이름 — 종전 '빨간 네모', Para #67 소유자 "빨간색 네모박스 · 디펙을 가리면 안 돼"): Defect 상자(BoxWidth × BoxHeight, Gray 픽셀) 바깥에 틈을 두고 선을 긋는다.
 *  c = 그릴 2d 문맥, (x, y) = Defect 가운데(그릴 좌표), (hw, hh) = Defect 상자 반폭 · 반높이(그릴 좌표), size = 그림 긴 변(선 굵기 · 최소 크기 기준).
 *  선 안쪽 가장자리 = 상자 + 틈 → 선이 Defect 위에 오지 않는다. 그린 네모 [왼, 위, 오른, 아래](선 바깥 가장자리)를 돌려준다. */
function cgDefBox(c,x,y,hw,hh,size){const lw=Math.max(2,Math.round(size/300)),gap=Math.max(4,lw*2),mn=Math.max(8,size/60);
  const ax=Math.max(hw+gap,mn),ay=Math.max(hh+gap,mn);c.save();c.filter='none';c.strokeStyle='#ff2d2d';c.lineWidth=lw;c.strokeRect(x-ax-lw/2,y-ay-lw/2,2*ax+lw,2*ay+lw);c.restore();
  return [x-ax-lw,y-ay-lw,x+ax+lw,y+ay+lw]}
/** Defect 상자 반폭 · 반높이(Gray 사진 픽셀). BoxWidth/BoxHeight 는 Slot 기준 픽셀(v14.4.1 — 찍은 레시피 픽셀과 다를 수 있어 boxK 로 바꾼다), 값이 없으면 4. */
/** 그 Defect 의 프레임 크기(geoChoose · geoRecHit 의 W, H — v14.4.1 #89: 레시피마다 다름). 없으면 종전 3168×1024. */
const hitW=h=>h&&h.W>0?h.W:CG.GW,hitH=h=>h&&h.H>0?h.H:CG.GH;
function cgDefHalf(gray,d,hit){const sx=gray.width/hitW(hit),sy=gray.height/hitH(hit),k=boxK(d);return [Math.max(1,((d&&d.BoxWidth)||4)*k*sx)/2,Math.max(1,((d&&d.BoxHeight)||4)*k*sy)/2]}
/** Para ColorGray.tsx crop(): Fault 가운데 Color 시야(cs.cw × cs.ch Gray 픽셀)만큼 잘라(밖 = 검정) Color 크기(cs.ow × cs.oh)로 늘림 · 흑백. doc = 그릴 문서.
 *  d(Defect)를 주면 흑백 그림 위에 Defect 박스(cgDefBox, Defect 를 가리지 않음)와 측정 원을 그린다 — GL 측정용 raw 에는 그리지 않는다.
 *  opt = {box: Defect 박스(기본 그림 — 새 창 [Defect 박스] 가 끔), ring: 측정 원(기본 = 5-3 [측정 원 보기])} — Para v14.1.5. */
function cgCropCanvas(gray,hit,cs,doc,d,opt){doc=doc||document;opt=Object.assign({box:true,ring:GLC.show},opt);
  const x=hit.px*gray.width/hitW(hit),y=hit.py*gray.height/hitH(hit),left=Math.round(x-cs.cw/2),top=Math.round(y-cs.ch/2);
  const raw=document.createElement('canvas');raw.width=cs.cw;raw.height=cs.ch;const g=raw.getContext('2d',{willReadFrequently:true});g.fillStyle='#000';g.fillRect(0,0,cs.cw,cs.ch);
  const sl=Math.max(0,left),st=Math.max(0,top),sr=Math.min(gray.width,left+cs.cw),sb=Math.min(gray.height,top+cs.ch);
  if(sr>sl&&sb>st)g.drawImage(gray,sl,st,sr-sl,sb-st,sl-left,st-top,sr-sl,sb-st);
  const out=doc.createElement('canvas');out.width=cs.ow;out.height=cs.oh;const o2=out.getContext('2d');o2.imageSmoothingQuality='high';o2.filter='grayscale(1)';o2.drawImage(raw,0,0,cs.ow,cs.oh);o2.filter='none';
  let mark=null;if(d){const fx=cs.ow/cs.cw,fy=cs.oh/cs.ch,[hw,hh]=cgDefHalf(gray,d,hit),M=Math.max(cs.ow,cs.oh);if(opt.box)mark=cgDefBox(o2,(x-left)*fx,(y-top)*fy,hw*fx,hh*fy,M);if(opt.ring)glRing(o2,(x-left)*fx,(y-top)*fy,GLC.r*fx,GLC.r*fy,M)}
  return {canvas:out,raw,box:[left,top,left+cs.cw,top+cs.ch],cx:x-left,cy:y-top,mark,hit}}
/** Gray 프레임 전체 + Defect 박스(Defect — 가리지 않게 바깥에, Para #67. 종전 빨간 + 는 Defect 위를 지나가 없앰) + 노란 상자(Crop 범위). */
function cgFrameCanvas(gray,hit,cs,doc,d,o){doc=doc||document;o=Object.assign({box:true,ring:GLC.show},o);const cv=doc.createElement('canvas');cv.width=gray.width;cv.height=gray.height;const c=cv.getContext('2d');c.drawImage(gray,0,0);
  const sx=gray.width/hitW(hit),sy=gray.height/hitH(hit),x=hit.px*sx,y=hit.py*sy,lw=Math.max(2,gray.width/700);
  if(cs){c.strokeStyle='#ffd23f';c.lineWidth=lw;c.strokeRect(x-cs.cw/2,y-cs.ch/2,cs.cw,cs.ch)}
  const [hw,hh]=cgDefHalf(gray,d,hit);if(o.box)cgDefBox(c,x,y,hw,hh,Math.max(gray.width,gray.height));if(d&&o.ring)glRing(c,x,y,GLC.r,GLC.r,Math.max(gray.width,gray.height));return cv}
/** GL(Local 추정): Crop 원본(Gray 해상도)에서 Fault 가운데 Box W×H · Ring 폭. */
function cgGL(k,gray,d){const sx=gray.width/hitW(k.hit),sy=gray.height/hitH(k.hit),bk=boxK(d),bw=Math.max(1,(d.BoxWidth||4)*bk*sx),bh=Math.max(1,(d.BoxHeight||4)*bk*sy);
  return measureGL(k.raw.getContext('2d',{willReadFrequently:true}).getImageData(0,0,k.raw.width,k.raw.height),k.cx,k.cy,bw,bh,S.o.ring)}
/** v14.4.1(#89, 소유자 "기본 모드에서 새창으로 이미지 볼 때 대규모 모드에서 보는 것처럼 동일하게 — 화면 잠금 · 빨간 박스 해제 등, GL 원은 ㄴㄴ"): 새 창은 두 모드가 같은 창 · 같은 코드.
 *  자료원 src = {n(), sel(), go(k), step(dir)?, pick(k)?, v(k) → 칸 자료, key?}, 칸 자료 = {hd(머리 글 HTML), space(Space 안내), d(Defect — 크기 측정), c:{name, path, bmp(), px(Color 픽셀 µm), ow(Color 원래 폭)}|null, cwhy, g:{hit, name, path, bmp(), crop, d}|null, gwhy, ring, rel, pre()}.
 *  대규모 = 5-2 · 5-3 목록(bigSrc), 기본 = Step 3 · 4 리뷰 목록(baseSrc) · Step 2 쌍별 상세 표 · 지도의 목록 밖 점(listSrc). */
function photoWinOpen(src){if(!src||!src.n())return;let w=PW.w;
  if(!w||w.closed){w=winOpen('cw_photo','width=1600,height=1000');PW.w=w;photoWinInit(w)}
  PW.src=src;PW.V=src.V||null;if(src.V)PW.items=src.items;try{w.focus();w.document.body.focus()}catch(e){}photoWinShow()}
function photoWin(V,items){if(!V||!items||!items.length)return;photoWinOpen(bigSrc(V,items))}
/** 대규모 자료원: 목록 V(가상 표) + 줄(PW.items — 5-2 를 다시 고르면 바뀐다). Space = 최종 목록 ☑/☐. */
function bigSrc(V,items){return {V,items,n:()=>V.n,sel:()=>V.sel,go:k=>vtGo(V,k),pick:k=>pickToggle(PW.items[k]),v:k=>bigView(PW.items[k],k,V.n),
  pre:k=>{for(let j=k+1;j<=k+2&&j<PW.items.length;j++){const q=PW.items[j],rq=q.r||cgOf(q.s,q.i);if(rq.c)cgBitmap(q.s,rq.c.file);if(rq.hit)cgBitmap(q.s,rq.hit.frame.file)}}}}
function bigView(p,k,n){if(!p)return null;const s=p.s,C=s.cols,i=p.i,r=p.r||cgOf(s,i),dir=s.cg&&s.cg.path?s.cg.path+'/':'',cn=r.c?cleanName(r.c.file):'',gn=r.hit?cleanName(r.hit.frame.file):'';
  return {hd:`${k+1} / ${n} · ${esc(s.lotName||'')} · ${esc(s.slotName||'')} · ID ${s.idByOrder?i:C.id[i]} · <b>${esc(clsText(s,i))}</b> · Recipe <b>${esc(rcp5(s,i))}</b> · Zone ${esc(rvInfo(bigDef(s,i)).zone)} · Region ${C.rg[i]} · Contrast ${fv(C.c[i])}${p.glv!=null?` · <b>GL ${f1(p.glv)}</b>`:''} ${pickBadge(p)}`,
    space:'Space = 최종 목록 ☑/☐',rel:!pcBaseSet(),ring:null,d:bigDef(s,i),
    c:r.c?{name:cn,path:cn?pcPath(p.c?p.c.path:dir+cn):'',bmp:()=>cgBitmap(s,r.c.file),px:pyFloat(cgGet(r.c,'PixelSizeX')),ow:pyFloat(cgGet(r.c,'ImageSizeX'))}:null,cwhy:p.cerr||r.why||'Color 항목 없음',
    g:r.hit?{hit:r.hit,name:gn,path:gn?pcPath(p.g?p.g.path:dir+gn):'',bmp:()=>cgBitmap(s,r.hit.frame.file),crop:r.crop||cgCropSize({}),d:bigDef(s,i)}:null,gwhy:p.gerr||`Gray: ${r.why||'위치 없음'}`}}
/** 기본 자료원: 리뷰 패널 P(Step 3 · 4) — ↑↓ = ☑ 줄만(목록과 같은 규칙), Space = ☑/☐, 목록 · 지도에서 고르면 새 창도 따라감(showPanel). */
function baseSrc(P){return {key:P,n:()=>P.items.length,sel:()=>P.sel,go:k=>{P.sel=k;showPanel(P)},step:dir=>panelStep(P,dir),pick:k=>{panelTog(P,k);photoWinShow()},
  v:k=>baseView(P.items[k],k,P.items.length,pOn(P,P.items[k])),pre:k=>basePre(P.items,k)}}
/** 기본 자료원: 줄 목록 L 의 k 번째(쌍별 상세 표 · 목록 밖 점). pick = ☑/☐ 바꾸기(없으면 Space 없음). */
function listSrc(L,k,pick,on){let i=k;return {key:L,n:()=>L.length,sel:()=>i,go:j=>{i=j;photoWinShow()},pick:pick?j=>{pick(L[j]);photoWinShow()}:null,
  v:j=>baseView(L[j],j,L.length,on?on(L[j]):null),pre:j=>basePre(L,j)}}
const basePre=(L,k)=>{for(let j=k+1;j<=k+2&&j<L.length;j++){const d=L[j]&&L[j].d;if(!d)continue;const c=linkColor(d,d.scan,S.o.ctol),g=grayOf(d);if(c)grayBmp(d.scan,{file:c.c.file});if(g.frame)grayBmp(d.scan,g.frame)}};
/** 기본 모드 줄 하나 → 칸 자료(대규모 bigView 와 같은 모양). Color = linkColor, Gray = grayOf(geoHit — 대규모와 같은 계산), Crop = Color 시야(대규모와 같음 · cgCropSize). */
function baseView(q,k,n,on){if(!q||!q.d)return null;const d=q.d,s=d.scan,x=info(q),c=linkColor(d,s,S.o.ctol),g=grayOf(d),G=s.geo;
  const cn=c?cleanName(c.c.file):'',gn=g.frame?cleanName(g.frame.file):'',pth=nm=>nm?`${s.name}/${nm}`:'';
  const raw=c?Object.fromEntries([['ImageSizeX',c.c.w],['ImageSizeY',c.c.h],['PixelSizeX',c.c.psx],['PixelSizeY',c.c.psy]].filter(e=>e[1]!=null)):{},cs=cgCropSize(raw,geoPix(G,d.recipe),G&&G.rcpix&&G.rcpix.get(d.recipe))||cgCropSize({});
  return {hd:`${k+1} / ${n} · [${esc(x.st)}] ${esc(x.step)} · Slot ${esc(x.slot||'-')} · 호기 ${esc(x.tool||'-')} · ID ${esc(x.id)} · Recipe <b>${esc(rcpName(d))}</b> · Zone ${esc(zoneLbl(d.zone,s))} · Wafer ${f1(x.X)}, ${f1(x.Y)} µm · Die ${esc(x.die)} · Contrast ${fv(x.contrast)}`
      +(on==null?'':` <b class="pk ${on?'on':'off'}" id="pk">${on?'☑':'☐'}</b>`),space:on==null?'':'Space = ☑/☐',rel:true,ring:false,d,
    c:c?{name:cn,path:pth(cn),bmp:()=>grayBmp(s,{file:c.c.file}),px:c.c.psx,ow:c.c.w}:null,cwhy:colorWhy(d,s,S.o.ctol),
    g:g.frame?{hit:g,name:gn,path:pth(gn),bmp:()=>grayBmp(s,g.frame),crop:cs,d}:null,gwhy:`Gray: ${g.reason||'위치 없음'}`}}
/** 새 창 화면 · 키(소유자 "큰 화면으로 볼 때 방향키로 다음 목록" — ↑↓ ←→ · PageUp/PageDown · Home/End · J/K, 꾹 누르면 계속 넘어감). 사진을 눌러 원래 크기로 봐도 키는 그대로. */
function photoWinInit(w){const doc=w.document;doc.title='사진 · Color / Gray';MZ.on=false;   // 새 창은 늘 사진 3칸으로 시작
  doc.head.insertAdjacentHTML('beforeend',`<meta charset="utf-8"><style>html,body{height:100%;margin:0}body{background:#0b0b0b;color:#ccc;font:12px "Malgun Gothic","Segoe UI",sans-serif;display:flex;flex-direction:column}
    .hd{flex:none;padding:3px 10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hd i{color:#888;font-style:normal}
    .pv{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:minmax(0,2.2fr) minmax(0,1fr);gap:6px;padding:0 6px 6px}
    figure{margin:0;min-width:0;min-height:0;background:#000;border-radius:6px;display:flex;flex-direction:column;overflow:hidden}
    figure.wide{grid-column:1 / span 2}
    figcaption{flex:none;background:#161a22;color:#eee;padding:3px 8px;font-size:13px;overflow-wrap:anywhere;user-select:text;border-bottom:1px solid #2a2f3a}
    figcaption b{color:#fff;font-weight:700}figcaption i{color:#aaa;font-style:normal}
    figcaption .pp{display:block;font:12px Consolas,"Malgun Gothic",monospace;color:#b9c6d8;user-select:all}figcaption .pp.rel{color:#e0b060}
    .im{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden}
    .im>canvas{max-width:100%;max-height:100%;cursor:zoom-in}.im.full{overflow:auto;align-items:flex-start;justify-content:flex-start}.im.full>canvas{max-width:none;max-height:none;margin:auto;flex:none}
    .im.drag,.im.drag>canvas{cursor:grabbing}figure{position:relative}.zb{position:absolute;right:8px;bottom:8px;background:rgba(22,26,34,.85);color:#ffe08a;font-size:12px;padding:2px 8px;border-radius:4px;pointer-events:none}
    .ms{color:#ff9a92;padding:10px}
    .pv.conly{grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr)}.pv.conly #fx,.pv.conly #ff{display:none}.hd .ng{color:#ffb37a;font-weight:600}
    .tb{flex:none;display:flex;align-items:center;gap:8px;padding:3px 10px 0}.tb .hd{flex:1;min-width:0;padding:0}
    .lk{flex:none;display:inline-flex;align-items:center;gap:4px;padding:1px 8px;border-radius:4px;background:#222a36;color:#eee;font-weight:700;cursor:pointer;white-space:nowrap}.lk.on{background:#10b981;color:#04231a}.lk input{margin:0}
    .hd .pk{padding:0 6px;border-radius:4px;font-weight:700}.hd .pk.on{background:#10b981;color:#04231a}.hd .pk.off{background:#333;color:#bbb}${MZ_CSS}</style>`);
  doc.body.tabIndex=-1;
  // 칸 = 제목(사진 파일명 + 전체 경로, 사진을 가리지 않게 위에) + 사진
  doc.body.innerHTML=`<div class="tb"><label class="lk" id="lkL" title="켜면 지금 칸마다의 확대 배율과 보는 곳을 다음 Defect 에도 그대로 씁니다(Color · Gray Crop = 사진의 같은 자리, Gray 프레임 = Defect 를 따라감). 끄면 사진을 바꿀 때 창 맞춤."><input type="checkbox" id="pwLock"> 🔒 확대 · 위치 고정</label>`
    +`<label class="lk" id="bxL" title="흑백 사진(Gray Crop · Gray 프레임)의 Defect 박스(빨간 상자 = 장비가 잡은 Defect 범위)를 켜고 끕니다(B). 확대 · 보는 곳은 그대로."><input type="checkbox" id="pwBox"> Defect 박스</label><button class="lk mzb" id="pwMz" title="사진을 원래 픽셀로 크게 띄워 직선 · 원 · 사각형으로 길이와 넓이를 잽니다(M). 보기만 하고 저장하지 않습니다">크기 측정 (M)</button><div class="hd" id="hd"></div></div><div class="pv"><figure id="fc"><figcaption>Color</figcaption><div class="im"></div><div class="zb" hidden></div></figure><figure id="fx"><figcaption>Gray Crop (Color 시야)</figcaption><div class="im"></div><div class="zb" hidden></div></figure>`
    +`<figure id="ff" class="wide"><figcaption>Gray 프레임</figcaption><div class="im"></div><div class="zb" hidden></div></figure></div>`+MZ_HTML;
  doc.addEventListener('keydown',e=>{if(mzKey(doc,e))return;const src=PW.src,N=src?src.n():0;if(!N||e.ctrlKey||e.altKey||e.metaKey)return;const k=e.key.length===1?e.key.toLowerCase():e.key,
      mv={ArrowDown:1,ArrowRight:1,PageDown:1,j:1,ArrowUp:-1,ArrowLeft:-1,PageUp:-1,k:-1}[k];
    if(mv){src.go(src.step?src.step(mv):Math.max(0,Math.min(N-1,src.sel()+mv)));e.preventDefault()}else if(k==='Home'||k==='End'){src.go(k==='Home'?0:N-1);e.preventDefault()}
    else if(k===' '){if(src.pick)src.pick(src.sel());e.preventDefault()}
    else if(k==='Escape'||k==='0'){doc.querySelectorAll('.im>canvas').forEach(c=>{pwSet(c,1);pwRemember(c)});e.preventDefault()}
    else if(k==='f'||k==='l'){const b=doc.getElementById('pwLock');b.checked=!b.checked;b.dispatchEvent(new Event('change'));e.preventDefault()}
    else if(k==='b'){pwBoxSet(!PWB.on);e.preventDefault()}});
  {const b=doc.getElementById('pwBox');b.checked=PWB.on;b.parentNode.classList.toggle('on',PWB.on);b.addEventListener('change',()=>{pwBoxSet(b.checked);try{doc.body.focus()}catch(e){}})}
  {const b=doc.getElementById('pwLock'),L=doc.getElementById('lkL');b.checked=PWL.on;L.classList.toggle('on',PWL.on);
    // 켜는 순간 지금 보이는 배율 · 보는 곳을 기억, 끄면 기억을 지움(다음 사진부터 창 맞춤)
    b.addEventListener('change',()=>{PWL.on=b.checked;L.classList.toggle('on',PWL.on);PWL.v={};if(PWL.on)doc.querySelectorAll('.im>canvas').forEach(c=>pwRemember(c));pwLockSave();
      doc.querySelectorAll('.im>canvas').forEach(c=>{const zb=c.parentNode.parentNode.querySelector('.zb');if(zb&&!PWL.on){zb.textContent=zb.textContent.replace(/( · )?🔒 고정$/,'');zb.hidden=!(c._z>1)}else pwBadge(c)});try{doc.body.focus()}catch(e){}})}
  mzBind(doc);try{doc.body.focus()}catch(e){}}
// ── 새 창 사진 크기 측정(소유자 2026-11-23 "사진 새 창에서 따로 버튼 — 확대해서 정확하게, 직선 · 원 · 사각형, 넓이도") ──────────
//   사진 = 원본 픽셀 그대로(Gray 프레임 · Color 사진). µm = 사진 픽셀 × 그 사진의 픽셀 크기:
//   Gray = 찍은 레시피 픽셀(변환 파일 → s_FrameData → RecipesInfo.ini, geoPix), Color = ColorImageGrabingInfo.ini PixelSizeX(없으면 RecipesInfo.ini ColorPixelSize).
//   목록 · 정보의 장비 값(Width · Area)은 Slot 기준 픽셀(µm 환산 픽셀) 단위라 사진 픽셀과 다를 수 있다 — 측정은 늘 사진 픽셀로 한다.
const MZ={on:false,which:'g',tool:'line',sh:{c:[],g:[]},key:null,img:{},view:{},sc:{},px:{},v:null,drag:null,tk:0};
const MZ_T=[['line','직선','1'],['circle','원','2'],['rect','사각형','3'],['pan','옮기기','4']],MZ_NM={line:'직선',circle:'원',rect:'사각형'};
const MZ_N='①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';
const MZ_CSS=`.pv[hidden],.mz[hidden]{display:none}.mzon #lkL,.mzon #bxL{display:none}
  .mzb{border:0;font:inherit}.mzb.on{background:#10b981;color:#04231a}
  .mz{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:6px;padding:0 6px 6px}
  .mzl{min-width:0;min-height:0;display:flex;flex-direction:column;background:#000;border-radius:6px;overflow:hidden}
  .mzbar{flex:none;display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:5px 8px;background:#161a22;border-bottom:1px solid #2a2f3a}
  .mzbar button{font:12px "Malgun Gothic","Segoe UI",sans-serif;padding:3px 10px;border-radius:4px;border:1px solid #2f3746;background:#222a36;color:#eee;cursor:pointer}
  .mzbar button.on{background:#10b981;border-color:#10b981;color:#04231a;font-weight:700}.mzbar button:disabled{opacity:.4;cursor:default}
  .mzbar .sep{width:1px;height:18px;background:#2f3746}.mzbar .zl{margin-left:auto;color:#ffe08a}
  .mzcv{flex:1;min-height:0;position:relative}.mzcv canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair;touch-action:none}.mzcv.pan canvas{cursor:grab}
  .mzs{min-height:0;overflow:auto;background:#11151c;border-radius:6px;padding:8px 10px;color:#dde3ee}
  .mzs h4{margin:10px 0 4px;font-size:13px;color:#fff}.mzs h4:first-child{margin-top:0}
  .mzs .px{font:12px Consolas,"Malgun Gothic",monospace;line-height:1.7}.mzs .px b{color:#ffe08a}
  .mzs ol{margin:0;padding:0;list-style:none}.mzs li{display:grid;grid-template-columns:22px 1fr auto;gap:4px;align-items:start;padding:5px 0;border-bottom:1px solid #232a36}
  .mzs li .n{font-weight:700;color:#7ee2b8}.mzs li .v{font:12px Consolas,"Malgun Gothic",monospace;line-height:1.5}.mzs li .v b{color:#7ee2b8;font-weight:700}
  .mzs li button{background:none;border:0;color:#888;cursor:pointer;font-size:13px}.mzs .ref{margin-top:10px;color:#aab3c2;line-height:1.5}.mzs .hp{margin-top:10px;color:#8b95a7;line-height:1.6}`;
const MZ_HTML=`<div class="mz" id="mz" hidden><div class="mzl"><div class="mzbar" id="mzBar"></div><div class="mzcv" id="mzCv"><canvas aria-label="크기 측정 사진"></canvas></div></div><aside class="mzs" id="mzSide"></aside></div>`;
/** 사진마다 픽셀 크기(µm) · 출처. 측정 화면에서만 보인다(소유자 — 찍은 레시피 줄은 측정할 때만). */
function mzPix(v){const d=v&&v.d,s=d&&d.scan,G=s&&(s.geo||s.cg),r=d?d.recipe:null,nm=G&&G.rname&&G.rname.get(r);let g=null,c=null;
  if(v&&v.g){const t=G?tfPix(cgTfFor(G.tfs,r)):null,from=t>0.05&&t<20?'변환 파일':G&&G.fpix.get(r)?'s_FrameData':G&&G.rpix.get(r)?'RecipesInfo.ini':'기본값';
    g={pix:geoPix(G,r),lab:`Recipe ${r??'-'}${nm?' '+nm:''}`,from}}
  if(v&&v.c){const rp=G&&G.rcpix&&G.rcpix.get(r),p=v.c.px>0?v.c.px:rp;c={pix:p>0?p:0.4674,from:v.c.px>0?'ColorImageGrabingInfo.ini':rp>0?'RecipesInfo.ini':'기본값'}}
  return {g,c}}
function mzVal(sh,w){w=w||MZ.which;const p=MZ.px[w],sc=MZ.sc[w]||1,u=(p?p.pix:0)*sc,dx=sh.b[0]-sh.a[0],dy=sh.b[1]-sh.a[1],f=(v,n)=>v.toFixed(n);
  if(sh.t==='line'){const L=Math.hypot(dx,dy);return {px:`${f(L*sc,1)} px`,um:`${f(L*u,2)} µm`,lab:`${f(L*u,2)} µm`}}
  if(sh.t==='circle'){const r=Math.hypot(dx,dy),A=Math.PI*r*r*u*u;return {px:`지름 ${f(2*r*sc,1)} px`,um:`지름 ${f(2*r*u,2)} µm · 넓이 ${f(A,2)} µm²`,lab:`⌀ ${f(2*r*u,2)} µm · ${f(A,1)} µm²`}}
  const W=Math.abs(dx),H=Math.abs(dy);return {px:`${f(W*sc,1)} × ${f(H*sc,1)} px`,um:`${f(W*u,2)} × ${f(H*u,2)} µm · 넓이 ${f(W*H*u*u,2)} µm²`,lab:`${f(W*u,2)} × ${f(H*u,2)} µm · ${f(W*H*u*u,1)} µm²`}}
function mzToggle(doc,on){MZ.on=on==null?!MZ.on:!!on;doc.querySelector('.pv').hidden=MZ.on;doc.getElementById('mz').hidden=!MZ.on;doc.body.classList.toggle('mzon',MZ.on);
  const b=doc.getElementById('pwMz');b.classList.toggle('on',MZ.on);b.textContent=MZ.on?'측정 끝내기 (Esc)':'크기 측정 (M)';
  if(MZ.on){const src=PW.src;mzLoad(doc,src&&src.n()?src.v(src.sel()):null)}}
/** 지금 Defect 의 사진을 측정 화면에. Defect 가 바뀌면 측정을 비운다. */
async function mzLoad(doc,v){const src=PW.src,key=v?`${src?src.sel():''}|${v.g?v.g.name:''}|${v.c?v.c.name:''}`:'';
  if(MZ.key!==key){MZ.key=key;MZ.sh={c:[],g:[]};MZ.view={}}
  MZ.v=v;MZ.px=mzPix(v);const tk=++MZ.tk,[cb,gb]=await Promise.all([v&&v.c?v.c.bmp():null,v&&v.g?v.g.bmp():null]);if(tk!==MZ.tk||!MZ.on)return;
  MZ.img={c:cb,g:gb};MZ.sc={g:gb&&v.g?hitW(v.g.hit)/gb.width:1,c:cb&&v.c&&v.c.ow>0?v.c.ow/cb.width:1};
  if(!MZ.img[MZ.which])MZ.which=gb?'g':'c';if(!MZ.view[MZ.which])mzFit(doc,MZ.which);mzBar(doc);mzDraw(doc);mzSide(doc)}
/** Defect 크기(그 사진의 픽셀) = Box(Slot 기준 픽셀) × µm 환산 픽셀 ÷ 사진 픽셀. */
function mzDefPx(which){const d=MZ.v&&MZ.v.d,P=MZ.px[which];if(!d||!P||!d.scan)return 0;const u=sizePix(d.scan).pix;return Math.max(d.BoxWidth||0,d.BoxHeight||0)*u/P.pix/(MZ.sc[which]||1)}
/** 처음 화면 = Defect 자리를 가운데(Gray = 프레임의 Defect 위치, Color = 사진 가운데) · Defect 크기의 약 6배가 보이게. whole = 사진 전체(0 키). */
function mzFit(doc,which,whole){const im=MZ.img[which],box=doc.getElementById('mzCv');if(!im)return;const W=box.clientWidth||800,H=box.clientHeight||600,fit=Math.min(W/im.width,H/im.height);
  let s=fit,cx=im.width/2,cy=im.height/2;
  if(!whole){if(which==='g'&&MZ.v&&MZ.v.g){const h=MZ.v.g.hit;cx=h.px*im.width/hitW(h);cy=h.py*im.height/hitH(h)}const dp=mzDefPx(which);s=Math.max(fit,Math.min(64,Math.min(W,H)/Math.max(30,6*dp||140)))}
  MZ.view[which]={s,min:fit/2,ox:cx-W/2/s,oy:cy-H/2/s}}
function mzBar(doc){const b=doc.getElementById('mzBar'),has=k=>!!MZ.img[k],V=MZ.view[MZ.which];
  b.innerHTML=`<button data-mzw="g" class="${MZ.which==='g'?'on':''}" ${has('g')?'':'disabled'}>Gray 사진</button><button data-mzw="c" class="${MZ.which==='c'?'on':''}" ${has('c')?'':'disabled'}>Color 사진</button><span class="sep"></span>`
    +MZ_T.map(([t,n,k])=>`<button data-mzt="${t}" class="${MZ.tool===t?'on':''}" title="${k} 키">${n}</button>`).join('')
    +`<span class="sep"></span><button data-mzu title="Ctrl+Z">되돌리기</button><button data-mzc>모두 지우기</button><span class="zl" id="mzZ"></span>`;
  doc.getElementById('mzCv').classList.toggle('pan',MZ.tool==='pan');mzZoomTxt(doc)}
function mzZoomTxt(doc){const z=doc.getElementById('mzZ'),V=MZ.view[MZ.which];if(z)z.textContent=V?`확대 ×${V.s>=10?Math.round(V.s):V.s.toFixed(1)} (사진 1픽셀 = 화면 ${V.s>=10?Math.round(V.s):V.s.toFixed(1)}픽셀)`:''}
function mzDraw(doc){const box=doc.getElementById('mzCv'),cv=box.querySelector('canvas'),dpr=doc.defaultView.devicePixelRatio||1,W=box.clientWidth,H=box.clientHeight;
  if(cv.width!==Math.round(W*dpr)||cv.height!==Math.round(H*dpr)){cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr)}
  const c=cv.getContext('2d'),im=MZ.img[MZ.which],V=MZ.view[MZ.which];c.setTransform(1,0,0,1,0,0);c.fillStyle='#000';c.fillRect(0,0,cv.width,cv.height);
  if(!im||!V){c.fillStyle='#ff9a92';c.font=`${14*dpr}px "Malgun Gothic",sans-serif`;c.fillText('사진이 없습니다',20*dpr,30*dpr);return}
  const k=V.s*dpr;c.setTransform(k,0,0,k,-V.ox*k,-V.oy*k);c.imageSmoothingEnabled=V.s<3;c.drawImage(im,0,0);
  if(V.s>=12){const x0=Math.max(0,Math.floor(V.ox)),y0=Math.max(0,Math.floor(V.oy)),x1=Math.min(im.width,Math.ceil(V.ox+W/V.s)),y1=Math.min(im.height,Math.ceil(V.oy+H/V.s));   // 픽셀 격자
    c.strokeStyle='rgba(255,255,255,.16)';c.lineWidth=1/k;c.beginPath();for(let x=x0;x<=x1;x++){c.moveTo(x,y0);c.lineTo(x,y1)}for(let y=y0;y<=y1;y++){c.moveTo(x0,y);c.lineTo(x1,y)}c.stroke()}
  const L=MZ.sh[MZ.which],u=1/k;
  for(const sh of L){const col=MZ.drag&&MZ.drag.sh===sh?'#fde047':'#34d399',[ax,ay]=sh.a,[bx,by]=sh.b;c.strokeStyle=c.fillStyle=col;c.lineWidth=2*u;c.beginPath();
    if(sh.t==='line'){c.moveTo(ax,ay);c.lineTo(bx,by)}else if(sh.t==='circle')c.arc(ax,ay,Math.hypot(bx-ax,by-ay),0,Math.PI*2);else c.rect(Math.min(ax,bx),Math.min(ay,by),Math.abs(bx-ax),Math.abs(by-ay));c.stroke();
    if(sh.t==='circle'){c.setLineDash([4*u,3*u]);c.beginPath();c.moveTo(ax,ay);c.lineTo(bx,by);c.stroke();c.setLineDash([])}
    for(const [x,y] of [sh.a,sh.b])c.fillRect(x-3*u,y-3*u,6*u,6*u)}
  c.setTransform(1,0,0,1,0,0);c.font=`600 ${12*dpr}px "Malgun Gothic","Segoe UI",sans-serif`;c.textBaseline='middle';
  const put=[];   // 글 상자끼리 겹치면 아래로 비킨다
  L.forEach((sh,i)=>{const [ax,ay]=sh.a,[bx,by]=sh.b,r=Math.hypot(bx-ax,by-ay),[x,y]=sh.t==='line'?[Math.max(ax,bx),ax>bx?ay:by]:sh.t==='circle'?[ax+r*0.72,ay-r*0.72]:[Math.max(ax,bx),Math.min(ay,by)],
      t=`${MZ_N[i]||i+1} ${mzVal(sh).lab}`,tw=c.measureText(t).width,sx=(x-V.ox)*k+8*dpr;let sy=(y-V.oy)*k-10*dpr;
    for(let g=0;g<30&&put.some(q=>sx<q[0]+q[2]&&q[0]<sx+tw+8*dpr&&Math.abs(q[1]-sy)<22*dpr);g++)sy+=22*dpr;put.push([sx-4*dpr,sy,tw+8*dpr]);
    c.fillStyle='rgba(8,12,18,.82)';c.fillRect(sx-4*dpr,sy-10*dpr,tw+8*dpr,20*dpr);c.fillStyle='#e9fff5';c.fillText(t,sx,sy)});
  mzZoomTxt(doc)}
function mzSide(doc){const P=MZ.px,el=doc.getElementById('mzSide'),L=MZ.sh[MZ.which],d=MZ.v&&MZ.v.d,sp=d&&d.scan?sizePix(d.scan):null;
  el.innerHTML=`<h4>사진 픽셀 크기</h4><div class="px">${P.g?`Gray 사진 · ${esc(P.g.lab)} · <b>${+P.g.pix.toFixed(6)} µm</b> (${esc(P.g.from)})`:'Gray 사진 없음'}<br>${P.c?`Color 사진 · <b>${+P.c.pix.toFixed(6)} µm</b> (${esc(P.c.from)})`:'Color 사진 없음'}</div>`
    +`<h4>측정 · ${MZ.which==='g'?'Gray 사진':'Color 사진'} (${L.length}개)</h4>`
    +(L.length?`<ol>${L.map((sh,i)=>{const m=mzVal(sh);return `<li><span class="n">${MZ_N[i]||i+1}</span><span class="v">${MZ_NM[sh.t]} · ${m.px}<br><b>${m.um}</b></span><button data-mzdel="${i}" title="지우기">✕</button></li>`}).join('')}</ol>`:'<div class="hp">사진 위에서 끌어 그리면 여기에 길이 · 넓이가 나옵니다.</div>')
    +(d&&sp?`<div class="ref">참고 · 장비 값: Width ${um4(d.BlobBreadth*sp.pix)} µm · Area ${um4(d.area*sp.pix*sp.pix)} µm²</div>`:'')
    +`<div class="hp">휠 = 확대 · 축소(사진 픽셀의 64배까지, 12배부터 픽셀 격자) · 오른쪽 끌기 또는 [옮기기] = 사진 옮기기 · 네모 점 끌기 = 고치기 · 1 2 3 4 = 도구 · Ctrl+Z = 되돌리기 · 0 = 사진 전체 · ↑↓ = 다음 Defect · Esc = 측정 끝</div>`}
function mzHit(p,V){const L=MZ.sh[MZ.which],tol=8/V.s;for(let i=L.length-1;i>=0;i--){const sh=L[i];for(const end of ['b','a'])if(Math.hypot(sh[end][0]-p[0],sh[end][1]-p[1])<=tol)return {sh,end}}return null}
function mzRe(doc){mzBar(doc);mzDraw(doc);mzSide(doc)}
function mzBind(doc){const w=doc.defaultView,cv=doc.querySelector('#mzCv canvas'),focus=()=>{try{doc.body.focus()}catch(e){}};
  doc.getElementById('pwMz').addEventListener('click',()=>{mzToggle(doc);focus()});
  doc.getElementById('mzBar').addEventListener('click',e=>{const t=e.target.closest('button');if(!t)return;
    if(t.dataset.mzw){MZ.which=t.dataset.mzw;if(!MZ.view[MZ.which])mzFit(doc,MZ.which)}else if(t.dataset.mzt)MZ.tool=t.dataset.mzt;
    else if('mzu' in t.dataset)MZ.sh[MZ.which].pop();else if('mzc' in t.dataset)MZ.sh[MZ.which]=[];mzRe(doc);focus()});
  doc.getElementById('mzSide').addEventListener('click',e=>{const t=e.target.closest('[data-mzdel]');if(!t)return;MZ.sh[MZ.which].splice(+t.dataset.mzdel,1);mzRe(doc)});
  const pt=e=>{const r=cv.getBoundingClientRect(),V=MZ.view[MZ.which];return [V.ox+(e.clientX-r.left)/V.s,V.oy+(e.clientY-r.top)/V.s]};
  cv.addEventListener('wheel',e=>{const V=MZ.view[MZ.which];if(!V)return;e.preventDefault();const [x,y]=pt(e),s=Math.max(V.min,Math.min(64,V.s*(e.deltaY<0?1.25:0.8)));
    V.ox=x-(x-V.ox)*V.s/s;V.oy=y-(y-V.oy)*V.s/s;V.s=s;mzDraw(doc)},{passive:false});
  cv.addEventListener('contextmenu',e=>e.preventDefault());
  cv.addEventListener('pointerdown',e=>{const V=MZ.view[MZ.which];if(!V||!MZ.img[MZ.which])return;try{cv.setPointerCapture(e.pointerId)}catch(x){}const p=pt(e);
    if(e.button!==0||MZ.tool==='pan'){MZ.drag={pan:true,x:e.clientX,y:e.clientY,ox:V.ox,oy:V.oy};return}
    const h=mzHit(p,V);if(h){MZ.drag={sh:h.sh,end:h.end};return}
    const sh={t:MZ.tool,a:p,b:p.slice()};MZ.sh[MZ.which].push(sh);MZ.drag={sh,end:'b',nw:true}});
  cv.addEventListener('pointermove',e=>{const D=MZ.drag;if(!D)return;const V=MZ.view[MZ.which];
    if(D.pan){V.ox=D.ox-(e.clientX-D.x)/V.s;V.oy=D.oy-(e.clientY-D.y)/V.s;mzDraw(doc)}else{D.sh[D.end]=pt(e);mzDraw(doc);mzSide(doc)}});
  const up=()=>{const D=MZ.drag;MZ.drag=null;if(D&&D.nw&&Math.hypot(D.sh.b[0]-D.sh.a[0],D.sh.b[1]-D.sh.a[1])<0.5)MZ.sh[MZ.which].pop();if(D){mzDraw(doc);mzSide(doc)}};
  cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);
  w.addEventListener('resize',()=>{if(MZ.on)mzDraw(doc)})}
/** 측정 화면 키(측정 중이 아니면 M 만). true = 처리함(새 창 원래 키로 안 넘김). ↑↓ · Space 는 원래대로(다음 Defect). */
function mzKey(doc,e){const k=e.key.length===1?e.key.toLowerCase():e.key;
  if(!MZ.on){if(k==='m'&&!e.ctrlKey&&!e.altKey&&!e.metaKey){mzToggle(doc,true);e.preventDefault();return true}return false}
  if(k==='Escape'||(k==='m'&&!e.ctrlKey)){mzToggle(doc,false);e.preventDefault();return true}
  if((e.ctrlKey&&k==='z')||k==='Delete'||k==='Backspace'){MZ.sh[MZ.which].pop();mzRe(doc);e.preventDefault();return true}
  const t=MZ_T.find(x=>x[2]===k);if(t){MZ.tool=t[0];mzBar(doc);e.preventDefault();return true}
  if(k==='0'){mzFit(doc,MZ.which,true);mzRe(doc);e.preventDefault();return true}
  return false}
function photoWinFollow(V){if(PW.w&&!PW.w.closed&&PW.V===V)photoWinShow()}
/** 새 창 문서(손댈 수 없으면 null — 새 창을 새로 고침(F5)하면 빈 창이 다른 출처가 된다). */
function pwDoc(w){try{const d=w.document;d.getElementById('fc');return d}catch(e){return null}}
async function photoWinShow(){let w=PW.w;if(!w||w.closed)return;let doc=pwDoc(w);
  if(!doc){try{w.close()}catch(e){}PW.w=null;w=winOpen('cw_photo_'+Date.now(),'width=1600,height=1000');PW.w=w;photoWinInit(w);doc=w.document;try{w.focus()}catch(e){}}   // 닫고 새 창
  const src=PW.src,tk=++PW.tok,$w=id=>doc.getElementById(id),K=src?src.sel():0,v=src&&src.n()?src.v(K):null;
  if(!$w('fc')||!doc.querySelector('#fc .im'))photoWinInit(w);   // 같은 출처로 새로 고쳐졌으면 다시 만든다
  const F=id=>{const f=$w(id);return {cap:f.querySelector('figcaption'),im:f.querySelector('.im')}},fc=F('fc'),fx=F('fx'),ff=F('ff'),pv=doc.querySelector('.pv');
  for(const f of [fc,fx,ff]){f.im.replaceChildren();f.im.classList.remove('full','drag');const zb=f.im.parentNode.querySelector('.zb');if(zb)zb.hidden=true}pv.classList.remove('conly');
  const cap=(f,h,title)=>{f.cap.innerHTML=h;f.cap.title=title||''};
  if(!v){if(MZ.on)mzToggle(doc,false);$w('hd').textContent='보여 줄 Defect 가 없습니다';cap(fc,'Color');cap(fx,'Gray Crop (Color 시야)');cap(ff,'Gray 프레임');return}
  const ms=(f,t)=>f.im.insertAdjacentHTML('beforeend',`<p class="ms">${esc(t)}</p>`),zoom=pwZoom,ring=()=>v.ring==null?GLC.show:v.ring;PW.ring=ring;
  $w('hd').innerHTML=v.hd+` <i>(↑↓ ←→ 이전 · 다음${v.space?' · '+v.space:''} · F = 확대 · 위치 고정 · B = Defect 박스 켜기/끄기 · M = 크기 측정 · 사진 누르기 = 2배씩 확대(Shift · 오른쪽 = 축소, 휠 · 끌기) · Esc = 창 맞춤)</i>`
    +(v.rel&&src.V?' <i style="color:#e0b060">· 전체 경로: 5-1 의 [원본 폴더 경로(PC)] 를 적으면 PC 경로로 나옵니다(지금은 고른 폴더부터)</i>':'');if(MZ.on)mzLoad(doc,v);
  // 사진 파일명 + 전체 경로(소유자 "사진 파일명뿐만 아니라 전체 경로도") — 경로는 사진을 실제로 찾은 곳(없으면 매칭 폴더 + 이름)
  const rel=v.rel?' rel':'',pl=x=>x?`<span class="pp${rel}">${esc(x)}</span>`:'',cp=v.c?v.c.path:'',gp=v.g?v.g.path:'',gn=v.g?v.g.name:'';
  cap(fc,`Color · <b>${esc(v.c?v.c.name:'없음')}</b>${pl(cp)}`,cp);
  cap(fx,`Gray Crop (Color 시야) · <b>${esc(gn||'없음')}</b>${pl(gp)}`,gp);
  cap(ff,`Gray 프레임 · <b>${esc(gn||'없음')}</b>${v.g?` · 픽셀 (${f1(v.g.hit.px)}, ${f1(v.g.hit.py)}) · ${hitW(v.g.hit)}×${hitH(v.g.hit)}`:''} <i class="lg">· ${esc(pwLegend(ring()))}</i>${pl(gp)}`,gp);
  const draw=b=>{const cv=doc.createElement('canvas');cv.width=b.width;cv.height=b.height;cv.getContext('2d').drawImage(b,0,0);zoom(cv);return cv};
  const cb=v.c?await v.c.bmp():null;if(tk!==PW.tok)return;
  if(cb){const c=draw(cb);c._pid='fc';fc.im.append(c);pwApply(c)}else ms(fc,v.c?`Color 파일 없음: ${v.c.name}`:(v.cwhy||'Color 항목 없음'));
  // Gray 가 없으면(Color 사진만 저장된 Slot 등) Color 를 창 전체에 크게(소유자 "Color 이미지만 있을 경우에도 Color 이미지만이라도 띄워야")
  const conly=why=>{if(!cb){ms(fx,why);return}pv.classList.add('conly');why=why.replace(/^Gray:\s*/,'');$w('hd').insertAdjacentHTML('beforeend',` <b class="ng" title="${esc(why)}">· Gray 없음 — Color 만 크게 (${esc(why)})</b>`)};
  if(!v.g){conly(v.gwhy||'Gray: 위치 없음');return}
  const gb=await v.g.bmp();if(tk!==PW.tok)return;
  if(!gb){conly(`Gray 파일 없음: ${v.g.name}`);return}
  const H=v.g.hit,dd=v.g.d,cs=v.g.crop||cgCropSize({}),k=cgCropCanvas(gb,H,cs,doc,dd,{box:PWB.on,ring:ring()});zoom(k.canvas);k.canvas._pid='fx';fx.im.append(k.canvas);pwApply(k.canvas);
  const fr=cgFrameCanvas(gb,H,cs,doc,dd,{box:PWB.on,ring:ring()});zoom(fr);fr._pid='ff';fr._anchor=[H.px/hitW(H),H.py/hitH(H)];ff.im.append(fr);pwApply(fr);   // 프레임은 Defect 자리를 기준으로 고정
  // Defect 박스 · 측정 원(대규모만)을 바꾸면 같은 캔버스에 다시 그린다(크기 같음 → 확대 · 스크롤 그대로)
  k.canvas._redraw=()=>k.canvas.getContext('2d').drawImage(cgCropCanvas(gb,H,cs,doc,dd,{box:PWB.on,ring:ring()}).canvas,0,0);
  fr._redraw=()=>fr.getContext('2d').drawImage(cgFrameCanvas(gb,H,cs,doc,dd,{box:PWB.on,ring:ring()}),0,0);
  if(src.pre)src.pre(K)}

// ── 5-3: 사진 정밀 조사 ────────────────────────────────────────────────
const THUMB=new Map();   // 짝 번호 → {c, g(data URL), gl, err} — 설정이 바뀌면 비운다
const C5={items:[],base:[],tok:0,gtok:0,mode:'one',page:0};const G5=48,TW=240;
const VC=makeVT($('#c5list'),[['최종',46,'pk',null],['5-1 #',60,'num',null],['상태',150,'s',null],['Lot',120,'',null],['Slot',100,'',null],['ID',60,'num',null],['장비 스캔 분류',130,'',null],['리뷰 결과',130,'',null],['Recipe',120,'',null],['흑백 GL 평균',96,'num','gl'],['Contrast(실제)',110,'num',null],['Area (µm²)',86,'num',null,'a'],['Width (µm)',62,'num',null,'w']],{
  sort:()=>GLC.sort,onSort:k=>{GLC.sort=GLC.sort==='gl-d'?'gl-a':'gl-d';c5Refresh()},
  row:k=>{const p=C5.items[k],s=p.s,C=s.cols,i=p.i;return [p.pick?'☑':'☐',p.k+1,ST5[p.st],s.lotName,s.slotName||'',s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),glCell(p),fv(C.c[i]),...umCells(s,C,i)]},
  cls:k=>'st-'+C5.items[k].st+(C5.items[k].pick?' pk':''),onSel:()=>{c5Show();photoWinFollow(VC)},onEnter:()=>photoWin(VC,C5.items),onSpace:k=>pickToggle(C5.items[k])});
$('#c5list').addEventListener('click',e=>{const c=e.target.closest('.br>span.pk');if(c)pickToggle(C5.items[+c.parentNode.dataset.k])});
/** 5-3 목록: [사진 있는 것만] = Color 나 Gray 사진 중 하나라도 있는 것(소유자 "Color 이미지만 있을 경우에도 Color 이미지만이라도 띄워야") — 종전 'Color·Gray 매칭 완료만'은 Color 만인 Defect 를 숨겼다. */
const hasPhoto=p=>p.st==='ok'||p.st==='color'||p.st==='gray';
/** 5-3 사진 상태 필터(소유자: "Color 만 · 짝 매칭 · 흑백만 구분해서 볼 수 있게 체크박스"): 켠 상태만 보인다. 기본 = Color·Gray 매칭 완료 · Color 만 · Gray 만(종전 [사진 있는 것만]과 같음). */
const ST5_LAB={ok:'Color·Gray 매칭 완료',color:'Color 만',gray:'Gray 만',none:'둘 다 없음'};
const c5StOn=()=>new Set([...document.querySelectorAll('#c5stF [data-st5]')].filter(x=>x.checked).map(x=>x.dataset.st5));
function c5StText(on){const k=Object.keys(ST5_LAB).filter(x=>on.has(x));if(k.length===4)return '';if(k.length===3&&!on.has('none'))return ' (사진 있는 것만)';return ` (${k.length?k.map(x=>ST5_LAB[x]).join(' · '):'보기를 하나도 안 켬'})`}
function c5Refresh(keep){const on=c5StOn(),T=C5.q||[],P=c5Pool().filter(p=>!T.length||qAll(T,b5Text(p))),n={};for(const p of P)n[p.st]=(n[p.st]||0)+1;   // v14.1.8: 5-2 의 ☑ 줄 · 검색
  document.querySelectorAll('#c5stF [data-n5]').forEach(x=>x.textContent=`(${(n[x.dataset.n5]||0).toLocaleString()})`);
  C5.base=P.filter(p=>on.has(p.st));C5.items=glApply(C5.base);vtSet(VC,C5.items.length,keep);pixLineSet($('#c5Pix'),C5.items.map(p=>p.s));   // #84: base = GL 범위 전(흑백 GL 측정 대상 고르기)
  $('#c5cnt').textContent=`Defect ${C5.items.length.toLocaleString()}개${c5StText(on)}${glNote()}${T.length?` · 검색 '${T.join(' ')}'`:''} · 불러온 사진 ${C5.items.filter(p=>THUMB.has(p.k)).length}개`+(C5.note?' · '+C5.note:'');C5.note='';
  $('#c5one').hidden=C5.mode!=='one';$('#c5gridBox').hidden=C5.mode!=='grid';$$('[data-v5]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.v5===C5.mode));
  if(C5.mode==='one')c5Show();else c5Grid();if(PW.V===VC)PW.items=C5.items;pickInfo()}
/** 진행 기록 줄(5-3 사진 하나): 지금 무엇을 읽는지 · 끝난 것 · 걸린 시간. 진행 중인 줄은 0.2초마다 시간이 올라간다(멈추면 응답 기다리는 중). */
function stLog(box,tk){const L=[],t0=performance.now();let cur=null;
  const draw=()=>{const now=performance.now();box.innerHTML=L.map(l=>{const sec=((l.k==='on'?now:l.e)-l.s)/1000;
    return `<div class="${l.k}">${l.k==='on'?'⏳':l.k==='ok'?'✔':'✖'} ${esc(l.t)}${l.x?` — ${esc(l.x)}`:''}${l.s&&sec>=0.01?` <span class="muted">${sec.toFixed(2)}초</span>`:''}</div>`}).join('')};
  const iv=setInterval(()=>{if(tk!==C5.tok){clearInterval(iv);return}draw()},200);
  const close=()=>{if(cur&&cur.k==='on'){cur.k='ok';cur.e=performance.now()}};
  return {step(t){close();cur={t,k:'on',s:performance.now()};L.push(cur);draw()},done(x){if(cur){cur.k='ok';cur.e=performance.now();if(x)cur.x=x}draw()},
    fail(x){if(cur&&cur.k==='on'){cur.k='err';cur.e=performance.now();cur.x=x}else L.push({t:x,k:'err'});draw()},
    end(){close();clearInterval(iv);L.push({t:`이 Defect 끝 (${((performance.now()-t0)/1000).toFixed(2)}초)`,k:'ok'});draw()}}}
async function c5Show(){
  const p=C5.items[VC.sel],tk=++C5.tok,cf=$('#c5Color'),gf=$('#c5Gray'),st=$('#c5St'),rv=cf.parentNode;rv.classList.remove('conly');
  cf.innerHTML='<figcaption>Color 원본</figcaption>';gf.innerHTML='<figcaption>Gray Crop (Color 시야)</figcaption>';
  if(!p){cf.insertAdjacentHTML('beforeend','<div class="ph">보여 줄 Defect 가 없습니다</div>');$('#c5Info').innerHTML='';$('#c5Rv').textContent='';st.innerHTML='';return}
  const s=p.s,log=stLog(st,tk),r=p.r||cgOf(s,p.i),d=bigDef(s,p.i),x=info({d,raw:true,label:s.lotPath});d.gl=p.gl||null;
  const cn=r.c?cleanName(r.c.file):'',gn=r.hit?cleanName(r.hit.frame.file):'';   // 사진 파일명(소유자) — 칸 제목에
  const dir=s.cg&&s.cg.path?s.cg.path+'/':'',cp=cn?pcPath(p.c?p.c.path:dir+cn):'',gp=gn?pcPath(p.g?p.g.path:dir+gn):'',pl=x=>x?`<span class="pp">${esc(x)}</span>`:'';   // 전체 경로(소유자)
  cf.querySelector('figcaption').innerHTML=`Color 원본 · <b>${esc(cn||'없음')}</b>${pl(cp)}`;gf.querySelector('figcaption').innerHTML=`Gray Crop (Color 시야) · <b>${esc(gn||'없음')}</b>${pl(gp)}`;
  const ct=r.c?`${cleanName(r.c.file)} · ${CG_HOW[r.how]}`:(p.cerr||r.why||'Color 항목 없음');
  const gt=r.hit?`${cleanName(r.hit.frame.file)} · (${f1(r.hit.px)}, ${f1(r.hit.py)}) · 후보 ${r.hit.n} · 프레임 ${hitW(r.hit)}×${hitH(r.hit)} · 좌표 기준 ${CG.MODES[s.cg.plan.mode]} · ${geoModel(r.hit)}`:(p.gerr||`Gray: ${r.why}`);
  const fill=()=>{$('#c5Info').innerHTML=kvHtml([['상태',ST5[p.st]],['순서',`${VC.sel+1} / ${C5.items.length}`],['장비 스캔 분류',clsFirst(s,p.i)],['리뷰 결과',clsName(s,p.i)],['Lot 폴더',s.lotPath],['흑백 GL 평균 (원)',glInfo(p)],...infoRows(d,x,ct,gt),['Color 경로',cp||'-'],['Gray 경로',gp||'-']])};fill();$('#c5Rv').textContent=rvText(d);
  if(r.c){log.step(`Color 이미지 읽기 · 디코딩: ${cleanName(r.c.file)}`);const b=await cgBitmap(s,r.c.file);if(tk!==C5.tok)return;
    if(b){const cv=document.createElement('canvas');cv.width=b.width;cv.height=b.height;cv.getContext('2d').drawImage(b,0,0);cv.onclick=()=>photoWin(VC,C5.items);cf.append(cv);log.done(`${b.width}×${b.height}px`)}
    else{cf.insertAdjacentHTML('beforeend',`<div class="ph">Color 파일 없음: ${esc(cleanName(r.c.file))}</div>`);log.fail('Color 파일 없음')}}
  else{cf.insertAdjacentHTML('beforeend',`<div class="ph">${esc(ct)}</div>`);log.fail(ct)}
  const hasC=!!cf.querySelector('canvas');if(!r.hit&&hasC)rv.classList.add('conly');   // Gray 가 없으면 Color 를 칸 전체에(소유자)
  if(r.hit){log.step(`Gray 프레임 읽기 · 디코딩: ${cleanName(r.hit.frame.file)}`);const b=await cgBitmap(s,r.hit.frame.file);if(tk!==C5.tok)return;if(!b&&hasC)rv.classList.add('conly');
    if(b){log.step('Crop(Color 시야) · GL 계산');const k=cgCropCanvas(b,r.hit,r.crop||cgCropSize({}),document,d);d.gl=p.gl=cgGL(k,b,d);k.canvas.onclick=()=>photoWin(VC,C5.items);gf.append(k.canvas);
      log.done(`픽셀 (${f1(r.hit.px)}, ${f1(r.hit.py)}) · Crop ${k.raw.width}×${k.raw.height} → ${k.canvas.width}×${k.canvas.height}`);fill()}
    else{gf.insertAdjacentHTML('beforeend',`<div class="ph">Gray 파일 없음: ${esc(cleanName(r.hit.frame.file))}</div>`);log.fail('Gray 파일 없음')}}
  else{gf.insertAdjacentHTML('beforeend',`<div class="ph">${esc(gt)}</div>`);log.fail(gt)}
  log.end();
  // 다음 3개 미리 읽기(Color · Gray 프레임)
  for(let j=VC.sel+1;j<=VC.sel+3&&j<C5.items.length;j++){const q=C5.items[j],rq=q.r||cgOf(q.s,q.i);if(rq.c)cgBitmap(q.s,rq.c.file);if(rq.hit)cgBitmap(q.s,rq.hit.frame.file)}
}
/** 격자용 작은 사진 2장(Color 축소 · Gray Crop(Color 시야)) → data URL. note(글, 단계). */
async function prepThumb(p,note){
  let t=THUMB.get(p.k);if(t)return t;const s=p.s,r=p.r||cgOf(s,p.i),d=bigDef(s,p.i),err=[];let c=null,g=null,g0=null,gl=null;
  const small=src=>{const k=Math.min(1,TW/Math.max(src.width,src.height)),cv=document.createElement('canvas');cv.width=Math.max(1,Math.round(src.width*k));cv.height=Math.max(1,Math.round(src.height*k));
    const x=cv.getContext('2d');x.imageSmoothingQuality='high';x.drawImage(src,0,0,cv.width,cv.height);return cv};
  if(r.c){note&&note(`Color 읽기 · 축소: ${s.slotName} / ${cleanName(r.c.file)}`,0);const b=await cgBitmap(s,r.c.file);if(b)c=small(b).toDataURL('image/jpeg',0.9);else err.push('Color 파일 없음')}
  else err.push('Color 없음');
  if(r.hit){note&&note(`Gray 프레임 읽기 · Crop: ${s.slotName} / ${cleanName(r.hit.frame.file)}`,1);const b=await cgBitmap(s,r.hit.frame.file);
    if(b){const cs=r.crop||cgCropSize({}),k=cgCropCanvas(b,r.hit,cs,document,d,{ring:true});gl=p.gl=cgGL(k,b,d);g=small(k.canvas).toDataURL('image/jpeg',0.92);
      g0=small(cgCropCanvas(b,r.hit,cs,document,d,{ring:false}).canvas).toDataURL('image/jpeg',0.92)}else err.push('Gray 파일 없음')}
  else err.push(p.gerr||'Gray 위치 없음');
  t={c,g,g0,gl,err};THUMB.set(p.k,t);return t}
function c5Card(p,k){const t=THUMB.get(p.k),s=p.s,C=s.cols,i=p.i,r=p.r||cgOf(s,i),cn=r.c?cleanName(r.c.file):'',gn=r.hit?cleanName(r.hit.frame.file):'',dir=s.cg&&s.cg.path?s.cg.path+'/':'';
  const cp=cn?pcPath(p.c?p.c.path:dir+cn):'',gp=gn?pcPath(p.g?p.g.path:dir+gn):'';   // 마우스를 올리면 전체 경로
  return `<div class="g5 st-${p.st}${p.pick?' pk':''}" data-k="${k}" title="눌러서 크게 보기"><div class="gh">${p.pick?'☑ ':''}${k+1}. ${esc(s.lotName)} · ${esc(s.slotName||'')} · ID ${s.idByOrder?i:C.id[i]} · C ${fv(C.c[i])}</div>
    <div class="gi"><div data-l="Color" title="${esc(cp)}">${t?(t.c?`<img src="${t.c}" alt="Color">`:'<span class="ph">Color 없음</span>'):'<span class="ph">⏳</span>'}</div><div data-l="Gray Crop" title="${esc(gp)}">${t?(t.g?`<img src="${GLC.show||!t.g0?t.g:t.g0}" alt="Gray Crop">`:'<span class="ph">Gray 없음</span>'):'<span class="ph">⏳</span>'}</div></div>
    <div class="gn"><span title="${esc(cp)}">${esc(cn||'-')}</span><span title="${esc(gp)}">${esc(gn||'-')}</span></div>
    ${t&&t.err.length?`<div class="ge">${esc(t.err.join(' · '))}</div>`:''}${t&&t.gl?`<div class="gm">ROI−local ${f1(t.gl.delta)} · ROI mean ${f1(t.gl.mean)}</div>`:''}</div>`}
function c5Grid(){const n=C5.items.length,pages=Math.max(1,Math.ceil(n/G5));C5.page=Math.max(0,Math.min(C5.page,pages-1));const a=C5.page*G5,b=Math.min(n,a+G5);
  $('#c5pg').textContent=`${C5.page+1} / ${pages} 쪽 (${n?a+1:0} ~ ${b} / ${n})`;
  $('#c5grid').innerHTML=C5.items.slice(a,b).map((p,j)=>c5Card(p,a+j)).join('')||'<p class="muted">보여 줄 Defect 가 없습니다.</p>';c5GridFill(++C5.gtok)}
async function c5GridFill(tk){const els=[...$$('#c5grid .g5')].filter(el=>!THUMB.has(C5.items[+el.dataset.k].k)),m=els.length,st=$('#c5gst');let k=0;
  for(const el of els){if(tk!==C5.gtok)return;const p=C5.items[+el.dataset.k];
    await prepThumb(p,t=>{if(tk===C5.gtok)st.textContent=`이 쪽 사진 준비 ${k} / ${m} · 지금: ${t}`});if(tk!==C5.gtok)return;
    const ne=document.createElement('div');ne.innerHTML=c5Card(p,+el.dataset.k);el.replaceWith(ne.firstElementChild);k++;st.textContent=`이 쪽 사진 준비 ${k} / ${m}`;await nextPaint()}
  st.textContent=m?`이 쪽 사진 ${m}개 준비 끝`:'이 쪽 사진은 모두 준비돼 있습니다';$('#c5cnt').textContent=$('#c5cnt').textContent.replace(/불러온 사진 \d+개/,`불러온 사진 ${C5.items.filter(p=>THUMB.has(p.k)).length}개`)}
/** [사진 모두 불러오기](v14.1.6, 종전 이름 = 목록 사진 미리 준비): 목록 전체 사진(로딩창 · 중지 가능). 같은 Gray 프레임끼리 묶어 프레임을 한 번만 디코딩한다. */
async function c5PrepAll(){const L=C5.items.filter(p=>!THUMB.has(p.k)).sort((a,b)=>a.s.id-b.s.id||natCmp(a.g?a.g.file:'',b.g?b.g.file:'')||a.k-b.k);if(!L.length)return;
  BIG.stop=false;const total=L.length,cancel=()=>{BIG.stop=true};let done=0,cur='',step=0;
  const STEPS=['① Color 이미지 읽기 · 축소','② Gray 프레임 읽기 · 디코딩 · 크롭 · GL 계산'];
  const pr=throttle(()=>busy({title:'사진 모두 불러오기',steps:STEPS,step,done,total,unit:'Defect',files:`불러온 사진 ${THUMB.size}개 · 같은 Gray 프레임끼리 묶어 한 번만 디코딩`,detail:cur,cancel}),80);
  busy({title:'사진 모두 불러오기',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  try{for(const p of L){if(BIG.stop)break;await prepThumb(p,(t,sp)=>{cur=t;step=sp;pr()});done++;pr()}}finally{busy(null)}
  c5Refresh(true)}

// ── 5-3 최종 목록(소유자 #68): Space 로 ☑ / ☐ → 사진을 넣은 엑셀 저장 ─────────────────
//   선택 = 짝 항목(BIG.pairs)의 p.pick — 5-3 목록 · 사진 새 창 · 격자가 같은 값을 본다. [다시 확인](5-2)을 해도 같은 Slot · Defect 면 남긴다.
const pickBadge=p=>`<b class="pk ${p&&p.pick?'on':'off'}" id="pk">${p&&p.pick?'☑ 최종 목록':'☐ 최종 목록 아님'}</b>`;
const pickList=()=>C5.items.filter(p=>p.pick);   // v14.1.8: 최종 목록 = 5-3 에 보이는 줄(보기 · GL 범위 · 검색) 중 ☑ — 다른 단계와 같은 규칙
function pickInfo(){const n=pickList().length;$('#c5pickN').textContent=`☑ ${n.toLocaleString()} / ${C5.items.length.toLocaleString()}개`;$('#c5pickN').classList.toggle('on',n>0);$('#c5save').disabled=!n;$('#c5saveCsv').disabled=!n;$('#c5saveZip').disabled=!n;
  $('#c5save').textContent=n?`💾 최종 목록 엑셀 저장 (☑ ${n.toLocaleString()}개 · 사진 포함)`:'💾 최종 목록 엑셀 저장 (사진 포함)'}
function pickToggle(p,v){if(!p)return;p.pick=v==null?!p.pick:!!v;pickChanged()}
function pickChanged(){vtPaint(VC);pickInfo();if(C5.mode==='grid')$$('#c5grid .g5').forEach(el=>{const p=C5.items[+el.dataset.k];if(!p)return;el.classList.toggle('pk',!!p.pick);const h=el.querySelector('.gh');h.textContent=h.textContent.replace(/^☑ /,'');if(p.pick)h.textContent='☑ '+h.textContent});
  const w=PW.w,doc=w&&!w.closed?pwDoc(w):null,b=doc&&doc.getElementById('pk');if(b&&PW.V)b.outerHTML=pickBadge(PW.items[PW.V.sel])}
/** 엑셀에 넣을 사진 하나 → JPEG(긴 쪽 mw × mh 안, 원본보다 크게 하지 않음). */
async function xlJpeg(src,mw,mh){const k=Math.min(1,mw/src.width,mh/src.height),cv=document.createElement('canvas');cv.width=Math.max(1,Math.round(src.width*k));cv.height=Math.max(1,Math.round(src.height*k));
  const c=cv.getContext('2d');c.imageSmoothingQuality='high';c.drawImage(src,0,0,cv.width,cv.height);
  const b=await new Promise(r=>cv.toBlob(r,'image/jpeg',0.88));return {data:new Uint8Array(await b.arrayBuffer()),w:cv.width,h:cv.height}}
/** 한 Defect 의 사진 3장(Color · Gray Crop + Defect 박스 · Gray 프레임 + Defect 박스 · 노란 Crop 범위)과 GL. 5-3 · 새 창과 같은 함수로 그린다. */
async function xlPhotos(p,orig){const s=p.s,r=p.r||cgOf(s,p.i),d=bigDef(s,p.i),o={c:null,g:null,f:null,gl:null,err:[]};
  if(r.c){const b=await cgBitmap(s,r.c.file);if(b)o.c=await xlJpeg(b,960,720);else o.err.push(`Color 파일 없음: ${cleanName(r.c.file)}`)}else o.err.push(p.cerr||r.why||'Color 항목 없음');
  if(r.hit){const b=await cgBitmap(s,r.hit.frame.file);
    if(b){const cs=r.crop||cgCropSize({}),k=cgCropCanvas(b,r.hit,cs,null,d);o.gl=p.gl=cgGL(k,b,d);if(!p.glp){p.glp=glProfile(b,r.hit);p.glv=glMean(p)}o.g=await xlJpeg(k.canvas,960,720);o.f=await xlJpeg(cgFrameCanvas(b,r.hit,cs,null,d),1800,600);
      if(orig)o.go=await cropPng(k.raw)}
    else o.err.push(`Gray 파일 없음: ${cleanName(r.hit.frame.file)}`)}
  else o.err.push(p.gerr||`Gray: ${r.why||'위치 없음'}`);
  if(orig){if(r.c){o.co=await xlOrig(s,r.c.file);if(o.co)o.c=o.co;else o.err.push('Color 원본 못 읽음 — 줄인 사진')}if(r.hit)o.fo=await xlOrig(s,r.hit.frame.file)}   // v14.3.17(#86): Color 열 = 원본으로 바꿈
  return o}
/** v14.3.17(#86) 흑백 원본 Crop = cgCropCanvas 의 raw(Gray 원본 픽셀을 Crop 범위만큼 그대로 — 늘림 · 흑백 필터 · Defect 박스 · 원 없음, 프레임 밖 = 검정) → PNG(무손실). */
async function cropPng(cv){const b=await new Promise(r=>cv.toBlob(r,'image/png'));return {data:new Uint8Array(await b.arrayBuffer()),w:cv.width,h:cv.height,ext:'png',orig:true}}
/** v14.1.10(#78) 원본 사진 = 매칭 폴더의 파일 바이트 그대로(줄이기 · 다시 압축 · 표시 그림 없음). JPEG · PNG 는 그대로, 그 밖의 형식만 같은 픽셀 PNG(무손실)로 바꾼다. 못 읽으면 null. */
const XLO={on:false};try{XLO.on=localStorage.getItem('cw.xlOrig')==='1'}catch(e){}
function xlOrigSet(on){XLO.on=!!on;$('#c5xlOrig').checked=XLO.on;try{localStorage.setItem('cw.xlOrig',XLO.on?'1':'0')}catch(e){}}
async function xlOrig(s,file){const g=s.cg,b=cleanName(file||'');if(!g||!g.dir||!b)return null;
  try{const nm=await g.dir.names(),e=nm&&!nm.err?nm.get(lower(b)):await g.dir.get(b);if(!e)return null;
    const f=await e.file(),data=new Uint8Array(await f.arrayBuffer()),bm=await createImageBitmap(f),w=bm.width,h=bm.height;
    const ext=data[0]===0xff&&data[1]===0xd8?'jpeg':data[0]===0x89&&data[1]===0x50&&data[2]===0x4e&&data[3]===0x47?'png':'';
    if(ext){bm.close&&bm.close();return {data,w,h,ext,orig:true}}
    const cv=document.createElement('canvas');cv.width=w;cv.height=h;cv.getContext('2d').drawImage(bm,0,0);bm.close&&bm.close();
    const pb=await new Promise(r=>cv.toBlob(r,'image/png'));return {data:new Uint8Array(await pb.arrayBuffer()),w,h,ext:'png',orig:true}}
  catch(e){return null}}
/** 엑셀 열: [제목, 폭 px, 사진 칸이면 'img' + 사진 상자 높이]. 사진 줄 높이 = XL_IMG_H + 여백. */
const XL_IMG_H=180,XL_COLS=[['5-1 #',52],['Lot',130],['Slot',110],['ID',60],['장비 스캔 분류',130],['리뷰 결과',130],['Recipe',110],['Contrast(실제)',96],
  ['Color',250,'c'],['Gray Crop (Defect 박스)',250,'g'],['Gray 프레임 (Defect 박스 · 노란 상자 = Crop 범위)',570,'f'],
  ['상태',120],['Area µm²',80],['Width',64],['Length',64],['Box W×H',84],['Wafer X',84],['Wafer Y',84],['Die (장비 Col, Row)',110],['Die (맵 X, Y)',110],['ROI−local',80],['ROI mean',80],
  ['Color 파일',190],['Color 전체 경로',380],['Gray 파일',190],['Gray 전체 경로',380],['사진 없음 이유',240],['Lot 경로',300],['흑백 GL 평균 (원)',110],['GL 원 반지름 px · 픽셀 수',150],['Zone',90],['Region',70],['판정 비트',110],['분류 코드',80],['Zone 이름',110],['판정 종류',150]];
/** v14.3.17(#86) [원본 이미지로 저장] 을 켜면 Color 열 = Color 원본 파일(XL_CO 제목), 흑백 표시 열 2개는 그대로 두고 Gray 프레임 열 바로 뒤에 원본 2열(XL_ORIG)을 넣는다.
 *  끄면 종전 XL_COLS 그대로(Para colorgray.FINAL_COLS 와 같은 차례). v14.1.10(#78) 의 'Color 원본' 추가 열은 없앰(Color 열을 바꾸므로). */
const XL_ORIG=[['Gray Crop 원본 (흑백 원본을 자른 그림 · 표시 없음)',250,'go'],['Gray 프레임 원본 (파일 그대로 · 표시 없음)',570,'fo']],XL_OI=XL_COLS.findIndex(c=>c[2]==='f')+1,
  XL_CI=XL_COLS.findIndex(c=>c[2]==='c'),XL_CO=['Color 원본 (파일 그대로)',250,'c'];
const xlCols=orig=>orig?[...XL_COLS.slice(0,XL_CI),XL_CO,...XL_COLS.slice(XL_CI+1,XL_OI),...XL_ORIG,...XL_COLS.slice(XL_OI)]:XL_COLS;
function xlRow(p,o,orig){const R=xlRow0(p,o);if(orig){R.splice(XL_OI,0,o.go?null:'(원본 없음)',o.fo?null:'(원본 없음)')}return R}
function xlRow0(p,o){const s=p.s,C=s.cols,i=p.i,ob=S.o,px2=um2(s),act=ob.coord==='actual',X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product),r=p.r||cgOf(s,i);
  const cn=r.c?cleanName(r.c.file):'',gn=r.hit?cleanName(r.hit.frame.file):'',dir=s.cg&&s.cg.path?s.cg.path+'/':'',cp=cn?pcPath(p.c?p.c.path:dir+cn):'',gp=gn?pcPath(p.g?p.g.path:dir+gn):'',n=v=>Number.isFinite(v)?+v.toFixed(3):'';
  return [p.k+1,s.lotName||'',s.slotName||'',s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),n(C.c[i]),
    o.c?null:'(Color 사진 없음)',o.g?null:'(Gray 사진 없음)',o.f?null:'(Gray 사진 없음)',
    ST5[p.st]||p.st,n(C.area[i]*px2),n(C.w[i]),n(C.l[i]),`${f1(C.bw[i])}×${f1(C.bh[i])}`,n(X),n(Y),die?`${die.col}, ${die.row}`:'-',(m=>m&&m.x!=null?`${m.x}, ${m.y}`:'-')(mapDie(X,Y,s)),o.gl?n(o.gl.delta):'',o.gl?n(o.gl.mean):'',
    cn,cp,gn,gp,o.err.join(' · '),s.lotPath||'',p.glv!=null?+p.glv.toFixed(2):'',p.glp?`${GLC.r} px · ${glCount(p)}픽셀`:'',...rv5Cells(s,i).slice(1)]}
/** v14 [📄 최종 목록 CSV 저장](Para 최종 목록 CSV v1): ☑ Defect 마다 한 줄. Para 프로그램 [Defect 분석 › Color·Gray 매칭] 이 '매칭폴더' + 'Color 파일'로 그 Defect 를 찾아
 *  추출하고(프로그램 매칭에 필요한 파일이 없으면 이 줄의 Gray 프레임 · GrayPX/PY · CropW/H 를 씀), BoxW/BoxH(Slot 기준 픽셀 — 장비 값 그대로)로 Defect 박스를 그린다. 열 이름이 약속 — 바꾸면 Para colorgray.FINAL_REQUIRED 도. */
const FL_HEAD=['5-1 #','Lot','Slot','ID','장비 스캔 분류','리뷰 결과','Recipe','Contrast(실제)','상태','Area µm²','Width','Length','BoxW','BoxH','Wafer X','Wafer Y','Die (장비 Col, Row)','Die (맵 X, Y)','흑백 GL 평균 (원)',
  'Color 파일','Color 전체 경로','Gray 파일','Gray 전체 경로','GrayPX(3168x1024기준)','GrayPY(3168x1024기준)','CropW','CropH','매칭폴더','매칭폴더(고른 폴더부터)','Lot 경로','Zone','Region','판정 비트','분류 코드','Zone 이름','판정 종류'];
function flRow(p){const s=p.s,C=s.cols,i=p.i,ob=S.o,px2=um2(s),act=ob.coord==='actual',X=act?C.ax[i]:C.x[i],Y=act?C.ay[i]:C.y[i],die=dieOf(X,Y,s.product),r=p.r||cgOf(s,i),
    cn=r.c?cleanName(r.c.file):'',gn=r.hit?cleanName(r.hit.frame.file):'',dir=s.cg&&s.cg.path?s.cg.path+'/':'',n=v=>Number.isFinite(v)?+v.toFixed(3):'',cs=r.crop||cgCropSize({});
  return [p.k+1,s.lotName||'',s.slotName||'',s.idByOrder?i:C.id[i],clsFirst(s,i),clsName(s,i),rcp5(s,i),n(C.c[i]),ST5[p.st]||p.st,n(C.area[i]*px2),n(C.w[i]),n(C.l[i]),n(C.bw[i]),n(C.bh[i]),n(X),n(Y),
    die?`${die.col}, ${die.row}`:'-',(m=>m&&m.x!=null?`${m.x}, ${m.y}`:'-')(mapDie(X,Y,s)),p.glv!=null?+p.glv.toFixed(2):'',cn,cn?pcPath(p.c?p.c.path:dir+cn):'',gn,gn?pcPath(p.g?p.g.path:dir+gn):'',r.hit?n(r.hit.px):'',r.hit?n(r.hit.py):'',
    r.hit?cs.cw:'',r.hit?cs.ch:'',s.cg&&s.cg.path?pcPath(s.cg.path):'',s.cg&&s.cg.path||'',s.lotPath||'',...rv5Cells(s,i).slice(1)]}
async function c5SaveCsv(){const L=pickList();if(!L.length)return alert('최종 목록(☑)이 비어 있습니다. 5-3 목록에서 줄을 고르고 Space 를 누르십시오.');
  const parts=['\ufeff'+FL_HEAD.map(csvQ).join(',')+'\r\n',...L.map(p=>flRow(p).map(csvQ).join(',')+'\r\n')];
  const msg=await saveCsv(parts,`최종목록_${stamp()}.csv`,true);$('#c5saveSt').textContent=msg?`${msg} (Defect ${L.length}개${pcBaseSet()?'':' — 전체 경로 없음: 5-1 [원본 폴더 경로]를 적으면 Para 에서 폴더를 따로 고르지 않아도 됩니다'})`:'저장 취소'}
/** [💾 최종 목록 엑셀 저장]: 저장 위치를 먼저 고르고(누른 직후에만 열림) → ☑ Defect 마다 사진 3장을 그려 → xlsx 한 파일(사진이 칸 안에). 원본 폴더에는 쓰지 않는다. */
async function c5SaveXlsx(){const L=pickList();if(!L.length)return alert('최종 목록(☑)이 비어 있습니다. 5-3 목록에서 줄을 고르고 Space 를 누르십시오.');
  const name=`최종목록_${stamp()}.xlsx`,h=await pickSave(name,[{description:'Excel',accept:{'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':['.xlsx']}}]);if(h===false)return;
  BIG.stop=false;const orig=XLO.on,COLS=xlCols(orig),cancel=()=>{BIG.stop=true},total=L.length,rows=[],pics=[],STEPS=[orig?'① Defect 마다 사진 읽기 · 그리기 — Color 원본(파일 그대로) · Gray Crop · Gray 프레임 + 흑백 원본 2장(Crop · 프레임)':'① Defect 마다 사진 3장 읽기 · 그리기(Color · Gray Crop · Gray 프레임)','② 엑셀 파일 만들기 · 저장'];let done=0,cur='';
  const pr=throttle(()=>busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:0,done,total,unit:'Defect',files:`사진 ${pics.length}장`,detail:cur,cancel}),80);
  busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});let msg;
  try{for(const p of L){if(BIG.stop)break;cur=`${p.s.lotName||''} · ${p.s.slotName||''} · 5-1 #${p.k+1}`;pr();
      const o=await xlPhotos(p,orig),ri=rows.length+1;rows.push(xlRow(p,o,orig));COLS.forEach(([,,k],ci)=>{if(k&&o[k])pics.push({row:ri,col:ci,...o[k]})});done++;pr()}
    if(BIG.stop){msg=`중지 — 저장하지 않았습니다 (${done} / ${total} 개 준비)`;return}
    busy({title:'최종 목록 엑셀 저장',steps:STEPS,step:1,done:total,total,unit:'Defect',files:`사진 ${pics.length}장`,detail:'xlsx 묶는 중',cancel});await nextPaint();
    const blob=xlsxBlob('최종 목록',COLS,rows,pics);
    if(h){const w=await h.createWritable();await w.write(blob);await w.close();msg=`저장: ${h.name} (Defect ${rows.length}개 · 사진 ${pics.length}장${orig?` · 원본 ${pics.filter(x=>x.orig).length}장`:''} · ${(blob.size/1048576).toFixed(1)} MB)`}
    else{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),5000);
      msg=`다운로드 폴더에 저장: ${name} (Defect ${rows.length}개 · 사진 ${pics.length}장${orig?` · 원본 ${pics.filter(x=>x.orig).length}장`:''})`}
  }catch(e){msg=`저장 실패: ${(e&&e.message)||e}`}
  finally{busy(null);$('#c5saveSt').textContent=msg||''}
  return msg}
/** v14.3.17(#86) 원본 파일 바이트(형식 그대로 · 바꾸지 않음) + 파일 이름. 읽기만 한다(원본 폴더에 쓰지 않음). 못 읽으면 null. */
async function origBytes(s,file){const g=s.cg,b=cleanName(file||'');if(!g||!g.dir||!b)return null;
  try{const nm=await g.dir.names(),e=nm&&!nm.err?nm.get(lower(b)):await g.dir.get(b);if(!e)return null;const f=await e.file();return {name:f.name||b,data:new Uint8Array(await f.arrayBuffer())}}catch(e){return null}}
/** zip 안 이름 겹침 막기: 같은 원본(key 같음)은 한 번만, 이름만 같고 다른 그림은 '이름_2.확장자'. 돌려줌 = 넣을 이름 | null(이미 넣음). */
function zipName(U,dir,name,key){const k=dir+'\u0000'+key;if(U.keys.has(k))return null;U.keys.add(k);const dot=name.lastIndexOf('.'),stem=dot>0?name.slice(0,dot):name,ext=dot>0?name.slice(dot):'';
  let n=dir+name,i=2;while(U.names.has(lower(n)))n=`${dir}${stem}_${i++}${ext}`;U.names.add(lower(n));return n}
/** [🗂 최종 목록 사진 파일.zip 저장](#86): ☑ Defect 마다 color/ = Color 원본, gray/ = 흑백 프레임 원본(둘 다 파일 바이트 그대로 복사), gray crop/ = 흑백 원본을 Crop 범위로 자른 그림(PNG 무손실, 표시 없음).
 *  파일 이름 = 원본 파일 이름(gray crop 은 같은 이름 + .png). 여러 Defect 가 같은 원본을 쓰면 color · gray 는 한 번만, gray crop 은 Defect 마다(이름 겹치면 _2 …). 원본 폴더에는 쓰지 않는다. */
async function c5SaveZip(){const L=pickList();if(!L.length)return alert('최종 목록(☑)이 비어 있습니다. 5-3 목록에서 줄을 고르고 Space 를 누르십시오.');
  const name=`최종목록_사진_${stamp()}.zip`,h=await pickSave(name,[{description:'ZIP',accept:{'application/zip':['.zip']}}]);if(h===false)return;
  BIG.stop=false;const cancel=()=>{BIG.stop=true},total=L.length,files=[],U={keys:new Set(),names:new Set()},cnt={color:0,gray:0,crop:0},miss=[],STEPS=['① Defect 마다 원본 사진 읽기(color · gray 복사, gray crop 자르기)','② zip 파일 만들기 · 저장'];let done=0,cur='',msg;
  const pr=throttle(()=>busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:0,done,total,unit:'Defect',files:`파일 ${files.length}개`,detail:cur,cancel}),80);
  busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  try{for(const p of L){if(BIG.stop)break;const s=p.s,r=p.r||cgOf(s,p.i),sk=s.cg&&s.cg.path||s.id;cur=`${s.lotName||''} · ${s.slotName||''} · 5-1 #${p.k+1}`;pr();
      if(r.c){const key=sk+'|'+lower(cleanName(r.c.file));if(!U.keys.has('color/\u0000'+key)){const b=await origBytes(s,r.c.file);if(b){files.push([zipName(U,'color/',b.name,key),b.data]);cnt.color++}else miss.push(`Color ${cleanName(r.c.file)}`)}}
      if(r.hit){const gf=cleanName(r.hit.frame.file),key=sk+'|'+lower(gf);
        if(!U.keys.has('gray/\u0000'+key)){const b=await origBytes(s,r.hit.frame.file);if(b){files.push([zipName(U,'gray/',b.name,key),b.data]);cnt.gray++}else miss.push(`Gray ${gf}`)}
        const bm=await cgBitmap(s,r.hit.frame.file);
        if(bm){const k=cgCropCanvas(bm,r.hit,r.crop||cgCropSize({}),null,null),c=await cropPng(k.raw),dot=gf.lastIndexOf('.'),nm=(dot>0?gf.slice(0,dot):gf)+'.png',zn=zipName(U,'gray crop/',nm,key+'|'+r.hit.px+','+r.hit.py);
          if(zn){files.push([zn,c.data]);cnt.crop++}}}
      done++;pr()}
    if(BIG.stop){msg=`중지 — 저장하지 않았습니다 (${done} / ${total} 개 준비)`;return}
    if(!files.length){msg='저장할 사진 파일이 없습니다 (☑ Defect 의 원본 사진을 읽지 못함 — 매칭 폴더 확인)';return}
    busy({title:'최종 목록 사진 파일.zip 저장',steps:STEPS,step:1,done:total,total,unit:'Defect',files:`파일 ${files.length}개`,detail:'zip 묶는 중',cancel});await nextPaint();
    const blob=zipStore(files,'application/zip'),sum=`Defect ${total}개 · color ${cnt.color} · gray ${cnt.gray} · gray crop ${cnt.crop}개 · ${(blob.size/1048576).toFixed(1)} MB${miss.length?` · 못 읽음 ${miss.length}개(${miss.slice(0,3).join(', ')}${miss.length>3?' …':''})`:''}`;
    if(h){const w=await h.createWritable();await w.write(blob);await w.close();msg=`저장: ${h.name} (${sum})`}
    else{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),5000);msg=`다운로드 폴더에 저장: ${name} (${sum})`}
  }catch(e){msg=`저장 실패: ${(e&&e.message)||e}`}
  finally{busy(null);$('#c5saveSt').textContent=msg||''}
  return msg}

// ── xlsx 만들기(외부 라이브러리 없음): 시트 1장 + 사진(oneCellAnchor) + 저장 방식 zip ─────────────────
const xmlEsc=v=>String(v).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f￾￿]/g,'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const xlCol=n=>{let s='';n++;while(n){const m=(n-1)%26;s=String.fromCharCode(65+m)+s;n=(n-1-m)/26}return s};
/** cols = [[제목, 폭 px, 사진 칸 표시]], rows = 값 배열(null = 빈 칸), pics = [{row(1부터), col(0부터), data(JPEG · PNG), w, h, ext('jpeg' 기본 | 'png')}]. */
function xlsxBlob(sheet,cols,rows,pics){const NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main',RN='http://schemas.openxmlformats.org/officeDocument/2006/relationships',X='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const imgRow=new Set(pics.map(p=>p.row)),last=xlCol(cols.length-1)+(rows.length+1),E=9525;
  const cell=(v,r,c,st)=>{const ref=xlCol(c)+r;if(v==null||v==='')return `<c r="${ref}" s="${st}"/>`;
    return typeof v==='number'&&Number.isFinite(v)?`<c r="${ref}" s="${st}"><v>${v}</v></c>`:`<c r="${ref}" s="${st}" t="inlineStr"><is><t xml:space="preserve">${xmlEsc(v)}</t></is></c>`};
  const sd=[`<row r="1" ht="33" customHeight="1">${cols.map((c,j)=>cell(c[0],1,j,1)).join('')}</row>`];
  rows.forEach((R,k)=>{const r=k+2;sd.push(`<row r="${r}"${imgRow.has(k+1)?` ht="${(XL_IMG_H+10)*0.75}" customHeight="1"`:''}>${R.map((v,j)=>cell(v,r,j,2)).join('')}</row>`)});
  const ws=X+`<worksheet xmlns="${NS}" xmlns:r="${RN}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>`
    +`<sheetFormatPr defaultRowHeight="15"/><cols>${cols.map((c,j)=>`<col min="${j+1}" max="${j+1}" width="${Math.max(4,(c[1]-5)/7).toFixed(2)}" customWidth="1"/>`).join('')}</cols>`
    +`<sheetData>${sd.join('')}</sheetData><autoFilter ref="A1:${last}"/><drawing r:id="rId1"/></worksheet>`;
  const anc=pics.map((p,k)=>{const bw=cols[p.col][1]-10,f=Math.min(bw/p.w,XL_IMG_H/p.h),cx=Math.round(p.w*f*E),cy=Math.round(p.h*f*E);
    return `<xdr:oneCellAnchor><xdr:from><xdr:col>${p.col}</xdr:col><xdr:colOff>${5*E}</xdr:colOff><xdr:row>${p.row}</xdr:row><xdr:rowOff>${5*E}</xdr:rowOff></xdr:from><xdr:ext cx="${cx}" cy="${cy}"/>`
      +`<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="${k+2}" name="사진 ${k+1}"/><xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>`
      +`<xdr:blipFill><a:blip r:embed="rId${k+1}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>`
      +`<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="${cx}" cy="${cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>`}).join('');
  const files=[
    ['[Content_Types].xml',X+`<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="jpeg" ContentType="image/jpeg"/><Default Extension="png" ContentType="image/png"/>`
      +`<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`
      +`<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/></Types>`],
    ['_rels/.rels',X+`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${RN}/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
    ['xl/workbook.xml',X+`<workbook xmlns="${NS}" xmlns:r="${RN}"><sheets><sheet name="${xmlEsc(sheet)}" sheetId="1" r:id="rId1"/></sheets>`
      +`<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'${xmlEsc(sheet)}'!$A$1:$${xlCol(cols.length-1)}$${rows.length+1}</definedName></definedNames></workbook>`],
    ['xl/_rels/workbook.xml.rels',X+`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${RN}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="${RN}/styles" Target="styles.xml"/></Relationships>`],
    ['xl/styles.xml',X+`<styleSheet xmlns="${NS}"><fonts count="2"><font><sz val="10"/><name val="맑은 고딕"/></font><font><b/><sz val="10"/><name val="맑은 고딕"/></font></fonts>`
      +`<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFD9E1F2"/><bgColor indexed="64"/></patternFill></fill></fills>`
      +`<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>`
      +`<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>`
      +`<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`],
    ['xl/worksheets/sheet1.xml',ws],
    ['xl/worksheets/_rels/sheet1.xml.rels',X+`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${RN}/drawing" Target="../drawings/drawing1.xml"/></Relationships>`],
    ['xl/drawings/drawing1.xml',X+`<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="${RN}">${anc}</xdr:wsDr>`],
    ['xl/drawings/_rels/drawing1.xml.rels',X+`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${pics.map((p,k)=>`<Relationship Id="rId${k+1}" Type="${RN}/image" Target="../media/image${k+1}.${p.ext||'jpeg'}"/>`).join('')}</Relationships>`],
    ...pics.map((p,k)=>[`xl/media/image${k+1}.${p.ext||'jpeg'}`,p.data])];
  return zipStore(files,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
/** zip(저장 방식 = 압축 없음 — JPEG 는 이미 압축됨). files = [[이름, 문자열 | Uint8Array]]. */
const CRC_T=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;t[n]=c>>>0}return t})();
function crc32(b){let c=0xffffffff;for(let i=0;i<b.length;i++)c=CRC_T[(c^b[i])&255]^(c>>>8);return (c^0xffffffff)>>>0}
function zipStore(files,type){const te=new TextEncoder(),parts=[],cen=[];let off=0;const d=new Date(),dt=((d.getFullYear()-1980)<<9)|((d.getMonth()+1)<<5)|d.getDate(),tm=(d.getHours()<<11)|(d.getMinutes()<<5)|(d.getSeconds()>>1);
  for(const [name,body] of files){const nm=te.encode(name),data=typeof body==='string'?te.encode(body):body,crc=crc32(data),h=new DataView(new ArrayBuffer(30));
    h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint16(6,0x0800,true);h.setUint16(8,0,true);h.setUint16(10,tm,true);h.setUint16(12,dt,true);h.setUint32(14,crc,true);h.setUint32(18,data.length,true);h.setUint32(22,data.length,true);h.setUint16(26,nm.length,true);h.setUint16(28,0,true);
    parts.push(h.buffer,nm,data);const c=new DataView(new ArrayBuffer(46));
    c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint16(8,0x0800,true);c.setUint16(10,0,true);c.setUint16(12,tm,true);c.setUint16(14,dt,true);c.setUint32(16,crc,true);c.setUint32(20,data.length,true);c.setUint32(24,data.length,true);
    c.setUint16(28,nm.length,true);c.setUint32(42,off,true);cen.push(c.buffer,nm);off+=30+nm.length+data.length}
  const cl=cen.reduce((a,b)=>a+(b.byteLength!=null?b.byteLength:b.length),0),e=new DataView(new ArrayBuffer(22));
  e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,cl,true);e.setUint32(16,off,true);
  return new Blob([...parts,...cen,e.buffer],{type})}


// ── rev6: 흑백 GL(원) — 소유자 "실제 흑백 이미지 픽셀의 gray level · 원형 영역 · 크기만 · 예시 이미지에 원을 그려 정함 · 최대 64 px" ─────────
//   GL = Gray 프레임 원본 픽셀에서 가운데 (cx, cy) = Defect 좌표(Crop · Defect 박스와 같은 hit.px/py), 원 안 = 픽셀 가운데 (x+0.5, y+0.5) 가 반지름 r 이내, 프레임 밖은 뺌, 값 = 0~255 단순 평균.
//   측정 때 Defect 마다 반지름 0.5 px 단계(1 ~ 128 칸)별 누적 합 · 개수만 기억(glp) → 원 크기를 바꿔도 사진을 다시 읽지 않고 바로 다시 계산.
//   (d ≤ r ⇔ ceil(2d) ≤ 2r — r 이 0.5 단위라 칸 나눔이 정확하다.) 표시 그림(Crop 늘림 · 흑백 필터 · Defect 박스 · 원)은 재는 값에 안 들어간다.
const GL_MAX=64,GL_K=GL_MAX*2;
const GLC={r:5.5,lo:0,hi:255,sort:'',show:true};try{const v=+localStorage.getItem('cw.glR');if(v>=0.5&&v<=GL_MAX)GLC.r=Math.round(v*2)/2;GLC.show=localStorage.getItem('cw.glShow')!=='0'}catch(e){}
const glK=r=>Math.max(1,Math.min(GL_K,Math.round(r*2)));
let GLCV=null;
function glProfile(gray,hit){const cx=hit.px*gray.width/hitW(hit),cy=hit.py*gray.height/hitH(hit),S=new Float64Array(GL_K+1),N=new Uint32Array(GL_K+1);
  const x0=Math.max(0,Math.floor(cx-GL_MAX-1)),y0=Math.max(0,Math.floor(cy-GL_MAX-1)),x1=Math.min(gray.width,Math.ceil(cx+GL_MAX+1)),y1=Math.min(gray.height,Math.ceil(cy+GL_MAX+1));
  if(x1>x0&&y1>y0){const w=x1-x0,h=y1-y0;if(!GLCV)GLCV=document.createElement('canvas');GLCV.width=w;GLCV.height=h;
    const g=GLCV.getContext('2d',{willReadFrequently:true});g.clearRect(0,0,w,h);g.drawImage(gray,x0,y0,w,h,0,0,w,h);const D=g.getImageData(0,0,w,h).data,R2=GL_MAX*GL_MAX;
    for(let y=0;y<h;y++){const dy=y0+y+.5-cy;for(let x=0;x<w;x++){const dx=x0+x+.5-cx,d2=dx*dx+dy*dy;if(d2>R2)continue;let k=Math.ceil(Math.sqrt(d2)*2-1e-9);if(k<1)k=1;
      const o=(y*w+x)*4;S[k]+=(299*D[o]+587*D[o+1]+114*D[o+2])/1000;N[k]++}}   // 흑백 JPEG 은 R=G=B 라 그 값 그대로
    for(let k=1;k<=GL_K;k++){S[k]+=S[k-1];N[k]+=N[k-1]}}
  return {S,N,cx,cy,w:gray.width,h:gray.height}}
const glCount=(p,r)=>p.glp?p.glp.N[glK(r==null?GLC.r:r)]:0;
function glMean(p,r){const P=p.glp;if(!P)return null;const k=glK(r==null?GLC.r:r);return P.N[k]?P.S[k]/P.N[k]:null}
const glCan=p=>p.st==='ok'||p.st==='gray';   // 흑백 사진이 있는 Defect(소유자 "흑백 이미지가 포함된 케이스는 다")
const glCell=p=>p.glv!=null?f1(p.glv):p.glErr?'못 잼':glCan(p)?'측정 전':'흑백 없음';
const glInfo=p=>p.glv!=null?`${f2(p.glv)} (반지름 ${GLC.r} px · 원 안 ${glCount(p)}픽셀 · 프레임 원본 픽셀)`:p.glErr||(glCan(p)?'측정 전 — [흑백 GL 측정]':'흑백 사진 없음');
/** 표시 그림에 측정 원(하늘색). (x, y) 가운데, rx · ry 반지름(그림 좌표), ref = 그림 긴 변(선 굵기). */
function glRing(c,x,y,rx,ry,ref){c.save();c.strokeStyle='#22d3ee';c.lineWidth=Math.max(1,Math.round(ref/900));c.setLineDash([Math.max(3,ref/300),Math.max(2,ref/600)]);c.beginPath();c.ellipse(x,y,Math.max(.5,rx),Math.max(.5,ry),0,0,Math.PI*2);c.stroke();c.restore()}
/** 원 크기를 바꿈 → 모든 측정값 다시 계산(사진 다시 안 읽음) · 표시 그림 다시. */
function glSetR(r){r=Math.round(Math.max(.5,Math.min(GL_MAX,+r||GLC.r))*2)/2;GLC.r=r;try{localStorage.setItem('cw.glR',String(r))}catch(e){}
  for(const p of BIG.pairs||[])if(p.glp)p.glv=glMean(p);THUMB.clear();glRInfo();c5Refresh(true);if(PW.V===VC)photoWinFollow(VC)}
/** Para v14.1.5 [측정 원 보기](소유자 "측정원 on, off — 5-3 상단 흑백 GL 측정 구간에"): 표시 그림의 측정 원만 켜고 끔(GL 값 · 측정 그대로).
 *  5-3 하나씩 · 격자(준비한 작은 사진은 원 있는 · 없는 것 둘 다 둠 — 다시 읽지 않음) · 새 창(확대 그대로 다시 그림) · 최종 목록 엑셀 사진이 따른다. */
function glShowSet(on){GLC.show=!!on;$('#glShow').checked=GLC.show;try{localStorage.setItem('cw.glShow',GLC.show?'1':'0')}catch(e){}
  if(BIG.stage===3)c5Refresh(true);pwRedraw()}
function glRInfo(){$('#glR').value=GLC.r;$('#glRn').textContent=`(원 안 약 ${Math.round(Math.PI*GLC.r*GLC.r)}픽셀 · 지름 ${GLC.r*2} px)`}
/** 범위 바(두 손잡이) · 분포 막대 · 정렬. base = 상태 필터를 지난 목록. */
function glApply(base){const lo=Math.min(GLC.lo,GLC.hi),hi=Math.max(GLC.lo,GLC.hi),on=lo>0||hi<255;
  const H=new Uint32Array(256);let nv=0,nin=0;for(const p of base)if(p.glv!=null){nv++;const b=Math.max(0,Math.min(255,Math.round(p.glv)));H[b]++;if(p.glv>=lo&&p.glv<=hi+0.999)nin++}
  glHist(H,lo,hi);let L=on?base.filter(p=>p.glv!=null&&p.glv>=lo&&p.glv<=hi+0.999):base.slice();   // 손잡이는 정수 — hi 칸(예 170.0 ~ 170.99)까지 넣음
  if(GLC.sort){const sg=GLC.sort==='gl-d'?-1:1;L.sort((a,b)=>{const va=a.glv,vb=b.glv;if(va==null||vb==null)return (va==null)-(vb==null)||a.k-b.k;return sg*(va-vb)||a.k-b.k})}
  $('#glRngT').textContent=`GL ${lo} ~ ${hi}`;$('#glSort').value=GLC.sort;
  for(const [id,v] of [['glLoN',lo],['glHiN',hi],['glLo',lo],['glHi',hi]]){const e=$('#'+id);if(document.activeElement!==e)e.value=v}   // 바 · 숫자 칸 · 정렬 칸이 같은 값
  $('#glRngN').textContent=` · 측정한 ${nv.toLocaleString()}개 중 범위 안 ${nin.toLocaleString()}개`+(on?` (범위를 정하면 측정 안 된 · 흑백 없는 ${(base.length-nv).toLocaleString()}개는 숨김)`:'');
  C5.glOn=on;return L}
const glNote=()=>C5.glOn?` · GL ${Math.min(GLC.lo,GLC.hi)} ~ ${Math.max(GLC.lo,GLC.hi)}`:'';
function glHist(H,lo,hi){const cv=$('#glHist'),r=cv.getBoundingClientRect(),W=Math.max(200,Math.round(r.width||620)),Hh=46;if(cv.width!==W)cv.width=W;cv.height=Hh;const c=cv.getContext('2d');c.clearRect(0,0,W,Hh);
  const pad=7,bw=(W-2*pad)/256;let mx=0;for(const v of H)mx=Math.max(mx,v);const cs=getComputedStyle(document.documentElement),acc=cs.getPropertyValue('--acc').trim()||'#3b82f6',mu=cs.getPropertyValue('--line').trim()||'#ccc';
  for(let b=0;b<256;b++){if(!H[b])continue;const h=Math.max(1,Math.round((Hh-6)*Math.sqrt(H[b]/mx)));c.fillStyle=b>=lo&&b<=hi?acc:mu;c.fillRect(pad+b*bw,Hh-h,Math.max(1,bw-.2),h)}
  c.fillStyle='rgba(0,0,0,.08)';c.fillRect(0,0,pad+lo*bw,Hh);c.fillRect(pad+(hi+1)*bw,0,W,Hh)}
/** [흑백 GL 측정]: 사람이 고른 최종 목록(☑)의 Defect 중 흑백 사진이 있는 것(Color·Gray 매칭 완료 · Gray 만)만 — Para #84(소유자 "5-3 리스트 전체를 재면 낭비, 최종 목록만").
 *  대상 = 5-3 에 보이는 줄(보기 · 검색, GL 범위는 측정 결과라 보지 않음) 중 ☑. 같은 Gray 프레임끼리 묶어 한 번만 읽고, 다음 프레임은 미리 읽음. 이미 잰 것은 건너뜀. */
const glTargets=()=>(C5.base||[]).filter(p=>p.pick&&glCan(p));
async function glRun(){const T=glTargets(),L=T.filter(p=>!p.glp);
  if(!L.length){$('#glSt').textContent=T.length?'새로 잴 Defect 가 없습니다(최종 목록 ☑ 의 흑백 사진은 모두 잼).':'최종 목록(☑)에 흑백 사진이 있는 Defect 가 없습니다. 목록에서 잴 Defect 를 ☑ 로 고르십시오(Space).';return}
  const G=new Map();for(const p of L){const r=p.r||cgOf(p.s,p.i);if(!r.hit){p.glErr='흑백 위치 없음: '+(r.why||'');continue}const k=p.s.id+'|'+lower(cleanName(r.hit.frame.file));let g=G.get(k);if(!g)G.set(k,g={s:p.s,file:r.hit.frame.file,ps:[]});g.ps.push({p,hit:r.hit})}
  const F=[...G.values()],total=L.length,t0=performance.now(),STEPS=['① Gray 프레임 읽기 · 디코딩(같은 프레임은 한 번)','② 원 안 픽셀 평균(반지름 0.5 px 단계마다 기억)'];
  BIG.stop=false;let done=0,bad=0,cur='';const cancel=()=>{BIG.stop=true};
  const pr=throttle(()=>busy({title:'흑백 GL 측정',steps:STEPS,step:0,done,total,unit:'Defect',files:`Gray 프레임 ${F.length.toLocaleString()}장 · 못 잰 것 ${bad}`,detail:cur,cancel}),80);
  busy({title:'흑백 GL 측정',steps:STEPS,step:0,done:0,total,unit:'Defect',files:'',detail:'',cancel,reset:true});
  try{for(let j=0;j<F.length;j++){if(BIG.stop)break;const f=F[j];cur=`${f.s.slotName||''} / ${cleanName(f.file)}`;pr();
      if(F[j+1])cgBitmap(F[j+1].s,F[j+1].file);   // 다음 프레임 미리 읽기
      const b=await cgBitmap(f.s,f.file);
      for(const {p,hit} of f.ps){if(b){p.glp=glProfile(b,hit);p.glv=glMean(p);p.glErr=null}else{p.glErr='흑백 사진 못 읽음: '+cleanName(f.file);bad++}done++}
      pr();if(j%8===7)await nextPaint()}}
  finally{busy(null)}
  $('#glSt').textContent=`${BIG.stop?'중지 — ':''}최종 목록 ☑ 측정 ${done.toLocaleString()}/${total.toLocaleString()}개 · 못 잰 것 ${bad} · ${((performance.now()-t0)/1000).toFixed(1)}초`;
  if(!GLC.sort)GLC.sort='gl-d';c5Refresh(true)}
// ── 측정 원 그리기 창(소유자 "PPT 도형 그리기처럼 — 가: Defect 가운데에서 바깥으로 끌기"): 원본 픽셀을 각지게 크게, 원 안 픽셀을 칠함, 지금 Defect 의 평균 · 픽셀 수를 바로 보여 줌
const GLD={p:null,b:null,hit:null,prof:null,r:5.5,z:8,drag:false,list:[],i:0,tok:0};
/** 예시 후보 = 5-3 목록에서 흑백 사진이 있는 Defect, 처음 = 지금 고른 줄(없으면 맨 앞). 사진 양옆 ‹ › · ← → = 다른 예시(Para v14.1.7). */
async function glDlgOpen(){const L=C5.items.filter(p=>p&&glCan(p));if(!L.length)return alert('흑백 사진이 있는 Defect 가 목록에 없습니다. 5-3 목록에서 Color·Gray 매칭 완료 · Gray 만 Defect 를 고르십시오.');
  Object.assign(GLD,{list:L,r:GLC.r,drag:false,z:+$('#glZ').value||8});
  if(!await glDlgShow(Math.max(0,L.indexOf(C5.items[VC.sel])),1))return alert('예시로 쓸 흑백 사진을 읽지 못했습니다.');
  $('#glDlg').hidden=false;glDlgDraw();$('#glCv').focus()}
/** 예시 사진: 후보 i 부터 dir(1 = 다음, −1 = 이전) 쪽으로 읽을 수 있는 첫 사진(끝에서 처음으로 돌아감, 최대 20개 건너뜀). 반지름 · 확대는 그대로. */
async function glDlgShow(i,dir){const L=GLD.list,n=L.length,tk=++GLD.tok;
  for(let k=0;k<Math.min(n,20);k++){const j=((i+dir*k)%n+n)%n,p=L[j],r=p.r||cgOf(p.s,p.i);if(!r.hit)continue;
    const b=await cgBitmap(p.s,r.hit.frame.file);if(tk!==GLD.tok)return false;if(!b)continue;
    Object.assign(GLD,{i:j,p,b,hit:r.hit,prof:p.glp||glProfile(b,r.hit)});
    $('#glDSrc').textContent=`예시: ${p.s.lotName||''} · ${p.s.slotName||''} · 5-1 #${p.k+1} · ${cleanName(r.hit.frame.file)} (원본 픽셀)`;
    $('#glDPos').textContent=n>1?`예시 사진 ${j+1} / ${n} · ‹ › 또는 ← → 로 바꾸기`:'예시 사진 1 / 1';$('#glPrev').disabled=$('#glNext').disabled=n<2;return true}
  return false}
async function glDlgStep(d){if(!GLD.b||GLD.list.length<2)return;if(await glDlgShow(GLD.i+d,d))glDlgDraw()}
function glDlgDraw(){const cv=$('#glCv'),c=cv.getContext('2d'),W=cv.width,z=GLD.z,b=GLD.b,P=GLD.prof,cx=P.cx,cy=P.cy,vw=W/z,ox=cx-vw/2,oy=cy-vw/2,r=GLD.r;
  c.fillStyle='#000';c.fillRect(0,0,W,W);c.imageSmoothingEnabled=false;
  const sx=Math.max(0,Math.floor(ox)),sy=Math.max(0,Math.floor(oy)),ex=Math.min(b.width,Math.ceil(ox+vw)),ey=Math.min(b.height,Math.ceil(oy+vw));
  if(ex>sx&&ey>sy)c.drawImage(b,sx,sy,ex-sx,ey-sy,(sx-ox)*z,(sy-oy)*z,(ex-sx)*z,(ey-sy)*z);
  c.fillStyle='rgba(34,211,238,.38)';const R=Math.ceil(r)+1;   // 원 안 픽셀(픽셀 가운데가 원 안) — 재는 규칙과 같음
  for(let y=Math.floor(cy-R);y<=Math.ceil(cy+R);y++)for(let x=Math.floor(cx-R);x<=Math.ceil(cx+R);x++){if(x<0||y<0||x>=b.width||y>=b.height)continue;const dx=x+.5-cx,dy=y+.5-cy;if(Math.ceil(Math.sqrt(dx*dx+dy*dy)*2-1e-9)<=Math.round(r*2)||(dx*dx+dy*dy===0))c.fillRect((x-ox)*z,(y-oy)*z,z,z)}
  if(z>=8){c.strokeStyle='rgba(255,255,255,.13)';c.lineWidth=1;c.beginPath();for(let x=Math.ceil(ox);x<=ox+vw;x++){const X=Math.round((x-ox)*z)+.5;c.moveTo(X,0);c.lineTo(X,W)}for(let y=Math.ceil(oy);y<=oy+vw;y++){const Y=Math.round((y-oy)*z)+.5;c.moveTo(0,Y);c.lineTo(W,Y)}c.stroke()}
  c.strokeStyle='#22d3ee';c.lineWidth=2;c.beginPath();c.arc(W/2,W/2,r*z,0,Math.PI*2);c.stroke();
  c.strokeStyle='#ffd23f';c.lineWidth=2;c.beginPath();c.moveTo(W/2-8,W/2);c.lineTo(W/2+8,W/2);c.moveTo(W/2,W/2-8);c.lineTo(W/2,W/2+8);c.stroke();
  const k=glK(r),n=P.N[k],m=n?P.S[k]/n:null;$('#glDR').value=r;
  $('#glDN').textContent=`원 안 ${n.toLocaleString()}픽셀 · 이 Defect 평균 GL ${m==null?'-':m.toFixed(1)}`+(r*z>W/2?' · 원이 화면보다 큼 — 확대를 줄이십시오':'')}
function glDlgAt(e){const cv=$('#glCv'),q=cv.getBoundingClientRect(),k=cv.width/q.width,mx=(e.clientX-q.left)*k,my=(e.clientY-q.top)*k,d=Math.hypot(mx-cv.width/2,my-cv.height/2)/GLD.z;
  GLD.r=Math.max(.5,Math.min(GL_MAX,Math.round(d*2)/2));glDlgDraw()}
function glDlgClose(ok){if(ok)glSetR(GLD.r);$('#glDlg').hidden=true;GLD.b=null;try{$('#c5list').focus()}catch(e){}}
// ── Step 5 이동 · 단추 ────────────────────────────────────────────────
function b5tabs(){const b=$$('[data-b5]');b[1].disabled=!BIG.scans.length;b[2].disabled=!c5Pool().length;b.forEach(x=>x.setAttribute('aria-pressed',+x.dataset.b5===BIG.stage))}
function b5go(n){BIG.stage=n;[1,2,3].forEach(k=>$('#b5p'+k).hidden=k!==n);$(`[data-b5flt="${n}"]`).after($('#bigFlt'));$('#bigFlt').setAttribute('aria-label',`5-${n} 필터`);b5tabs();   // 필터 카드 한 벌이 지금 단계로 따라감(값 그대로)
  if(n===1){bigLots();bigRefresh();$('#bigList').focus()}else if(n===2){b5Refresh();$('#b5list').focus()}
  else{b5Refresh();const P=c5Pool();const on=c5StOn();if(!P.some(p=>p.st!=='skip'&&on.has(p.st))&&P.some(p=>p.st!=='skip')){const el=document.querySelector('#c5stF [data-st5="none"]');if(!on.has('none')&&P.some(p=>p.st==='none')){el.checked=true;C5.note='보이는 Defect 가 없어 [둘 다 없음]을 켰습니다.'}}
    c5Refresh();$('#c5list').focus()}}
const curVT=()=>BIG.stage===1?VA:BIG.stage===2?VB:(C5.mode==='one'?VC:null);
$$('[data-b5]').forEach(b=>b.onclick=()=>b5go(+b.dataset.b5));
$('#bigFltIn').innerHTML=fltRngHtml();umHeads();$('#bigFltRcp').innerHTML=fltRcpHtml(false);$('#bigFltZn').innerHTML=fltZnHtml(false);$('#bigFltSort').innerHTML=fltSortHtml(false);$('#bigFltClr').outerHTML=fltClrHtml();   // v14.1.5: 줄마다 따로
fltBind($('#bigFlt'),()=>{const v=$('#bigFlt [data-f="sort"]').value,[sk]=BIG.sort?BIG.sort.split('-'):[''];if(v||['c','a','w','l','r',''].includes(sk))BIG.sort=v;bigRefresh()});
$('#bigFlt [data-f="sort"]').value=BIG.sort;
$$('#bigLot,#bigSlot').forEach(el=>el.addEventListener('change',bigRefresh));
$('#bigCls').addEventListener('change',e=>{const d=e.target.dataset||{},g=d.cls1!=null?1:d.cls2!=null?2:0;if(!g)return;const off=BIG['clsOff'+g],k=d['cls'+g];if(e.target.checked)off.delete(k);else off.add(k);bigLots();bigRefresh()});
$('#bigCls').addEventListener('click',e=>{const g=e.target.dataset&&e.target.dataset.clsall;if(!g)return;const off=BIG['clsOff'+g];if(off.size)off.clear();else $$(`#bigCls [data-cls${g}]`).forEach(x=>off.add(x.dataset['cls'+g]));bigLots();bigRefresh()});
$('#bigLotOff').addEventListener('change',e=>{const k=e.target.dataset&&e.target.dataset.lotoff;if(k==null)return;if(e.target.checked)BIG.lotOff.delete(k);else BIG.lotOff.add(k);bigLots();bigRefresh()});
$('#bigLotOff').addEventListener('click',e=>{if(!(e.target.dataset&&e.target.dataset.lotall))return;if(BIG.lotOff.size)BIG.lotOff.clear();else $$('#bigLotOff [data-lotoff]').forEach(x=>BIG.lotOff.add(x.dataset.lotoff));bigLots();bigRefresh()});
$('#bigTbl').addEventListener('click',e=>{const p=e.target.dataset.bigdel;if(p==null)return;BIG.scans=BIG.scans.filter(w=>w.lotPath!==p);BIG.pairs=null;bigLots();bigRefresh();b5tabs()});
$('#bigClear').onclick=()=>{BIG.scans=[];BIG.pairs=null;THUMB.clear();bigMsg([]);bigLots();bigRefresh();b5tabs()};
$('#bigCsv').onclick=async()=>{const parts=bigCsv();if(parts)bigMsg([['ok','목록 CSV '+(await saveCsv(parts,`Defect_목록_${stamp()}.csv`,true)||'저장 취소')]])};
$('#toB2').onclick=()=>b5Start(true);
$('#b5pair').onclick=()=>b5Start(false);
$('#b5csv').onclick=async()=>{const r=await saveCsv(pairCsv(B5.items.filter(p=>p.on2)),csvName(),true);if(r)$('#b5pairSt').insertAdjacentHTML('beforeend',`<div class="msg ok">CSV ${esc(r)}</div>`)};
$('#b5show').addEventListener('change',b5Refresh);
$('#toB1').onclick=()=>b5go(1);$('#toB3').onclick=()=>b5go(3);   // v14.1.6: 5-3 의 [← 5-2] 단추는 없앰(소유자 — 단계 탭을 누르면 됨)
$('#c5stF').addEventListener('change',()=>c5Refresh());
lsBind('c5Ls',{onQ:T=>{C5.q=T;c5Refresh()}});document.querySelectorAll('[data-ls="def"]').forEach(x=>x.checked=LS.def);
$$('[data-v5]').forEach(b=>b.onclick=()=>{C5.mode=b.dataset.v5;c5Refresh(true)});
$('#c5prev').onclick=()=>{C5.page--;c5Grid()};$('#c5next').onclick=()=>{C5.page++;c5Grid()};
$('#c5grid').addEventListener('click',e=>{const el=e.target.closest('.g5');if(!el)return;C5.mode='one';VC.sel=+el.dataset.k;c5Refresh(true);vtGo(VC,VC.sel,true)});
$('#b5prep').onclick=()=>c5PrepAll();
$('#c5pickAll').onclick=()=>{C5.items.forEach(p=>{if(p.st!=='skip')p.pick=true});pickChanged()};
$('#c5pickNone').onclick=()=>{C5.items.forEach(p=>p.pick=false);pickChanged()};   // v14.1.8: 보이는 줄만(안 보이는 줄은 그대로)
$('#c5save').onclick=()=>c5SaveXlsx();$('#c5saveZip').onclick=()=>c5SaveZip();$('#c5xlOrig').checked=XLO.on;$('#c5xlOrig').onchange=e=>xlOrigSet(e.target.checked);$('#c5saveCsv').onclick=()=>c5SaveCsv();
// rev6 흑백 GL(원)
glRInfo();$('#glR').addEventListener('change',e=>glSetR(e.target.value));$('#glShow').checked=GLC.show;$('#glShow').addEventListener('change',e=>glShowSet(e.target.checked));$('#glRun').onclick=()=>glRun();$('#glSet').onclick=()=>glDlgOpen();
for(const id of ['glLo','glHi'])$('#'+id).addEventListener('input',e=>{GLC[id==='glLo'?'lo':'hi']=+e.target.value;c5Refresh(true)});   // 끄는 동안 바로 거르고 정렬
$('#glSort').addEventListener('change',e=>{GLC.sort=e.target.value;c5Refresh()});
for(const [id,k] of [['glLoN','lo'],['glHiN','hi']])$('#'+id).addEventListener('input',e=>{const v=Math.round(+e.target.value);if(e.target.value!==''&&v>=0&&v<=255){GLC[k]=v;c5Refresh(true)}});
$('#glRngAll').onclick=()=>{GLC.lo=0;GLC.hi=255;$('#glLo').value=0;$('#glHi').value=255;c5Refresh(true)};
{const cv=$('#glCv');cv.tabIndex=0;
  cv.addEventListener('pointerdown',e=>{GLD.drag=true;try{cv.setPointerCapture(e.pointerId)}catch(x){}glDlgAt(e);e.preventDefault()});
  cv.addEventListener('pointermove',e=>{if(GLD.drag)glDlgAt(e)});cv.addEventListener('pointerup',()=>{GLD.drag=false});cv.addEventListener('pointercancel',()=>{GLD.drag=false});
  cv.addEventListener('wheel',e=>{e.preventDefault();GLD.r=Math.max(.5,Math.min(GL_MAX,GLD.r+(e.deltaY<0?.5:-.5)));glDlgDraw()},{passive:false});
  $('#glZ').addEventListener('change',e=>{GLD.z=+e.target.value;if(GLD.b)glDlgDraw()});
  $('#glDR').addEventListener('input',e=>{const v=+e.target.value;if(v>=.5&&v<=GL_MAX){GLD.r=Math.round(v*2)/2;glDlgDraw()}});
  $('#glDOk').onclick=()=>glDlgClose(true);$('#glDNo').onclick=()=>glDlgClose(false);
  $('#glPrev').onclick=()=>glDlgStep(-1);$('#glNext').onclick=()=>glDlgStep(1);
  $('#glDlg').addEventListener('keydown',e=>{const tg=e.target.tagName;
    if(e.key==='Escape'){glDlgClose(false);e.preventDefault()}else if(e.key==='Enter'&&tg!=='BUTTON'){glDlgClose(true);e.preventDefault()}
    else if((e.key==='ArrowLeft'||e.key==='ArrowRight')&&tg!=='INPUT'&&tg!=='SELECT'){glDlgStep(e.key==='ArrowLeft'?-1:1);e.preventDefault()}e.stopPropagation()})}
$('#c5win').onclick=()=>photoWin(VC,C5.items);$('#b5win').onclick=()=>photoWin(VB,B5.items);
$('#c5up').onclick=()=>vtGo(VC,VC.sel-1);$('#c5down').onclick=()=>vtGo(VC,VC.sel+1);
// 원본 폴더 경로(PC): 5-1 · 5-2 두 칸이 같은 값, 이 PC 에 기억. 바꾸면 사진 새 창 · 5-3 · 결과 목록의 전체 경로를 바로 다시 그림.
try{$('#bigBase').value=$('#bigBase1').value=localStorage.getItem('cw.bigBase')||''}catch(e){}
for(const id of ['#bigBase','#bigBase1'])$(id).addEventListener('change',e=>{const v=e.target.value.trim();$('#bigBase').value=$('#bigBase1').value=v;try{localStorage.setItem('cw.bigBase',v)}catch(x){}
  if(BIG.stage===2&&BIG.pairs)vtPaint(VB);if(BIG.stage===3)c5Refresh(true);if(PW.w&&!PW.w.closed)photoWinShow()});
/** 설정(Step 2 의 허용오차 · Wafer · Crop 크기 · Ring 폭)이 바뀌면: 5-1 목록 다시 그림, 5-3 사진(GL) 다시 계산. rev5: 짝(매칭)에 쓰는 설정은 없다. */
function bigOptsChanged(){S.o=S.cmp?S.o:opts();THUMB.clear();
  if(!$('#step5').classList.contains('on'))return;if(BIG.stage===1&&BIG.view)vtPaint(VA);else if(BIG.stage===3)c5Refresh(true)}
// 폴더 고르기: 폴더 핸들(showDirectoryPicker, 읽기 전용)을 쓸 수 있으면 Slot 안 사진 목록을 만들지 않아 훨씬 빠르다. 없으면 <input webkitdirectory>(브라우저가 사진까지 목록을 만든다 — 사진 내용은 읽지 않는다).
/** #66: 폴더 핸들로 .ini 가 막힌 브라우저 → 이 PC 에서는 앞으로 파일 목록 방식(Step 1 과 같음). 아직 누른 직후면 바로 폴더 고르기 창을 연다. */
function bigToList(why){busy(null);try{localStorage.setItem('cw.bigList','1')}catch(e){}BIG.useList=true;
  // #72: 소유자가 이 알림을 '못 찾음' 버그로 읽었다 — 파일은 그대로 있고, 빠른 방식이 .ini 를 못 여는 것뿐. 읽는 방식만 바꾸고 같은 폴더를 다시 고르면 된다고 쓴다.
  bigMsg([['warn',`안내: 파일이 없는 것이 아닙니다. 이 브라우저(Edge · Chrome)는 빠른 폴더 읽기(폴더 핸들)로 .ini 파일(ColorImageGrabingInfo.ini · ProductInfo.ini 등)을 열지 못하게 합니다(${why}). 그래서 이번에는 아무것도 읽지 않았습니다.`],
    ['warn','읽는 방식을 Step 1 ~ 4 와 같은 파일 목록 방식으로 바꿨습니다(이 PC 에 기억 — 다음부터는 이 알림이 나오지 않습니다). 아래 [같은 폴더 다시 고르기]를 누르고 같은 폴더를 고르십시오. 큰 폴더는 브라우저가 파일 목록을 만드는 데 시간이 더 걸립니다.']]);
  const b=document.createElement('button');b.className='pri';b.id='bigRepick';b.textContent='같은 폴더 다시 고르기';b.onclick=()=>$('#bigAdd').click();$('#bigMsg').appendChild(b);
  try{if(navigator.userActivation&&navigator.userActivation.isActive)$('#bigAdd').click()}catch(e){}}
/** #72: 폴더를 고른 직후 고른 폴더에서 .ini 이름을 한 번 묻는다 — 이 Chrome 이 막으면 이름 검사에서 바로 TypeError(파일이 있든 없든). 폴더 전체를 훑기 전에 알아본다. */
/** #72 후속(소유자 "Edge 로 열어 다시 검토"): 소유자 회사 PC 는 Edge — 그 Edge 가 폴더 핸들로 .ini 를 막았다(#66 알림). Edge 면 처음부터 파일 목록 방식(알림 · 다시 고르기 없음). */
function isEdge(){if(PARA)return false;try{const b=navigator.userAgentData&&navigator.userAgentData.brands;if(b&&b.some(x=>/edge/i.test(x.brand)))return true}catch(e){}return /\bEdg\//.test(navigator.userAgent||'')}
async function fsaProbe(h){try{await h.getFileHandle(CG.CI)}catch(e){if(fsaBlocked(e))return `${CG.CI}: ${e.message}`}return ''}
$('#bigAdd').onclick=async()=>{
  if(PARA){let R;try{R=await PARA.pick()}catch(e){bigMsg([['err','폴더를 고르지 못했습니다: '+(e.message||e)]]);return}if(R)await bigPickHandle(R.handle);return}   // v14: 엔진이 고른 폴더를 직접 읽음
  if(window.showDirectoryPicker&&!BIG.useList&&!useList()&&!isEdge()){let h;try{h=await window.showDirectoryPicker({mode:'read'})}catch(e){if(e&&e.name==='AbortError')return;h=null}
    if(h){const blk=await fsaProbe(h);if(blk){bigToList(blk);return}await bigPickHandle(h);return}}
  busy({title:'폴더 고르는 중',indet:true,count:'…',files:'폴더를 고르면 브라우저가 파일 목록을 만듭니다(이 브라우저는 빠른 길을 쓸 수 없어 사진 이름까지 모두 셉니다). 큰 폴더는 시간이 걸립니다.',detail:'고르기를 취소했으면 [닫기]를 누르십시오.',close:true,reset:true});$('#bigInput').click()};
$('#bigInput').addEventListener('cancel',()=>busy(null));
$('#bigInput').onchange=async e=>{const fs=[...e.target.files];e.target.value='';if(!fs.length){busy(null);return}
  busy({title:'5-1 Contrast 모으기',steps:STEPS_A,step:0,indet:true,count:`파일 ${fs.length.toLocaleString()}개`,files:'Slot 폴더(Surface.flt) 찾는 중…'});await nextPaint();
  await addBigEntries(fs.map(f=>({path:f.webkitRelativePath||f.name,file:f})))};

// ════════════════════════════════════════════════════════════════════════
// 14. 마법사 이동 · 테마
// ════════════════════════════════════════════════════════════════════════
function go(n){if(n>=3&&n<5&&!S.cmp&&!runCompare())n=2;$$('section.step').forEach(s=>s.classList.toggle('on',s.id==='step'+n));
  $$('nav button[data-step]').forEach(b=>b.toggleAttribute('aria-current',b.dataset.step==n)&&b.setAttribute('aria-current','step'));
  if(n==3){if(S.venn&&S.venn.shown)refresh3()}if(n==4){refresh4();P4.el('List').focus()}if(n==5)b5go(BIG.stage||1)}
$$('nav button[data-step]').forEach(b=>b.onclick=()=>go(+b.dataset.step));$('#to2').onclick=()=>go(2);
['#tol','#cropSz','#ringW'].forEach(s=>$(s).addEventListener('change',()=>{grayMemo.clear();if(S.cmp)runCompare();else S.o=opts();bigOptsChanged()}));
$('#themeBtn').onclick=()=>{const r=document.documentElement,dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme:dark)').matches;
  r.dataset.theme=dark?'light':'dark';try{localStorage.setItem('cw.theme',r.dataset.theme)}catch(e){}repaintAll()};
try{const t=localStorage.getItem('cw.theme');if(t)document.documentElement.dataset.theme=t}catch(e){}
renderScans();
try{$('#inWin').checked=inWinPref()}catch(e){}$('#inWin').addEventListener('change',e=>{try{localStorage.setItem('cw.inWin',e.target.checked?'1':'0')}catch(x){}});
if(PARA){document.body.classList.add('para');   // v14 Defect 분석 탭: [대규모 Defect 분석] = Step 5 만, [다이어그램 분석] = Step 1 ~ 4 만
  if(PARA.mode==='big'){$$('nav button[data-step]').forEach(b=>{if(b.dataset.step!=='5')b.hidden=true});go(5)}
  else if(PARA.mode==='diagram')$('nav button[data-step="5"]').hidden=true}
// 시험용(Playwright): 순수 함수와 파일 주입
window.__cw={PARA,DEFECT_DESC,codeName,PCOLS,panelPh,panelCls,panelRow,pFin,baseSaveCsv,baseSaveXlsx,baseSaveZip,baseGlRun,baseFlRow,baseXlRow,panelGlRange,winOpen,ovWin,OVW,FL_HEAD,flRow,c5SaveCsv,isEdge,rcp5,rcpSum,rv5Cells,nextPaint,yieldMC,retryRead,transientErr,BUSY,rvInfo,rvText,rcpName,typeName,parseEqCls,parseZones,mapFrame,mapDie,mapGeom,flatTag,parseW2T,paintMap,ptDieKeys,glApply,GLC,GLD,glProfile,glMean,glCount,glRun,glTargets,glSetR,glDlgOpen,glDlgClose,glDlgShow,glDlgStep,PWL,pwCenter,pickToggle,pickList,c5SaveXlsx,c5SaveZip,origBytes,zipName,cropPng,xlsxBlob,XLO,xlOrigSet,xlOrig,xlCols,xlRow,zipStore,crc32,bigDef,dirList,dirFind,cgMiss,parseManRe,clsFirst,clsName,clsText,pcPath,CG,cgColors,cgFault,cgRecipe,cgIndex,cgFrames,cgTfKey,cgTfFor,cgMap,cgCropSize,geoLoad,geoLoadFd,geoHit,geoChoose,geoPlan,geoRect,geoSize,geoPix,geoWhy,geoModel,tfSize,tfPix,parseRecipesInfo,cgFrameData,geoFramesFromNames,cgColorsFromNames,dirFromFiles,cgPlan,cgLink,cgOf,cgShort,cgLoad,cgDirH,cgDirsFromList,cgCropCanvas,cgFrameCanvas,cgDefBox,cgDefHalf,pwSet,pwFit,PZ_MAX,cgBitmap,pyRound,pyFloat,photoWin,PW,opts,colsDiff,colsFromDefs,findLikeStep1,fullLoad,b5SlotTbl,readText,colorsFromNames,colorModel,colorWhy,b5Start,saveCsv,planUnits,unitOfPath,BIG,C5,VA,VB,VC,THUMB,addBigEntries,bigPickHandle,walkFast,bigRefresh,bigBuild,bigRankOf,b5Refresh,B5,fltSpan,bigRcpFill,bigFacetFill,bigCsv,pairCsv,b5Pair,b5go,c5PrepAll,parseFltCols,applyPanel,busy,lotsOf,setUnit,matchBySlot,renderScans,setPanel,buildVenn,regLabel,refresh3,refresh4,pickRegion,popMap,PANELS,vennMaskAt,selectPair,stLabel,viewLabel,parseDieLoc,parseMd,fltLayout,fltRec,fltRecErr,parseFlt,parseIni,parseColors,parseFrames,parseTransform,parseProduct,dieOf,surfaceCount,matchSets,grayOf,linkColor,measureGL,addEntries,csvText,state:S,go,REC};

};
