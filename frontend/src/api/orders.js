import client from './client'

export const createOrder = (data) => client.post('/orders', data)
export const getOrders = (params) => client.get('/orders', { params })
export const getOrder = (id) => client.get(`/orders/${id}`)
export const cancelOrder = (id) => client.put(`/orders/${id}/cancel`)
export const payOrder = (id) => client.post(`/orders/${id}/pay`)
export const completeOrder = (id) => client.put(`/orders/${id}/complete`)
export const applyRefund = (id, reason) => client.post(`/orders/${id}/refund`, { reason })
