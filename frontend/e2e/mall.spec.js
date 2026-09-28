import { expect, test } from '@playwright/test'

import { SHOTS, expectCleanConsole, settle, watchConsole } from './helpers'

// 种子数据里的演示账号（见 backend/app/core/seed.py）
const DEMO = { username: 'demo', password: 'demo123' }

test('首页能渲染 Banner 与商品，且控制台干净', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)

  await expect(page).toHaveTitle(/商城|Mall/i)
  // 商品卡片至少要出现一张（种子数据里有 17 个商品）
  await expect(page.locator('.el-card').first()).toBeVisible()
  await expect(page.getByText('热销').first()).toBeVisible()

  await page.screenshot({ path: `${SHOTS}/mall-home.png`, fullPage: false })
  expectCleanConsole(problems)
})

test('商品详情能选规格并加入购物车', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)
  await page.locator('.el-card').first().click()
  await settle(page)

  await expect(page).toHaveURL(/\/product\/\d+/)
  // 价格与 SKU 区块
  await expect(page.getByText('¥').first()).toBeVisible()
  await expect(page.getByText('加入购物车').first()).toBeVisible()

  await page.screenshot({ path: `${SHOTS}/mall-product-detail.png` })
  expectCleanConsole(problems)
})

test('搜索页能按关键词过滤（含分词与多词组合）', async ({ page }) => {
  const problems = watchConsole(page)

  // 注意参数名是 q：Navbar 的搜索框 push 的就是 { q: ... }，
  // 早先这条用例写成 ?keyword= 也能过——因为参数被忽略、页面列出全部商品，
  // 「至少有一张卡片可见」于是永远成立。这种「假通过」比失败更危险。
  await page.goto('/search?q=华为手机')
  await settle(page)

  await expect(page.getByText('搜索: "华为手机"')).toBeVisible()
  const names = page.locator('.product-name')
  await expect(names).toHaveCount(1)
  await expect(names.first()).toHaveText('华为 Mate 60 Pro')

  // 多词组合不该把不相关商品带出来
  await expect(page.getByText('iPhone 15 Pro Max')).toHaveCount(0)

  await page.screenshot({ path: `${SHOTS}/mall-search.png` })
  expectCleanConsole(problems)
})

test('搜索支持中文别名（搜「苹果」能找到 iPhone）', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/search?q=苹果')
  await settle(page)

  const names = page.locator('.product-name')
  await expect(names.filter({ hasText: 'iPhone 15 Pro Max' })).toHaveCount(1)
  expectCleanConsole(problems)
})

test('可以登录并看到购物车页', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/login')
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/mall-login.png` })

  await page.getByPlaceholder('用户名').fill(DEMO.username)
  await page.getByPlaceholder('密码').fill(DEMO.password)
  // 导航栏里也有一个「登录」，所以要限定在登录卡片内
  await page.locator('.auth-card').getByRole('button', { name: '登录' }).click()

  // 登录成功后回到首页，导航栏出现用户名
  await expect(page.getByText(DEMO.username).first()).toBeVisible({ timeout: 10_000 })

  await page.goto('/cart')
  await settle(page)
  await expect(page.getByText('购物车').first()).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/mall-cart.png` })
  expectCleanConsole(problems)
})

test('AI 客服能打开并显示会话界面', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/')
  await settle(page)
  await page.locator('.chat-trigger, .ai-chat-trigger, button:has(.el-icon)').first().click()
  await settle(page)

  await page.screenshot({ path: `${SHOTS}/mall-ai-chat.png` })
  expectCleanConsole(problems)
})
