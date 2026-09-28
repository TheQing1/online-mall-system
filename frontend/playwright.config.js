// 端到端冒烟测试：真浏览器打开真页面，验证「页面能不能用」。
//
// 与单测的分工：单元测试该测纯逻辑，这里只管「渲染出来了吗、点得动吗、
// 控制台有没有报错」——尤其是按需引入组件这类改动，缺样式或组件没注册
// 在构建阶段是发现不了的，只有真跑一遍才知道。
//
// 前置：后端跑在 :8000，商城跑在 :5173，后台跑在 :5174。
//
//   # 登录接口按 IP 限流（默认 10 次/分钟），而 E2E 每轮要登录 3 次，
//   # 连跑几轮就会自己撞上限流返回 429 —— 跑 E2E 时把配额调大：
//   RATE_LIMIT_LOGIN=1000 uvicorn app.main:app --port 8000
//   npm run test:e2e
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    locale: 'zh-CN',
  },
  projects: [
    {
      name: 'mall',
      // 注意：testMatch 匹配的是完整路径，不能写 ^ 锚定文件名
      testMatch: /mall(-styles)?\.spec\.js$/,
      use: { baseURL: 'http://localhost:5173' },
    },
    {
      name: 'admin',
      testMatch: /admin(-styles)?\.spec\.js$/,
      use: { baseURL: 'http://localhost:5174' },
    },
  ],
})
