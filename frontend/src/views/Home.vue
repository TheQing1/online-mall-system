<template>
  <div>
    <Navbar />
    <el-main>
      <!-- Banner -->
      <el-carousel height="360px" class="banner">
        <el-carousel-item v-for="i in 3" :key="i">
          <div class="banner-item" :style="{ background: ['#409eff', '#67c23a', '#e6a23c'][i-1] }">
            <h1>欢迎来到 Online Mall</h1>
            <p>精选好物，品质生活</p>
          </div>
        </el-carousel-item>
      </el-carousel>

      <!-- 分类 -->
      <h2 class="section-title">商品分类</h2>
      <div class="categories">
        <el-button
          v-for="cat in categories"
          :key="cat.id"
          @click="$router.push(`/category/${cat.id}`)"
          style="margin: 4px"
        >
          {{ cat.name }}
          <template v-if="cat.children?.length">
            ({{ cat.children.map(c => c.name).join(' / ') }})
          </template>
        </el-button>
      </div>

      <!-- 热销推荐 -->
      <h2 class="section-title">热销推荐</h2>
      <div class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" />
      </div>
      <el-empty v-if="!products.length" description="暂无商品" />
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import { getProducts, getCategories } from '@/api/products'

const products = ref([])
const categories = ref([])

onMounted(async () => {
  try {
    const [prodRes, catRes] = await Promise.all([
      getProducts({ page: 1, page_size: 8, sort_by: 'sales' }),
      getCategories()
    ])
    products.value = prodRes.items
    categories.value = catRes
  } catch (e) {
    console.error('Failed to load home data:', e)
  }
})
</script>

<style scoped>
.banner { margin-bottom: 30px; border-radius: 8px; overflow: hidden; }
.banner-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #fff;
}
.banner-item h1 { font-size: 36px; margin-bottom: 8px; }
.section-title { margin: 30px 0 16px; font-size: 22px; }
.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
</style>
