import client from './client'

export const getProfile = () => client.get('/auth/me')
export const updateProfile = (data) => client.put('/users/profile', data)
export const getAddresses = () => client.get('/users/addresses')
export const createAddress = (data) => client.post('/users/addresses', data)
export const updateAddress = (id, data) => client.put(`/users/addresses/${id}`, data)
export const deleteAddress = (id) => client.delete(`/users/addresses/${id}`)
