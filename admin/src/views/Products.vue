<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>商品管理</h2>
      <el-button type="primary" @click="openDialog(null)">添加商品</el-button>
    </div>

    <el-table :data="products" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="price" label="价格" width="100">
        <template #default="{ row }">¥{{ row.price }}</template>
      </el-table-column>
      <el-table-column prop="stock" label="库存" width="80" />
      <el-table-column prop="sales" label="销量" width="80" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'on' ? 'success' : 'danger'">
            {{ row.status === 'on' ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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
        @size-change="fetchProducts"
        @current-change="fetchProducts"
      />
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑商品' : '添加商品'"
      width="520px"
      @closed="resetForm"
    >
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="商品名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="商品描述" />
        </el-form-item>
        <el-form-item label="价格" required>
          <el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="库存" required>
          <el-input-number v-model="form.stock" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" placeholder="选择分类" clearable style="width:100%">
            <el-option
              v-for="cat in flatCategories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="图片">
          <div>
            <div v-for="(img, i) in form.images" :key="i" style="display:inline-block;position:relative;margin:0 8px 8px 0">
              <img :src="img" style="width:80px;height:80px;object-fit:cover;border-radius:4px" />
              <el-button
                type="danger" size="small" circle
                style="position:absolute;top:-8px;right:-8px"
                :icon="Close"
                @click="form.images.splice(i, 1)"
              />
            </div>
            <el-upload
              :action="uploadUrl"
              :headers="uploadHeaders"
              :show-file-list="false"
              :before-upload="beforeUpload"
              :on-success="onUploadSuccess"
              accept="image/*"
              style="display:inline-block"
            >
              <el-button type="primary" plain :icon="Plus" :loading="uploading">上传图片</el-button>
            </el-upload>
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="form.statusOn"
            active-text="上架"
            inactive-text="下架"
          />
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
import { Close, Plus } from '@element-plus/icons-vue'
import client from '@/api/client'

const products = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const dialogVisible = ref(false)
const saving = ref(false)
const uploading = ref(false)
const editingId = ref(null)
const categories = ref([])
const formRef = ref(null)

const uploadUrl = '/api/v1/admin/upload'
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('admin_token')}`
}))

const form = reactive({
  name: '',
  description: '',
  price: 0,
  stock: 0,
  images: [],
  category_id: null,
  statusOn: true,
})

function beforeUpload(file) {
  const valid = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!valid.includes(file.type)) {
    ElMessage.error('仅支持 JPG/PNG/GIF/WebP 格式')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('图片不能超过 2MB')
    return false
  }
  uploading.value = true
  return true
}

function onUploadSuccess(res) {
  form.images.push(res.url)
  uploading.value = false
  ElMessage.success('上传成功')
}

const isEdit = computed(() => editingId.value !== null)

// Flatten categories tree for select
const flatCategories = computed(() => {
  const result = []
  function walk(list, prefix = '') {
    for (const cat of list) {
      result.push({ id: cat.id, name: prefix + cat.name })
      if (cat.children && cat.children.length) {
        walk(cat.children, prefix + '-- ')
      }
    }
  }
  walk(categories.value)
  return result
})

async function fetchProducts() {
  loading.value = true
  try {
    const res = await client.get('/admin/products', {
      params: { page: page.value, page_size: pageSize.value }
    })
    products.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function fetchCategories() {
  try {
    const res = await client.get('/admin/categories')
    categories.value = res
  } catch {}
}

function openDialog(row) {
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.description = row.description || ''
    form.price = parseFloat(row.price)
    form.stock = row.stock
    form.images = row.images || []
    form.category_id = row.category_id
    form.statusOn = row.status === 'on'
  } else {
    editingId.value = null
  }
  dialogVisible.value = true
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.description = ''
  form.price = 0
  form.stock = 0
  form.images = []
  form.category_id = null
  form.statusOn = true
}

async function handleSave() {
  if (!form.name) {
    ElMessage.warning('请输入商品名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description || null,
      price: form.price,
      stock: form.stock,
      images: form.images,
      category_id: form.category_id,
      status: form.statusOn ? 'on' : 'off',
    }
    if (isEdit.value) {
      await client.put(`/admin/products/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await client.post('/admin/products', payload)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchProducts()
  } catch {
    // Error handled by interceptor
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除商品 "${row.name}" 吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await client.delete(`/admin/products/${row.id}`)
    ElMessage.success('删除成功')
    fetchProducts()
  } catch {}
}

onMounted(() => {
  fetchProducts()
  fetchCategories()
})
</script>
