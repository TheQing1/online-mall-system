import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes = [
  {
    path: '/admin',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAdmin: true }
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/AdminLogin.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAdmin) {
    const token = localStorage.getItem('admin_token')
    if (!token) {
      next('/admin/login')
      return
    }
    // Verify token still valid by checking /auth/me
    try {
      const axios = (await import('axios')).default
      const res = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.data.role !== 'admin') {
        ElMessage.error('无管理员权限')
        next('/admin/login')
        return
      }
    } catch {
      localStorage.removeItem('admin_token')
      next('/admin/login')
      return
    }
  }
  next()
})

export default router
