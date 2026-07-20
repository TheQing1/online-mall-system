<template>
  <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh">
    <h1 style="font-size:72px;color:#dcdfe6">404</h1>
    <p style="font-size:18px;color:#909399;margin:16px 0">页面不存在</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </div>
</template>
