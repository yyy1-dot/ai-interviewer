/**
 * AI面试官 - 全局状态管理（Pinia）
 *
 * 本文件包含两个Store：
 *   useAuthStore     —— 用户登录状态、登录/注册/退出
 *   useInterviewStore —— 面试流程状态、开始/答题/报告
 *
 * 使用方式：
 *   import { useAuthStore, useInterviewStore } from '@/store'
 *   const authStore = useAuthStore()
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, register as registerApi, getMe } from '@/api'
import { startInterview, submitAnswer, getReport } from '@/api'


// ===== 用户认证Store =====

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('token') || '')

  // 设置登录状态（保存到localStorage持久化）
  function setAuth(u, t) {
    user.value = u
    token.value = t
    localStorage.setItem('user', JSON.stringify(u))
    localStorage.setItem('token', t)
  }

  // 清除登录状态
  function clearAuth() {
    user.value = null
    token.value = ''
    localStorage.removeItem('user')
    localStorage.removeItem('token')
  }

  // 登录
  async function login(username, password) {
    const res = await loginApi(username, password)
    setAuth(res.data.user, res.data.access_token)
    return res
  }

  // 注册
  async function register(username, email, password) {
    const res = await registerApi(username, email, password)
    setAuth(res.data.user, res.data.access_token)
    return res
  }

  // 退出
  function logout() {
    clearAuth()
  }

  // 刷新用户信息
  async function fetchUser() {
    try {
      const res = await getMe()
      user.value = res.data
      localStorage.setItem('user', JSON.stringify(res.data))
    } catch {
      clearAuth()
    }
  }

  // 是否已登录
  const isLoggedIn = () => !!token.value

  return { user, token, login, register, logout, fetchUser, isLoggedIn }
})


// ===== 面试流程Store =====

export const useInterviewStore = defineStore('interview', () => {
  const sessionId = ref(null)
  const position = ref('')
  const questions = ref([])
  const currentIndex = ref(0)
  const answers = ref([])
  const report = ref(null)
  const loading = ref(false)

  // 重置所有状态（新面试前调用）
  function resetState() {
    sessionId.value = null
    position.value = ''
    questions.value = []
    currentIndex.value = 0
    answers.value = []
    report.value = null
    loading.value = false
  }

  // 开始面试
  async function start(resumeId, pos) {
    loading.value = true
    try {
      const res = await startInterview(resumeId, pos)
      sessionId.value = res.data.session_id
      position.value = res.data.position
      questions.value = res.data.questions
      currentIndex.value = 0
      return res.data
    } finally {
      loading.value = false
    }
  }

  // 提交回答
  async function answer(questionId, answerText) {
    loading.value = true
    try {
      const res = await submitAnswer(sessionId.value, questionId, answerText)
      answers.value.push({
        questionId, answerText,
        score: res.data.score, feedback: res.data.feedback,
      })
      currentIndex.value++
      return res.data
    } finally {
      loading.value = false
    }
  }

  // 获取面试报告
  async function fetchReport() {
    loading.value = true
    try {
      const res = await getReport(sessionId.value)
      report.value = res.data
      return res.data
    } finally {
      loading.value = false
    }
  }

  // 当前题目
  const currentQuestion = () => {
    if (currentIndex.value < questions.value.length) {
      return questions.value[currentIndex.value]
    }
    return null
  }

  // 是否已完成所有题目
  const isCompleted = () => currentIndex.value >= questions.value.length

  return {
    sessionId, position, questions, currentIndex, answers, report, loading,
    start, answer, fetchReport, resetState, currentQuestion, isCompleted,
  }
})
