<template>
  <div>
    <Navbar />
    <el-main v-if="product">
      <div class="detail">
        <div class="detail-gallery">
          <img :src="currentImage || '/placeholder.png'" class="main-img" />
          <div v-if="product.images?.length" class="thumb-list">
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
          <div class="price">¥{{ currentSku.price }}</div>
          <div class="meta">
            <span>总库存: {{ product.stock }}</span>
            <span>销量: {{ product.sales }}</span>
            <span>分类: {{ product.category_name || '未分类' }}</span>
          </div>
          <div class="description">{{ product.description || '暂无描述' }}</div>

          <!-- 规格选择 -->
          <div v-for="(values, label) in specOptions" :key="label" class="spec-row">
            <span class="spec-label">{{ label }}</span>
            <el-radio-group v-model="selectedSpecs[label]" @change="onSpecChange">
              <el-radio-button v-for="v in values" :key="v" :value="v" border>
                {{ v }}
              </el-radio-button>
            </el-radio-group>
          </div>

          <div class="meta" v-if="currentSku">
            <span>规格: {{ currentSku.name }}</span>
            <span>SKU 库存: {{ currentSku.stock }}</span>
          </div>

          <div class="actions">
            <el-input-number v-model="quantity" :min="1" :max="Math.max(currentSku.stock, 1)" />
            <el-button type="primary" size="large" @click="addToCart">加入购物车</el-button>
            <el-button type="danger" size="large" @click="buyNow">立即购买</el-button>
            <el-button size="large" :type="isFav ? 'warning' : 'default'" @click="toggleFavorite">
              {{ isFav ? '已收藏' : '收藏' }}
            </el-button>
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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getProduct } from '@/api/products'
import { addFavorite, removeFavorite } from '@/api/user'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()

const product = ref(null)
const currentImage = ref('')
const quantity = ref(1)
const selectedSkuId = ref(null)
const selectedSpecs = ref({})
const isFav = ref(false)

const specOptions = computed(() => {
  const options = {}
  for (const sku of product.value?.skus || []) {
    for (const [label, value] of Object.entries(sku.specs || {})) {
      ;(options[label] ||= new Set()).add(value)
    }
  }
  const result = {}
  for (const [k, v] of Object.entries(options)) result[k] = [...v]
  return result
})

const currentSku = computed(() =>
  product.value?.skus?.find((s) => s.id === selectedSkuId.value) || product.value?.skus?.[0] || { price: 0, stock: 0, name: '' }
)

function matchSku() {
  if (!product.value?.skus?.length) return
  if (product.value.skus.length === 1) {
    selectedSkuId.value = product.value.skus[0].id
    return
  }
  const target = product.value.skus.find((sku) =>
    Object.entries(selectedSpecs.value).every(
      ([k, v]) => (sku.specs || {})[k] === v
    )
  )
  selectedSkuId.value = target?.id || null
}

function onSpecChange() {
  matchSku()
  quantity.value = 1
}

onMounted(async () => {
  try {
    product.value = await getProduct(route.params.id)
    currentImage.value = product.value.images?.[0] || ''
    // 默认选第一组规格值，自动匹配 SKU
    for (const [label, values] of Object.entries(specOptions.value)) {
      selectedSpecs.value[label] = values[0]
    }
    matchSku()
    if (auth.isLoggedIn) {
      try {
        const res = await import('@/api/user').then((m) => m.getFavorites({ page_size: 100 }))
        isFav.value = !!res.items.find((p) => p.id === Number(route.params.id))
      } catch {}
    }
  } catch (e) {
    ElMessage.error('商品不存在或已下架')
  }
})

function requireLogin() {
  if (!auth.isLoggedIn) {
    router.push('/login')
    return false
  }
  return true
}

async function addToCart() {
  if (!requireLogin()) return
  if (!selectedSkuId.value) {
    ElMessage.warning('请先选择完整规格')
    return
  }
  try {
    await cart.addItem(product.value.id, quantity.value, selectedSkuId.value)
    ElMessage.success('已加入购物车')
  } catch {}
}

function buyNow() {
  addToCart()
  router.push('/cart')
}

async function toggleFavorite() {
  if (!requireLogin()) return
  try {
    if (isFav.value) {
      await removeFavorite(product.value.id)
      isFav.value = false
      ElMessage.success('已取消收藏')
    } else {
      await addFavorite(product.value.id)
      isFav.value = true
      ElMessage.success('收藏成功')
    }
  } catch {}
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
.meta { color: #666; margin: 12px 0; display: flex; gap: 20px; flex-wrap: wrap; }
.description { line-height: 1.8; margin: 20px 0; color: #666; }
.spec-row { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
.spec-label { min-width: 48px; color: #666; }
.actions { display: flex; gap: 12px; align-items: center; margin-top: 30px; flex-wrap: wrap; }
</style>
