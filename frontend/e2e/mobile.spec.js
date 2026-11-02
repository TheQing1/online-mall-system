// 移动端（375×812）用例。
//
// 存在的理由：全站曾经**一条 @media 都没有**——首页写死 4 列网格、
// AI 客服窗写死 400px 宽，在 375px 的手机上直接横向溢出，整块客服窗
// 有一截在视口外，连关闭按钮都点不到。而桌面端 1440 视口永远发现不了这些。
//
// 这批用例只断言「手机上能不能正常用」这一层，不重复跑桌面端的全部场景。
import { expect, test } from '@playwright/test'

import {
  SHOTS,
  expectCleanConsole,
  expectNoHorizontalOverflow,
  settle,
  watchConsole,
} from './helpers'

test('移动端首页不横向溢出，商品网格自动收缩', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  // 核心断言：没有横向滚动条
  await expectNoHorizontalOverflow(page, '首页')

  // 网格必须真的收缩了：375px 视口下应当是多列布局而不是挤成一列，
  // 也不能还是桌面端的 4 列（那样每张卡片只有 ~70px 宽）。
  const grid = page.locator('.product-grid').first()
  await expect(grid).toBeVisible()
  const columns = await grid.evaluate((el) => {
    const style = getComputedStyle(el)
    return style.gridTemplateColumns.split(' ').length
  })
  expect(columns, '移动端商品网格列数应在 2~3 列之间').toBeGreaterThanOrEqual(2)
  expect(columns, '移动端不应仍是桌面端的 4 列').toBeLessThanOrEqual(3)

  await page.screenshot({ path: `${SHOTS}/mobile-home.png` })
  expectCleanConsole(problems)
})

test('移动端 AI 客服窗口完整落在视口内', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  await page.getByTestId('ai-chat-fab').click()
  await settle(page)

  const chatWindow = page.getByTestId('ai-chat-window')
  await expect(chatWindow).toBeVisible()

  // 修复前客服窗写死 400px 宽，视口只有 375px —— 右边一截落在屏幕外。
  // 断言它的整个包围盒都在视口内，而不只是「可见」。
  const box = await chatWindow.boundingBox()
  const viewport = page.viewportSize()
  expect(box, '客服窗应有包围盒').not.toBeNull()
  expect(box.x, '客服窗左边不应超出视口').toBeGreaterThanOrEqual(0)
  expect(
    box.x + box.width,
    `客服窗右边超出视口（${box.x + box.width}px > ${viewport.width}px）`
  ).toBeLessThanOrEqual(viewport.width + 1)
  expect(box.y, '客服窗上边不应超出视口').toBeGreaterThanOrEqual(0)
  expect(box.y + box.height, '客服窗下边不应超出视口').toBeLessThanOrEqual(
    viewport.height + 1
  )

  // 关闭按钮必须点得到（这就是「溢出」最实际的后果）
  await expect(page.getByText('AI 智能客服')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/mobile-ai-chat.png` })

  await expectNoHorizontalOverflow(page, 'AI 客服窗口打开后')
  expectCleanConsole(problems)
})

test('移动端商品详情可读且不溢出', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)
  await page.locator('.product-grid .el-card').first().click()
  await settle(page)

  await expect(page).toHaveURL(/\/product\/\d+/)
  await expect(page.getByText('加入购物车').first()).toBeVisible()
  await expectNoHorizontalOverflow(page, '商品详情')

  await page.screenshot({ path: `${SHOTS}/mobile-product-detail.png` })
  expectCleanConsole(problems)
})
