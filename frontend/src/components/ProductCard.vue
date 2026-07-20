<template>
  <el-card class="product-card" shadow="hover" @click="$router.push(`/product/${product.id}`)">
    <img :src="product.images?.[0] || '/placeholder.png'" class="product-img" />
    <div class="product-info">
      <h3 class="product-name">{{ product.name }}</h3>
      <div class="product-price">¥{{ product.price }}</div>
      <div class="product-sales">已售 {{ product.sales }}</div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({ product: { type: Object, required: true } })
</script>

<style scoped>
.product-card { cursor: pointer; transition: transform 0.2s; }
.product-card:hover { transform: translateY(-4px); }
.product-img { width: 100%; height: 200px; object-fit: cover; border-radius: 4px; }
.product-name { font-size: 14px; margin: 8px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.product-price { font-size: 18px; color: #f56c6c; font-weight: bold; }
.product-sales { font-size: 12px; color: #999; margin-top: 4px; }
</style>
