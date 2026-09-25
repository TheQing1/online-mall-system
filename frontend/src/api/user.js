import client from './client'

export const getProfile = () => client.get('/auth/me')
export const updateProfile = (data) => client.put('/users/profile', data)
export const getAddresses = () => client.get('/users/addresses')
export const createAddress = (data) => client.post('/users/addresses', data)
export const updateAddress = (id, data) => client.put(`/users/addresses/${id}`, data)
export const deleteAddress = (id) => client.delete(`/users/addresses/${id}`)
export const getFavorites = (params) => client.get('/users/favorites', { params })
export const addFavorite = (productId) => client.post(`/users/favorites/${productId}`)
export const removeFavorite = (productId) => client.delete(`/users/favorites/${productId}`)
