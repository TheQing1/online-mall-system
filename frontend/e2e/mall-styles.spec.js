import { expect, test } from '@playwright/test'

import { settle } from './helpers'

/**
 * 按需引入最容易「静默变丑」：组件注册没漏、控制台也干净，但样式根本没引进来
 * ——页面能跑，只是没样式。这类问题构建阶段发现不了，所以用计算样式断言钉住。
 */

test('模板组件的样式生效（el-button 有主题色与圆角）', async ({ page }) => {
  await page.goto('/login')
  await settle(page)

  const button = page.locator('.auth-card .el-button').first()
  await expect(button).toBeVisible()
  const style = await button.evaluate((el) => {
    const s = getComputedStyle(el)
    return { background: s.backgroundColor, radius: s.borderRadius }
  })
  expect(style.background).not.toBe('rgba(0, 0, 0, 0)')
  expect(style.radius).not.toBe('0px')
})

test('服务式组件 ElMessage 的样式生效', async ({ page }) => {
  await page.goto('/login')
  await settle(page)

  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.locator('.auth-card').getByRole('button', { name: '登录' }).click()

  // ElMessage 是显式 import 的，按需引入插件管不到它，
  // 样式靠 main.js 里单独引的 message/style/css —— 这条用例就是那个改动的守门人
  const message = page.locator('.el-message').first()
  await expect(message).toBeVisible({ timeout: 10_000 })
  const style = await message.evaluate((el) => {
    const s = getComputedStyle(el)
    return { background: s.backgroundColor, padding: s.padding }
  })
  expect(style.background).not.toBe('rgba(0, 0, 0, 0)')
  expect(style.padding).not.toBe('0px')
})
