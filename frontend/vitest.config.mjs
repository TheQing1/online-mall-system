import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// 单元测试单独一份配置，不复用 vite.config.js：
// 构建配置里有 Element Plus 的按需引入插件，那些在 jsdom 下既没必要、
// 还会拉慢启动。单测要的是「快」和「确定」，不是和生产构建一模一样。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // 只收 src 下的 *.test.js，避免把 e2e/ 里的 Playwright 用例当成单测收集
    include: ['src/**/*.test.js'],
    // e2e 跑的是真浏览器，和单测互不干扰
    exclude: ['node_modules', 'dist', 'e2e'],
  },
})
