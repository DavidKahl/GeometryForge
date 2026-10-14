import * as THREE from 'three';
import {artifactURL,type Loaded} from './api';

const textures=new Map<string,THREE.Texture>();
export function clearGameTextures(){for(const t of textures.values())t.dispose();textures.clear()}
export function gameMaterial(l:Loaded,id:string){
  const spec=l.game?.materials[id];
  const rgba=spec?.base_color??[.6,.65,.7,1];
  const material=new THREE.MeshStandardMaterial({color:new THREE.Color(rgba[0],rgba[1],rgba[2]),roughness:spec?.roughness??.5,metalness:spec?.metallic??0});
  if(!spec||!l.game)return material;
  const root=l.game.manifest.replace(/manifest\.json$/,'');
  const load=(path:string,srgb=false)=>{const url=artifactURL(root+path,true);let texture=textures.get(url);if(!texture){texture=new THREE.TextureLoader().load(url);texture.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;textures.set(url,texture)}return texture};
  if(spec.textures.base_color)material.map=load(spec.textures.base_color.path,true);
  if(spec.textures.normal)material.normalMap=load(spec.textures.normal.preview_path??spec.textures.normal.path);
  if(spec.textures.orm){const map=load(spec.textures.orm.path);material.roughnessMap=map;material.metalnessMap=map;material.aoMap=map;material.roughness=1;material.metalness=1}
  if(spec.textures.emissive){material.emissiveMap=load(spec.textures.emissive.path,true);material.emissive.set(0xffffff)}
  if(spec.blend_mode==='TRANSLUCENT'){material.transparent=true;material.opacity=rgba[3]}
  if(spec.blend_mode==='MASKED')material.alphaTest=.5;
  return material;
}
