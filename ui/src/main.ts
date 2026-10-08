import * as THREE from 'three';
import './style.css';
import {api,artifactURL,clearCache,el,fileName,find,loadParts,natural,runTime,session,shortId,startSession,type Context,type Filament,type Kit,type Loaded,type Project,type Run} from './api';
import {addGround,makePane,Viewer,type Pane} from './scene';
import {baseName,renderParts,type Diff,type PartsState,type Row} from './parts';
import {renderRuns} from './runs';
import {openLightbox,type Item} from './lightbox';

document.querySelector('#app')!.innerHTML=`
<aside><a class="brand" href="/">◈ <span>GeometryForge<small>LOCAL WORKSHOP</small></span></a><div class="section-title">PROJECTS <button id="add" class="icon" title="Register or create project">＋</button></div><div id="projects"></div><label class="archived"><input id="show-archived" type="checkbox"> Show archived</label><footer>Built in your agent.<br>Inspected here.</footer></aside>
<main>
<header class="top"><div class="title-block"><div class="title-line"><h1 id="title">Choose a project</h1><span id="banner" class="pill banner">Register a project to inspect its runs.</span></div><p id="path">A local library of geometry and the evidence behind it.</p></div>
<div class="actions"><button id="copy" class="primary" title="Copy a reference your agent can resume from">Copy agent reference</button><details class="menu"><summary class="button icon" title="More project actions" aria-label="More project actions">⋯</summary><div class="menu-items"><button id="rename">Rename project</button><button id="archive">Archive project</button></div></details></div></header>
<div class="workspace">
<section class="canvas-panel">
<div class="toolbar"><div id="run-chip" class="run-chip"></div><button id="safe" class="small ghost" title="Open the safe point run">↺ Safe point</button><nav id="crumbs" class="crumbs" aria-label="View"></nav><span class="spacer"></span>
<div id="colour-mode" class="segmented" hidden title="Colour by part or by planned filament"><button data-colour="part" class="active">Part colours</button><button data-colour="filament">Filaments</button></div>
<div id="pose" class="segmented" hidden><button data-pose="assembly" class="active">Assembly pose</button><button data-pose="print">Print pose</button></div>
<div id="compare-mode" class="segmented" hidden><button data-mode="split" class="active">Side by side</button><button data-mode="overlay">Overlay</button></div>
<select id="backend" aria-label="Backend"><option>blender</option><option>houdini</option></select><button id="fit" class="small" title="Fit view (F)">Fit</button></div>
<div id="diff" class="diff" hidden></div>
<div id="viewport"><div id="overlays"></div><div class="empty" id="empty">Your geometry will appear here.<br><small>Select a run to explore its parts.</small></div><div id="progress" hidden></div><div id="hover" hidden></div><span id="dimensions"></span></div>
<div class="hint">Click a part to select · Ctrl/Shift-click to add · double-click or <kbd>I</kbd> to isolate · <kbd>H</kbd> hide · <kbd>Alt</kbd>+<kbd>H</kbd> show all · <kbd>F</kbd> fit · <kbd>Esc</kbd> back</div>
</section>
<section class="side">
<div class="tabs" role="tablist"><button id="tab-parts" role="tab" class="active" aria-selected="true">Parts <span id="parts-count" class="count"></span></button><button id="tab-runs" role="tab" aria-selected="false">Runs <span id="runs-count" class="count"></span></button></div>
<div id="panel-parts" class="panel"><div class="parts-tools"><input id="part-filter" type="search" placeholder="Filter parts…" aria-label="Filter parts"><div class="segmented small-seg"><button id="show-all" title="Show all parts">All</button><button id="show-none" title="Hide all parts">None</button><button id="show-invert" title="Invert visibility">Invert</button></div></div><div id="selection-bar" class="selection-bar"></div><div id="parts"></div></div>
<div id="panel-runs" class="panel" hidden><p class="muted pad">Click a run to open it as <b>A</b>. <b>Compare</b> puts another run beside it as <b>B</b>.</p><div id="runs"></div></div>
</section></div>
<section id="details" class="card details" hidden></section>
<section class="card renders-card"><h2>Renders <span id="renders-note" class="muted"></span></h2><div id="renders" class="renders"></div></section>
<section class="evidence"><div class="card"><h2>Validation evidence</h2><div id="checks">No run selected.</div><pre id="errors"></pre></div><div class="card"><h2>Files &amp; logs <span id="files-note" class="muted"></span></h2><div id="artifacts"></div></div></section>
</main>
<dialog id="dialog"><form id="project-form"><h2>Add a project</h2><label>Project folder<input id="folder" required placeholder="E:\\Models\\My project"></label><label><input type="checkbox" id="create"> Create an empty project in this folder</label><p>Modeling and generation stay in your agent.</p><div class="actions"><button type="button" id="cancel">Cancel</button><button type="submit" class="primary">Add project</button></div></form></dialog><div id="toast" role="status"></div>`;

