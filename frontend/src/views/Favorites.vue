<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>我的收藏</h2>
      <AsyncState
        :loading="loading"
        :error="error"
        :empty="!products.length"
        empty-text="还没有收藏商品"
        @retry="load"
      >
        <div class="grid">
          <div v-for="p in products" :key="p.id" class="fav-card">
            <img
              :src="p.images?.[0] || '/placeholder.png'"
              class="img"
              :alt="p.name"
              loading="lazy"
              @click="$router.push(`/product/${p.id}`)"
            />
            <div class="info">
              <div class="name" @click="$router.push(`/product/${p.id}`)">{{ p.name }}</div>
              <div class="price">¥{{ p.price }}</div>
            </div>
            <el-button size="small" type="danger" plain @click="remove(p.id)">取消收藏</el-button>
          </div>
        </div>
      </AsyncState>
      <el-button v-if="!products.length && !loading && !error" @click="$router.push('/')">
        去逛逛
      </el-button>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AsyncState from '@/components/AsyncState.vue'
import { getFavorites, removeFavorite } from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const products = ref([])
const loading = ref(true)
const error = ref('')

onMounted(() => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  load()
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    products.value = (await getFavorites({ page_size: 100 })).items
  } catch (e) {
    // 修复前这里是空 catch，失败时页面永远显示「还没有收藏商品」
    error.value = '收藏加载失败，请稍后重试'
    console.error('Failed to load favorites:', e)
  } finally {
    loading.value = false
  }
}

async function remove(id) {
  try {
    await removeFavorite(id)
    ElMessage.success('已取消收藏')
    load()
  } catch (e) {
    console.error('Failed to remove favorite:', e)
  }
}
</script>

<style scoped>
.container { max-width: 1100px; margin: 0 auto; padding: 0 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.fav-card { background: #fff; border-radius: 8px; padding: 10px; border: 1px solid #ebeef5; }
.img { width: 100%; height: 170px; object-fit: cover; border-radius: 6px; cursor: pointer; }
.info { padding: 8px 0; }
.name { font-size: 14px; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.price { color: #f56c6c; font-weight: bold; margin-top: 6px; }

@media (max-width: 768px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .img { height: 120px; }
}
</style>
