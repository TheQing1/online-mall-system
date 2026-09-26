<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>购物车</h2>
      <el-empty v-if="!items.length" description="购物车是空的">
        <el-button type="primary" @click="$router.push('/')">去逛逛</el-button>
      </el-empty>
      <template v-else>
        <el-table :data="items" style="width:100%">
          <el-table-column label="商品" min-width="260">
            <template #default="{ row }">
              <div style="display:flex;align-items:center;gap:12px">
                <img :src="row.product.image || '/placeholder.png'" style="width:60px;height:60px;object-fit:cover;border-radius:4px" />
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
      </template>
    </el-main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { updateCartItem, deleteCartItem } from '@/api/cart'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const auth = useAuthStore()
const cartStore = useCartStore()

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
  try {
    await cartStore.fetchCart()
  } catch {
    ElMessage.error('购物车加载失败，请稍后重试')
  }
}

async function updateQty(row) {
  try {
    await updateCartItem(row.id, row.quantity)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '修改数量失败')
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
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    fetchCart()
  }
}
</script>

<style scoped>
.container { max-width: 1000px; margin: 0 auto; }
.sku-text { font-size: 12px; color: #909399; margin-top: 2px; }
.cart-footer { display: flex; justify-content: flex-end; align-items: center; gap: 20px; margin-top: 20px; padding: 16px; background: #fff; border-radius: 8px; }
.total { font-size: 20px; font-weight: bold; color: #f56c6c; }
</style>
