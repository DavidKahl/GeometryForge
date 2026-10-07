import * as THREE from 'three';

export type Artifact={path:string;sha256:string};
export type Measurements={bbox_mm?:number[];volume_mm3?:number;bed_mm?:number[];checks?:Record<string,boolean>};
export type Part={reused:boolean;artifacts:Artifact[];measurements?:Measurements};
export type Backend={parts:Record<string,Part>;checks:Record<string,{passed:boolean;reused:boolean}>;native?:Artifact;changed_parts:string[];rebuilt_parts:string[]};
export type Run={id:string;parent:string|null;status:string;backends:Record<string,Backend>;failures:string[]};
export type Project={path:string;title:string;archived:boolean};
export type Context={safe_point:string|null;safe_point_label:string;issues:string[];backends:Record<string,{stale:boolean;working_changed:boolean}>};
export type Loaded={name:string;part:Part;geometries:THREE.BufferGeometry[];rotation:number[]};

let token='';
export const session={key:''};

export async function api(url:string,method='GET',body?:unknown){
  const response=await fetch('/api'+url,{method,headers:{'Content-Type':'application/json','X-GeometryForge-Token':token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||data.detail||'Request failed');return data;
}
export async function startSession(){token=(await api('/session')).token}
export const artifactURL=(path:string,inline=false)=>`/api/projects/${session.key}/artifact?path=${encodeURIComponent(path)}${inline?'&inline=1':''}`;
export const fileName=(path:string)=>path.split('/').pop()!;
export const find=(part:Part|undefined,suffix:string)=>part?.artifacts.find(a=>a.path.endsWith(suffix));

// Natural order keeps aft_fin_2 before aft_fin_10.
export const natural=new Intl.Collator(undefined,{numeric:true}).compare;

// Geometry is cached per artifact URL: switching runs, backends or views never re-downloads a part.
const geometryCache=new Map<string,Promise<{geometries:THREE.BufferGeometry[];rotation:number[]}>>();
export function clearCache(){for(const entry of geometryCache.values())void entry.then(e=>e.geometries.forEach(g=>g.dispose()),()=>{});geometryCache.clear()}
function geometry(path:string){
  const url=artifactURL(path);let entry=geometryCache.get(url);
  if(!entry){
    entry=fetch(url).then(r=>{if(!r.ok)throw Error(`Could not load ${fileName(path)}`);return r.json()}).then(data=>{
      const objects:{vertices:number[][];faces:number[][];print_rotation_deg?:number[]}[]=data.objects;
      const geometries=objects.map(obj=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(obj.vertices.flat(),3));g.setIndex(obj.faces.flat());g.computeVertexNormals();g.computeBoundingBox();return g});
      return {geometries,rotation:objects[0]?.print_rotation_deg??[0,0,0]};
    });
    entry.catch(()=>geometryCache.delete(url));geometryCache.set(url,entry);
  }
  return entry;
}

export async function loadParts(backend:Backend,progress:(done:number,total:number)=>void){
  const names=Object.keys(backend.parts).sort(natural).filter(n=>find(backend.parts[n],'/assembly.json'));
  const result=new Map<string,Loaded>();let done=0,next=0;progress(0,names.length);
  const worker=async()=>{while(next<names.length){const name=names[next++];const part=backend.parts[name];
    const {geometries,rotation}=await geometry(find(part,'/assembly.json')!.path);result.set(name,{name,part,geometries,rotation});progress(++done,names.length)}};
  await Promise.all(Array.from({length:Math.min(6,names.length)},worker));
  return new Map(names.filter(n=>result.has(n)).map(n=>[n,result.get(n)!]));
}

export function runTime(id:string){
  const m=/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(id);if(!m)return id;
  const date=new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6]));
  return date.toLocaleDateString(undefined,{month:'short',day:'numeric'})+' · '+date.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});
}
export const shortId=(id:string)=>id.split('-').pop()!;
export function el<K extends keyof HTMLElementTagNameMap>(tag:K,props:Partial<HTMLElementTagNameMap[K]>&{class?:string}={},...children:(Node|string)[]){
  const node=document.createElement(tag);const {class:cls,...rest}=props;if(cls)node.className=cls;Object.assign(node,rest);node.append(...children);return node;
}
