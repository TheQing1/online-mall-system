<template>
  <div class="ai-chatbot">
    <div class="chat-fab" @click="chat.toggle()" v-if="!chat.isOpen">
      <el-icon :size="24"><ChatDotRound /></el-icon>
    </div>

    <el-card class="chat-window" v-if="chat.isOpen" shadow="always">
      <template #header>
        <div class="chat-header">
          <span>🛎️ AI 智能客服</span>
          <div>
            <el-button link size="small" @click="chat.newConversation()">新对话</el-button>
            <el-button :icon="Close" circle size="small" @click="chat.close()" />
          </div>
        </div>
      </template>

      <div class="chat-messages" ref="msgContainer">
        <div v-if="!chat.messages.length" class="chat-empty">
          <p>你好！我是商城 AI 客服，可以回答退换货、配送、支付等常见问题。</p>
          <div class="quick-questions">
            <el-tag
              v-for="q in quickQuestions"
              :key="q"
              class="quick-tag"
              @click="ask(q)"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>
        <div v-for="(msg, i) in chat.messages" :key="i" :class="['chat-msg', msg.role]">
          <div class="msg-bubble">
            <span style="white-space: pre-wrap">{{ msg.content }}</span>
            <div v-if="msg.products?.length" class="product-list">
              <div
                v-for="p in msg.products"
                :key="p.id"
                class="product-chip"
                @click="$router.push(`/product/${p.id}`)"
              >
                <img :src="p.image || '/placeholder.png'" class="product-img" />
                <div class="product-info">
                  <div class="product-name">{{ p.name }}</div>
                  <div class="product-price">¥{{ p.price }} · 已售 {{ p.sales }}</div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-if="chat.isTyping && i === chat.messages.length - 1 && !msg.content && !msg.products?.length"
            class="typing-dots"
          >
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="inputText"
          placeholder="输入你的问题，如：怎么申请退款？"
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

const quickQuestions = [
  '怎么申请退款？',
  '多久能送到？',
  '有什么手机推荐？',
  '怎么转人工客服？',
]

async function ask(q) {
  inputText.value = q
  await send()
}

async function send() {
  if (!inputText.value.trim() || chat.isTyping) return
  const text = inputText.value
  inputText.value = ''
  await chat.sendMessage(text)
  scrollToBottom()
}

watch(
  () => chat.messages.length + chat.messages.at(-1)?.content.length,
  () => nextTick(scrollToBottom)
)

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
.chat-window { width: 400px; height: 560px; display: flex; flex-direction: column; }
.chat-header { display: flex; justify-content: space-between; align-items: center; }
.chat-messages { flex: 1; overflow-y: auto; padding: 8px 0; }
.chat-empty { text-align: center; color: #666; padding: 30px 10px; font-size: 13px; line-height: 1.8; }
.quick-questions { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.quick-tag { cursor: pointer; border-radius: 14px; justify-content: flex-start; }
.chat-msg { margin-bottom: 12px; }
.chat-msg.user { text-align: right; }
.chat-msg.user .msg-bubble {
  display: inline-block; background: #409eff; color: #fff;
  padding: 8px 14px; border-radius: 16px 4px 16px 16px;
  max-width: 85%; text-align: left; font-size: 14px;
}
.chat-msg.assistant .msg-bubble {
  display: inline-block; background: #f0f0f0; color: #333;
  padding: 8px 14px; border-radius: 4px 16px 16px 16px;
  max-width: 90%; text-align: left; font-size: 14px;
}
.product-list { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.product-chip {
  display: flex; gap: 10px; background: #fff; border: 1px solid #e4e7ed;
  border-radius: 8px; padding: 6px; cursor: pointer; align-items: center;
}
.product-chip:hover { border-color: #409eff; }
.product-img { width: 44px; height: 44px; border-radius: 6px; object-fit: cover; }
.product-info { line-height: 1.4; min-width: 0; }
.product-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.product-price { font-size: 12px; color: #f56c6c; }
.chat-input { margin-top: 8px; }
.typing-dots { display: inline-flex; gap: 4px; padding: 8px 14px; }
.typing-dots span {
  width: 8px; height: 8px; border-radius: 50%;
  background: #ccc; animation: typing 1.4s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%,60%,100% { opacity: 0.3; } 30% { opacity: 1; } }
</style>
