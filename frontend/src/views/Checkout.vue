<template>
  <div>
    <Navbar />
    <el-main class="container">
      <h2>确认订单</h2>
      <!-- 选择地址 -->
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

      <!-- 商品清单 -->
      <el-card style="margin-bottom:16px">
        <template #header>商品清单</template>
        <el-table :data="cartItems" style="width:100%">
          <el-table-column label="商品">
            <template #default="{ row }">{{ row.product.name }}</template>
          </el-table-column>
          <el-table-column label="单价" width="100">¥{{ row.product.price }}</el-table-column>
          <el-table-column label="数量" width="80">x{{ row.quantity }}</el-table-column>
          <el-table-column label="小计" width="100">¥{{ (row.product.price * row.quantity).toFixed(2) }}</el-table-column>
        </el-table>
      </el-card>

      <!-- 备注 -->
      <el-card style="margin-bottom:16px">
        <template #header>订单备注</template>
        <el-input v-model="remark" type="textarea" placeholder="选填" />
      </el-card>

      <div class="checkout-footer">
        <span class="total">应付: ¥{{ totalAmount }}</span>
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

const router = useRouter()
const cartItems = ref([])
const addresses = ref([])
const selectedAddressId = ref(null)
const remark = ref('')
const submitting = ref(false)

const totalAmount = computed(() =>
  cartItems.value.reduce((s, i) => s + i.product.price * i.quantity, 0).toFixed(2)
)

onMounted(async () => {
  try {
    const [cart, addrs] = await Promise.all([getCart(), getAddresses()])
    cartItems.value = cart.items
    addresses.value = addrs
    if (addrs.length) {
      const def = addrs.find(a => a.is_default) || addrs[0]
      selectedAddressId.value = def.id
    }
  } catch {}
})

async function submitOrder() {
  submitting.value = true
  try {
    await createOrder({ address_id: selectedAddressId.value, remark: remark.value })
    ElMessage.success('下单成功！')
    router.push('/orders')
  } catch {} finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.container { max-width: 900px; margin: 0 auto; }
.checkout-footer { display: flex; justify-content: flex-end; align-items: center; gap: 20px; padding: 16px; background: #fff; border-radius: 8px; }
.total { font-size: 24px; font-weight: bold; color: #f56c6c; }
</style>
