<template>
  <div class="interview">
    <header class="header">
      <el-button text @click="handleBack" :icon="ArrowLeft">返回</el-button>
      <h3>{{ position }} - 面试中</h3>
      <el-tag :type="completed ? 'success' : 'warning'">
        {{ completed ? '已完成' : `第${qIndex + 1}/${questions.length}题` }}
      </el-tag>
    </header>

    <main class="chat-area" ref="chatRef">
      <div v-for="(m, i) in messages" :key="i" class="message" :class="m.role">
        <div class="message-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div class="message-bubble" :class="m.bubbleClass || ''">
          <!-- 题目 -->
          <template v-if="m.type === 'question'">
            <div class="msg-meta">
              <el-tag size="small">{{ typeLabel(m.data.question_type) }}</el-tag>
              <el-tag size="small">{{ diffLabel(m.data.difficulty) }}</el-tag>
            </div>
            <p class="question-text">{{ m.data.question_text }}</p>
            <el-button v-if="m.question_audio" size="small" text @click="playAudio(m.question_audio)">
              播放语音
            </el-button>
          </template>

          <!-- 文字回答 -->
          <template v-else-if="m.type === 'text_answer'">
            <p>{{ m.text }}</p>
          </template>

          <!-- 语音识别结果 -->
          <template v-else-if="m.type === 'transcription'">
            <p class="trans-text">"{{ m.text }}"</p>
          </template>

          <!-- 评分 -->
          <template v-else-if="m.type === 'score'">
            <div class="score">得分：<strong>{{ m.score }}</strong></div>
            <p>{{ m.feedback }}</p>
            <el-button v-if="m.feedback_audio" size="small" text @click="playAudio(m.feedback_audio)">
              播放语音评价
            </el-button>
          </template>

          <!-- 报告 -->
          <template v-else-if="m.type === 'report'">
            <h4>面试评估报告</h4>
            <div class="total-score">总分：<strong>{{ m.data.total_score }}</strong></div>
            <div class="detail-scores" v-if="m.data.detail_scores">
              <el-tag v-for="(val, key) in m.data.detail_scores" :key="key" class="score-tag">
                {{ key }}: {{ val }}
              </el-tag>
            </div>
            <div class="section" v-if="m.data.strengths"><strong>优点：</strong>{{ m.data.strengths }}</div>
            <div class="section" v-if="m.data.weaknesses"><strong>不足：</strong>{{ m.data.weaknesses }}</div>
            <div class="section" v-if="m.data.suggestion"><strong>建议：</strong>{{ m.data.suggestion }}</div>
          </template>

          <!-- 错误 -->
          <template v-else-if="m.type === 'error'">
            <p class="error-msg">{{ m.message }}</p>
          </template>
        </div>
      </div>
    </main>

    <!-- 输入区 -->
    <footer class="input-area" v-if="!completed && !reportData">
      <!-- 录音按钮 -->
      <el-button type="danger" size="large" :class="{ recording: isRecording }" @click="toggleRecord" circle>
        <el-icon :size="22"><Microphone /></el-icon>
      </el-button>

      <!-- 文字输入 -->
      <el-input v-model="answerText" type="textarea" :rows="3" placeholder="输入回答..."
        :disabled="loading" @keyup.enter.ctrl="handleTextSubmit" />
      <el-button type="primary" :loading="loading" :disabled="!answerText.trim()" @click="handleTextSubmit">
        发送
      </el-button>
    </footer>

    <!-- 完成状态 -->
    <footer class="input-area" v-if="completed && !reportData">
      <el-button type="success" size="large" :loading="loading" @click="handleReport">生成面试报告</el-button>
    </footer>

    <footer class="input-area" v-if="reportData">
      <el-button type="primary" @click="$router.push('/history')">查看历史记录</el-button>
      <el-button @click="$router.push('/dashboard')">返回首页</el-button>
    </footer>

    <!-- 隐藏的音频播放器 -->
    <audio ref="audioPlayer" style="display:none" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Microphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const chatRef = ref(null)
const audioPlayer = ref(null)

// 状态
const ws = ref(null)
const sessionId = ref(null)
const position = ref('')
const questions = ref([])
const qIndex = ref(0)
const messages = ref([])
const reportData = ref(null)
const completed = ref(false)
const loading = ref(false)
const answerText = ref('')
const isRecording = ref(false)
let mediaRecorder = null
let audioChunks = []

// 辅助
function typeLabel(t) {
  return { technical: '技术', behavioral: '行为', project: '项目' }[t] || t
}
function diffLabel(d) {
  return { easy: '简单', medium: '中等', hard: '困难' }[d] || d
}
async function scrollToBottom() {
  await nextTick()
  if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
}

// 播放 base64 音频
function playAudio(b64) {
  if (!b64 || !audioPlayer.value) return
  audioPlayer.value.src = 'data:audio/mp3;base64,' + b64
  audioPlayer.value.play().catch(() => {})
}

// WebSocket 连接
function connectWs(token, resumeId, pos) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.host
  const url = `${protocol}//${host}/ws/interview?token=${token}`

  const socket = new WebSocket(url)
  ws.value = socket

  socket.onopen = () => {
    socket.send(JSON.stringify({ type: 'start', resume_id: resumeId, position: pos }))
  }

  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    handleMsg(msg)
  }

  socket.onerror = () => {
    ElMessage.error('WebSocket 连接失败')
  }

  socket.onclose = () => {
    // ignore
  }
}

