<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>购物车</h2>
      <AsyncState
        :loading="loading"
        :error="error"
        :empty="!items.length"
        empty-text="购物车是空的"
        @retry="fetchCart"
      >
        <el-table :data="items" style="width:100%">
          <el-table-column label="商品" min-width="260">
            <template #default="{ row }">
              <div style="display:flex;align-items:center;gap:12px">
                <img :src="row.product.image || '/placeholder.png'" :alt="row.product.name" style="width:60px;height:60px;object-fit:cover;border-radius:4px" />
                <div>
                  <div>{{ row.product.name }}</div>
                  <div class="sku-text">{{ row.sku_name }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="{ row }">¥{{ row.unit_price }}</template>
          </el-table-column>
          <el-table-column label="数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.quantity" :min="1" size="small" @change="updateQty(row)" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="120">
            <template #default="{ row }">¥{{ (Number(row.unit_price) * row.quantity).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button type="danger" size="small" @click="removeItem(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="cart-footer">
          <span class="total">合计: ¥{{ totalAmount }}</span>
          <el-button type="danger" size="large" @click="$router.push('/checkout')">去结算</el-button>
        </div>
      </AsyncState>
      <el-button v-if="!items.length && !loading && !error" @click="$router.push('/')">
        去逛逛
      </el-button>
    </el-main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AsyncState from '@/components/AsyncState.vue'
import { updateCartItem, deleteCartItem } from '@/api/cart'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const auth = useAuthStore()
const cartStore = useCartStore()
const loading = ref(true)
const error = ref('')

// 单一数据源：本地不再维护一份 items，直接读 store，
// 避免「页面里一份、store 里一份」两处状态不同步。
const items = computed(() => cartStore.items)

const totalAmount = computed(() =>
  items.value.reduce((s, i) => s + Number(i.unit_price) * i.quantity, 0).toFixed(2)
)

onMounted(() => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  fetchCart()
})

async function fetchCart() {
  loading.value = true
  error.value = ''
  try {
    await cartStore.fetchCart()
  } catch (e) {
    // 修复前只弹一条 toast，页面上仍是「购物车是空的」空态
    error.value = '购物车加载失败，请稍后重试'
    console.error('Failed to load cart:', e)
  } finally {
    loading.value = false
  }
}

async function updateQty(row) {
  try {
    await updateCartItem(row.id, row.quantity)
  } catch (e) {
    // 拦截器已经弹过全局提示，这里不再重复弹（避免双 toast）
    console.error('Failed to update cart item:', e)
  } finally {
    // 无论成功失败都以服务端为准刷新，失败时把数量回滚成真实值
    fetchCart()
  }
}

async function removeItem(id) {
  try {
    await deleteCartItem(id)
    ElMessage.success('已删除')
  } catch (e) {
    console.error('Failed to delete cart item:', e)
  } finally {
    fetchCart()
  }
}
</script>

<style scoped>
.container { max-width: 1000px; margin: 0 auto; padding: 0 16px; }
.sku-text { font-size: 12px; color: #909399; margin-top: 2px; }
.cart-footer { display: flex; justify-content: flex-end; align-items: center; gap: 20px; margin-top: 20px; padding: 16px; background: #fff; border-radius: 8px; }

@media (max-width: 768px) {
  .cart-footer { flex-direction: column; align-items: stretch; gap: 12px; }
  .total { font-size: 17px; text-align: right; }
}
.total { font-size: 20px; font-weight: bold; color: #f56c6c; }
</style>
