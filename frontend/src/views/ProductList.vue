<template>
  <div>
    <Navbar />
    <el-main>
      <h2>{{ title }}</h2>
      <div class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" />
      </div>
      <el-empty v-if="!products.length" description="暂无商品" />
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
import { getProducts } from '@/api/products'

const route = useRoute()
const products = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const title = computed(() => {
  if (route.query.q) return `搜索: "${route.query.q}"`
  return '商品列表'
})

async function fetchData() {
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
    console.error('Failed to load products:', e)
  }
}

watch(() => route.query.q, () => { page.value = 1; fetchData() })
watch(() => route.params.id, () => { page.value = 1; fetchData() })
onMounted(fetchData)
</script>

<style scoped>
.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
</style>