const $=(id:string)=>document.getElementById(id)!;
const viewer=new Viewer($('viewport'));
let projects:Record<string,Project>={},runs:Run[]=[],ctx:Context|undefined,revision=0;
let runA:Run|undefined,runB:Run|undefined,loadedA=new Map<string,Loaded>(),loadedB:Map<string,Loaded>|undefined;
let colourMode:'part'|'filament'='part',pose:'assembly'|'print'='assembly',mode:'split'|'overlay'='split',hovered:string|undefined,assemblyCamera:ReturnType<Viewer['saveCamera']>|undefined;
const state:PartsState={selection:new Set(),hidden:new Set(),filter:'',collapsed:new Set(),isolated:null};
const backendName=()=>($('backend') as HTMLSelectElement).value;
const sha=(l:Loaded|undefined)=>find(l?.part,'/assembly.json')?.sha256;

function toast(message:string){$('toast').textContent=message;setTimeout(()=>$('toast').textContent='',5000)}
function guarded(fn:()=>Promise<unknown>){return ()=>void fn().catch(e=>toast(String(e)))}

// ---------- 3D scene construction ----------
function partColor(name:string){let h=0;for(const c of baseName(name))h=(h*31+c.charCodeAt(0))>>>0;return new THREE.Color().setHSL(.43+(h%5)*.055,.32,.62)}
const ghostMaterial=()=>new THREE.MeshStandardMaterial({color:0xff9a4d,transparent:true,opacity:.32,depthWrite:false,roughness:.8,emissive:0x5a2400});

// Filament colours come from the run's own plan (decisions.print.filaments), so old runs keep their colours.
const SLOT_FALLBACK=['#cfd8dc','#37474f','#ff8a65','#4fc3f7','#aed581','#ba68c8','#ffd54f','#e57373'];
const filamentPlan=(run?:Run)=>run?.decisions?.print?.filaments??[];
function filamentColour(run:Run|undefined,slot:number){return new THREE.Color(filamentPlan(run).find(f=>f.slot===slot)?.colour??SLOT_FALLBACK[(slot-1)%SLOT_FALLBACK.length])}

function partObject(l:Loaded,ghost=false,run?:Run){
  const holder=new THREE.Group(),body=new THREE.Group();holder.userData.part=l.name;holder.add(body);
  for(const [i,geometry] of l.geometries.entries()){const colour=colourMode==='filament'?filamentColour(run,l.filaments[i]):partColor(l.name);
    const mesh=new THREE.Mesh(geometry,ghost?ghostMaterial():new THREE.MeshStandardMaterial({color:colour,roughness:.55,metalness:.05}));
    mesh.userData.part=ghost?undefined:l.name;mesh.userData.ghost=ghost;body.add(mesh)}
  // Print pose matches the exporter: static XYZ Euler (trimesh 'sxyz'), centered in X/Y, resting on Z=0.
  if(pose==='print'&&state.isolated){const [x,y,z]=l.rotation.map(THREE.MathUtils.degToRad);body.rotation.set(x,y,z,'ZYX')}
  return holder;
}

function rebuild(refit:boolean){
  const names=state.isolated??[...loadedA.keys()];const split=!!runB&&mode==='split';
  const a=makePane(),b=split?makePane():undefined,panes=b?[a,b]:[a];
  const place=(pane:Pane,loaded:Map<string,Loaded>|undefined,run:Run|undefined,ghost=false)=>{const out=new Map<string,THREE.Group>();
    for(const n of names){const l=loaded?.get(n);if(l){const o=partObject(l,ghost,run);pane.root.add(o);out.set(n,o)}}return out};
  const objsA=place(a,loadedA,runA),objsB=b?place(b,loadedB,runB):runB&&mode==='overlay'?place(a,loadedB,runB,true):new Map<string,THREE.Group>();
  if(state.isolated){
    // A fresh scene for the selection: recentre so each part is inspected on its own ground, not at its assembly position.
    const boxOf=(o?:THREE.Object3D)=>o?new THREE.Box3().setFromObject(o,pose==='print'):new THREE.Box3();
    if(pose==='print'){let cursor=0;const gap=8,slots=names.map(n=>{const ba=boxOf(objsA.get(n)),bb=boxOf(objsB.get(n));const w=Math.max(ba.isEmpty()?0:ba.max.x-ba.min.x,bb.isEmpty()?0:bb.max.x-bb.min.x);const x=cursor+w/2;cursor+=w+gap;return x});
      const shift=(cursor-gap)/2;names.forEach((n,i)=>{for(const o of [objsA.get(n),objsB.get(n)]){if(!o)continue;const box=boxOf(o);const c=box.getCenter(new THREE.Vector3());o.position.set(slots[i]-shift-c.x,-c.y,-box.min.z)}})}
    else{const ref=new THREE.Box3();for(const n of names)ref.union(boxOf(objsA.get(n)??objsB.get(n)));const c=ref.getCenter(new THREE.Vector3());
      for(const o of [...objsA.values(),...objsB.values()])o.position.set(-c.x,-c.y,-ref.min.z)}
  }
  const bed=pose==='print'&&state.isolated?[...loadedA.values()][0]?.part.measurements?.bed_mm:undefined;
  const union=new THREE.Box3();for(const p of panes)union.union(new THREE.Box3().setFromObject(p.root));
  for(const p of panes)addGround(p,union,bed);
  viewer.setPanes(panes);applyState();if(refit)viewer.fit();renderOverlays(names,objsB);updateDimensions();
}

