import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const isLoggedIn = computed(() => !!user.value)

  async function login(username, password) {
    const axios = (await import('axios')).default
    const res = await axios.post('/api/v1/auth/login', { username, password })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    user.value = res.data.user
    return res.data
  }

  async function register(username, password) {
    const axios = (await import('axios')).default
    const res = await axios.post('/api/v1/auth/register', { username, password })
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('user', JSON.stringify(res.data.user))
    user.value = res.data.user
    return res.data
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    user.value = null
  }

  return { user, isLoggedIn, login, register, logout }
})
