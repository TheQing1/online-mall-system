<template>
  <div>
    <h2 style="margin-bottom:16px">用户管理</h2>

    <el-table :data="users" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getActive(row) ? 'success' : 'info'">
            {{ getActive(row) ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            size="small"
            :type="getActive(row) ? 'warning' : 'success'"
            @click="handleToggleActive(row)"
          >
            {{ getActive(row) ? '禁用' : '启用' }}
          </el-button>
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
        @size-change="fetchUsers"
        @current-change="fetchUsers"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function fetchUsers() {
  loading.value = true
  try {
    const res = await client.get('/admin/users', {
      params: { page: page.value, page_size: pageSize.value }
    })
    users.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function getActive(row) {
  return row.is_active !== undefined ? row.is_active : true
}

async function handleToggleActive(row) {
  const action = getActive(row) ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定${action}用户 "${row.username}" 吗？`, '确认操作', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await client.put(`/admin/users/${row.id}/toggle-active`)
    row.is_active = !getActive(row)
    ElMessage.success(`用户已${action}`)
  } catch {}
}

onMounted(fetchUsers)
</script>
