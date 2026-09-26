import { createRouter, createWebHistory } from 'vue-router'

// requiresAuth 的页面统一由下面的全局守卫拦截。
// 之前是每个页面各自在 onMounted 里手写一遍判断，重复且漏掉了
// /user/profile 与 /user/addresses（未登录也能打开，然后接口 401）。
const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('@/views/ProductList.vue'),
  },
  {
    path: '/category/:id',
    name: 'Category',
    component: () => import('@/views/ProductList.vue'),
  },
  {
    path: '/product/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue'),
  },
  {
    path: '/cart',
    name: 'Cart',
    component: () => import('@/views/Cart.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/user/profile',
    name: 'UserProfile',
    component: () => import('@/views/UserProfile.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/user/addresses',
    name: 'Addresses',
    component: () => import('@/views/Addresses.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/user/favorites',
    name: 'Favorites',
    component: () => import('@/views/Favorites.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/checkout',
    name: 'Checkout',
    component: () => import('@/views/Checkout.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/payment/:id',
    name: 'Payment',
    component: () => import('@/views/Payment.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/Orders.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/orders/:id',
    name: 'OrderDetail',
    component: () => import('@/views/OrderDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 只判断有没有 token（本地存在性），真正的身份与权限校验始终在服务端：
// 过期或伪造的 token 会被接口以 401 拒绝，axios 拦截器再清 token 跳登录页。
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !localStorage.getItem('token')) {
    // 带上原目标地址，登录后可以直接回到用户本来想去的页面
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  next()
})

export default router
