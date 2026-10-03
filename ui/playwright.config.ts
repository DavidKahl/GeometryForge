import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests',use:{baseURL:'http://127.0.0.1:8743',viewport:{width:1440,height:1050},launchOptions:{args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']}},workers:1});