function applyState(){
  for(const pane of viewer.panes)for(const holder of pane.root.children){const name=holder.userData.part as string;
    holder.visible=!!state.isolated||!state.hidden.has(name);
    holder.traverse(o=>{const m=o as THREE.Mesh;if(!m.isMesh||m.userData.ghost)return;const mat=m.material as THREE.MeshStandardMaterial;
      const selected=state.selection.has(name);mat.emissive.set(selected?0x2fb894:hovered===name?0x4a6a80:0x000000);mat.emissiveIntensity=selected?.45:.35})}
}

function updateDimensions(){
  const box=new THREE.Box3();viewer.panes[0]?.root.traverse(o=>{if((o as THREE.Mesh).isMesh&&o.visible&&o.parent?.parent?.visible)box.expandByObject(o)});
  $('dimensions').textContent=box.isEmpty()?'':box.getSize(new THREE.Vector3()).toArray().map(v=>v.toFixed(1)).join(' × ')+' mm';
}

function runLabel(run:Run){return `${runTime(run.id)} · ${shortId(run.id)} · ${run.status}`}
function renderOverlays(names:string[],objsB:Map<string,THREE.Group>){
  const host=$('overlays');host.replaceChildren();host.classList.toggle('split',!!runB&&mode==='split');if(!runA)return;
  const label=(text:string,role:'a'|'b',side:'left'|'right')=>{const node=el('div',{class:`pane-label ${role} ${side}`},el('b',{textContent:role.toUpperCase()}),el('span',{textContent:text}));host.append(node);return node};
  if(!runB)return;
  if(mode==='overlay'){label(`${runLabel(runA)} — solid`,'a','left');const b=label(`${runLabel(runB)} — orange ghost`,'b','right');b.append(stopCompareButton());return}
  label(runLabel(runA),'a','left');const b=label(runLabel(runB),'b','right');b.append(stopCompareButton());
  host.append(el('div',{class:'divider'}));
  const missing=!loadedB?`No ${backendName()} output in this run.`:state.isolated&&!objsB.size?`${names.length===1?names[0]:'These parts'} ${names.length===1?"isn't":"aren't"} in this run.`:'';
  if(missing)host.append(el('div',{class:'pane-empty',textContent:missing}));
}
function stopCompareButton(){const b=el('button',{class:'icon ghost',title:'Stop comparing (Esc)',ariaLabel:'Stop comparing',textContent:'✕'});b.onclick=()=>void setCompare(undefined);return b}

// ---------- Loading runs ----------
async function loadView(refit=true){
  const rev=++revision,backend=backendName(),progress=$('progress');
  const show=(done:number,total:number)=>{if(rev!==revision)return;progress.hidden=done>=total;progress.textContent=`Loading parts ${done}/${total}`};
  const a=runA?.backends[backend],b=runB?.backends[backend];
  const [la,lb]=await Promise.all([a?loadParts(a,show):Promise.resolve(new Map<string,Loaded>()),b?loadParts(b,()=>{}):Promise.resolve(undefined)]);
  if(rev!==revision)return;progress.hidden=true;loadedA=la;loadedB=lb;
  for(const set of [state.selection,state.hidden])for(const n of [...set])if(!loadedA.has(n))set.delete(n);
  if(state.isolated){state.isolated=state.isolated.filter(n=>loadedA.has(n));if(!state.isolated.length)state.isolated=null}
  $('empty').hidden=loadedA.size>0;rebuild(refit);renderAll();
}

