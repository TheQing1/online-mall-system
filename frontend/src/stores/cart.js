import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCartStore = defineStore('cart', () => {
  const count = ref(0)
  const items = ref([])

  async function fetchCart() {
    // Will be implemented when cart API is ready
    const token = localStorage.getItem('token')
    if (!token) return
    try {
      const axios = (await import('axios')).default
      const res = await axios.get('/api/v1/cart', {
        headers: { Authorization: `Bearer ${token}` }
      })
      items.value = res.data.items || []
      count.value = res.data.total_count || 0
    } catch {}
  }

  async function addItem(productId, quantity) {
    const token = localStorage.getItem('token')
    if (!token) return
    const axios = (await import('axios')).default
    await axios.post('/api/v1/cart/items', { product_id: productId, quantity }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    await fetchCart()
  }

  return { count, items, fetchCart, addItem }
})
