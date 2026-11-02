<template>
  <div>
    <Navbar />
    <el-main>
      <!-- Banner -->
      <el-carousel :height="bannerHeight" class="banner">
        <el-carousel-item v-for="b in banners" :key="b.id" @click="goBanner(b)">
          <div class="banner-item">
            <img :src="b.image" class="banner-img" alt="" />
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
      <AsyncState
        :loading="loading"
        :error="error"
        :empty="!products.length"
        empty-text="暂无商品"
        @retry="fetchData"
      >
        <div class="product-grid">
          <ProductCard v-for="p in products" :key="p.id" :product="p" />
        </div>
      </AsyncState>
    </el-main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Navbar from '@/components/Navbar.vue'
import ProductCard from '@/components/ProductCard.vue'
import AsyncState from '@/components/AsyncState.vue'
import { getProducts, getCategories } from '@/api/products'
import { getBanners } from '@/api/content'

const router = useRouter()
const products = ref([])
const categories = ref([])
const banners = ref([])
// 三态：加载中 / 出错 / 空。修复前这三个状态渲染出来完全一样，
// 网络失败时用户永远停在「暂无商品」，和真的没商品无法区分。
const loading = ref(true)
const error = ref('')

// Banner 高度：素材是 600x450 的横图（4:3）。桌面端固定 360px 没问题，
// 但手机上如果还按 360px 高、宽度只有 375px，4:3 的图会被 object-fit: cover
// 裁掉左右两边大半，商品主体经常只剩半截。
// 窄屏降到 200px 并放宽裁切方向之外，更重要的是把比例算进去。
const isNarrow = ref(false)
const bannerHeight = computed(() => (isNarrow.value ? '200px' : '360px'))

function syncViewport() {
  isNarrow.value = window.innerWidth <= 768
}

function onResize() {
  syncViewport()
}

async function fetchData() {
  loading.value = true
  error.value = ''
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
    // 修复前只 console.error：用户界面上什么都没发生，永远停在空态。
    // 现在把错误写进 state 交给 AsyncState 渲染成「加载失败 + 重试」。
    error.value = '商品加载失败，请检查网络后重试'
    console.error('Failed to load home data:', e)
  } finally {
    loading.value = false
  }
}

function goBanner(banner) {
  if (banner.link) router.push(banner.link)
}

onMounted(fetchData)

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.banner { margin-bottom: 30px; border-radius: 8px; overflow: hidden; }
.banner-item { position: relative; width: 100%; height: 100%; cursor: pointer; }
/* object-position 居中偏左：Banner 素材的主体（手机/笔记本）偏左，
   默认的 center 在窄屏裁切时容易把主体切掉一半。 */
.banner-img { width: 100%; height: 100%; object-fit: cover; object-position: center; }
.banner-overlay {
  position: absolute; left: 40px; bottom: 36px; color: #fff;
  text-shadow: 0 2px 8px rgba(0,0,0,0.4); pointer-events: none;
}
.banner-overlay h1 { font-size: 32px; margin: 0; }
.section-title { margin: 30px 0 16px; font-size: 22px; }
/* 自适应列数：原来写死 repeat(4, 1fr)，在手机上 4 列挤成一坨且横向溢出。
   auto-fill + minmax 让列数随容器宽度自动增减，窄屏 2 列、宽屏 4~5 列，
   不需要任何断点。minmax 的下限 220px 是商品卡片能正常显示价格的最小宽度。 */
.product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }

@media (max-width: 768px) {
  .banner-overlay { left: 16px; bottom: 16px; }
  .banner-overlay h1 { font-size: 20px; }
  .section-title { margin: 20px 0 12px; font-size: 18px; }
  .product-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
}
</style>
