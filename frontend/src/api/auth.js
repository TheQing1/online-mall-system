import client from './client'

export const login = (username, password) => client.post('/auth/login', { username, password })
export const register = (username, password) => client.post('/auth/register', { username, password })
