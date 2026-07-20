<template>
  <div>
    <Navbar />
    <el-main class="auth-container">
      <el-card class="auth-card">
        <h2>注册</h2>
        <el-form :model="form" :rules="rules" ref="formRef" label-width="0" size="large">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="密码（至少6位）" show-password :prefix="Lock" />
          </el-form-item>
          <el-form-item prop="confirmPassword">
            <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" show-password :prefix="Lock" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleRegister" :loading="loading" style="width:100%">
              注册
            </el-button>
          </el-form-item>
        </el-form>
        <p class="auth-link">已有账号？<router-link to="/login">去登录</router-link></p>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import Navbar from '@/components/Navbar.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '', confirmPassword: '' })

const validateConfirm = (rule, value, callback) => {
  if (value !== form.password) callback(new Error('两次密码不一致'))
  else callback()
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少6位', trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validateConfirm, trigger: 'blur' }]
}

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.register(form.username, form.password)
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e) {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container { display: flex; justify-content: center; align-items: center; min-height: calc(100vh - 200px); }
.auth-card { width: 400px; }
.auth-card h2 { text-align: center; margin-bottom: 24px; }
.auth-link { text-align: center; color: #999; font-size: 14px; }
</style>
