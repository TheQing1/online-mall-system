<template>
  <div>
    <Navbar />
    <el-main class="container" v-if="order">
      <el-card class="pay-card">
        <template #header>模拟收银台</template>
        <div class="pay-info">
          <div class="order-no">订单号：{{ order.order_no }}</div>
          <div class="amount">¥{{ order.total_amount }}</div>
          <div class="receiver">
            收货人：{{ order.address_snapshot?.receiver }} {{ order.address_snapshot?.phone }}
          </div>
          <el-alert
            title="当前为页面化模拟支付，后续可无缝切换微信支付/支付宝（预留回调接口）"
            type="info"
            :closable="false"
            style="margin: 12px 0"
          />
        </div>
        <div class="pay-actions">
          <el-button size="large" @click="$router.push('/orders')">稍后支付</el-button>
          <el-button type="success" size="large" :loading="paying" @click="pay">
            确认支付（模拟成功）
          </el-button>
        </div>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getOrder, payOrder } from '@/api/orders'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const order = ref(null)
const paying = ref(false)

onMounted(async () => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  try {
    order.value = await getOrder(route.params.id)
    if (order.value.status !== 'pending_pay') {
      ElMessage.info('订单已处理')
      router.replace(`/orders/${order.value.id}`)
    }
  } catch (e) {
    // 原来这里是空 catch：加载失败时收银台就是一片空白，用户完全不知道发生了什么
    ElMessage.error(e.response?.data?.detail || '订单加载失败，请稍后重试')
    router.replace('/orders')
  }
})

async function pay() {
  paying.value = true
  try {
    await payOrder(order.value.id)
    ElMessage.success('支付成功')
    router.push(`/orders/${order.value.id}`)
  } catch (e) {
    // 常见原因：订单已被超时自动关单，或状态已变更。必须把原因告诉用户
    ElMessage.error(e.response?.data?.detail || '支付失败，请稍后重试')
  } finally {
    paying.value = false
  }
}
</script>

<style scoped>
.container { max-width: 640px; margin: 60px auto; }
.pay-card { text-align: center; }
.pay-info { padding: 20px; }
.order-no { color: #909399; margin-bottom: 12px; }
.amount { font-size: 44px; font-weight: bold; color: #f56c6c; margin-bottom: 16px; }
.receiver { color: #606266; margin-bottom: 8px; }
.pay-actions { display: flex; justify-content: center; gap: 16px; padding-bottom: 10px; }
</style>
