<template>
  <div class="dashboard">
    <header class="header">
      <h2>AI面试官</h2>
      <div class="header-right">
        <span class="user-name">{{ authStore.user?.username }}</span>
        <el-button text @click="handleLogout">退出</el-button>
      </div>
    </header>

    <main class="main">
      <div class="welcome-card">
        <h1>欢迎使用AI面试官</h1>
        <p>上传简历，选择应聘岗位，开启智能面试体验</p>
      </div>

      <div class="steps">
        <div class="step">
          <div class="step-num">1</div>
          <div class="step-content">
            <h3>上传简历</h3>
            <p>支持PDF格式，将自动解析您的教育背景、技能和工作经验</p>
            <el-upload
              :auto-upload="false"
              :limit="1"
              accept=".pdf"
              :on-change="handleFileChange"
              :file-list="fileList"
            >
              <el-button type="primary" :icon="Upload">选择PDF简历</el-button>
            </el-upload>
            <el-button
              v-if="selectedFile"
              :loading="uploading"
              class="upload-btn"
              type="success"
              @click="handleUpload"
            >
              上传并解析
            </el-button>
            <div v-if="resumeInfo" class="resume-info">
              <el-tag type="success">简历已解析</el-tag>
              <p v-if="resumeInfo.skills">技能：{{ resumeInfo.skills }}</p>
            </div>
          </div>
        </div>

        <div class="step">
          <div class="step-num">2</div>
          <div class="step-content">
            <h3>选择岗位并开始面试</h3>
            <p>输入应聘岗位，AI将根据简历内容生成专业面试题目</p>
            <el-input
              v-model="position"
              placeholder="例如：Python后端工程师"
              :disabled="!resumeInfo"
              class="position-input"
            />
            <el-button
              type="primary"
              size="large"
              :disabled="!resumeInfo || !position"
              :loading="starting"
              @click="handleStartInterview"
            >
              开始面试
            </el-button>
          </div>
        </div>
      </div>

      <div class="history-section">
        <el-button type="info" text @click="$router.push('/history')">
          查看历史面试记录 →
        </el-button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/store'
import { uploadResume, parseResume } from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const selectedFile = ref(null)
const fileList = ref([])
const uploading = ref(false)
const resumeInfo = ref(null)
const position = ref('')
const starting = ref(false)

function handleFileChange(file) {
  selectedFile.value = file.raw
  fileList.value = [file]
}

async function handleUpload() {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const res = await uploadResume(selectedFile.value)
    const resumeId = res.data.id
    const parseRes = await parseResume(resumeId)
    resumeInfo.value = parseRes.data
    ElMessage.success('简历上传解析成功')
  } catch {
    // error handled by interceptor
  } finally {
    uploading.value = false
  }
}

async function handleStartInterview() {
  starting.value = true
  try {
    router.push({
      path: '/interview/new',
      query: { resumeId: resumeInfo.value.id, position: position.value }
    })
  } finally {
    starting.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: #f5f7fa;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-name {
  color: #606266;
}
.main {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
}
.welcome-card {
  text-align: center;
  margin-bottom: 48px;
}
.welcome-card h1 {
  font-size: 32px;
  color: #303133;
  margin-bottom: 8px;
}
.welcome-card p {
  color: #909399;
  font-size: 16px;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.step {
  display: flex;
  gap: 20px;
  background: #fff;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.step-num {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  flex-shrink: 0;
}
.step-content h3 {
  margin-bottom: 8px;
  color: #303133;
}
.step-content p {
  color: #909399;
  margin-bottom: 16px;
}
.upload-btn {
  margin-left: 12px;
}
.resume-info {
  margin-top: 12px;
  padding: 12px;
  background: #f0f9eb;
  border-radius: 8px;
}
.position-input {
  margin-bottom: 12px;
  max-width: 400px;
  display: block;
}
.history-section {
  text-align: center;
  margin-top: 40px;
}
</style>
