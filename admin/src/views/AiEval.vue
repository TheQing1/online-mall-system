<template>
  <div>
    <div class="header">
      <h2>RAG 检索评测</h2>
      <div>
        <el-button type="success" :loading="running" @click="runEval">运行评测</el-button>
        <el-button type="primary" @click="dialogVisible = true">添加用例</el-button>
      </div>
    </div>

    <el-alert
      type="info" :closable="false" style="margin-bottom:14px"
      title="评测只验证向量检索召回（Top-5 内是否命中期望文档），不消耗大模型 Token。运行前请确认知识库索引已同步。"
    />

    <div v-if="lastResult">
      <el-result
        :icon="lastResult.hit_rate >= 0.7 ? 'success' : 'warning'"
        :title="`命中率 ${(lastResult.hit_rate * 100).toFixed(1)}%（${lastResult.results.filter(r => r.hit).length}/${lastResult.total}）`"
      />
      <el-table :data="lastResult.results" border stripe size="small">
        <el-table-column prop="question" label="问题" min-width="220" />
        <el-table-column prop="expected_title" label="期望文档" width="160" />
        <el-table-column label="是否命中" width="90">
          <template #default="{ row }">
            <el-tag :type="row.hit ? 'success' : 'danger'">{{ row.hit ? '命中' : '未命中' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="实际召回" min-width="240">
          <template #default="{ row }">
            <div v-for="t in row.retrieved_titles" :key="t" style="font-size:12px">{{ t }}</div>
            <span v-if="!row.retrieved_titles?.length" style="color:#c0c4cc">无召回</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <h3 style="margin:24px 0 12px">测试用例</h3>
    <el-table :data="cases" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="question" label="问题" min-width="260" />
      <el-table-column prop="expected_title" label="期望文档" width="200" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="添加评测用例" width="480px">
      <el-form label-width="90px">
        <el-form-item label="问题" required>
          <el-input v-model="form.question" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="期望文档标题" required>
          <el-input v-model="form.expected_title" placeholder="与知识库文档标题一致" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const cases = ref([])
const loading = ref(false)
const running = ref(false)
const lastResult = ref(null)
const dialogVisible = ref(false)
const form = reactive({ question: '', expected_title: '' })

async function fetchCases() {
  loading.value = true
  try {
    cases.value = await client.get('/admin/ai/eval-cases')
  } finally {
    loading.value = false
  }
}

async function runEval() {
  running.value = true
  try {
    lastResult.value = await client.post('/admin/ai/eval/run')
    ElMessage.success('评测完成')
  } finally {
    running.value = false
  }
}

async function handleSave() {
  if (!form.question.trim() || !form.expected_title.trim()) {
    ElMessage.warning('请完整填写')
    return
  }
  try {
    await client.post('/admin/ai/eval-cases', { ...form })
    ElMessage.success('已添加')
    dialogVisible.value = false
    form.question = ''
    form.expected_title = ''
    fetchCases()
  } catch {}
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该用例吗？', '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await client.delete(`/admin/ai/eval-cases/${row.id}`)
    fetchCases()
  } catch {}
}

onMounted(fetchCases)
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
