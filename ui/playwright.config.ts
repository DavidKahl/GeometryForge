import {defineConfig} from '@playwright/test';

// The tests run against generated fixture projects (tests/fixture_server.py) on their own port,
// so they need neither Blender/Houdini nor any locally registered project.
export default defineConfig({
  testDir:'tests',
  use:{baseURL:'http://127.0.0.1:8744',viewport:{width:1440,height:1050},launchOptions:{args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},
  workers:1,
  webServer:{command:'uv run --project .. --extra viewer python tests/fixture_server.py --port 8744',url:'http://127.0.0.1:8744/api/session',timeout:180000,reuseExistingServer:!process.env.CI,stdout:'pipe'},
});
