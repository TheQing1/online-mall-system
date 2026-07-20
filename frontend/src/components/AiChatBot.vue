<template>
  <div class="ai-chatbot">
    <!-- 悬浮按钮 -->
    <div class="chat-fab" @click="chat.toggle()" v-if="!chat.isOpen">
      <el-icon :size="24"><ChatDotRound /></el-icon>
    </div>

    <!-- 聊天窗口 -->
    <el-card class="chat-window" v-if="chat.isOpen" shadow="always">
      <template #header>
        <div class="chat-header">
          <span>🤖 AI 智能客服</span>
          <el-button :icon="Close" circle size="small" @click="chat.close()" />
        </div>
      </template>

      <!-- 消息列表 -->
      <div class="chat-messages" ref="msgContainer">
        <div v-if="!chat.messages.length" class="chat-empty">
          <p>👋 你好！我是商城 AI 客服</p>
          <p>有什么可以帮你的吗？</p>
        </div>
        <div
          v-for="(msg, i) in chat.messages"
          :key="i"
          :class="['chat-msg', msg.role]"
        >
          <div class="msg-bubble">{{ msg.content }}</div>
          <div v-if="chat.isTyping && i === chat.messages.length - 1 && !msg.content" class="typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="chat-input">
        <el-input
          v-model="inputText"
          placeholder="输入你的问题..."
          @keyup.enter="send"
          :disabled="chat.isTyping"
        >
          <template #append>
            <el-button @click="send" :disabled="chat.isTyping || !inputText.trim()" type="primary">
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, Close } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const inputText = ref('')
const msgContainer = ref(null)

async function send() {
  if (!inputText.value.trim() || chat.isTyping) return
  const text = inputText.value
  inputText.value = ''
  await chat.sendMessage(text)
  scrollToBottom()
}

watch(() => chat.messages.length, () => {
  nextTick(scrollToBottom)
})

function scrollToBottom() {
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.ai-chatbot { position: fixed; bottom: 24px; right: 24px; z-index: 1000; }
.chat-fab {
  width: 56px; height: 56px; border-radius: 50%;
  background: #409eff; color: #fff; display: flex;
  align-items: center; justify-content: center;
  cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.chat-fab:hover { transform: scale(1.1); }
.chat-window { width: 380px; height: 520px; display: flex; flex-direction: column; }
.chat-header { display: flex; justify-content: space-between; align-items: center; }
.chat-messages {
  flex: 1; overflow-y: auto; padding: 8px 0;
  min-height: 350px; max-height: 350px;
}
.chat-empty { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }
.chat-msg { margin-bottom: 12px; }
.chat-msg.user { text-align: right; }
.chat-msg.user .msg-bubble {
  display: inline-block; background: #409eff; color: #fff;
  padding: 8px 14px; border-radius: 16px 4px 16px 16px;
  max-width: 80%; word-break: break-word; font-size: 14px;
}
.chat-msg.assistant .msg-bubble {
  display: inline-block; background: #f0f0f0; color: #333;
  padding: 8px 14px; border-radius: 4px 16px 16px 16px;
  max-width: 80%; word-break: break-word; font-size: 14px;
}
.chat-input { margin-top: 8px; }
.typing-dots { display: flex; gap: 4px; padding: 8px 14px; }
.typing-dots span {
  width: 8px; height: 8px; border-radius: 50%;
  background: #ccc; animation: typing 1.4s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }
</style>
