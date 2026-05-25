<template>
  <div class="home">
    <div class="hero">
      <h1>AI面试官</h1>
      <p>基于大语言模型的智能面试平台，让每一次面试都高效、专业、公平</p>
      <div class="actions">
        <el-button type="primary" size="large" @click="$router.push('/login')">立即登录</el-button>
        <el-button size="large" @click="$router.push('/register')">注册账号</el-button>
      </div>
    </div>
    <div class="features">
      <div class="feature-card" v-for="f in features" :key="f.title">
        <h3>{{ f.title }}</h3>
        <p>{{ f.desc }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const features = [
  { title: '简历解析', desc: '上传PDF简历，AI自动提取教育背景、技能和工作经验' },
  { title: '智能出题', desc: '基于简历内容和岗位需求，定制化生成面试题目' },
  { title: '实时评分', desc: 'AI即时评估回答质量，提供专业反馈和改进建议' },
  { title: '语音交互', desc: '支持语音输入输出，模拟真实面试对话场景' },
  { title: '报告生成', desc: '自动生成详细面试评估报告，多维度评分' },
]
</script>

<style scoped>
.home {
  min-height: 100vh;
}
.hero {
  text-align: center;
  padding: 100px 20px 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}
.hero h1 {
  font-size: 48px;
  margin-bottom: 16px;
}
.hero p {
  font-size: 18px;
  opacity: 0.9;
  max-width: 600px;
  margin: 0 auto 32px;
}
.actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}
.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  max-width: 1000px;
  margin: 60px auto;
  padding: 0 20px;
}
.feature-card {
  padding: 32px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  text-align: center;
}
.feature-card h3 {
  margin-bottom: 12px;
  color: #303133;
}
.feature-card p {
  color: #909399;
  line-height: 1.6;
}
</style>
