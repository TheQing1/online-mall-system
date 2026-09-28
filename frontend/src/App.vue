<template>
  <!-- 原先是通过 app.use(ElementPlus, { locale: zhCn }) 设置中文；
       按需引入后没有全局注册这回事了，改用 ConfigProvider 包住根组件。
       不做这一步的话分页、表格空状态这类内置文案会退回英文。 -->
  <el-config-provider :locale="zhCn">
    <router-view />
    <AiChatBot />
  </el-config-provider>
</template>

<script setup>
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import AiChatBot from '@/components/AiChatBot.vue'
</script>

<style>
/* 全局样式 */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f5f7fa; color: #333; }
a { color: #409eff; text-decoration: none; }
</style>
