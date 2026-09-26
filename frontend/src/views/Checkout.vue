<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>确认订单</h2>
      <el-card style="margin-bottom:16px">
        <template #header>收货地址</template>
        <el-radio-group v-model="selectedAddressId">
          <el-radio v-for="addr in addresses" :key="addr.id" :value="addr.id" border style="margin:8px;padding:12px">
            {{ addr.receiver }} {{ addr.phone }} — {{ addr.province }}{{ addr.city }}{{ addr.district }} {{ addr.detail }}
          </el-radio>
        </el-radio-group>
        <el-empty v-if="!addresses.length" description="请先添加收货地址">
          <el-button @click="$router.push('/user/addresses')">去添加</el-button>
        </el-empty>
      </el-card>

      <el-card style="margin-bottom:16px">
        <template #header>商品清单</template>
        <el-table :data="cartItems" style="width:100%">
          <el-table-column label="商品">
            <template #default="{ row }">
              <div>
                <div>{{ row.product.name }}</div>
                <div class="sku-text">{{ row.sku_name }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="100">
            <template #default="{ row }">¥{{ row.unit_price }}</template>
          </el-table-column>
          <el-table-column label="数量" width="80">
            <template #default="{ row }">x{{ row.quantity }}</template>
          </el-table-column>
          <el-table-column label="小计" width="110">
            <template #default="{ row }">¥{{ (Number(row.unit_price) * row.quantity).toFixed(2) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card style="margin-bottom:16px">
        <template #header>订单备注</template>
        <el-input v-model="remark" type="textarea" placeholder="选填" />
      </el-card>

      <div class="checkout-footer">
        <div>
          <div class="tip">下单后请在 30 分钟内完成支付，超时订单将自动取消</div>
          <span class="total">应付: ¥{{ totalAmount }}</span>
        </div>
        <el-button type="danger" size="large" @click="submitOrder" :loading="submitting" :disabled="!selectedAddressId">
          提交订单
        </el-button>
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getCart } from '@/api/cart'
import { getAddresses } from '@/api/user'
import { createOrder } from '@/api/orders'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const cartItems = ref([])
const addresses = ref([])
const selectedAddressId = ref(null)
const remark = ref('')
const submitting = ref(false)

const totalAmount = computed(() =>
  cartItems.value.reduce((s, i) => s + Number(i.unit_price) * i.quantity, 0).toFixed(2)
)

onMounted(async () => {
  if (!auth.isLoggedIn) {
    router.replace('/login')
    return
  }
  try {
    const [cart, addrs] = await Promise.all([getCart(), getAddresses()])
    cartItems.value = cart.items
    addresses.value = addrs
    if (addrs.length) {
      const def = addrs.find((a) => a.is_default) || addrs[0]
      selectedAddressId.value = def.id
    }
  } catch (e) {
    // 空 catch 会让「购物车为空 / 地址加载失败」都表现成一个没有内容的确认页
    ElMessage.error(e.response?.data?.detail || '结算信息加载失败，请稍后重试')
  }
})

async function submitOrder() {
  submitting.value = true
  try {
    const order = await createOrder({
      address_id: selectedAddressId.value,
      remark: remark.value,
    })
    ElMessage.success('下单成功，请尽快完成支付')
    router.push(`/payment/${order.id}`)
  } catch {
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.container { max-width: 900px; margin: 0 auto; }
.sku-text { font-size: 12px; color: #909399; }
.checkout-footer { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 16px; background: #fff; border-radius: 8px; }
.total { font-size: 24px; font-weight: bold; color: #f56c6c; }
.tip { font-size: 12px; color: #909399; margin-bottom: 4px; }
</style>
