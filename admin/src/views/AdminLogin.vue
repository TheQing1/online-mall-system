<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>管理员登录</h2>
      <el-form :model="form" ref="formRef" label-width="0" size="large" @keyup.enter="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="管理员账号" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="loading" style="width:100%">登录</el-button>
        </el-form-item>
      </el-form>
      <p v-if="error" style="color:#f56c6c;text-align:center">{{ error }}</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const res = await axios.post('/api/v1/auth/login', form)
    if (res.data.user.role !== 'admin') {
      error.value = '无管理员权限'
      return
    }
    localStorage.setItem('admin_token', res.data.access_token)
    router.push('/admin')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f0f2f5; }
.login-card { width: 400px; }
.login-card h2 { text-align: center; margin-bottom: 24px; }
</style>
