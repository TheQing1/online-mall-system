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

  function toggle() {
    isOpen.value = !isOpen.value
    if (isOpen.value) init()
  }

  function close() {
    isOpen.value = false
  }

  async function init() {
    if (loaded.value) return
    try {
      const res = await fetch(`/api/v1/ai-chat/sessions/${sessionId.value}/messages`)
      const history = await res.json()
      messages.value = history.map((m) => ({
        role: m.role,
        content: m.content,
        products: [],
      }))
      loaded.value = true
    } catch {
      messages.value = []
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || isTyping.value) return
    loaded.value = true
    messages.value.push({ role: 'user', content: text, products: [] })
    messages.value.push({ role: 'assistant', content: '', products: [] })
    isTyping.value = true

    const token = localStorage.getItem('token')
    try {
      const response = await fetch('/api/v1/ai-chat/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId.value, message: text }),
      })
      if (!response.ok) throw new Error('Network error')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finished = false

      while (true) {
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
      await fetch(`/api/v1/ai-chat/sessions/${sessionId.value}`, { method: 'DELETE' })
    } catch {}
    sessionId.value = newSessionId()
    persistSession()
    messages.value = []
    loaded.value = true
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
  }
})
