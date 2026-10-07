import {test,expect,type Page} from '@playwright/test';

const project=(page:Page,name:string)=>page.locator('#projects .project').filter({hasText:name});
const leaves=(page:Page)=>page.locator('#parts .part-row');
async function openFalcon(page:Page){await page.goto('/');await project(page,'Falcon9').click();await expect(leaves(page)).toHaveCount(6,{timeout:30000})}

test('native projects, complete assemblies, history, visibility and evidence',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(project(page,'Falcon9')).toHaveCount(1);await expect(project(page,'Desk Organizer')).toHaveCount(1);
  await project(page,'Falcon9').click();
  await expect(leaves(page)).toHaveCount(6,{timeout:30000});
  await expect(page.locator('#dimensions')).toContainText('mm');
  await expect(page.locator('#checks')).toContainText('lower_joint');
  const eye=leaves(page).first().locator('input');
  await eye.uncheck();await expect(eye).not.toBeChecked();await eye.check();
  await page.locator('#fit').click();
  await page.screenshot({path:'../docs/viewer-windows.png',fullPage:true});
  const options=await page.locator('#backend option').allTextContents();
  if(options.includes('houdini')){await page.locator('#backend').selectOption('houdini');await expect(leaves(page)).toHaveCount(6)}
  await project(page,'Desk Organizer').click();
  await expect(leaves(page)).toHaveCount(1,{timeout:30000});
  await expect(page.locator('#banner')).toContainText('SAFE POINT');
  await expect(page.locator('#checks')).toContainText('cavities');
  expect(errors).toEqual([]);
});

test('run status and reuse are visible',async({page})=>{
  await openFalcon(page);
  await page.locator('#tab-runs').click();
  await page.locator('#runs .run').filter({hasText:'failed'}).last().click();
  await expect(page.locator('#errors')).not.toBeEmpty();
  await expect(page.locator('#safe')).toBeVisible();await page.locator('#safe').click();await expect(page.locator('#safe')).toBeHidden();
});

test('filter, groups, selection and isolate view',async({page})=>{
  await openFalcon(page);
  await page.locator('#part-filter').fill('stage');
  await expect(leaves(page)).toHaveCount(2);
  await page.locator('.group-row').filter({hasText:'stage'}).click();
  await expect(page.locator('#selection-bar')).toContainText('2 selected');
  await page.locator('#part-filter').fill('');
  await page.locator('#show-none').click();await expect(page.locator('#parts .part-row input:checked')).toHaveCount(0);
  await page.locator('#show-all').click();await expect(page.locator('#parts .part-row input:checked')).toHaveCount(6);
  await page.locator('.part-row[data-part=fairing] .iso').click();
  await expect(page.locator('#crumbs')).toContainText('fairing');
  await expect(page.locator('#details')).toBeVisible();await expect(page.locator('#details')).toContainText('Print bbox');
  await expect(page.locator('#renders .thumb')).toHaveCount(1);
  await page.locator('#pose [data-pose=print]').click();await expect(page.locator('#pose [data-pose=print]')).toHaveClass(/active/);
  await page.keyboard.press('Escape');
  await expect(page.locator('#crumbs')).toHaveText('Assembly');
  await expect(page.locator('#pose')).toBeHidden();
});

test('compare runs side by side and per part',async({page})=>{
  await openFalcon(page);
  await page.locator('#backend').selectOption('houdini');
  await page.locator('#tab-runs').click();
  await page.locator('#runs .run[data-run$=b43b8238] .compare').click();
  await expect(page.locator('.pane-label.a')).toBeVisible();await expect(page.locator('.pane-label.b')).toContainText('b43b8238');
  await expect(page.locator('#diff')).toContainText('only in A');
  await page.locator('#tab-parts').click();
  await page.locator('.part-row[data-part=fairing] .iso').click();
  await expect(page.locator('.pane-empty')).toHaveText("fairing isn't in this run.");
  await page.locator('#crumbs button').click();
  await page.locator('.part-row[data-part=coupon] .iso').click();
  await expect(page.locator('.pane-empty')).toHaveCount(0);
  await page.locator('#compare-mode [data-mode=overlay]').click();await expect(page.locator('.pane-label.b')).toContainText('ghost');
  await page.keyboard.press('Escape');await page.keyboard.press('Escape');
  await expect(page.locator('.pane-label')).toHaveCount(0);await expect(page.locator('#diff')).toBeHidden();
});

test('renders open in the viewer and download only on request',async({page})=>{
  await openFalcon(page);
  let downloads=0;page.on('download',()=>downloads++);
  await page.locator('#renders .thumb').first().click();
  await expect(page.locator('#lightbox')).toBeVisible();
  await expect(page.locator('#lightbox img')).toHaveJSProperty('complete',true);
  await page.keyboard.press('ArrowRight');await expect(page.locator('#lightbox-counter')).toContainText('2 /');
  expect(downloads).toBe(0);
  const download=page.waitForEvent('download');await page.locator('#lightbox-download').click();
  expect((await download).suggestedFilename()).toBe('preview.png');
  await page.keyboard.press('Escape');await expect(page.locator('#lightbox')).toBeHidden();
  await page.getByRole('button',{name:'View backend log'}).click();await expect(page.locator('#lightbox .log')).not.toHaveText('Loading…');
});
