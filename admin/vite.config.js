import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

// 同商城前台：dev 与 preview 共用代理，端到端测试跑在 preview 上
const proxy = {
  '/api': { target: 'http://localhost:8000', changeOrigin: true },
  '/static': { target: 'http://localhost:8000', changeOrigin: true }
}

export default defineConfig({
  plugins: [
    vue(),
    // 同商城前台：Element Plus 按需引入，详见 frontend/vite.config.js 的注释
    AutoImport({ resolvers: [ElementPlusResolver()], dts: false }),
    Components({ resolvers: [ElementPlusResolver()], dts: false }),
  ],
  base: '/admin/',
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  server: {
    port: 5174,
    proxy
  },
  preview: {
    port: 5174,
    proxy
  }
})
