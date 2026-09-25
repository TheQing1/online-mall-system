<template>
  <div>
    <div class="header">
      <h2>Banner 管理</h2>
      <el-button type="primary" @click="openDialog(null)">添加 Banner</el-button>
    </div>
    <el-table :data="banners" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="图片" width="180">
        <template #default="{ row }">
          <img :src="row.image" style="width:160px;height:60px;object-fit:cover;border-radius:4px" />
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="link" label="跳转链接" min-width="160" />
      <el-table-column prop="sort" label="排序" width="70" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑 Banner' : '添加 Banner'" width="520px" @closed="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="跳转链接">
          <el-input v-model="form.link" placeholder="/search?keyword=手机" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="图片" required>
          <img v-if="form.image" :src="form.image" style="width:320px;height:120px;object-fit:cover;border-radius:6px;margin-bottom:8px;display:block" />
          <el-upload
            :action="uploadUrl" :headers="uploadHeaders" :show-file-list="false"
            :on-success="onUploadSuccess" accept="image/*"
          >
            <el-button>上传图片</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const banners = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({ title: '', image: '', link: '', sort: 0, is_active: true })

const uploadUrl = '/api/v1/admin/upload'
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('admin_token')}` }))
const isEdit = computed(() => editingId.value !== null)

function resetForm() {
  editingId.value = null
  Object.assign(form, { title: '', image: '', link: '', sort: 0, is_active: true })
}

function onUploadSuccess(res) {
  form.image = res.url
  ElMessage.success('上传成功')
}

async function fetchBanners() {
  loading.value = true
  try {
    banners.value = await client.get('/admin/banners')
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id
    Object.assign(form, {
      title: row.title,
      image: row.image,
      link: row.link || '',
      sort: row.sort,
      is_active: row.is_active,
    })
  } else {
    resetForm()
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.title || !form.image) {
    ElMessage.warning('标题与图片必填')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, link: form.link || null }
    if (isEdit.value) await client.put(`/admin/banners/${editingId.value}`, payload)
    else await client.post('/admin/banners', payload)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchBanners()
  } catch {
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除 Banner「${row.title}」吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await client.delete(`/admin/banners/${row.id}`)
    ElMessage.success('删除成功')
    fetchBanners()
  } catch {}
}

onMounted(fetchBanners)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
