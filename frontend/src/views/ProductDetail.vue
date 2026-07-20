<template>
  <div>
    <Navbar />
    <el-main v-if="product">
      <div class="detail">
        <div class="detail-gallery">
          <img :src="currentImage || '/placeholder.png'" class="main-img" />
          <div class="thumb-list">
            <img
              v-for="(img, i) in product.images"
              :key="i"
              :src="img"
              class="thumb"
              :class="{ active: img === currentImage }"
              @click="currentImage = img"
            />
          </div>
        </div>
        <div class="detail-info">
          <h1>{{ product.name }}</h1>
          <div class="price">¥{{ product.price }}</div>
          <div class="meta">
            <span>库存: {{ product.stock }}</span>
            <span>销量: {{ product.sales }}</span>
          </div>
          <div class="description">{{ product.description || '暂无描述' }}</div>
          <div class="actions">
            <el-input-number v-model="quantity" :min="1" :max="product.stock" />
            <el-button type="primary" size="large" @click="addToCart">加入购物车</el-button>
            <el-button type="danger" size="large" @click="buyNow">立即购买</el-button>
          </div>
        </div>
      </div>
    </el-main>
    <el-main v-else>
      <el-skeleton :rows="10" animated />
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getProduct } from '@/api/products'
import { useCartStore } from '@/stores/cart'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()
const product = ref(null)
const currentImage = ref('')
const quantity = ref(1)

onMounted(async () => {
  try {
    product.value = await getProduct(route.params.id)
    currentImage.value = product.value.images?.[0] || ''
  } catch (e) {
    ElMessage.error('商品不存在或已下架')
  }
})

function getToken() { return localStorage.getItem('token') }

async function addToCart() {
  if (!getToken()) { router.push('/login'); return }
  try {
    await cart.addItem(product.value.id, quantity.value)
    ElMessage.success('已加入购物车')
  } catch {}
}

function buyNow() {
  addToCart()
  router.push('/cart')
}
</script>

<style scoped>
.detail { display: flex; gap: 40px; max-width: 1200px; margin: 0 auto; }
.detail-gallery { flex: 1; max-width: 500px; }
.main-img { width: 100%; height: 400px; object-fit: cover; border-radius: 8px; }
.thumb-list { display: flex; gap: 8px; margin-top: 12px; }
.thumb { width: 60px; height: 60px; object-fit: cover; cursor: pointer; border: 2px solid transparent; border-radius: 4px; }
.thumb.active { border-color: #409eff; }
.detail-info { flex: 1; }
.price { font-size: 28px; color: #f56c6c; font-weight: bold; margin: 16px 0; }
.meta { color: #999; margin: 12px 0; display: flex; gap: 20px; }
.description { line-height: 1.8; margin: 20px 0; color: #666; }
.actions { display: flex; gap: 12px; align-items: center; margin-top: 30px; }
</style>
