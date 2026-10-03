import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import './style.css';

type Artifact={path:string;sha256:string};
type Part={reused:boolean;artifacts:Artifact[];measurements:{bbox_mm:number[]}};
type Backend={parts:Record<string,Part>;checks:Record<string,{passed:boolean;reused:boolean}>;native:Artifact;changed_parts:string[];rebuilt_parts:string[]};
type Run={id:string;status:string;backends:Record<string,Backend>;failures:string[];plan:unknown};
type Project={path:string;title:string;archived:boolean};
type Context={safe_point:string|null;safe_point_label:string;issues:string[];backends:Record<string,{stale:boolean;working_changed:boolean}>};

document.querySelector('#app')!.innerHTML=`
<aside><a class="brand" href="/">◈ <span>GeometryForge<small>LOCAL WORKSHOP</small></span></a><div class="section-title">PROJECTS <button id="add" title="Register or create project">＋</button></div><div id="projects"></div><label class="archived"><input id="show-archived" type="checkbox"> Show archived</label><footer>Built in your agent.<br>Inspected here.</footer></aside>
<main><header><div><span class="eyebrow">YOUR WORK, EVERY ITERATION</span><h1 id="title">Choose a project</h1><p id="path">A local library of geometry and the evidence behind it.</p></div><div class="actions"><button id="rename">Rename</button><button id="archive">Archive</button><button id="copy">Copy agent reference</button></div></header>
<div id="banner">Register a project to inspect its runs.</div><div class="workspace"><section class="canvas-panel"><div class="toolbar"><strong>Assembly</strong><select id="backend" aria-label="Backend"><option>blender</option><option>houdini</option></select><button id="fit">Fit view</button><span id="dimensions"></span></div><div id="viewport"><div class="empty" id="empty">Your geometry will appear here.<br><small>Select a run to explore its parts.</small></div></div><div id="parts"></div></section>
<section class="history"><div class="section-title">RUN HISTORY <button id="safe">Safe point</button></div><div id="runs"></div></section></div>
<section class="evidence"><div><h2>Validation evidence</h2><div id="checks">No run selected.</div></div><div><h2>Artifacts & diagnostics</h2><div id="artifacts"></div><pre id="errors"></pre></div></section></main>
<dialog id="dialog"><form id="project-form"><h2>Add a project</h2><label>Project folder<input id="folder" required placeholder="E:\\Models\\My project"></label><label><input type="checkbox" id="create"> Create an empty project in this folder</label><p>Modeling and generation stay in your agent.</p><div class="actions"><button type="button" id="cancel">Cancel</button><button type="submit">Add project</button></div></form></dialog><div id="toast" role="status"></div>`;
const $=(id:string)=>document.getElementById(id)!;
let token='',projects:Record<string,Project>={},key='',runs:Run[]=[],selected:Run|undefined,ctx:Context|undefined,revision=0;
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));$('viewport').append(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color('#101a26');
const camera=new THREE.PerspectiveCamera(42,1,.1,10000);camera.up.set(0,0,1);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
scene.add(new THREE.HemisphereLight(0xdbeaff,0x314151,3));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(80,-100,160);scene.add(light);
const grid=new THREE.GridHelper(400,20,0x405061,0x253341);grid.rotation.x=Math.PI/2;grid.position.z=-.1;scene.add(grid);
let model=new THREE.Group();scene.add(model);
new ResizeObserver(()=>{const r=$('viewport').getBoundingClientRect();renderer.setSize(r.width,r.height);camera.aspect=r.width/r.height;camera.updateProjectionMatrix()}).observe($('viewport'));
renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera)});
function toast(message:string){$('toast').textContent=message;setTimeout(()=>$('toast').textContent='',5000)}
async function api(url:string,method='GET',body?:unknown){const response=await fetch('/api'+url,{method,headers:{'Content-Type':'application/json','X-GeometryForge-Token':token},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||'Request failed');return data}
const artifactURL=(path:string)=>`/api/projects/${key}/artifact?path=${encodeURIComponent(path)}`;
function clear(){for(const child of [...model.children]){const mesh=child as THREE.Mesh;mesh.geometry.dispose();(mesh.material as THREE.Material).dispose();model.remove(mesh)}$('parts').replaceChildren();$('empty').hidden=false}
function fit(){const box=new THREE.Box3().setFromObject(model);if(box.isEmpty())return;const size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());const distance=Math.max(size.length(),20)*1.6;controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(1,-1,.7).normalize().multiplyScalar(distance));camera.near=distance/1000;camera.far=distance*100;camera.updateProjectionMatrix();controls.update();$('dimensions').textContent=size.toArray().map(v=>v.toFixed(1)).join(' × ')+' mm'}
function button(text:string,fn:()=>void){const b=document.createElement('button');b.textContent=text;b.onclick=fn;return b}
async function refreshProjects(){projects=await api('/projects');$('projects').replaceChildren();for(const [id,p] of Object.entries(projects)){if(p.archived&&!($('show-archived') as HTMLInputElement).checked)continue;const b=button(p.title,()=>void openProject(id));b.className='project '+(id===key?'active':'');$('projects').append(b)}}
async function openProject(id:string){revision++;clear();key=id;selected=undefined;$('title').textContent=projects[id].title;$('path').textContent=projects[id].path;await refreshProjects();await refresh();if(!selected&&runs.length)await selectRun(runs[0])}
async function refresh(){if(!key)return;const requested=key;const result=await Promise.all([api(`/projects/${requested}/context`),api(`/projects/${requested}/runs`)]);if(key!==requested)return;[ctx,runs]=result;$('banner').textContent=ctx!.safe_point_label+' · '+Object.entries(ctx!.backends).map(([b,s])=>`${b}: ${s.stale?'out of date':'current'}${s.working_changed?' (saved edits detected)':''}`).join(' · ');$('runs').replaceChildren();for(const run of runs){const b=button('',()=>void selectRun(run));b.className='run '+(selected?.id===run.id?'selected':'');const title=document.createElement('strong');title.textContent=run.id;const status=document.createElement('span');status.textContent=run.status+(run.id===ctx!.safe_point?' · SAFE POINT':'');status.className='status '+run.status;b.append(title,status);$('runs').append(b)} }
async function selectRun(run:Run){selected=run;await refresh();const sel=$('backend') as HTMLSelectElement;const previous=sel.value;sel.replaceChildren(...Object.keys(run.backends).map(b=>{const o=document.createElement('option');o.value=b;o.textContent=b;return o}));if(run.backends[previous])sel.value=previous;await showBackend()}
async function showBackend(){const rev=++revision;clear();$('checks').replaceChildren();$('artifacts').replaceChildren();$('errors').textContent=selected?.failures.join('\n')||'';const backend=selected?.backends[($('backend') as HTMLSelectElement).value];if(!backend)return;
for(const [name,result] of Object.entries(backend.checks)){const row=document.createElement('div');row.className='check';row.textContent=`${result.passed?'✓':'×'} ${name} · ${result.reused?'reused evidence':'fresh check'}`;$('checks').append(row)}
const link=(a:Artifact,label:string)=>{const el=document.createElement('a');el.href=artifactURL(a.path);el.textContent=label;el.download='';$('artifacts').append(el)};
if(backend.native)link(backend.native,'Editable native scene');
let index=0;for(const [name,part] of Object.entries(backend.parts)){const raw=part.artifacts.find(a=>a.path.endsWith('/assembly.json'));if(!raw)continue;const data=await(await fetch(artifactURL(raw.path))).json();if(rev!==revision)return;const meshes:THREE.Mesh[]=[];
for(const obj of data.objects){const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(obj.vertices.flat(),3));geometry.setIndex(obj.faces.flat());geometry.computeVertexNormals();const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:new THREE.Color().setHSL(.43+(index%5)*.055,.32,.62),roughness:.6}));model.add(mesh);meshes.push(mesh)}
const label=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=true;toggle.onchange=()=>meshes.forEach(m=>m.visible=toggle.checked);label.append(toggle,document.createTextNode(`${name} · ${part.reused?'reused':'updated'}`));$('parts').append(label);for(const a of part.artifacts.filter(a=>/\.(stl|3mf|png)$/.test(a.path)))link(a,`${name} · ${a.path.split('/').pop()}`);index++}
if(selected){const b=($('backend') as HTMLSelectElement).value;const log=`.geometryforge/runs/${selected.id}/${b}/${b}.log`;link({path:log,sha256:''},'Backend log')}
$('empty').hidden=model.children.length>0;fit()}
function guarded(fn:()=>Promise<unknown>){return ()=>void fn().catch(e=>toast(String(e)))}
$('backend').onchange=guarded(showBackend);$('fit').onclick=fit;$('safe').onclick=()=>{const run=runs.find(r=>r.id===ctx?.safe_point);if(run)void selectRun(run)};
$('copy').onclick=guarded(async()=>{await navigator.clipboard.writeText(`GeometryForge project: ${projects[key].path}\nRun: ${selected?.id||'none'}\nStart with: geometryforge context "${projects[key].path}"`);toast('Agent reference copied')});
$('rename').onclick=guarded(async()=>{if(!key)return;const title=prompt('Project display name',projects[key].title);if(title){await api(`/projects/${key}`,'PATCH',{title});await refreshProjects();$('title').textContent=title}});
$('archive').onclick=guarded(async()=>{if(!key)return;await api(`/projects/${key}`,'PATCH',{archived:!projects[key].archived});await refreshProjects()});
$('show-archived').onchange=guarded(refreshProjects);$('add').onclick=()=>($('dialog') as HTMLDialogElement).showModal();$('cancel').onclick=()=>($('dialog') as HTMLDialogElement).close();
$('project-form').onsubmit=e=>{e.preventDefault();void(async()=>{const item=await api('/projects','POST',{path:($('folder') as HTMLInputElement).value,create:($('create') as HTMLInputElement).checked});($('dialog') as HTMLDialogElement).close();await refreshProjects();await openProject(item.key)})().catch(e=>toast(String(e)))};
void(async()=>{token=(await api('/session')).token;await refreshProjects();const first=Object.keys(projects).find(k=>!projects[k].archived);if(first)await openProject(first)})().catch(e=>toast(String(e)));
setInterval(()=>void refresh().catch(e=>toast(String(e))),5000);
