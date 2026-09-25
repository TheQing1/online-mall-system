<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>我的订单</h2>
      <el-tabs v-model="statusTab" @tab-change="fetchOrders">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane label="待支付" name="pending_pay" />
        <el-tab-pane label="已支付" name="paid" />
        <el-tab-pane label="已发货" name="shipped" />
        <el-tab-pane label="已完成" name="completed" />
        <el-tab-pane label="退款/售后" name="refunding" />
      </el-tabs>
      <el-empty v-if="!orders.length" description="暂无订单" />
      <el-table v-else :data="orders" style="width:100%">
        <el-table-column prop="order_no" label="订单号" width="200" />
        <el-table-column label="商品" min-width="240">
          <template #default="{ row }">
            <div v-for="item in row.items" :key="item.id" style="margin:4px 0">
              {{ item.product_name }}（{{ item.sku_name }}）x{{ item.quantity }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="110">
          <template #default="{ row }">¥{{ row.total_amount }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/orders/${row.id}`)">详情</el-button>
            <el-button
              v-if="row.status === 'pending_pay'"
              size="small"
              type="danger"
              @click="$router.push(`/payment/${row.id}`)"
            >
              去支付
            </el-button>
            <el-button
              v-if="row.status === 'pending_pay'"
              size="small"
              @click="handleCancel(row.id)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getOrders, cancelOrder } from '@/api/orders'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()
const orders = ref([])
const statusTab = ref('')

onMounted(() => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  fetchOrders()
})

async function fetchOrders() {
  try {
    const params = { page: 1, page_size: 50 }
    if (statusTab.value) params.status = statusTab.value
    orders.value = (await getOrders(params)).items
  } catch {}
}

function statusType(s) {
  const map = { pending_pay: 'warning', paid: 'success', shipped: 'primary', completed: 'info', cancelled: 'info', refunding: 'danger', refunded: 'info' }
  return map[s] || ''
}

function statusText(s) {
  const map = { pending_pay: '待支付', paid: '已支付', shipped: '已发货', completed: '已完成', cancelled: '已取消', refunding: '退款中', refunded: '已退款' }
  return map[s] || s
}

function formatDate(d) {
  return d ? new Date(d).toLocaleString('zh-CN') : ''
}

async function handleCancel(id) {
  try {
    await ElMessageBox.confirm('确认取消订单？库存将自动释放。', '提示', { type: 'warning' })
    await cancelOrder(id)
    ElMessage.success('已取消')
    fetchOrders()
  } catch {}
}
</script>

<style scoped>
.container { max-width: 1150px; margin: 0 auto; }
</style>
