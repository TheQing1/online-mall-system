import client from './client'

export const createOrder = (data) => client.post('/orders', data)
export const getOrders = (params) => client.get('/orders', { params })
export const getOrder = (id) => client.get(`/orders/${id}`)
export const cancelOrder = (id) => client.put(`/orders/${id}/cancel`)
