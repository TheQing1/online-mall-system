<template>
  <div>
    <Navbar />
    <el-main>
      <h2>{{ title }}</h2>
      <AsyncState
        :loading="loading"
        :error="error"
        :empty="!products.length"
        :empty-text="route.query.q ? `没有找到与「${route.query.q}」相关的商品` : '暂无商品'"
        @retry="fetchData"
      >
        <div class="product-grid">
          <ProductCard v-for="p in products" :key="p.id" :product="p" />
        </div>
      </AsyncState>
      <div v-if="total > pageSize" style="display:flex;justify-content:center;margin-top:20px">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="fetchData"
        />
      </div>
    </el-main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import AsyncState from '@/components/AsyncState.vue'
import { getProducts } from '@/api/products'

const route = useRoute()
const products = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const error = ref('')

const title = computed(() => {
  if (route.query.q) return `搜索: "${route.query.q}"`
  return '商品列表'
})

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const res = await getProducts({
      page: page.value,
      page_size: pageSize,
      keyword: route.query.q || undefined,
      category_id: route.params.id ? Number(route.params.id) : undefined,
    })
    products.value = res.items
    total.value = res.total
  } catch (e) {
    // 修复前只 console.error：搜索失败时页面显示「暂无商品」，
    // 用户会以为「这个关键词真的没有商品」，而不是「请求失败了」。
    error.value = '商品加载失败，请检查网络后重试'
    console.error('Failed to load products:', e)
  } finally {
    loading.value = false
  }
}

watch(() => route.query.q, () => { page.value = 1; fetchData() })
watch(() => route.params.id, () => { page.value = 1; fetchData() })
onMounted(fetchData)
</script>

<style scoped>
/* 自适应列数：不用固定 4 列，也不用断点，窄屏 2 列、宽屏 4~5 列 */
.product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }

@media (max-width: 768px) {
  .product-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
}
</style>
