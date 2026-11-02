/**
 * axios 拦截器的行为测试。
 *
 * 这块是最值得单测的「胶水逻辑」之一：全局错误提示、401 跳登录、
 * 以及哪些接口**不该**走全局提示。这些规则出错的表现都很隐蔽——
 * 比如登录失败时触发整页跳转，把用户填好的表单冲掉。
 *
 * 注：Element Plus 的 ElMessage 在这里用 mock 替代，我们只关心
 * 「该不该弹」和「弹什么」，不关心它长什么样。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const messageError = vi.fn()

vi.mock('element-plus', () => ({
  ElMessage: { error: (...args) => messageError(...args) },
}))

/** 造一个 axios 形状的错误对象。 */
function httpError(status, detail, config = {}) {
  return {
    config,
    response: { status, data: detail ? { detail } : {} },
  }
}

describe('api/client 拦截器', () => {
  let requestHandlers
  let responseHandlers

  beforeEach(async () => {
    vi.resetModules()
    messageError.mockClear()
    localStorage.clear()

    // 用一个假的 axios.create 截获注册的拦截器，
    // 这样不需要真的发请求就能直接调用它们。
    requestHandlers = []
    responseHandlers = []
    vi.doMock('axios', () => ({
      default: {
        create: () => ({
          interceptors: {
            request: { use: (fn) => requestHandlers.push(fn) },
            response: { use: (ok, fail) => responseHandlers.push({ ok, fail }) },
          },
        }),
      },
    }))

    // 导入只为触发拦截器注册，本身不需要在用例里直接调用
    await import('@/api/client')
  })

  it('请求拦截器在有 token 时补上 Authorization', () => {
    localStorage.setItem('token', 'tk-123')
    const config = { headers: {} }

    const result = requestHandlers[0](config)

    expect(result.headers.Authorization).toBe('Bearer tk-123')
  })

  it('没有 token 时不加 Authorization 头', () => {
    const config = { headers: {} }
    const result = requestHandlers[0](config)
    expect(result.headers.Authorization).toBeUndefined()
  })

  it('响应成功时直接返回 data（而不是整个 response）', () => {
    const { ok } = responseHandlers[0]
    expect(ok({ data: { items: [1, 2] } })).toEqual({ items: [1, 2] })
  })

  it('普通请求失败时弹全局错误提示', () => {
    const { fail } = responseHandlers[0]
    const err = httpError(500, '服务器错误', { url: '/products' })

    fail(err).catch(() => {})

    expect(messageError).toHaveBeenCalledWith('服务器错误')
  })

  it('401 时清掉 token 并跳转登录页', () => {
    localStorage.setItem('token', 'expired')
    // jsdom 不允许真的改 location.href，用 defineProperty 截获赋值
    const assign = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })

    const { fail } = responseHandlers[0]
    fail(httpError(401, '未授权', { url: '/orders' })).catch(() => {})

    expect(localStorage.getItem('token')).toBeNull()
    expect(window.location.href).toBe('/login')
    expect(assign).not.toHaveBeenCalled()
  })

  it('登录接口失败**不**触发全局提示与跳转（否则会冲掉用户填的表单）', () => {
    localStorage.setItem('token', 'tk')

    const { fail } = responseHandlers[0]
    // 密码错误返回 401，但它不是「会话过期」
    fail(httpError(401, '用户名或密码错误', { url: '/auth/login' })).catch(() => {})

    expect(messageError).not.toHaveBeenCalled()
    // token 不应被清掉，也不应跳转
    expect(localStorage.getItem('token')).toBe('tk')
  })

  it('注册接口失败同样交给调用方处理', () => {
    const { fail } = responseHandlers[0]
    fail(httpError(400, '用户名已存在', { url: '/auth/register' })).catch(() => {})
    expect(messageError).not.toHaveBeenCalled()
  })

  it('config.silent 为真时完全静默（用于角标刷新等预期失败）', () => {
    const { fail } = responseHandlers[0]
    fail(httpError(500, '炸了', { url: '/cart', silent: true })).catch(() => {})
    expect(messageError).not.toHaveBeenCalled()
  })

  it('错误始终以 reject 传回，调用方仍能自己处理', async () => {
    const { fail } = responseHandlers[0]
    const err = httpError(500, '服务器错误', { url: '/products' })

    await expect(fail(err)).rejects.toBe(err)
  })

  it('没有 detail 时回退到通用文案', () => {
    const { fail } = responseHandlers[0]
    fail(httpError(500, null, { url: '/products' })).catch(() => {})
    expect(messageError).toHaveBeenCalledWith('请求失败')
  })
})
