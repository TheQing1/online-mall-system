import client from './client'

export const getCart = () => client.get('/cart')
export const addCartItem = (productId, quantity) => client.post('/cart/items', { product_id: productId, quantity })
export const updateCartItem = (itemId, quantity) => client.put(`/cart/items/${itemId}`, { quantity })
export const deleteCartItem = (itemId) => client.delete(`/cart/items/${itemId}`)
