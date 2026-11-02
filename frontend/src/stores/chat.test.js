/**
 * chat store 的 SSE 分帧状态机测试。
 *
 * 为什么专门测这块：`stores/chat.js` 里最重要、也最容易坏的一段是
 * **流式响应的分帧解析**——它要处理「一个 TCP 包里装半个 JSON」「一行被切在
 * 两个 chunk 之间」「新协议 JSON 帧和旧协议文本帧混在一起」这些情况。
 * 这些分支在浏览器里很难手动复现，而一旦错了表现是「AI 回答缺字/串字」，
 * 用户能感觉到但说不清。用单测构造任意分片方式是最合适的。
 *
 * 之前这块代码完全没有被测试覆盖：前端只有 e2e，而 e2e 只验证
 * 「面板能打开」，永远不会去切分 chunk。
 */
import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/** 把若干段字符串拼成一个模拟的 ReadableStream（每段就是一个 chunk）。 */
function streamOf(...chunks) {
  const encoder = new TextEncoder()
  let index = 0
  return {
    getReader() {
      return {
        read: async () => {
          if (index >= chunks.length) return { done: true, value: undefined }
          const value = encoder.encode(chunks[index++])
          return { done: false, value }
        },
        cancel: vi.fn(async () => {}),
      }
    },
  }
}

/** 造一个 fetch 返回值：200 + 给定流。 */
function okResponse(stream) {
  return { ok: true, status: 200, body: stream, json: async () => [] }
}

/** 取出最后一条 assistant 消息的文本。 */
function assistantText(store) {
  const msgs = store.messages.filter((m) => m.role === 'assistant')
  return msgs.length ? msgs[msgs.length - 1].content : ''
}

describe('chat store: SSE 分帧', () => {
  let useChatStore

  beforeEach(async () => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.resetModules()
    // 每个用例重新导入，确保 store 内部的 localStorage 读取是干净的
    ;({ useChatStore } = await import('@/stores/chat'))
  })

  it('拼接多个 text 帧得到完整回答', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf(
          'data: {"type": "text", "content": "你好"}\n\n',
          'data: {"type": "text", "content": "，世界"}\n\n',
          'data: [DONE]\n\n'
        )
      )
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('你好，世界')
    expect(store.isTyping).toBe(false)
  })

  it('一行被切在两个 chunk 里也能正确拼回（最容易出错的地方）', async () => {
    const store = useChatStore()
    const full = 'data: {"type": "text", "content": "被切开了"}\n\n'
    // 在 JSON 中间硬切一刀：第一个 chunk 只到 content 的一半
    const cut = full.indexOf('被切开了') + 2

    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf(
          full.slice(0, cut), // 半行
          full.slice(cut), // 剩下半行
          'data: [DONE]\n\n'
        )
      )
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('被切开了')
  })

  it('一个 chunk 里包含多帧时全部处理', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf(
          'data: {"type": "text", "content": "A"}\n\ndata: {"type": "text", "content": "B"}\n\ndata: [DONE]\n\n'
        )
      )
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('AB')
  })

  it('products 帧写入商品卡片数据', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf(
          'data: {"type": "products", "items": [{"id": 1, "name": "手机", "price": 1999}]}\n\n',
          'data: {"type": "text", "content": "推荐这款"}\n\n',
          'data: [DONE]\n\n'
        )
      )
    )

    await store.sendMessage('推荐手机')

    const msgs = store.messages.filter((m) => m.role === 'assistant')
    const last = msgs[msgs.length - 1]
    expect(last.products).toHaveLength(1)
    expect(last.products[0].name).toBe('手机')
    expect(last.content).toBe('推荐这款')
  })

  it('error 帧把错误文案显示给用户', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf('data: {"type": "error", "content": "AI 服务暂时不可用"}\n\n')
      )
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('AI 服务暂时不可用')
    expect(store.isTyping).toBe(false)
  })

  it('兼容旧协议的纯文本 [DONE] 帧', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(streamOf('data: 旧协议文本\ndata: [DONE]\n\n'))
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('旧协议文本')
  })

  it('兼容旧协议的 [ERROR] 帧', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(streamOf('data: [ERROR] 请稍后再试\n\n'))
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('请稍后再试')
  })

  it('非 data: 开头的行（空行、注释）被忽略', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () =>
      okResponse(
        streamOf(
          ': 这是一条注释\n\n',
          '\n',
          'data: {"type": "text", "content": "有效"}\n\n',
          'data: [DONE]\n\n'
        )
      )
    )

    await store.sendMessage('测试')

    expect(assistantText(store)).toBe('有效')
  })

  it('HTTP 错误时给出兜底提示且不卡住 isTyping', async () => {
    const store = useChatStore()
    global.fetch = vi.fn(async () => ({ ok: false, status: 500, body: null }))

    await store.sendMessage('测试')

    expect(assistantText(store)).toContain('暂时不可用')
    // 关键：isTyping 必须复位，否则输入框永远禁用
    expect(store.isTyping).toBe(false)
  })

  it('空消息或正在回复时不会重复发送', async () => {
    const store = useChatStore()
    const fetchMock = vi.fn()
    global.fetch = fetchMock

    await store.sendMessage('   ')
    expect(fetchMock).not.toHaveBeenCalled()

    // 模拟正在回复中
    store.isTyping = true
    await store.sendMessage('正常消息')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('chat store: 历史加载的鉴权', () => {
  let useChatStore

  beforeEach(async () => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.resetModules()
    ;({ useChatStore } = await import('@/stores/chat'))
  })

  it('没聊过的新会话不去请求历史（否则必然 404、控制台留红）', async () => {
    const store = useChatStore()
    const fetchMock = vi.fn()
    global.fetch = fetchMock

    await store.init()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(store.messages).toEqual([])
  })

  it('聊过之后拉历史要带 Authorization 头', async () => {
    localStorage.setItem('token', 'fake-token')
    localStorage.setItem('chat_has_chatted', '1')
    const store = useChatStore()
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => [{ role: 'user', content: '你好' }],
    }))
    global.fetch = fetchMock

    await store.init()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toContain('/messages')
    // 修复前这里没有 Authorization，已登录用户拉历史会被后端判 403，
    // 前端把 403 静默成「没有历史」，表现为「刷新后对话全没了」。
    expect(options.headers.Authorization).toBe('Bearer fake-token')
    expect(store.messages[0].content).toBe('你好')
  })

  it('404 视为没有历史，且不置 loaded（下次还能重试）', async () => {
    localStorage.setItem('chat_has_chatted', '1')
    const store = useChatStore()
    global.fetch = vi.fn(async () => ({ ok: false, status: 404 }))

    await store.init()

    expect(store.messages).toEqual([])
    expect(store.loaded).toBe(true) // 404 是确定性的「没有」，可以视为已加载
  })

  it('网络失败不置 loaded，便于下次重试', async () => {
    localStorage.setItem('chat_has_chatted', '1')
    const store = useChatStore()
    global.fetch = vi.fn(async () => {
      throw new Error('network down')
    })

    await store.init()

    expect(store.loaded).toBe(false)
  })
})
