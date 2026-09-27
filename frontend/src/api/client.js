import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

// 登录/注册返回 401/400 是业务结果（密码错误、用户名已占用），不是「会话过期」。
// 这两个接口的错误提示交给调用方（登录页用表单下方的小字提示）；如果走全局提示，
// 输错一次密码就会触发「跳转登录页 + 整页刷新」，把用户已经填好的内容冲掉。
const CALLER_HANDLED_PATHS = ['/auth/login', '/auth/register']

client.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  response => response.data,
  error => {
    const config = error.config || {}
    // silent：既不弹全局提示、也不触发 401 跳转，错误完全交给调用方。
    // 用于「失败属于预期结果」的场景（购物车角标刷新、路由守卫里的身份探测）。
    const callerHandlesError =
      config.silent ||
      CALLER_HANDLED_PATHS.some(path => (config.url || '').startsWith(path))

    if (!callerHandlesError) {
      ElMessage.error(error.response?.data?.detail || '请求失败')
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
