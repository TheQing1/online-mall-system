<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>我的收藏</h2>
      <el-empty v-if="!products.length" description="还没有收藏商品">
        <el-button type="primary" @click="$router.push('/')">去逛逛</el-button>
      </el-empty>
      <div class="grid" v-else>
        <div v-for="p in products" :key="p.id" class="fav-card">
          <img
            :src="p.images?.[0] || '/placeholder.png'"
            class="img"
            @click="$router.push(`/product/${p.id}`)"
          />
          <div class="info">
            <div class="name" @click="$router.push(`/product/${p.id}`)">{{ p.name }}</div>
            <div class="price">¥{{ p.price }}</div>
          </div>
          <el-button size="small" type="danger" plain @click="remove(p.id)">取消收藏</el-button>
        </div>
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getFavorites, removeFavorite } from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const products = ref([])

onMounted(() => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  load()
})

async function load() {
  try {
    products.value = (await getFavorites({ page_size: 100 })).items
  } catch {}
}

async function remove(id) {
  try {
    await removeFavorite(id)
    ElMessage.success('已取消收藏')
    load()
  } catch {}
}
</script>

<style scoped>
.container { max-width: 1100px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.fav-card { background: #fff; border-radius: 8px; padding: 10px; border: 1px solid #ebeef5; }
.img { width: 100%; height: 170px; object-fit: cover; border-radius: 6px; cursor: pointer; }
.info { padding: 8px 0; }
.name { font-size: 14px; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.price { color: #f56c6c; font-weight: bold; margin-top: 6px; }
</style>
