<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>我的订单</h2>
      <el-empty v-if="!orders.length" description="暂无订单" />
      <template v-else>
        <el-table :data="orders" style="width:100%">
          <el-table-column prop="order_no" label="订单号" width="220" />
          <el-table-column label="商品" min-width="250">
            <template #default="{ row }">
              <div v-for="item in row.items" :key="item.id" style="margin:4px 0">
                {{ item.product_name }} x{{ item.quantity }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="金额" width="120">
            <template #default="{ row }">¥{{ row.total_amount }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="$router.push(`/orders/${row.id}`)">详情</el-button>
              <el-button v-if="row.status === 'pending_pay'" size="small" type="danger" @click="handleCancel(row.id)">取消</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getOrders, cancelOrder } from '@/api/orders'

const orders = ref([])

onMounted(async () => {
  try { orders.value = (await getOrders({ page: 1, page_size: 50 })).items } catch {}
})

function statusType(s) {
  const map = { pending_pay: 'warning', paid: 'success', shipped: '', completed: 'info', cancelled: 'info', refunding: 'danger', refunded: 'info' }
  return map[s] || ''
}

function statusText(s) {
  const map = { pending_pay: '待付款', paid: '已支付', shipped: '已发货', completed: '已完成', cancelled: '已取消', refunding: '退款中', refunded: '已退款' }
  return map[s] || s
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

async function handleCancel(id) {
  try {
    await ElMessageBox.confirm('确认取消订单？', '提示', { type: 'warning' })
    await cancelOrder(id)
    ElMessage.success('已取消')
    orders.value = (await getOrders({ page: 1, page_size: 50 })).items
  } catch {}
}
</script>

<style scoped>
.container { max-width: 1100px; margin: 0 auto; }
</style>
