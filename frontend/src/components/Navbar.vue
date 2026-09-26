<template>
  <el-header class="navbar">
    <div class="nav-left">
      <router-link to="/" class="logo">🛍️ Online Mall</router-link>
    </div>
    <div class="nav-center">
      <el-input
        v-model="keyword"
        placeholder="搜索商品..."
        size="large"
        clearable
        @keyup.enter="search"
      >
        <template #append>
          <el-button @click="search" :icon="Search" />
        </template>
      </el-input>
    </div>
    <div class="nav-right">
      <router-link to="/cart">
        <el-badge :value="cartCount" :hidden="!cartCount">
          <el-button :icon="ShoppingCart" circle />
        </el-badge>
      </router-link>
      <template v-if="user">
        <el-dropdown>
          <el-button type="primary" plain>{{ user.username }}</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/orders')">我的订单</el-dropdown-item>
              <el-dropdown-item @click="$router.push('/user/favorites')">我的收藏</el-dropdown-item>
              <el-dropdown-item @click="$router.push('/user/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button @click="$router.push('/login')">登录</el-button>
        <el-button type="primary" @click="$router.push('/register')">注册</el-button>
      </template>
    </div>
  </el-header>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ShoppingCart } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const keyword = ref('')

const user = computed(() => auth.user)
const cartCount = computed(() => cart.count)

// 角标数量必须在进入应用时主动拉一次：此前只有「加入购物车」或打开购物车页面
// 才会填充 cart.count，于是刷新页面后角标总是空的。这里读取失败就当空车，不打扰用户。
function loadCart() {
  if (!auth.isLoggedIn) return
  cart.fetchCart().catch(() => {})
}

onMounted(loadCart)
watch(() => auth.isLoggedIn, loadCart)

function search() {
  if (keyword.value.trim()) {
    router.push({ path: '/search', query: { q: keyword.value.trim() } })
  }
}

function logout() {
  auth.logout()
  router.push('/')
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 40px;
  height: 64px;
  border-bottom: 1px solid #eee;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo { font-size: 20px; font-weight: bold; color: #409eff; text-decoration: none; white-space: nowrap; }
.nav-center { flex: 1; max-width: 500px; }
.nav-right { display: flex; align-items: center; gap: 12px; }
</style>
