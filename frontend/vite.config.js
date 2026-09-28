import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：模板里的 <el-xxx> 在构建时按需注入组件与它自己的样式，
    // 不再整包加载（原先 main.js 里 `import ElementPlus` + 全量 index.css，
    // 还把 2000 多个图标全量注册了一遍）。
    //
    // dts: false —— 本项目是 JS 不是 TS，不需要生成 auto-imports.d.ts / components.d.ts。
    //
    // 注意：插件只处理**模板里**用到的组件。显式 import 的服务式组件
    // （ElMessage / ElMessageBox / ElLoading…）不受它管，样式要在 main.js 单独引。
    AutoImport({ resolvers: [ElementPlusResolver()], dts: false }),
    Components({ resolvers: [ElementPlusResolver()], dts: false }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
