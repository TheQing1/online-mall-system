<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>分类管理</h2>
      <el-button type="primary" @click="openDialog(null)">添加分类</el-button>
    </div>

    <el-table :data="categories" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column prop="sort" label="排序" width="100" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑分类' : '添加分类'"
      width="420px"
      @closed="resetForm"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="分类名称" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const categories = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)

const form = reactive({ name: '', sort: 0 })
const isEdit = computed(() => editingId.value !== null)

async function fetchCategories() {
  loading.value = true
  try {
    const res = await client.get('/admin/categories')
    categories.value = res
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.sort = row.sort
  } else {
    editingId.value = null
    form.name = ''
    form.sort = 0
  }
  dialogVisible.value = true
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.sort = 0
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  saving.value = true
  try {
    const payload = { name: form.name.trim(), sort: form.sort }
    if (isEdit.value) {
      await client.put(`/admin/categories/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await client.post('/admin/categories', payload)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchCategories()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除分类 "${row.name}" 吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await client.delete(`/admin/categories/${row.id}`)
    ElMessage.success('删除成功')
    fetchCategories()
  } catch {}
}

onMounted(fetchCategories)
</script>
