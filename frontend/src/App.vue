<template>
  <router-view />
  <AiChatBot />
</template>

<script setup>
import AiChatBot from '@/components/AiChatBot.vue'
</script>

<style>
/* 全局样式 */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f5f7fa; color: #333; }
a { color: #409eff; text-decoration: none; }
</style>
