import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useChatStore } from '@/stores/chat'
import { login as loginApi, register as registerApi } from '@/api/auth'

/**
 * 读取本地缓存的用户信息。
 * localStorage 里的内容可能被手工改坏、或残留旧版本的结构，
 * 直接 JSON.parse 会抛异常并让整个应用白屏（store 是在模块初始化时求值的），
 * 所以这里兜底：解析失败就清掉这份脏数据当作未登录。
 */
function readStoredUser() {
  const raw = localStorage.getItem('user')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    localStorage.removeItem('user')
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref(readStoredUser())
  const isLoggedIn = computed(() => !!user.value)

  function persist(data) {
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    user.value = data.user
  }

  async function login(username, password) {
    const data = await loginApi(username, password)
    persist(data)
    return data
  }

  async function register(username, password) {
    const data = await registerApi(username, password)
    persist(data)
    return data
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    user.value = null
    // 购物车角标要跟着清掉，否则退出后还显示上一个用户的件数
    useCartStore().reset()
    // 会话 id 也要清：它绑定的是上一个用户的会话，留着会让下一个登录的人
    // 拿着别人的 session_id 请求（现在后端会正确地返回 403），表现为无法对话
    useChatStore().reset()
  }

  return { user, isLoggedIn, login, register, logout }
})
