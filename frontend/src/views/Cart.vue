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
          <el-table-column label="商品" min-width="300">
            <template #default="{ row }">
              <div style="display:flex;align-items:center;gap:12px">
                <img :src="row.product.image || '/placeholder.png'" style="width:60px;height:60px;object-fit:cover;border-radius:4px" />
                <span>{{ row.product.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="{ row }">¥{{ row.product.price }}</template>
          </el-table-column>
          <el-table-column label="数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.quantity" :min="1" size="small" @change="updateQty(row)" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="120">
            <template #default="{ row }">¥{{ (row.product.price * row.quantity).toFixed(2) }}</template>
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getCart, updateCartItem, deleteCartItem } from '@/api/cart'
import { useCartStore } from '@/stores/cart'

const cartStore = useCartStore()
const items = ref([])

const totalAmount = computed(() => items.value.reduce((sum, i) => sum + i.product.price * i.quantity, 0).toFixed(2))

onMounted(fetchCart)

async function fetchCart() {
  try {
    const res = await getCart()
    items.value = res.items
    cartStore.count = res.total_count
    cartStore.items = res.items
  } catch {}
}

async function updateQty(row) {
  try { await updateCartItem(row.id, row.quantity) } catch { fetchCart() }
}

async function removeItem(id) {
  try {
    await deleteCartItem(id)
    ElMessage.success('已删除')
    fetchCart()
  } catch {}
}
</script>

<style scoped>
.container { max-width: 1000px; margin: 0 auto; }
.cart-footer { display: flex; justify-content: flex-end; align-items: center; gap: 20px; margin-top: 20px; padding: 16px; background: #fff; border-radius: 8px; }
.total { font-size: 20px; font-weight: bold; color: #f56c6c; }
</style>
