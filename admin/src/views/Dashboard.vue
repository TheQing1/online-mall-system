<template>
  <div>
    <h2>数据概览</h2>
    <el-row :gutter="16" style="margin-top:20px">
      <el-col :span="6" v-for="s in stats" :key="s.label">
        <el-card>
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const stats = ref([
  { label: '用户总数', value: 0 },
  { label: '商品总数', value: 0 },
  { label: '订单总数', value: 0 },
  { label: '总销售额 (¥)', value: 0 },
])

onMounted(async () => {
  try {
    const data = await client.get('/admin/dashboard')
    stats.value[0].value = data.total_users
    stats.value[1].value = data.total_products
    stats.value[2].value = data.total_orders
    stats.value[3].value = parseFloat(data.total_revenue).toFixed(2)
  } catch {}
})
</script>

<style scoped>
.stat-label { font-size: 14px; color: #999; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; margin-top: 8px; }
</style>
