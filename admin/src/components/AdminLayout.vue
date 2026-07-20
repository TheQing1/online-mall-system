<template>
  <el-container style="min-height:100vh">
    <el-aside width="220px" style="background:#304156">
      <div class="logo">🛒 商城管理</div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/admin">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据概览</span>
        </el-menu-item>
        <el-menu-item index="/admin/products">
          <el-icon><Goods /></el-icon>
          <span>商品管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/categories">
          <el-icon><Menu /></el-icon>
          <span>分类管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/orders">
          <el-icon><Document /></el-icon>
          <span>订单管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/knowledge">
          <el-icon><Reading /></el-icon>
          <span>知识库</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;justify-content:flex-end;align-items:center;border-bottom:1px solid #eee;background:#fff">
        <span style="margin-right:16px">管理员</span>
        <el-button @click="logout">退出</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { DataAnalysis, Goods, Menu, Document, User, Reading } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

function logout() {
  localStorage.removeItem('admin_token')
  router.push('/admin/login')
}
</script>

<style scoped>
.logo { color: #fff; text-align: center; padding: 16px; font-size: 18px; font-weight: bold; }
</style>
