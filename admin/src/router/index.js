import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const routes = [
  {
    path: '/admin',
    component: () => import('@/components/AdminLayout.vue'),
    meta: { requiresAdmin: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'products', name: 'AdminProducts', component: () => import('@/views/Products.vue') },
      { path: 'categories', name: 'AdminCategories', component: () => import('@/views/Categories.vue') },
      { path: 'orders', name: 'AdminOrders', component: () => import('@/views/Orders.vue') },
      { path: 'users', name: 'AdminUsers', component: () => import('@/views/Users.vue') },
      { path: 'knowledge', name: 'AdminKnowledge', component: () => import('@/views/Knowledge.vue') },
    ]
  },
  {
    path: '/admin/login',
    name: 'AdminLogin',
    component: () => import('@/views/AdminLogin.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue')
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
