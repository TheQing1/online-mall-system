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
        <el-descriptions-item label="下单时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="order.paid_at" label="支付时间">{{ formatDate(order.paid_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="order.refund_reason" label="退款原因">{{ order.refund_reason }}</el-descriptions-item>
        <el-descriptions-item v-if="order.refund_note" label="审核说明">{{ order.refund_note }}</el-descriptions-item>
      </el-descriptions>

      <h3 style="margin-top:20px">商品明细</h3>
      <el-table :data="order.items" style="width:100%;margin-top:12px">
        <el-table-column label="商品" prop="product_name" />
        <el-table-column label="规格" width="160" prop="sku_name" />
        <el-table-column label="单价" width="110">
          <template #default="{ row }">¥{{ row.price }}</template>
        </el-table-column>
        <el-table-column label="数量" width="80" prop="quantity" />
      </el-table>

      <div class="actions">
        <template v-if="order.status === 'pending_pay'">
          <el-button type="danger" @click="$router.push(`/payment/${order.id}`)">去支付</el-button>
          <el-button @click="handleCancel">取消订单</el-button>
        </template>
        <el-button v-if="order.status === 'shipped'" type="success" @click="handleComplete">
          确认收货
        </el-button>
        <el-button
          v-if="['paid', 'shipped', 'completed'].includes(order.status)"
          type="warning"
          plain
          @click="refundDialog = true"
        >
          申请退款
        </el-button>
      </div>

      <el-dialog v-model="refundDialog" title="申请退款" width="420">
        <el-input
          v-model="refundReason"
          type="textarea"
          :rows="3"
          placeholder="请填写退款原因，例如：不想要了 / 商品质量问题"
        />
        <template #footer>
          <el-button @click="refundDialog = false">取消</el-button>
          <el-button type="warning" :loading="refunding" @click="handleRefund">提交申请</el-button>
        </template>
      </el-dialog>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import {
  getOrder,
  cancelOrder,
  completeOrder,
  applyRefund,
} from '@/api/orders'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const order = ref(null)
const refundDialog = ref(false)
const refundReason = ref('')
const refunding = ref(false)

onMounted(() => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  load()
})

async function load() {
  try {
    order.value = await getOrder(route.params.id)
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

async function handleCancel() {
  try {
    await ElMessageBox.confirm('确认取消订单？', '提示', { type: 'warning' })
    await cancelOrder(order.value.id)
    ElMessage.success('已取消')
    load()
  } catch {}
}

async function handleComplete() {
  try {
    await ElMessageBox.confirm('确认已收到货？', '提示')
    await completeOrder(order.value.id)
    ElMessage.success('交易完成')
    load()
  } catch {}
}

async function handleRefund() {
  if (!refundReason.value.trim()) {
    ElMessage.warning('请填写退款原因')
    return
  }
  refunding.value = true
  try {
    await applyRefund(order.value.id, refundReason.value.trim())
    ElMessage.success('退款申请已提交，等待商家审核')
    refundDialog.value = false
    load()
  } catch {
  } finally {
    refunding.value = false
  }
}
</script>

<style scoped>
.container { max-width: 900px; margin: 0 auto; }
.actions { margin-top: 24px; display: flex; gap: 12px; }
</style>
