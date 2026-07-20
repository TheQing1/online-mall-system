<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>订单管理</h2>
      <el-select v-model="statusFilter" placeholder="筛选状态" clearable style="width:160px" @change="fetchOrders">
        <el-option label="待支付" value="pending_pay" />
        <el-option label="已支付" value="paid" />
        <el-option label="已发货" value="shipped" />
        <el-option label="已完成" value="completed" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="退款中" value="refunding" />
        <el-option label="已退款" value="refunded" />
      </el-select>
    </div>

    <el-table :data="orders" border stripe v-loading="loading">
      <el-table-column prop="order_no" label="订单号" width="200" />
      <el-table-column prop="user_id" label="用户ID" width="80" />
      <el-table-column prop="total_amount" label="金额" width="100">
        <template #default="{ row }">¥{{ row.total_amount }}</template>
      </el-table-column>
      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <el-select
            :model-value="row.status"
            size="small"
            style="width:120px"
            @change="(val) => handleStatusChange(row, val)"
          >
            <el-option label="待支付" value="pending_pay" />
            <el-option label="已支付" value="paid" />
            <el-option label="已发货" value="shipped" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="退款中" value="refunding" />
            <el-option label="已退款" value="refunded" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="showDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px;display:flex;justify-content:flex-end">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchOrders"
        @current-change="fetchOrders"
      />
    </div>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="订单详情" width="600px">
      <div v-if="currentOrder">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ currentOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="用户ID">{{ currentOrder.user_id }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ currentOrder.total_amount }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(currentOrder.status) }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ currentOrder.created_at }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ currentOrder.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin-top:16px">商品明细</h4>
        <el-table :data="currentOrder.items" border size="small">
          <el-table-column prop="product_name" label="商品" />
          <el-table-column prop="price" label="单价" width="100" />
          <el-table-column prop="quantity" label="数量" width="80" />
        </el-table>
        <h4 style="margin-top:16px">收货地址</h4>
        <p v-if="currentOrder.address_snapshot">
          {{ currentOrder.address_snapshot.receiver }}
          {{ currentOrder.address_snapshot.phone }}<br/>
          {{ currentOrder.address_snapshot.province }}
          {{ currentOrder.address_snapshot.city }}
          {{ currentOrder.address_snapshot.district }}
          {{ currentOrder.address_snapshot.detail }}
        </p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import client from '@/api/client'

const orders = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const statusFilter = ref('')

const detailVisible = ref(false)
const currentOrder = ref(null)

const statusMap = {
  pending_pay: '待支付',
  paid: '已支付',
  shipped: '已发货',
  completed: '已完成',
  cancelled: '已取消',
  refunding: '退款中',
  refunded: '已退款',
}

function statusLabel(s) {
  return statusMap[s] || s
}

async function fetchOrders() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await client.get('/admin/orders', { params })
    orders.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function handleStatusChange(row, newStatus) {
  try {
    await client.put(`/admin/orders/${row.id}/status`, null, {
      params: { status: newStatus }
    })
    row.status = newStatus
    ElMessage.success('状态更新成功')
  } catch {}
}

function showDetail(row) {
  currentOrder.value = row
  detailVisible.value = true
}

onMounted(fetchOrders)
</script>
