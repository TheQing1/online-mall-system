import { createApp } from 'vue'
import { createPinia } from 'pinia'

// 服务式组件（能用 JS 直接调的那些）不走模板解析，按需引入插件管不到它们，
// 所以样式要在这里显式引一次。用组件的 style 入口而不是裸 theme-chalk 文件，
// 是因为它会连带把它依赖的样式（overlay 等）一起引进来。
import 'element-plus/es/components/message/style/css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)

app.mount('#app')