async function openRun(run:Run){
  runA=run;if(runB?.id===run.id)runB=undefined;
  const sel=$('backend') as HTMLSelectElement,previous=sel.value;
  sel.replaceChildren(...Object.keys(run.backends).map(b=>el('option',{value:b,textContent:b})));if(run.backends[previous])sel.value=previous;
  await loadView();
}
async function setCompare(run:Run|undefined){runB=run;await loadView(false);if(run)toast(`Comparing B ${shortId(run.id)} with A ${shortId(runA!.id)}`)}

// ---------- Panels ----------
function diffOf(name:string):Diff|undefined{if(!runB)return undefined;const a=loadedA.get(name),b=loadedB?.get(name);return !b?'onlyA':!a?'onlyB':sha(a)===sha(b)?'same':'changed'}
function renderAll(){renderPartsPanel();renderRunsPanel();renderToolbar();renderDiff();renderDetails();renderRenders();renderEvidence()}

function renderPartsPanel(){
  const rows:Row[]=[...loadedA.values()].map(l=>({name:l.name,reused:l.part.reused,diff:diffOf(l.name)}));
  if(runB&&loadedB)for(const n of loadedB.keys())if(!loadedA.has(n))rows.push({name:n,reused:false,diff:'onlyB'});
  renderParts($('parts'),rows,state,{select,setHidden,isolate});
  $('parts-count').textContent=String(loadedA.size);
  const bar=$('selection-bar'),n=state.selection.size;bar.replaceChildren();
  if(n){const names=[...state.selection].sort(natural);
    bar.append(el('span',{textContent:n===1?names[0]:`${n} selected`,title:names.join(', ')}),
      button('Isolate',()=>isolate(names),'small primary'),button('Hide',()=>setHidden(names,true),'small'),button('Clear',()=>select([],'replace'),'small ghost'))}
}
function renderRunsPanel(){renderRuns($('runs'),runs,runA,runB,ctx?.safe_point??null,{open:r=>void openRun(r).catch(e=>toast(String(e))),compare:r=>void setCompare(r).catch(e=>toast(String(e)))});$('runs-count').textContent=String(runs.length)}

function renderToolbar(){
  $('run-chip').replaceChildren(...(runA?[el('b',{textContent:'A'}),el('span',{textContent:runTime(runA.id)}),el('span',{class:'pill '+runA.status,textContent:runA.status+(runA.id===ctx?.safe_point?' · safe point':'')})]:[]));
  ($('safe') as HTMLButtonElement).hidden=!ctx?.safe_point||ctx.safe_point===runA?.id;
  const crumbs=$('crumbs');crumbs.replaceChildren();
  if(state.isolated){const iso=state.isolated;crumbs.append(button('‹ Assembly',exitIsolate,'small ghost crumb-back'),el('span',{class:'sep',textContent:'›'}),
    el('strong',{textContent:iso.length===1?iso[0]:groupLabel(iso),title:iso.join(', ')}))}
  else crumbs.append(el('strong',{textContent:'Assembly'}));
  $('pose').hidden=!state.isolated;$('compare-mode').hidden=!runB;
  $('colour-mode').hidden=!filamentPlan(runA).length&&![...loadedA.values()].some(l=>l.filaments.some(f=>f!==1));
  $('colour-mode').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.colour===colourMode));
  $('pose').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.pose===pose));
  $('compare-mode').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
}
function groupLabel(names:string[]){const bases=new Set(names.map(baseName));return bases.size===1?`${[...bases][0]} ×${names.length}`:`${names.length} parts`}

function renderDiff(){
  const host=$('diff');host.hidden=!runB;if(!runB||!runA)return;
  const names=new Set([...loadedA.keys(),...(loadedB?.keys()??[])]);const groups:Record<Diff,string[]>={changed:[],same:[],onlyA:[],onlyB:[]};
  for(const n of [...names].sort(natural))groups[diffOf(n)!].push(n);
  const chip=(label:string,list:string[],cls:string,selectable=true)=>{const b=button(`${list.length} ${label}`,()=>{if(selectable&&list.length){select(list,'replace');showTab('parts')}},`chip ${cls}`);b.disabled=!list.length||!selectable;b.title=list.join(', ')||'none';return b};
  host.replaceChildren(el('span',{class:'muted',textContent:`B ${shortId(runB.id)} vs A ${shortId(runA.id)} · ${backendName()}:`}),
    chip('changed',groups.changed,'changed'),chip('only in A',groups.onlyA,'onlyA'),chip('only in B',groups.onlyB,'onlyB',false),chip('identical',groups.same,'same'));
}

