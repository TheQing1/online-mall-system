import client from './client'

export const getProducts = (params) => client.get('/products', { params })
export const getProduct = (id) => client.get(`/products/${id}`)
export const getCategories = () => client.get('/products/categories')

/**
 * 搜索建议（自动补全）。
 *
 * `silent: true`：用户边打字边请求，失败（断网、限流 429）属于**预期结果**，
 * 不该弹全局错误提示——否则删两个字就会跳出一堆红条。下拉不显示即可。
 */
export const getSuggestions = (q, limit = 8) =>
  client.get('/products/suggest', { params: { q, limit }, silent: true })
