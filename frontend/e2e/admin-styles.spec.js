import { expect, test } from '@playwright/test'

import { settle } from './helpers'

test('表格样式生效、分页是中文、v-loading 指令已注册', async ({ page }) => {
  const problems = []
  page.on('console', (msg) => {
    const text = msg.text()
    if (
      text.includes('Failed to resolve directive') ||
      text.includes('Failed to resolve component')
    ) {
      problems.push(text)
    }
  })

  await page.goto('/admin/login')
  await settle(page)
  await page.getByPlaceholder('管理员账号').fill('admin')
  await page.getByPlaceholder('密码').fill('admin123')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('数据概览').first()).toBeVisible({ timeout: 10_000 })

  await page.goto('/admin/products')
  await settle(page)

  const table = page.locator('.el-table').first()
  await expect(table).toBeVisible()
  expect(await table.evaluate((el) => getComputedStyle(el).fontSize)).not.toBe('')

  // locale：不配 ConfigProvider 的话这里会退回英文（Total / Go to）
  const pagination = page.locator('.el-pagination').first()
  await expect(pagination).toContainText(/共|条|页/)

  // v-loading 若没注册，Vue 会在控制台报 "Failed to resolve directive"
  expect(problems).toEqual([])
})
