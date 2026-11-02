import { createApp } from 'vue'
import { createPinia } from 'pinia'

// 服务式组件（能用 JS 直接调的那些）不走模板解析，按需引入插件管不到它们，
// 所以样式要在这里显式引一次。用组件的 style 入口而不是裸 theme-chalk 文件，
// 是因为它会连带把它依赖的样式（overlay 等）一起引进来。
//
// 教训：一开始只引了 message，漏了 message-box。构建**不报错**、lint 也不报错，
// 只有在「删除地址 / 取消订单 / 确认收货」弹确认框时才会看到没有背景、没有按钮
// 样式的裸 DOM。抓法是把 dist 里的 CSS 和实际用到的服务式组件对一遍：
//   grep -o 'el-message-box' frontend/dist/assets/*.css | wc -l   # 修复前为 0
// 现在用 ElMessageBox 的页面有 Addresses / OrderDetail / Orders 三个。
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)

app.mount('#app')
