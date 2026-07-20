import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

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
    const msg = error.response?.data?.detail || '请求失败'
    ElMessage.error(msg)
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
