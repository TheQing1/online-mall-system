import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isOpen = ref(false)
  const isTyping = ref(false)

  function toggle() {
    isOpen.value = !isOpen.value
  }

  function close() {
    isOpen.value = false
  }

  async function sendMessage(text) {
    if (!text.trim()) return

    // 添加用户消息
    messages.value.push({ role: 'user', content: text })
    // 添加空的 AI 消息占位
    messages.value.push({ role: 'assistant', content: '' })
    isTyping.value = true

    const token = localStorage.getItem('token')

    try {
      const response = await fetch('/api/v1/ai-chat/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ message: text })
      })

      if (!response.ok) throw new Error('Network error')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            if (data.startsWith('[ERROR]')) {
              const lastMsg = messages.value[messages.value.length - 1]
              lastMsg.content = data.slice(8) // Remove "[ERROR] " prefix
              continue
            }
            const lastMsg = messages.value[messages.value.length - 1]
            lastMsg.content += data
          }
        }
      }
    } catch (e) {
      const lastMsg = messages.value[messages.value.length - 1]
      lastMsg.content = '抱歉，AI 客服暂时不可用，请稍后再试。'
    } finally {
      isTyping.value = false
    }
  }

  return { messages, isOpen, isTyping, toggle, close, sendMessage }
})
