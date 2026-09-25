import client from './client'

export const getBanners = () => client.get('/banners')
