<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>知识库管理</h2>
      <el-button type="primary" @click="openDialog(null)">添加文档</el-button>
    </div>

    <el-table :data="docs" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="category" label="分类" width="120">
        <template #default="{ row }">
          <el-tag>{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑文档' : '添加文档'"
      width="600px"
      @closed="resetForm"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="文档标题" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="form.category" placeholder="选择分类" style="width:100%">
            <el-option label="商品相关" value="product" />
            <el-option label="订单相关" value="order" />
            <el-option label="退款相关" value="refund" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="8" placeholder="文档内容" />
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

const docs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)

const form = reactive({ title: '', content: '', category: 'other' })
const isEdit = computed(() => editingId.value !== null)

const categoryMap = {
  product: '商品相关',
  order: '订单相关',
  refund: '退款相关',
  other: '其他',
}

function categoryLabel(c) {
  return categoryMap[c] || c
}

async function fetchDocs() {
  loading.value = true
  try {
    const res = await client.get('/admin/knowledge')
    docs.value = res
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id
    form.title = row.title
    form.content = row.content
    form.category = row.category
  } else {
    editingId.value = null
    form.title = ''
    form.content = ''
    form.category = 'other'
  }
  dialogVisible.value = true
}

function resetForm() {
  editingId.value = null
  form.title = ''
  form.content = ''
  form.category = 'other'
}

async function handleSave() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      category: form.category,
    }
    if (isEdit.value) {
      await client.put(`/admin/knowledge/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await client.post('/admin/knowledge', payload)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchDocs()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除文档 "${row.title}" 吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await client.delete(`/admin/knowledge/${row.id}`)
    ElMessage.success('删除成功')
    fetchDocs()
  } catch {}
}

onMounted(fetchDocs)
</script>
