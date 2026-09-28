import { expect, test } from '@playwright/test'

import { SHOTS, expectCleanConsole, settle, watchConsole } from './helpers'

const ADMIN = { username: 'admin', password: 'admin123' }

test('后台能用管理员账号登录并进入看板', async ({ page }) => {
  const problems = watchConsole(page)

  await page.goto('/admin/login')
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/admin-login.png` })

  await page.getByPlaceholder('管理员账号').fill(ADMIN.username)
  await page.getByPlaceholder('密码').fill(ADMIN.password)
  await page.getByRole('button', { name: '登录' }).click()

  // 看板标题（Dashboard.vue 里是「数据概览」）
  await expect(page.getByText('数据概览').first()).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.el-menu').first()).toBeVisible()
  await settle(page)
  await page.screenshot({ path: `${SHOTS}/admin-dashboard.png` })
  expectCleanConsole(problems)
})
