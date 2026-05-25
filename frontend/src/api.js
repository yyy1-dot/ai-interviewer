/**
 * AI面试官 - 所有后端API请求
 *
 * 本文件包含两部分：
 *   1. axios实例（统一配置、拦截器）
 *   2. 所有API函数（认证、简历、面试、语音）
 *
 * 使用方式：
 *   import request from '@/api'          // axios实例
 *   import { login, uploadResume } from '@/api'  // 具体API函数
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'

// ===== axios实例 =====

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截器：自动带上JWT令牌
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理错误
request.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code && data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    const msg = error.response?.data?.message || error.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request

// ===== 认证相关 API =====

export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

export function register(username, email, password) {
  return request.post('/auth/register', { username, email, password })
}

export function getMe() {
  return request.get('/auth/me')
}

// ===== 简历相关 API =====

export function uploadResume(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getResumeDetail(id) {
  return request.get(`/resume/${id}`)
}

export function parseResume(id) {
  return request.post(`/resume/${id}/parse`)
}

// ===== 面试相关 API =====

export function startInterview(resumeId, position) {
  return request.post('/interview/start', { resume_id: resumeId, position })
}

export function submitAnswer(sessionId, questionId, answerText) {
  return request.post(`/interview/${sessionId}/answer`, {
    question_id: questionId, answer_text: answerText,
  })
}

export function getScore(sessionId) {
  return request.get(`/interview/${sessionId}/score`)
}

export function getReport(sessionId) {
  return request.get(`/interview/${sessionId}/report`)
}

// ===== 语音相关 API =====

export function transcribeAudio(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/speech/transcribe', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getVoices() {
  return request.get('/speech/voices')
}
