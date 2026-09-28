import { expect } from '@playwright/test'

export const SHOTS = '../docs/screenshots'

/**
 * 收集控制台里的问题。
 *
 * 按需引入组件最容易出的两类问题都会在这里现形：
 * - "Failed to resolve component: el-xxx" —— 组件没注册
 * - "Failed to resolve directive: loading" —— 指令没注册（v-loading）
 * - pageerror / 未捕获异常 —— 运行时炸了
 */
export function watchConsole(page) {
  const problems = []
  page.on('console', (msg) => {
    const text = msg.text()
    // Vite 开发服务器自己的消息（依赖预构建、HMR 重载）不是应用问题；
    // 首次启动时它可能让页面重载一次，不过滤掉就会变成偶发失败。
    if (text.includes('[vite]')) return
    const suspicious =
      text.includes('Failed to resolve component') ||
      text.includes('Failed to resolve directive')
    if (msg.type() === 'error' || suspicious) {
      problems.push(`[${msg.type()}] ${text}`)
    }
  })
  page.on('pageerror', (err) => problems.push(`[pageerror] ${err.message}`))
  return problems
}

export function expectCleanConsole(problems) {
  expect(problems, `控制台不应有报错：\n${problems.join('\n')}`).toEqual([])
}

/** 等 Element Plus 的表格/卡片渲染完，避免截到骨架屏。 */
export async function settle(page) {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(400)
}
