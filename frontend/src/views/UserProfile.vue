<template>
  <div>
    <Navbar />
    <el-main class="profile-container">
      <el-card>
        <h2>个人资料</h2>
        <el-form :model="form" label-width="80px" style="max-width:500px">
          <el-form-item label="用户名">
            <el-input :value="auth.user?.username" disabled />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="请输入邮箱" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="form.phone" placeholder="请输入手机号" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="save" :loading="loading">保存</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import { useAuthStore } from '@/stores/auth'
import { updateProfile } from '@/api/user'

const auth = useAuthStore()
const loading = ref(false)
const form = reactive({
  email: auth.user?.email || '',
  phone: auth.user?.phone || '',
})

async function save() {
  loading.value = true
  try {
    await updateProfile({ email: form.email, phone: form.phone })
    ElMessage.success('保存成功')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.profile-container { max-width: 800px; margin: 0 auto; }
</style>
