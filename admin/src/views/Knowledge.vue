<template>
  <div>
    <div class="header">
      <h2>知识库管理</h2>
      <div>
        <el-button @click="importVisible = true">批量导入</el-button>
        <el-button type="primary" @click="openDialog(null)">添加文档</el-button>
      </div>
    </div>

    <el-table :data="docs" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="220" />
      <el-table-column prop="category" label="分类" width="110">
        <template #default="{ row }">
          <el-tag>{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="内容预览" min-width="280" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="175" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑文档' : '添加文档'" width="640px" @closed="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="文档标题（同步后作为检索出处）" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="form.category" style="width:100%">
            <el-option label="商品相关" value="product" />
            <el-option label="订单相关" value="order" />
            <el-option label="退款相关" value="refund" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="form.content" type="textarea" :rows="10" placeholder="文档内容；保存后将增量同步到向量索引，AI 客服立即生效" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存并同步索引</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="批量导入文档" width="520px">
      <el-form label-width="90px">
        <el-form-item label="分类">
          <el-select v-model="importCategory" style="width:100%">
            <el-option label="商品相关" value="product" />
            <el-option label="订单相关" value="order" />
            <el-option label="退款相关" value="refund" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            drag multiple :auto-upload="false" :limit="20"
            accept=".md,.txt" v-model:file-list="importFiles"
          >
            <el-icon style="font-size:40px;color:#c0c4cc"><UploadFilled /></el-icon>
            <div>拖拽或点击选择 .md / .txt 文件（支持多选）</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">导入并同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import client from '@/api/client'

const docs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const importVisible = ref(false)
const importing = ref(false)
const importCategory = ref('other')
const importFiles = ref([])

const form = reactive({ title: '', content: '', category: 'other' })
const isEdit = computed(() => editingId.value !== null)

const categoryMap = { product: '商品相关', order: '订单相关', refund: '退款相关', other: '其他' }
function categoryLabel(c) {
  return categoryMap[c] || c
}

async function fetchDocs() {
  loading.value = true
  try {
    docs.value = await client.get('/admin/knowledge')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editingId.value = null
  Object.assign(form, { title: '', content: '', category: 'other' })
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id
    Object.assign(form, {
      title: row.title,
      content: row.content,
      category: row.category,
    })
  } else {
    resetForm()
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('请填写标题与内容')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content.trim(),
      category: form.category,
    }
    if (isEdit.value) await client.put(`/admin/knowledge/${editingId.value}`, payload)
    else await client.post('/admin/knowledge', payload)
    ElMessage.success('保存成功，向量索引已同步')
    dialogVisible.value = false
    fetchDocs()
  } catch {
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${row.title}」吗？对应向量将同时移除。`, '确认删除', {
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

async function doImport() {
  const files = importFiles.value.map((f) => f.raw).filter(Boolean)
  if (!files.length) {
    ElMessage.warning('请选择文件')
    return
  }
  importing.value = true
  const fd = new FormData()
  fd.append('category', importCategory.value)
  files.forEach((f) => fd.append('files', f))
  try {
    const res = await client.post('/admin/knowledge/import', fd)
    ElMessage.success(res.message || '导入成功')
    importVisible.value = false
    importFiles.value = []
    fetchDocs()
  } catch {
  } finally {
    importing.value = false
  }
}

onMounted(fetchDocs)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
