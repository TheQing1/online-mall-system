// 搜索自动补全的端到端用例。
//
// 为什么单独写一个文件：这块的交互细节（防抖、键盘上下选择、回车提交、
// 点击选中、无结果提示）在真浏览器里才测得出来，单测只能覆盖纯逻辑。
import { expect, test } from '@playwright/test'

import { SHOTS, expectCleanConsole, settle, watchConsole } from './helpers'

test('输入关键词会弹出搜索建议，且高亮命中部分', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  const input = page.locator('.nav-center input').first()
  await input.click()
  await input.fill('华为')

  // 防抖 180ms + 网络往返，给足余量
  const panel = page.getByTestId('suggest-panel')
  await expect(panel).toBeVisible({ timeout: 5000 })

  // 至少要有华为相关的商品
  await expect(panel).toContainText('华为')

  // 命中的前缀应该是 `<em>`（红色），而不是纯文本
  const highlighted = panel.locator('em').first()
  await expect(highlighted).toBeVisible()
  await expect(highlighted).toHaveText('华为')

  await page.screenshot({ path: `${SHOTS}/mall-search-suggest.png` })
  expectCleanConsole(problems)
})

test('键盘上下键可以选择建议，回车提交搜索', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  const input = page.locator('.nav-center input').first()
  await input.click()
  await input.fill('华为')

  const panel = page.getByTestId('suggest-panel')
  await expect(panel).toBeVisible({ timeout: 5000 })

  // 按一次下键：第一项应该高亮
  await input.press('ArrowDown')
  await expect(page.getByTestId('suggest-item-0')).toHaveClass(/active/)

  // 再按一次：第二项高亮
  await input.press('ArrowDown')
  await expect(page.getByTestId('suggest-item-1')).toHaveClass(/active/)

  // 按上键回到第一项
  await input.press('ArrowUp')
  await expect(page.getByTestId('suggest-item-0')).toHaveClass(/active/)

  // 回车提交：应该跳转到搜索结果页，且 q 参数是选中的建议文本
  const expected = (await page.getByTestId('suggest-item-0').innerText()).trim()
  await input.press('Enter')
  await expect(page).toHaveURL(/\/search\?/)

  const url = new URL(page.url())
  expect(url.searchParams.get('q')).toBeTruthy()
  expect(expected).toContain(url.searchParams.get('q').slice(0, 2))

  expectCleanConsole(problems)
})

test('点击建议项直接跳到搜索结果', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  const input = page.locator('.nav-center input').first()
  await input.click()
  await input.fill('苹果')

  const panel = page.getByTestId('suggest-panel')
  await expect(panel).toBeVisible({ timeout: 5000 })

  const firstItem = page.getByTestId('suggest-item-0')
  const text = (await firstItem.innerText()).trim()
  await firstItem.click()

  await expect(page).toHaveURL(/\/search\?/)
  expect(new URL(page.url()).searchParams.get('q')).toBeTruthy()
  // 下拉在选中后应当收起
  await expect(page.getByTestId('suggest-panel')).toBeHidden()

  expectCleanConsole(problems)
})

test('输入无匹配内容时给出「没有找到」提示而不是空白下拉', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  const input = page.locator('.nav-center input').first()
  await input.click()
  await input.fill('zzz不存在的商品zzz')

  // 无结果面板有独立的 testid：它与建议列表是互斥的两种状态，
  // 共用一个 testid 会让断言分不清「有结果」还是「没结果」
  const empty = page.getByTestId('suggest-empty')
  await expect(empty).toContainText('没有找到', { timeout: 5000 })

  expectCleanConsole(problems)
})

test('Esc 关闭建议面板', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  const input = page.locator('.nav-center input').first()
  await input.click()
  await input.fill('华为')

  const panel = page.getByTestId('suggest-panel')
  await expect(panel).toBeVisible({ timeout: 5000 })

  await input.press('Escape')
  await expect(panel).toBeHidden()

  expectCleanConsole(problems)
})
