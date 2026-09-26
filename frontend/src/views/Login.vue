<template>
  <div>
    <Navbar />
    <el-main class="auth-container">
      <el-card class="auth-card">
        <h2>登录</h2>
        <el-form :model="form" :rules="rules" ref="formRef" label-width="0" size="large">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="密码" show-password :prefix="Lock" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleLogin" :loading="loading" style="width:100%">
              登录
            </el-button>
          </el-form-item>
        </el-form>
        <p class="auth-link">还没有账号？<router-link to="/register">立即注册</router-link></p>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import Navbar from '@/components/Navbar.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    // 被路由守卫拦下来时会带上 redirect，登录后回到原本要去的页面。
    // 只接受站内相对路径，避免被构造成 ?redirect=//evil.com 这种开放重定向。
    const redirect = route.query.redirect
    const target = typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
      ? redirect
      : '/'
    router.replace(target)
  } catch (e) {
    const msg = e.response?.data?.detail || '登录失败，请稍后重试'
    ElMessage.error(msg)
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