function focusPart(){const iso=state.isolated;if(iso?.length===1)return iso[0];return state.selection.size===1?[...state.selection][0]:undefined}
function fmt(v?:number,d=1){return v===undefined?'—':v.toFixed(d)}
function renderDetails(){
  const host=$('details'),name=focusPart(),a=name?loadedA.get(name):undefined;host.hidden=!a;if(!a||!name)return;
  const m=a.part.measurements??{},b=runB?loadedB?.get(name):undefined,mb=b?.part.measurements;
  const row=(label:string,av:string,bv?:string,delta?:string)=>el('tr',{},el('th',{textContent:label}),el('td',{textContent:av}),...(runB?[el('td',{textContent:bv??'—'}),el('td',{class:'delta',textContent:delta??''})]:[]));
  const dims=(x?:number[])=>x?x.map(v=>fmt(v)).join(' × ')+' mm':'—';
  const delta=(x?:number,y?:number,unit='')=>x===undefined||y===undefined?'':Math.abs(y-x)<.05?'=':`${y>x?'+':''}${(y-x).toFixed(1)}${unit}`;
  const table=el('table',{class:'measure'},el('thead',{},el('tr',{},el('th'),el('th',{textContent:runB?'A':'This run'}),...(runB?[el('th',{textContent:'B'}),el('th',{textContent:'Δ B−A'})]:[]))),
    el('tbody',{},row('Print bbox',dims(m.bbox_mm),b?dims(mb?.bbox_mm):'not in B',m.bbox_mm&&mb?.bbox_mm?m.bbox_mm.map((v,i)=>delta(v,mb.bbox_mm![i])).join(' / '):''),
      row('Volume',m.volume_mm3!==undefined?`${(m.volume_mm3/1000).toFixed(2)} cm³`:'—',mb?.volume_mm3!==undefined?`${(mb.volume_mm3/1000).toFixed(2)} cm³`:b?'—':'not in B',delta(m.volume_mm3&&m.volume_mm3/1000,mb?.volume_mm3&&mb.volume_mm3/1000,' cm³')),
      row('Geometry',a.part.reused?'reused':'built in this run',b?(sha(a)===sha(b)?'identical':'changed'):'—')));
  const checks=el('div',{class:'pills'},...Object.entries(m.checks??{}).sort(([,x],[,y])=>Number(x)-Number(y)).map(([k,v])=>el('span',{class:'pill '+(v?'passed':'failed'),textContent:`${v?'✓':'✕'} ${k.replaceAll('_',' ')}`})));
  const previews:Item[]=[];const pa=find(a.part,'preview.png');if(pa)previews.push({path:pa.path,title:`${name} · A`,subtitle:runLabel(runA!),kind:'image'});
  const pb=find(b?.part,'preview.png');if(pb&&runB)previews.push({path:pb.path,title:`${name} · B`,subtitle:runLabel(runB),kind:'image'});
  const thumbs=el('div',{class:'detail-thumbs'},...previews.map((p,i)=>thumb(p,()=>openLightbox(previews,i))));
  const files=el('div',{class:'files'},...a.part.artifacts.filter(x=>/\.(stl|3mf)$/.test(x.path)).map(x=>downloadLink(x.path,`⤓ ${fileName(x.path)}`)));
  const actions=el('div',{class:'actions'});if(!state.isolated)actions.append(button('Isolate',()=>isolate([name]),'small primary'));else actions.append(button('‹ Back to assembly',exitIsolate,'small'));
  host.replaceChildren(el('div',{class:'details-head'},el('h2',{},name,el('span',{class:'muted',textContent:` · ${backendName()}`})),actions),
    el('div',{class:'details-body'},thumbs,el('div',{},table,checks,files)));
}

function thumb(item:Item,onclick:()=>void){const b=el('button',{class:'thumb',title:`View ${item.title}`},el('img',{src:artifactURL(item.path,true),alt:item.title,loading:'lazy'}),el('span',{textContent:item.title}));b.onclick=onclick;return b}
function downloadLink(path:string,label:string){return el('a',{class:'file',href:artifactURL(path),download:fileName(path),textContent:label,title:`Download ${fileName(path)}`})}
function button(text:string,fn:()=>void,cls=''){const b=el('button',{textContent:text,class:cls});b.onclick=fn;return b}

