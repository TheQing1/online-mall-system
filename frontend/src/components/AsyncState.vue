<template>
  <!--
    统一的「加载中 / 出错 / 空 / 有数据」四态容器。

    为什么需要它：修复前前台的 6 个列表页都只有 `v-if="!items.length"` 一种判断，
    于是**加载中、真的没数据、请求失败**渲染出来完全一样，都是「暂无数据」。
    用户先看到「暂无商品」再突然变成商品列表；网络出错时更是永远停在
    「暂无商品」，和真的没商品无法区分。

    用法：
      <AsyncState :loading="loading" :error="error" :empty="!items.length"
                  empty-text="暂无商品" @retry="fetchData">
        <template #default> ...正常内容... </template>
      </AsyncState>
  -->
  <div class="async-state">
    <!-- 首屏加载：用骨架屏而不是转圈，避免内容区高度突然塌陷又撑开 -->
    <el-skeleton v-if="loading" :rows="rows" animated />

    <!-- 出错：给出可点击的重试，而不是只留一句错误文案 -->
    <el-result
      v-else-if="error"
      icon="warning"
      :title="errorTitle"
      :sub-title="error"
    >
      <template #extra>
        <el-button type="primary" @click="$emit('retry')">重新加载</el-button>
      </template>
    </el-result>

    <!-- 空：用 el-empty 区分于「加载中」和「出错」 -->
    <el-empty v-else-if="empty" :description="emptyText" />

    <slot v-else />
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  /** 错误信息（字符串）；为空表示没出错。调用方负责把 catch 到的错误写到这里。 */
  error: { type: String, default: '' },
  /** 是否为空态。通常传 `!items.length`。 */
  empty: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无数据' },
  errorTitle: { type: String, default: '加载失败' },
  rows: { type: Number, default: 4 },
})

defineEmits(['retry'])
</script>

<style scoped>
.async-state { min-height: 120px; }
</style>
