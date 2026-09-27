import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

// 登录接口返回 401/400 是业务结果（账号密码错误、无管理员权限），不是「会话过期」。
// 提示交给登录页自己渲染，避免输错密码时触发整页跳转刷新。
const CALLER_HANDLED_PATHS = ['/auth/login']

client.interceptors.request.use(config => {
  const token = localStorage.getItem('admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  response => response.data,
  error => {
    const config = error.config || {}
    // silent：不弹全局提示、也不触发跳转，错误完全交给调用方。
    // 用于路由守卫里的身份探测（守卫自己会跳登录页）。
    const callerHandlesError =
      config.silent ||
      CALLER_HANDLED_PATHS.some(path => (config.url || '').startsWith(path))

    if (!callerHandlesError) {
      ElMessage.error(error.response?.data?.detail || '请求失败')
      if (error.response?.status === 401) {
        localStorage.removeItem('admin_token')
        window.location.href = '/admin/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