function renderRenders(){
  const filter=state.isolated??(state.selection.size?[...state.selection]:null);
  const items:Item[]=[...loadedA.values()].filter(l=>!filter||filter.includes(l.name)).flatMap(l=>{const p=find(l.part,'preview.png');return p?[{path:p.path,title:l.name,subtitle:`${backendName()} · ${runLabel(runA!)}`,kind:'image' as const}]:[]});
  $('renders-note').textContent=filter?`· ${items.length} for the selection`:items.length?`· ${items.length}`:'';
  $('renders').replaceChildren(...(items.length?items.map((it,i)=>thumb(it,()=>openLightbox(items,i))):[el('p',{class:'muted',textContent:'No renders in this run.'})]));
}

function renderEvidence(){
  const backend=runA?.backends[backendName()];$('errors').textContent=runA?.failures.join('\n')||'';
  const checks=Object.entries(backend?.checks??{}).sort(([,x],[,y])=>Number(x.passed)-Number(y.passed));
  $('checks').replaceChildren(...(checks.length?checks.map(([name,r])=>el('div',{class:'check '+(r.passed?'passed':'failed')},el('span',{class:'pill '+(r.passed?'passed':'failed'),textContent:r.passed?'✓ pass':'✕ fail'}),el('span',{textContent:name}),el('span',{class:'tag',textContent:r.reused?'reused evidence':'fresh check'}))):[el('p',{class:'muted',textContent:runA?'No checks recorded for this backend.':'No run selected.'})]));
  const host=$('artifacts');host.replaceChildren();if(!runA||!backend)return;const b=backendName();
  const log=`.geometryforge/runs/${runA.id}/${b}/${b}.log`;
  const scene=el('div',{class:'files'});if(backend.native)scene.append(downloadLink(backend.native.path,`⤓ Editable native scene (${fileName(backend.native.path)})`));
  scene.append(button('View backend log',()=>openLightbox([{path:log,title:`${b}.log`,subtitle:runLabel(runA!),kind:'text'}]),'small'));
  renderKit(host,backend.kit);
  host.append(el('h3',{textContent:'Scene & logs'}),scene);
  const filter=state.isolated??(state.selection.size?[...state.selection]:null);
  const parts=[...loadedA.values()].filter(l=>!filter||filter.includes(l.name));
  $('files-note').textContent=filter?`· ${parts.length} selected part${parts.length===1?'':'s'}`:'';
  const table=el('table',{class:'files-table'},el('thead',{},el('tr',{},el('th',{textContent:'Part'}),el('th',{textContent:'Print files'}),el('th',{textContent:'Render'}))),
    el('tbody',{},...parts.map(l=>{const png=find(l.part,'preview.png');const view=png?button('View',()=>openLightbox([{path:png.path,title:l.name,subtitle:runLabel(runA!),kind:'image'}]),'small ghost'):'—';
      return el('tr',{},el('td',{textContent:l.name}),el('td',{},...l.part.artifacts.filter(x=>/\.(stl|3mf)$/.test(x.path)).map(x=>downloadLink(x.path,'⤓ '+fileName(x.path).split('.').pop()!.toUpperCase()))),el('td',{},view))})));
  host.append(el('h3',{textContent:'Print files'}),table);
}

// Whole-model deliverables: the Bambu project with plates, the assembled model, and the slicer-neutral files.
function renderKit(host:HTMLElement,kit:Kit|undefined){
  if(!kit)return;const files=new Map(kit.artifacts.map(a=>[fileName(a.path),a.path]));const bambu=kit.bambu?.files;
  const plates=bambu?.['kit.3mf']?.plates??0;
  const rows:[string,string][]=[['kit.3mf',`Bambu Studio project · ${plates} plate${plates===1?'':'s'} · every part in print orientation`],
    ['assembled-bambu.3mf','Assembled model with filament colours, for planning (larger than the bed)'],
    ['assembled.3mf','Assembled model, slicer-neutral'],['kit-raw.3mf','All parts in print orientation, slicer-neutral, not arranged']];
  const list=el('div',{class:'kit-files'},...rows.filter(([f])=>files.has(f)).map(([f,label])=>el('div',{class:'kit-file'},downloadLink(files.get(f)!,'⤓ '+f),el('span',{class:'muted',textContent:label}))));
  const slots=new Map<number,string[]>();for(const [part,used] of Object.entries(kit.parts))for(const s of used)slots.set(s,[...(slots.get(s)??[]),part]);
  const plan=Object.values(kit.filaments) as Filament[];
  const legend=el('div',{class:'filaments'},...[...slots.keys()].sort((a,b)=>a-b).map(s=>{const f=plan.find(x=>x.slot===s);const parts=slots.get(s)!.sort(natural);
    const chip=button('',()=>{select(parts,'replace');showTab('parts')},'filament');chip.title=`Select the ${parts.length} parts printed in slot ${s}:\n${parts.join(', ')}`;
    const swatch=el('span',{class:'swatch'});swatch.style.background='#'+filamentColour(runA,s).getHexString(THREE.SRGBColorSpace);
    chip.append(swatch,el('b',{textContent:String(s)}),el('span',{textContent:`${f?.name??'Slot '+s}${f?.material?' · '+f.material:''}`}),el('small',{class:'muted',textContent:`${parts.length} part${parts.length===1?'':'s'}`}));return chip}));
  host.append(el('h3',{textContent:'Full model'}),list,legend);
  if(kit.bambu?.skipped)host.append(el('p',{class:'muted note',textContent:kit.bambu.skipped}));
  else if(kit.bambu?.machine)host.append(el('p',{class:'muted note',textContent:`Arranged by Bambu Studio for ${kit.bambu.machine} · ${kit.bambu.process}. Not sliced; check plates and supports in the slicer.`}));
}

