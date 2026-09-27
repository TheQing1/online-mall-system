import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'

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
      // silent：角标刷新失败不该弹全局提示，由调用方决定是否提示
      const data = await client.get('/cart', { silent: true })
      items.value = data.items || []
      count.value = data.total_count || 0
    } catch (e) {
      reset()
      throw e
    }
  }

  async function addItem(productId, quantity, skuId = null) {
    const token = localStorage.getItem('token')
    if (!token) return
    await client.post('/cart/items', {
      product_id: productId,
      sku_id: skuId,
      quantity,
    })
    await fetchCart()
  }

  return { count, items, fetchCart, addItem, reset }
})
