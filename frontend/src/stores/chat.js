import { defineStore } from 'pinia'
import { ref } from 'vue'

function newSessionId() {
  if (crypto?.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isOpen = ref(false)
  const isTyping = ref(false)
  const loaded = ref(false)

  const sessionId = ref(localStorage.getItem('chat_session_id') || newSessionId())

  function persistSession() {
    localStorage.setItem('chat_session_id', sessionId.value)
  }

  /** 当前会话是否已经产生过消息（决定 init 要不要去服务端拉历史）。
   *
   * 服务端在收到第一条消息时才创建会话记录，所以「未聊过」= 拉历史必然 404。
   * 用一个 localStorage 标记代替试探性请求，既省一次往返，也不会在控制台
   * 留下一条 404。标记随 sessionId 一起重置。 */
  function hasChatted() {
    return localStorage.getItem('chat_has_chatted') === '1'
  }

  function markChatted() {
    localStorage.setItem('chat_has_chatted', '1')
  }

  function toggle() {
    isOpen.value = !isOpen.value
    if (isOpen.value) init()
  }

  function close() {
    isOpen.value = false
  }

  /** 统一的鉴权头：历史拉取与发消息必须用同一套，否则会出现
   *  「能发新消息但看不到历史」的割裂（见 init 的注释）。 */
  function authHeaders() {
    const token = localStorage.getItem('token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  async function init() {
    if (loaded.value) return
    // 会话是否存在过：服务端只在**收到第一条消息时**才创建会话记录
    // （见 ai_chat.chat 里的 get_or_create_session）。还没聊过的新会话去拉历史
    // 必然 404——虽然前端能容错，但浏览器控制台仍会记一条 "Failed to load
    // resource: 404"，而 e2e 断言「控制台零报错」会因此失败。
    // 这里直接跳过请求：没有消息就没有历史可拉，不必先问服务端要一个 404。
    if (!hasChatted()) {
      messages.value = []
      loaded.value = true
      return
    }
    try {
      // 必须带 token。会话一旦绑定到某个用户（后端 chat_service.get_accessible_session），
      // 匿名读取会直接 403；而下面的 catch 会把 403 静默成「历史为空」，
      // 表现为「刷新页面后 AI 对话全没了」。修复前这里就是裸 fetch、没有头。
      const res = await fetch(`/api/v1/ai-chat/sessions/${sessionId.value}/messages`, {
        headers: authHeaders(),
      })
      if (res.status === 404) {
        // 服务端记录已不存在（例如被清理），等同于没有历史
        messages.value = []
        loaded.value = true
        return
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const history = await res.json()
      messages.value = history.map((m) => ({
        role: m.role,
        content: m.content,
        products: [],
      }))
      loaded.value = true
    } catch {
      // 真正失败（断网 / 403 / 5xx）时不要把 loaded 置真：下次打开面板还会重试
      messages.value = []
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || isTyping.value) return
    loaded.value = true
    messages.value.push({ role: 'user', content: text, products: [] })
    messages.value.push({ role: 'assistant', content: '', products: [] })
    isTyping.value = true
    // 从这一刻起服务端会存下这条消息，之后 init 就能正常拉到历史
    markChatted()

    try {
      const response = await fetch('/api/v1/ai-chat/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ session_id: sessionId.value, message: text }),
      })
      if (!response.ok) throw new Error('Network error')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finished = false

      // 收到 [DONE]/[ERROR] 后就没必要继续读了：服务器在这之后只会关闭连接
      while (!finished) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          const lastMsg = messages.value[messages.value.length - 1]
          if (!lastMsg) continue

          try {
            const payload = JSON.parse(data)
            if (payload.type === 'done') {
              finished = true
            } else if (payload.type === 'error') {
              lastMsg.content = payload.content
              finished = true
            } else if (payload.type === 'products') {
              lastMsg.products = payload.items || []
            } else if (payload.type === 'text') {
              lastMsg.content += payload.content || ''
            }
          } catch {
            // 兼容旧协议文本帧
            if (data === '[DONE]') finished = true
            else if (data.startsWith('[ERROR]')) {
              lastMsg.content = data.slice(8)
              finished = true
            } else lastMsg.content += data
          }
        }
      }
      // 提前跳出循环时要主动取消，否则这条连接不会被回收
      if (finished) await reader.cancel()
    } catch {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg) lastMsg.content = '抱歉，AI 客服暂时不可用，请稍后再试。'
    } finally {
      isTyping.value = false
    }
  }

  async function newConversation() {
    // 清除历史会话，开一个新会话
    try {
      await fetch(`/api/v1/ai-chat/sessions/${sessionId.value}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
    } catch {
      // 删除失败也照样开新会话：本地状态才是用户直接感知到的东西
    }
    reset()
    loaded.value = true
  }

  /** 退出登录/切换用户时调用：丢弃会话 id 与内存中的消息。 */
  function reset() {
    sessionId.value = newSessionId()
    persistSession()
    // 新会话还没有任何消息，标记要一起清掉，否则会去拉一个必然 404 的历史
    localStorage.removeItem('chat_has_chatted')
    messages.value = []
    loaded.value = false
    isTyping.value = false
  }

  persistSession()
  return {
    messages,
    isOpen,
    isTyping,
    loaded,
    toggle,
    close,
    init,
    sendMessage,
    newConversation,
    reset,
  }
})