// ---------- Selection, visibility, isolation ----------
function select(names:string[],how:'replace'|'toggle'|'add'){
  if(how==='replace')state.selection=new Set(names);else for(const n of names)if(how==='toggle'&&state.selection.has(n))state.selection.delete(n);else state.selection.add(n);
  applyState();renderPartsPanel();renderDetails();renderRenders();renderEvidence();
}
function setHidden(names:string[],hidden:boolean){for(const n of names)hidden?state.hidden.add(n):state.hidden.delete(n);applyState();updateDimensions();renderPartsPanel()}
function isolate(names:string[]){
  names=names.filter(n=>loadedA.has(n));if(!names.length)return;if(!state.isolated)assemblyCamera=viewer.saveCamera();
  state.isolated=names;state.selection=new Set(names);rebuild(true);renderAll();
}
function exitIsolate(){if(!state.isolated)return;state.isolated=null;rebuild(false);if(assemblyCamera)viewer.restoreCamera(assemblyCamera);else viewer.fit();renderAll()}

// ---------- Viewport interaction ----------
const canvas=viewer.renderer.domElement;let down:{x:number;y:number}|undefined,hoverFrame=0;
canvas.addEventListener('pointerdown',e=>down={x:e.clientX,y:e.clientY});
canvas.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;down=undefined;const part=viewer.pick(e);
  if(part)select([part],e.ctrlKey||e.metaKey||e.shiftKey?'toggle':'replace');else if(!e.ctrlKey&&!e.shiftKey&&state.selection.size)select([],'replace')});
canvas.addEventListener('dblclick',e=>{const part=viewer.pick(e);if(part)isolate(state.selection.has(part)&&!state.isolated?[...state.selection]:[part])});
canvas.addEventListener('pointermove',e=>{if(e.buttons){$('hover').hidden=true;return}cancelAnimationFrame(hoverFrame);hoverFrame=requestAnimationFrame(()=>{
  const part=viewer.pick(e),tip=$('hover');if(part!==hovered){hovered=part;applyState()}tip.hidden=!part;canvas.style.cursor=part?'pointer':'';
  if(part){const r=$('viewport').getBoundingClientRect();tip.textContent=part;tip.style.left=`${e.clientX-r.left+14}px`;tip.style.top=`${e.clientY-r.top+14}px`}})});
canvas.addEventListener('pointerleave',()=>{$('hover').hidden=true;if(hovered){hovered=undefined;applyState()}});

document.addEventListener('keydown',e=>{
  const t=e.target as HTMLElement;if(document.querySelector('dialog[open]')||/^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName))return;if(e.ctrlKey||e.metaKey)return;
  const k=e.key.toLowerCase();
  if(k==='i'&&state.selection.size)isolate([...state.selection]);
  else if(k==='h'&&e.altKey)setHidden([...state.hidden],false);
  else if(k==='h'&&state.selection.size&&!state.isolated)setHidden([...state.selection],true);
  else if(k==='f')viewer.fit();
  else if(k==='escape'){if(state.isolated)exitIsolate();else if(runB)void setCompare(undefined);else if(state.selection.size)select([],'replace')}
  else return;e.preventDefault();
});

