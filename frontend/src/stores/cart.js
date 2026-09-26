import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCartStore = defineStore('cart', () => {
  const count = ref(0)
  const items = ref([])

  function reset() {
    count.value = 0
    items.value = []
  }

  /**
   * 拉取购物车。失败时会清空本地状态并**继续抛出**：
   * 清空是为了不让角标显示过期的数量，抛出是为了让页面能决定要不要提示用户
   *（后台角标那类场景直接 .catch(() => {}) 忽略即可）。
   */
  async function fetchCart() {
    const token = localStorage.getItem('token')
    if (!token) {
      reset()
      return
    }
    try {
      const axios = (await import('axios')).default
      const res = await axios.get('/api/v1/cart', {
        headers: { Authorization: `Bearer ${token}` },
      })
      items.value = res.data.items || []
      count.value = res.data.total_count || 0
    } catch (e) {
      reset()
      throw e
    }
  }

  async function addItem(productId, quantity, skuId = null) {
    const token = localStorage.getItem('token')
    if (!token) return
    const axios = (await import('axios')).default
    await axios.post(
      '/api/v1/cart/items',
      { product_id: productId, sku_id: skuId, quantity },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    await fetchCart()
  }

  return { count, items, fetchCart, addItem, reset }
})
