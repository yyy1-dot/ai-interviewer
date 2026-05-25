<template>
  <div class="history">
    <header class="header">
      <el-button text @click="$router.push('/dashboard')" :icon="ArrowLeft">返回</el-button>
      <h3>历史面试记录</h3>
    </header>

    <main class="main">
      <el-empty v-if="interviews.length === 0 && !loading" description="暂无面试记录" />

      <div class="list" v-if="interviews.length > 0">
        <div class="card" v-for="item in interviews" :key="item.id" @click="handleView(item)">
          <div class="card-header">
            <h4>{{ item.position }}</h4>
            <el-tag :type="item.status === 'completed' ? 'success' : 'info'">
              {{ item.status === 'completed' ? '已完成' : item.status === 'in_progress' ? '进行中' : '待开始' }}
            </el-tag>
          </div>
          <div class="card-body">
            <span>总分：<strong>{{ item.total_score ?? '--' }}</strong></span>
            <span class="card-time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>
      </div>

      <el-dialog v-model="detailVisible" title="面试详情" width="700px">
        <div v-if="currentReport" class="report-detail">
          <div class="total-score">总分：<strong>{{ currentReport.total_score }}</strong></div>
          <div class="detail-scores" v-if="currentReport.detail_scores">
            <el-tag v-for="(val, key) in currentReport.detail_scores" :key="key" class="score-tag">
              {{ key }}: {{ val }}
            </el-tag>
          </div>
          <div class="section" v-if="currentReport.strengths">
            <strong>优点：</strong>{{ currentReport.strengths }}
          </div>
          <div class="section" v-if="currentReport.weaknesses">
            <strong>不足：</strong>{{ currentReport.weaknesses }}
          </div>
          <div class="section" v-if="currentReport.suggestion">
            <strong>建议：</strong>{{ currentReport.suggestion }}
          </div>
        </div>
        <div v-else>
          <p v-if="currentScore">
            得分：{{ currentScore.total_score }}（已答{{ currentScore.answered_count }}/{{ currentScore.question_count }}题）
          </p>
          <p v-else>暂无详细信息</p>
        </div>
      </el-dialog>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getReport, getScore } from '@/api'
import request from '@/api'

const interviews = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentReport = ref(null)
const currentScore = ref(null)

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

async function loadHistory() {
  loading.value = true
  try {
    const res = await request.get('/report/list')
    if (res.data) {
      interviews.value = Array.isArray(res.data) ? res.data : []
    }
  } catch {
    interviews.value = []
  } finally {
    loading.value = false
  }
}

async function handleView(item) {
  detailVisible.value = true
  currentReport.value = null
  currentScore.value = null
  try {
    const res = await getReport(item.id)
    currentReport.value = res.data
  } catch {
    try {
      const res = await getScore(item.id)
      currentScore.value = res.data
    } catch {
      // nothing
    }
  }
}

onMounted(loadHistory)
</script>

<style scoped>
.history {
  min-height: 100vh;
  background: #f5f7fa;
}
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.header h3 { margin: 0; }
.main {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card {
  background: #fff;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.card-header h4 { margin: 0; }
.card-body {
  display: flex;
  justify-content: space-between;
  color: #909399;
}
.card-time { font-size: 13px; }
.report-detail .total-score {
  font-size: 24px;
  margin-bottom: 16px;
  color: #e6a23c;
}
.detail-scores {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.section {
  margin-top: 16px;
  line-height: 1.8;
  color: #606266;
}
</style>
