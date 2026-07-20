<template>
  <div>
    <Navbar />
    <el-main class="container" v-if="order">
      <h2>订单详情</h2>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(order.status)">{{ statusText(order.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="收货人">{{ order.address_snapshot?.receiver }}</el-descriptions-item>
        <el-descriptions-item label="电话">{{ order.address_snapshot?.phone }}</el-descriptions-item>
        <el-descriptions-item label="地址" :span="2">
          {{ order.address_snapshot?.province }}{{ order.address_snapshot?.city }}{{ order.address_snapshot?.district }} {{ order.address_snapshot?.detail }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ order.remark || '无' }}</el-descriptions-item>
        <el-descriptions-item label="总金额">¥{{ order.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
      </el-descriptions>

      <h3 style="margin-top:20px">商品明细</h3>
      <el-table :data="order.items" style="width:100%;margin-top:12px">
        <el-table-column label="商品" prop="product_name" />
        <el-table-column label="单价" width="120">
          <template #default="{ row }">¥{{ row.price }}</template>
        </el-table-column>
        <el-table-column label="数量" width="80" prop="quantity" />
      </el-table>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import { getOrder } from '@/api/orders'

const route = useRoute()
const order = ref(null)

onMounted(async () => {
  try { order.value = await getOrder(route.params.id) } catch {}
})

function statusType(s) {
  const map = { pending_pay: 'warning', paid: 'success', shipped: '', completed: 'info', cancelled: 'info', refunding: 'danger', refunded: 'info' }
  return map[s] || ''
}
function statusText(s) {
  const map = { pending_pay: '待付款', paid: '已支付', shipped: '已发货', completed: '已完成', cancelled: '已取消', refunding: '退款中', refunded: '已退款' }
  return map[s] || s
}
function formatDate(d) { return d ? new Date(d).toLocaleString('zh-CN') : '' }
</script>

<style scoped>
.container { max-width: 900px; margin: 0 auto; }
</style>
