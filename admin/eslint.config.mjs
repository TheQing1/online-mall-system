// ESLint 扁平配置（ESLint 9+）。
//
// 依赖已在 devDependencies 里（eslint / @eslint/js / eslint-plugin-vue / prettier），
// 直接 `npm run lint`（等价于 `npx eslint .`）；CI 里也会跑同一条命令。
//
// 只开「正确性」规则、不引格式规则：格式交给 Prettier，
// 避免两套工具互相打架产生大量无关改动。
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
    rules: {
      // 单文件组件名如 Cart.vue / Home.vue 是路由页面，不是复用组件
      'vue/multi-word-component-names': 'off',
      // <script setup> 的编译宏由 Vue 编译器校验，no-undef 会误报
      'no-undef': 'off',
      // 先降级为警告：存量代码里还有不少空 catch 与未使用变量，
      // 清理完再改成 error，这样 lint 从接入第一天起就能跑绿。
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-empty': ['warn', { allowEmptyCatch: true }],
      // 真正想拦住的问题
      'no-debugger': 'error',
      'no-dupe-keys': 'error',
      'no-unreachable': 'error',
      eqeqeq: ['warn', 'smart'],
    },
  },
]