// ---------- Toolbar & panels wiring ----------
function showTab(tab:'parts'|'runs'){for(const t of ['parts','runs']){$('tab-'+t).classList.toggle('active',t===tab);$('tab-'+t).setAttribute('aria-selected',String(t===tab));$('panel-'+t).hidden=t!==tab}}
$('tab-parts').onclick=()=>showTab('parts');$('tab-runs').onclick=()=>showTab('runs');
$('part-filter').oninput=()=>{state.filter=($('part-filter') as HTMLInputElement).value;renderPartsPanel()};
$('show-all').onclick=()=>setHidden([...loadedA.keys()],false);$('show-none').onclick=()=>setHidden([...loadedA.keys()],true);
$('show-invert').onclick=()=>{const all=[...loadedA.keys()];const shown=all.filter(n=>!state.hidden.has(n));state.hidden=new Set(shown);applyState();updateDimensions();renderPartsPanel()};
$('colour-mode').querySelectorAll('button').forEach(b=>(b as HTMLButtonElement).onclick=()=>{colourMode=(b as HTMLButtonElement).dataset.colour as typeof colourMode;rebuild(false);renderToolbar()});
$('pose').querySelectorAll('button').forEach(b=>(b as HTMLButtonElement).onclick=()=>{pose=(b as HTMLButtonElement).dataset.pose as typeof pose;rebuild(true);renderToolbar()});
$('compare-mode').querySelectorAll('button').forEach(b=>(b as HTMLButtonElement).onclick=()=>{mode=(b as HTMLButtonElement).dataset.mode as typeof mode;rebuild(false);renderToolbar()});
$('backend').onchange=guarded(()=>loadView());$('fit').onclick=()=>viewer.fit();
$('safe').onclick=()=>{const run=runs.find(r=>r.id===ctx?.safe_point);if(run)void openRun(run).catch(e=>toast(String(e)))};

// ---------- Projects ----------
async function refreshProjects(){projects=await api('/projects');$('projects').replaceChildren();for(const [id,p] of Object.entries(projects)){if(p.archived&&!($('show-archived') as HTMLInputElement).checked)continue;const b=button(p.title,()=>void openProject(id).catch(e=>toast(String(e))),'project '+(id===session.key?'active':''));b.title=p.path;$('projects').append(b)}}
async function openProject(id:string){
  revision++;clearCache();session.key=id;runA=runB=undefined;loadedA=new Map();loadedB=undefined;state.selection.clear();state.hidden.clear();state.isolated=null;state.filter='';($('part-filter') as HTMLInputElement).value='';
  viewer.setPanes([]);$('overlays').replaceChildren();$('title').textContent=projects[id].title;$('path').textContent=projects[id].path;renderAll();
  await refreshProjects();await refresh();const start=runs.find(r=>r.id===ctx?.safe_point)??runs[0];if(start)await openRun(start);else $('empty').hidden=false;
}
async function refresh(){
  if(!session.key)return;const requested=session.key;const result=await Promise.all([api(`/projects/${requested}/context`),api(`/projects/${requested}/runs`)]);if(session.key!==requested)return;[ctx,runs]=result;
  const stale=Object.values(ctx!.backends).some(s=>s.stale||s.working_changed);
  $('banner').textContent=ctx!.safe_point_label+' · '+Object.entries(ctx!.backends).map(([b,s])=>`${b}: ${s.stale?'out of date':'current'}${s.working_changed?' (saved edits detected)':''}`).join(' · ');
  $('banner').className='pill banner '+(ctx!.safe_point?stale?'warn':'passed':'candidate');
  renderRunsPanel();renderToolbar();
}

$('copy').onclick=guarded(async()=>{if(!session.key)return;const parts=state.isolated??[...state.selection];
  await navigator.clipboard.writeText(`GeometryForge project: ${projects[session.key].path}\nRun: ${runA?.id||'none'}${parts.length?`\nParts: ${parts.join(', ')}`:''}\nStart with: geometryforge context "${projects[session.key].path}"`);toast('Agent reference copied')});
$('rename').onclick=guarded(async()=>{if(!session.key)return;const title=prompt('Project display name',projects[session.key].title);if(title){await api(`/projects/${session.key}`,'PATCH',{title});await refreshProjects();$('title').textContent=title}});
$('archive').onclick=guarded(async()=>{if(!session.key)return;await api(`/projects/${session.key}`,'PATCH',{archived:!projects[session.key].archived});await refreshProjects()});
$('show-archived').onchange=guarded(refreshProjects);$('add').onclick=()=>($('dialog') as HTMLDialogElement).showModal();$('cancel').onclick=()=>($('dialog') as HTMLDialogElement).close();
$('project-form').onsubmit=e=>{e.preventDefault();void(async()=>{const item=await api('/projects','POST',{path:($('folder') as HTMLInputElement).value,create:($('create') as HTMLInputElement).checked});($('dialog') as HTMLDialogElement).close();await refreshProjects();await openProject(item.key)})().catch(e=>toast(String(e)))};
void(async()=>{await startSession();await refreshProjects();const first=Object.keys(projects).find(k=>!projects[k].archived);if(first)await openProject(first)})().catch(e=>toast(String(e)));
setInterval(()=>void refresh().catch(e=>toast(String(e))),5000);
