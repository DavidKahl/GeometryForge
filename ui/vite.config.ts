import {defineConfig} from 'vite';
import {copyFileSync} from 'node:fs';
export default defineConfig({base:'/',plugins:[{name:'third-party-license',closeBundle(){copyFileSync('node_modules/three/LICENSE','../geometryforge/web_dist/THREE-LICENSE.txt')}}],build:{outDir:'../geometryforge/web_dist',emptyOutDir:true,rollupOptions:{output:{manualChunks:{three:['three','three/addons/controls/OrbitControls.js']}}}}});
