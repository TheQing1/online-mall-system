<template>
  <div class="search-box">
    <el-input
      v-model="keyword"
      placeholder="搜索商品..."
      size="large"
      clearable
      :prefix-icon="Search"
      @input="onInput"
      @keydown="onKeydown"
      @keyup.enter="onEnter"
      @focus="onFocus"
      @blur="onBlur"
    />

    <!-- 下拉建议 -->
    <div v-if="open && items.length" class="suggest-panel" data-testid="suggest-panel">
      <div
        v-for="(item, index) in items"
        :key="item.text + item.type"
        :class="['suggest-item', { active: index === activeIndex }]"
        :data-testid="`suggest-item-${index}`"
        @mousedown.prevent="choose(item)"
        @mouseenter="activeIndex = index"
      >
        <el-icon class="suggest-icon"><Search /></el-icon>
        <span class="suggest-text" v-html="highlight(item.text)" />
        <el-tag v-if="item.type === 'category'" size="small" type="info" class="suggest-tag">
          分类
        </el-tag>
        <el-tag v-else-if="item.type === 'sku'" size="small" class="suggest-tag">规格</el-tag>
      </div>
    </div>

    <!-- 无结果：只在「确实搜过且确实没有」时提示，不打扰刚输入一个字的用户 -->
    <div
      v-else-if="open && noResult"
      class="suggest-panel suggest-empty"
      data-testid="suggest-empty"
    >
      没有找到相关商品
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { getSuggestions } from '@/api/products'

const router = useRouter()

const keyword = ref('')
const items = ref([])
const open = ref(false)
const activeIndex = ref(-1)
const noResult = ref(false)

// 防抖：每敲一个字就发一次请求会打爆后端，也会让下拉内容闪烁。
// 180ms 是「感觉即时」和「少发请求」之间的常见折中。
const DEBOUNCE_MS = 180
let timer = null
// 竞态保护：网络快的请求可能后发先至，导致下拉显示的是**上一次**输入的结果。
// 每次请求带一个自增序号，回来时序号对不上就丢弃。
let requestSeq = 0

function close() {
  open.value = false
  activeIndex.value = -1
}

async function fetchSuggestions(query) {
  const seq = ++requestSeq
  try {
    const res = await getSuggestions(query)
    if (seq !== requestSeq) return // 已有更新的请求，丢弃这次结果
    items.value = res?.items || []
    noResult.value = query.trim().length >= 2 && items.value.length === 0
  } catch {
    if (seq !== requestSeq) return
    // 失败就静默收起：自动补全是锦上添花，不该打断用户打字
    items.value = []
    noResult.value = false
  }
}

function onInput(value) {
  activeIndex.value = -1
  if (timer) clearTimeout(timer)

  const query = (value || '').trim()
  if (!query) {
    items.value = []
    noResult.value = false
    open.value = false
    return
  }

  timer = setTimeout(() => {
    fetchSuggestions(query)
    open.value = true
  }, DEBOUNCE_MS)
}

function onFocus() {
  if (items.value.length || noResult.value) open.value = true
}

function onBlur() {
  // 用延时而不是立即关闭：mousedown 在 blur 之前触发，
  // 立即关闭会让「点选下拉项」的动作落空（点不到就已经消失了）。
  setTimeout(close, 120)
}

function onKeydown(event) {
  if (!open.value || !items.value.length) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % items.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value =
      activeIndex.value <= 0 ? items.value.length - 1 : activeIndex.value - 1
  } else if (event.key === 'Escape') {
    close()
  }
}

function onEnter() {
  // 有高亮项就搜它，否则搜用户自己敲的内容
  if (activeIndex.value >= 0 && items.value[activeIndex.value]) {
    choose(items.value[activeIndex.value])
  } else {
    submit(keyword.value)
  }
}

function choose(item) {
  close()
  keyword.value = item.text
  submit(item.text)
}

function submit(raw) {
  const q = (raw || '').trim()
  if (!q) return
  if (timer) clearTimeout(timer)
  router.push({ path: '/search', query: { q } })
}

/** 把命中的前缀加粗。只做纯文本转义后的高亮，不引入 v-html 注入风险。 */
function highlight(text) {
  const query = keyword.value.trim()
  const escaped = escapeHtml(text)
  if (!query) return escaped
  const escapedQuery = escapeHtml(query)
  // 不区分大小写地高亮；用 split/join 而不是正则，避免用户输入里的
  // 特殊字符（* + ? 等）被当成正则元字符。
  const lowerText = text.toLowerCase()
  const lowerQuery = escapedQuery.toLowerCase()
  const index = lowerText.indexOf(lowerQuery)
  if (index < 0) return escaped
  // 注意：要按原文索引切分，再各自转义，避免转义后长度变化导致切错位置
  const before = escapeHtml(text.slice(0, index))
  const hit = escapeHtml(text.slice(index, index + query.length))
  const after = escapeHtml(text.slice(index + query.length))
  return `${before}<em>${hit}</em>${after}`
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 路由变化时清空（例如点了「我的订单」离开搜索页，回来时不该残留上次的下拉）
watch(
  () => router.currentRoute.value.fullPath,
  () => {
    close()
    items.value = []
  }
)

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<style scoped>
.search-box {
  position: relative;
  width: 100%;
}
.suggest-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  z-index: 2000;
  overflow: hidden;
}
.suggest-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  cursor: pointer;
  font-size: 14px;
  color: #303133;
}
.suggest-item:hover,
.suggest-item.active {
  background: #f5f7fa;
}
.suggest-icon {
  color: #909399;
  flex-shrink: 0;
}
.suggest-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 命中的部分是 `<em>`，只改颜色不加粗——加粗会让行宽跳动 */
.suggest-text :deep(em) {
  font-style: normal;
  color: #f56c6c;
}
.suggest-tag {
  flex-shrink: 0;
  transform: scale(0.85);
}
.suggest-empty {
  padding: 12px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
