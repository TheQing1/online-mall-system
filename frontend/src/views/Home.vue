<template>
  <div>
    <Navbar />
    <el-main>
      <!-- Banner -->
      <el-carousel height="360px" class="banner">
        <el-carousel-item v-for="b in banners" :key="b.id" @click="goBanner(b)">
          <div class="banner-item">
            <img :src="b.image" class="banner-img" />
            <div class="banner-overlay">
              <h1>{{ b.title }}</h1>
            </div>
          </div>
        </el-carousel-item>
      </el-carousel>
      <el-empty v-if="!banners.length" description="暂无 Banner" />

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
            ({{ cat.children.map((c) => c.name).join(' / ') }})
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
import { useRouter } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import { getProducts, getCategories } from '@/api/products'
import { getBanners } from '@/api/content'

const router = useRouter()
const products = ref([])
const categories = ref([])
const banners = ref([])

onMounted(async () => {
  try {
    const [prodRes, catRes, bannerRes] = await Promise.all([
      getProducts({ page: 1, page_size: 8, sort_by: 'sales' }),
      getCategories(),
      getBanners(),
    ])
    products.value = prodRes.items
    categories.value = catRes
    banners.value = bannerRes
  } catch (e) {
    console.error('Failed to load home data:', e)
  }
})

function goBanner(banner) {
  if (banner.link) router.push(banner.link)
}
</script>

<style scoped>
.banner { margin-bottom: 30px; border-radius: 8px; overflow: hidden; }
.banner-item { position: relative; width: 100%; height: 100%; cursor: pointer; }
.banner-img { width: 100%; height: 100%; object-fit: cover; }
.banner-overlay {
  position: absolute; left: 40px; bottom: 36px; color: #fff;
  text-shadow: 0 2px 8px rgba(0,0,0,0.4); pointer-events: none;
}
.banner-overlay h1 { font-size: 32px; margin: 0; }
.section-title { margin: 30px 0 16px; font-size: 22px; }
.product-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
</style>