// 处理消息
function handleMsg(msg) {
  switch (msg.type) {
    case 'connected':
      break
    case 'interview_started':
      sessionId.value = msg.session_id
      position.value = msg.position
      break
    case 'question':
      questions.value.push(msg.data)
      qIndex.value = questions.value.length - 1
      messages.value.push({
        role: 'system', type: 'question',
        data: msg.data, question_audio: msg.question_audio,
      })
      // 自动播放题目语音
      if (msg.question_audio) playAudio(msg.question_audio)
      scrollToBottom()
      break
    case 'transcription':
      messages.value.push({ role: 'user', type: 'transcription', text: msg.text })
      scrollToBottom()
      break
    case 'score':
      messages.value.push({
        role: 'system', type: 'score',
        score: msg.score, feedback: msg.feedback,
      })
      scrollToBottom()
      break
    case 'feedback_audio':
      // 评分后异步到达的反馈语音，追加到最近的 score 消息
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].type === 'score') {
          messages.value[i].feedback_audio = msg.data
          break
        }
      }
      if (msg.data) playAudio(msg.data)
      break
    case 'all_answered':
      completed.value = true
      scrollToBottom()
      break
    case 'report':
      reportData.value = msg.data
      messages.value.push({ role: 'system', type: 'report', data: msg.data })
      scrollToBottom()
      break
    case 'error':
      ElMessage.error(msg.message)
      loading.value = false
      break
    case 'pong':
      break
  }
}

// 文字提交
function handleTextSubmit() {
  const text = answerText.value.trim()
  if (!text || !ws.value) return
  const q = questions.value[qIndex.value]
  if (!q || completed.value) return

  messages.value.push({ role: 'user', type: 'text_answer', text })
  answerText.value = ''
  loading.value = true

  ws.value.send(JSON.stringify({
    type: 'text_answer',
    question_id: q.id,
    text,
  }))
  loading.value = false
  scrollToBottom()
}

// 录音功能
async function toggleRecord() {
  if (isRecording.value) {
    // 停止录音
    mediaRecorder?.stop()
    isRecording.value = false
    loading.value = true
  } else {
    // 开始录音
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      audioChunks = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        if (audioChunks.length === 0) { loading.value = false; return }

        const blob = new Blob(audioChunks, { type: 'audio/webm' })
        const reader = new FileReader()
        reader.onloadend = () => {
          const b64 = reader.result.split(',')[1]
          const q = questions.value[qIndex.value]
          if (ws.value && q) {
            ws.value.send(JSON.stringify({
              type: 'voice_answer',
              question_id: q.id,
              audio: b64,
            }))
          }
          loading.value = false
        }
        reader.readAsDataURL(blob)
      }

      mediaRecorder.start()
      isRecording.value = true
    } catch (e) {
      ElMessage.error('无法访问麦克风，请检查权限')
    }
  }
}

function handleReport() {
  if (!ws.value) return
  loading.value = true
  ws.value.send(JSON.stringify({ type: 'report' }))
  loading.value = false
}

function handleBack() {
  if (ws.value) ws.value.close()
  router.push('/dashboard')
}

// 生命周期
onMounted(() => {
  const token = localStorage.getItem('token')
  const resumeId = route.query.resumeId
  const pos = route.query.position
  if (!token || !resumeId || !pos) {
    ElMessage.warning('参数错误')
    router.push('/dashboard')
    return
  }
  connectWs(token, Number(resumeId), pos)
})

onUnmounted(() => {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
  }
  if (ws.value) ws.value.close()
})
</script>

<style scoped>
.interview { display: flex; flex-direction: column; height: 100vh; background: #f5f7fa; }
.header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.header h3 { flex: 1; margin: 0; }
.chat-area { flex: 1; overflow-y: auto; padding: 24px; max-width: 800px; width: 100%; margin: 0 auto; }
.message { display: flex; gap: 12px; margin-bottom: 20px; }
.message.user { flex-direction: row-reverse; }
.message-avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold; flex-shrink: 0; background: #409eff; color: #fff; }
.system .message-avatar { background: linear-gradient(135deg, #667eea, #764ba2); }
.message-bubble { max-width: 70%; padding: 16px; background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.user .message-bubble { background: #409eff; color: #fff; }
.msg-meta { display: flex; gap: 8px; margin-bottom: 8px; }
.question-text { color: #303133; line-height: 1.7; }
.score { margin-bottom: 8px; font-size: 16px; }
.score strong { color: #e6a23c; }
.total-score { font-size: 20px; margin-bottom: 12px; }
.total-score strong { color: #e6a23c; }
.detail-scores { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.score-tag { margin: 0; }
.section { margin-top: 12px; line-height: 1.7; }
.trans-text { font-style: italic; color: #909399; }
.error-msg { color: #f56c6c; }
.input-area { display: flex; gap: 12px; align-items: flex-end; padding: 16px 24px; background: #fff; border-top: 1px solid #ebeef5; max-width: 800px; width: 100%; margin: 0 auto; justify-content: center; }
.input-area .el-textarea { flex: 1; }
.recording { animation: pulse 1s infinite; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.6); } 50% { box-shadow: 0 0 0 12px rgba(245, 108, 108, 0); } }
</style>
