import {test,expect} from '@playwright/test';

test('native projects, complete assemblies, history, visibility and evidence',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('#projects .project')).toHaveCount(2);
  await page.locator('#projects .project').filter({hasText:'Falcon9'}).click();
  await expect(page.locator('#parts input')).toHaveCount(6,{timeout:30000});
  await expect(page.locator('#dimensions')).toContainText('mm');
  await expect(page.locator('#checks')).toContainText('lower_joint');
  await page.locator('#parts input').first().uncheck();
  await expect(page.locator('#parts input').first()).not.toBeChecked();
  await page.locator('#parts input').first().check();
  await page.locator('#fit').click();
  await page.screenshot({path:'../docs/viewer-windows.png',fullPage:true});
  const options=await page.locator('#backend option').allTextContents();
  if(options.includes('houdini')){await page.locator('#backend').selectOption('houdini');await expect(page.locator('#parts input')).toHaveCount(6)}
  await page.locator('#projects .project').filter({hasText:'Desk Organizer'}).click();
  await expect(page.locator('#parts input')).toHaveCount(1,{timeout:30000});
  await expect(page.locator('#banner')).toContainText('SAFE POINT');
  await page.locator('#safe').click();
  await expect(page.locator('#checks')).toContainText('cavities');
  expect(errors).toEqual([]);
});

test('run status and reuse are visible',async({page})=>{
  await page.goto('/');
  await page.locator('#projects .project').filter({hasText:'Falcon9'}).click();
  await expect(page.locator('#parts input')).toHaveCount(6,{timeout:30000});
  await page.locator('#runs .run').filter({hasText:'failed'}).last().click();
  await expect(page.locator('#errors')).not.toBeEmpty();
});
