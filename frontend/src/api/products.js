import client from './client'

export const getProducts = (params) => client.get('/products', { params })
export const getProduct = (id) => client.get(`/products/${id}`)
export const getCategories = () => client.get('/products/categories')
