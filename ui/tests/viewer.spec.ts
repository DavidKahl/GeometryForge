import {test,expect,type Page} from '@playwright/test';

// Fixture projects come from tests/fixture_server.py: "Fixture Lander" has six parts (hull, cap, fin_1..fin_4),
// three runs (fins only, full model = safe point, failed check) and both backends; "Fixture Box" has one part.
const project=(page:Page,name:string)=>page.locator('#projects .project').filter({hasText:name});
const leaves=(page:Page)=>page.locator('#parts .part-row');
async function openLander(page:Page){await page.goto('/');await project(page,'Fixture Lander').click();await expect(leaves(page)).toHaveCount(6,{timeout:30000})}

test('projects, assemblies, backends and evidence',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(project(page,'Fixture Lander')).toHaveCount(1);await expect(project(page,'Fixture Box')).toHaveCount(1);
  await project(page,'Fixture Lander').click();
  await expect(leaves(page)).toHaveCount(6,{timeout:30000});
  await expect(page.locator('#dimensions')).toContainText('mm');
  await expect(page.locator('#checks')).toContainText('body_joints');
  const eye=leaves(page).first().locator('input');
  await eye.uncheck();await expect(eye).not.toBeChecked();await eye.check();
  await page.locator('#fit').click();
  await page.locator('#backend').selectOption('houdini');await expect(leaves(page)).toHaveCount(6);
  await project(page,'Fixture Box').click();
  await expect(leaves(page)).toHaveCount(1,{timeout:30000});
  await expect(page.locator('#banner')).toContainText('SAFE POINT');
  await expect(page.locator('#checks')).toContainText('cavities');
  expect(errors).toEqual([]);
});

test('run status and safe point navigation',async({page})=>{
  await openLander(page);
  await page.locator('#tab-runs').click();
  await page.locator('#runs .run').filter({hasText:'failed'}).click();
  await expect(page.locator('#errors')).toContainText('break_check');
  await expect(page.locator('#safe')).toBeVisible();await page.locator('#safe').click();await expect(page.locator('#safe')).toBeHidden();
});

test('filter, groups, selection and isolate view',async({page})=>{
  await openLander(page);
  await page.locator('#part-filter').fill('fin');
  await expect(leaves(page)).toHaveCount(4);
  await page.locator('.group-row').filter({hasText:'fin'}).click();
  await expect(page.locator('#selection-bar')).toContainText('4 selected');
  await page.locator('#part-filter').fill('');
  await page.locator('#show-none').click();await expect(page.locator('#parts .part-row input:checked')).toHaveCount(0);
  await page.locator('#show-all').click();await expect(page.locator('#parts .part-row input:checked')).toHaveCount(6);
  await page.locator('.part-row[data-part=cap] .iso').click();
  await expect(page.locator('#crumbs')).toContainText('cap');
  await expect(page.locator('#details')).toBeVisible();await expect(page.locator('#details')).toContainText('Print bbox');
  await expect(page.locator('#renders .thumb')).toHaveCount(1);
  await page.locator('#pose [data-pose=print]').click();await expect(page.locator('#pose [data-pose=print]')).toHaveClass(/active/);
  await page.keyboard.press('Escape');
  await expect(page.locator('#crumbs')).toHaveText('Assembly');
  await expect(page.locator('#pose')).toBeHidden();
});

test('compare runs side by side and per part',async({page})=>{
  await openLander(page);
  await page.locator('#tab-runs').click();
  // The first fixture run only built the four fins.
  await page.locator('#runs .run').filter({hasText:'4 parts'}).locator('.compare').click();
  await expect(page.locator('.pane-label.a')).toBeVisible();await expect(page.locator('.pane-label.b')).toBeVisible();
  await expect(page.locator('#diff')).toContainText('2 only in A');
  await page.locator('#tab-parts').click();
  await page.locator('.part-row[data-part=hull] .iso').click();
  await expect(page.locator('.pane-empty')).toHaveText("hull isn't in this run.");
  await page.locator('#crumbs button').click();
  await page.locator('.part-row[data-part=fin_1] .iso').click();
  await expect(page.locator('.pane-empty')).toHaveCount(0);
  await page.locator('#compare-mode [data-mode=overlay]').click();await expect(page.locator('.pane-label.b')).toContainText('ghost');
  await page.keyboard.press('Escape');await page.keyboard.press('Escape');
  await expect(page.locator('.pane-label')).toHaveCount(0);await expect(page.locator('#diff')).toBeHidden();
});

test('filament colours and whole-model files',async({page})=>{
  await openLander(page);
  await page.locator('#colour-mode [data-colour=filament]').click();await expect(page.locator('#colour-mode [data-colour=filament]')).toHaveClass(/active/);
  await expect(page.locator('#artifacts')).toContainText('kit-raw.3mf');await expect(page.locator('#artifacts')).toContainText('assembled.3mf');
  await page.locator('button.filament').filter({hasText:'Dark'}).click();
  await expect(page.locator('#selection-bar')).toContainText('5 selected');
});

test('renders open in the viewer and download only on request',async({page})=>{
  await openLander(page);
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
