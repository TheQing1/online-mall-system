import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElLoading } from 'element-plus'

// 服务式组件与指令不受按需引入插件管理，样式要显式引（见 frontend/src/main.js 注释）
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
// v-loading 是指令（后台表格都在用），按需引入插件不处理指令，显式注册
app.use(ElLoading)

app.mount('#app')
