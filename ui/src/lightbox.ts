import {artifactURL,fileName,el} from './api';

// In-page viewer for renders and logs. Viewing never downloads; Download is an explicit action.
export type Item={path:string;title:string;subtitle?:string;kind:'image'|'text'};

const dialog=el('dialog',{id:'lightbox',class:'lightbox'});
const title=el('strong'),subtitle=el('span',{class:'muted'}),counter=el('span',{class:'muted',id:'lightbox-counter'});
const open=el('a',{class:'button ghost',target:'_blank',rel:'noopener',textContent:'Open in tab'});
const download=el('a',{class:'button',id:'lightbox-download',textContent:'Download'});
const close=el('button',{class:'ghost icon',title:'Close (Esc)',ariaLabel:'Close',textContent:'✕'});
const prev=el('button',{class:'nav prev',title:'Previous (←)',ariaLabel:'Previous',textContent:'‹'}),next=el('button',{class:'nav next',title:'Next (→)',ariaLabel:'Next',textContent:'›'});
const stage=el('div',{class:'stage'}),image=el('img',{alt:''}),text=el('pre',{class:'log'});
stage.append(image,text);
dialog.append(el('header',{},el('div',{class:'lightbox-title'},title,subtitle),counter,el('div',{class:'actions'},open,download,close)),stage,prev,next,
  el('footer',{class:'muted'},'Scroll to zoom · drag to pan · double-click to reset · ← → to browse'));
document.body.append(dialog);

let items:Item[]=[],index=0,zoom=1,pan={x:0,y:0},drag:{x:number;y:number}|undefined,token=0;
const transform=()=>{image.style.transform=`translate(${pan.x}px,${pan.y}px) scale(${zoom})`};
const reset=()=>{zoom=1;pan={x:0,y:0};transform()};

async function show(){
  const item=items[index];const t=++token;reset();
  title.textContent=item.title;subtitle.textContent=item.subtitle??'';counter.textContent=items.length>1?`${index+1} / ${items.length}`:'';
  open.href=artifactURL(item.path,true);download.href=artifactURL(item.path);download.download=fileName(item.path);
  prev.hidden=next.hidden=items.length<2;image.hidden=item.kind!=='image';text.hidden=item.kind!=='text';
  if(item.kind==='image'){image.src=open.href;image.alt=item.title}
  else{text.textContent='Loading…';const response=await fetch(open.href);const body=response.ok?await response.text():'Could not load this file.';if(t===token)text.textContent=body||'(empty log)'}
}
export function openLightbox(list:Item[],start=0){items=list;index=start;void show();if(!dialog.open)dialog.showModal()}
const step=(d:number)=>{if(items.length<2)return;index=(index+d+items.length)%items.length;void show()};

prev.onclick=()=>step(-1);next.onclick=()=>step(1);close.onclick=()=>dialog.close();
dialog.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')step(-1);else if(e.key==='ArrowRight')step(1)});
dialog.addEventListener('click',e=>{if(e.target===dialog||e.target===stage)dialog.close()});
stage.addEventListener('wheel',e=>{if(image.hidden)return;e.preventDefault();zoom=Math.min(12,Math.max(.5,zoom*Math.exp(-e.deltaY*.0015)));transform()},{passive:false});
image.addEventListener('pointerdown',e=>{drag={x:e.clientX-pan.x,y:e.clientY-pan.y};image.setPointerCapture(e.pointerId);e.preventDefault()});
image.addEventListener('pointermove',e=>{if(drag){pan={x:e.clientX-drag.x,y:e.clientY-drag.y};transform()}});
image.addEventListener('pointerup',()=>drag=undefined);image.addEventListener('dblclick',reset);
image.addEventListener('click',e=>e.stopPropagation());
