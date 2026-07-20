<template>
  <div>
    <Navbar />
    <el-main class="container">
      <el-card>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <h2>收货地址</h2>
          <el-button type="primary" @click="openDialog()">新增地址</el-button>
        </div>

        <el-table :data="addresses" style="width:100%">
          <el-table-column prop="receiver" label="收件人" />
          <el-table-column prop="phone" label="电话" />
          <el-table-column label="地址">
            <template #default="{ row }">
              {{ row.province }}{{ row.city }}{{ row.district }} {{ row.detail }}
              <el-tag v-if="row.is_default" type="danger" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="openDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Dialog -->
      <el-dialog :title="editing ? '编辑地址' : '新增地址'" v-model="dialogVisible" width="500px">
        <el-form :model="addrForm" label-width="80px">
          <el-form-item label="收件人"><el-input v-model="addrForm.receiver" /></el-form-item>
          <el-form-item label="电话"><el-input v-model="addrForm.phone" /></el-form-item>
          <el-form-item label="省"><el-input v-model="addrForm.province" /></el-form-item>
          <el-form-item label="市"><el-input v-model="addrForm.city" /></el-form-item>
          <el-form-item label="区"><el-input v-model="addrForm.district" /></el-form-item>
          <el-form-item label="详细地址"><el-input v-model="addrForm.detail" type="textarea" /></el-form-item>
          <el-form-item label="设为默认"><el-switch v-model="addrForm.is_default" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveAddress">保存</el-button>
        </template>
      </el-dialog>
    </el-main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { getAddresses, createAddress, updateAddress, deleteAddress } from '@/api/user'

const addresses = ref([])
const dialogVisible = ref(false)
const editing = ref(null)
const addrForm = reactive({
  receiver: '', phone: '', province: '', city: '', district: '', detail: '', is_default: false
})

onMounted(fetchAddresses)

async function fetchAddresses() {
  try { addresses.value = await getAddresses() } catch {}
}

function openDialog(row) {
  editing.value = row
  if (row) {
    Object.assign(addrForm, {
      receiver: row.receiver, phone: row.phone,
      province: row.province, city: row.city, district: row.district,
      detail: row.detail, is_default: row.is_default
    })
  } else {
    Object.assign(addrForm, { receiver: '', phone: '', province: '', city: '', district: '', detail: '', is_default: false })
  }
  dialogVisible.value = true
}

async function saveAddress() {
  try {
    if (editing.value) {
      await updateAddress(editing.value.id, addrForm)
    } else {
      await createAddress(addrForm)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchAddresses()
  } catch {}
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确认删除这个地址？', '提示', { type: 'warning' })
    await deleteAddress(id)
    ElMessage.success('删除成功')
    fetchAddresses()
  } catch {}
}
</script>

<style scoped>
.container { max-width: 1000px; margin: 0 auto; }
</style>
