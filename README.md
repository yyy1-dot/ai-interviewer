# AI面试官

基于 DeepSeek 大语言模型的智能面试官系统。上传简历 → AI 自动出题 → 文字或语音作答 → 实时评分 → 生成面试报告，一站式完成模拟面试。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.10+ / FastAPI |
| 大模型 | DeepSeek V4 API（OpenAI 兼容格式） |
| 语音识别 | OpenAI Whisper (tiny) |
| 语音合成 | Microsoft Edge-TTS |
| 前端 | Vue 3 + Vite + Element Plus |
| 实时通信 | WebSocket |
| 数据库 | MySQL 8.0（SQLAlchemy + aiomysql 异步驱动） |
| 缓存 | Redis |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 7+

### 2. 创建数据库

```sql
CREATE DATABASE ai_interview CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后用项目根目录的 `init_db.sql` 初始化表结构：

```bash
mysql -u root -p < init_db.sql
```

### 3. 后端启动

```bash
cd backend
cp .env.example .env          # 编辑 .env，填入数据库密码和 DeepSeek API Key
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 5. 一键启动（Windows）

双击项目根目录的 `start.bat`，会自动打开两个命令行窗口分别启动后端和前端。

## 项目结构

```
ai面试官/
├── backend/
│   ├── app/
│   │   ├── main.py          # 应用入口，FastAPI 创建、Redis 生命周期、路由注册
│   │   ├── config.py        # 配置管理（环境变量 → Pydantic Settings）
│   │   ├── database.py      # 异步数据库引擎、会话工厂、Base 基类
│   │   ├── models.py        # 6 张表的 SQLAlchemy 模型定义
│   │   ├── routes.py        # 所有 API 路由 + Pydantic 校验 + JWT 鉴权 + WebSocket
│   │   └── services.py      # 核心业务逻辑（认证、简历、AI、面试、语音）
│   ├── alembic/             # 数据库迁移（可选，也可直接用 init_db.sql）
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/           # 6 个页面组件
│   │   │   ├── Home.vue     # 首页（产品介绍）
│   │   │   ├── Login.vue    # 登录
│   │   │   ├── Register.vue # 注册
│   │   │   ├── Dashboard.vue# 控制台（上传简历 + 开始面试）
│   │   │   ├── Interview.vue# 面试页（实时对话，支持文字/语音输入）
│   │   │   └── History.vue  # 历史记录
│   │   ├── router/index.js  # Vue Router（含登录守卫）
│   │   ├── store.js         # Pinia 状态管理（auth、interview 两个 Store）
│   │   ├── api.js           # Axios 封装 + 所有 API 函数
│   │   ├── App.vue          # 根组件
│   │   └── main.js          # 入口（挂载 Element Plus、Router、Pinia）
│   ├── vite.config.js       # Vite 配置（含 API 代理）
│   └── package.json
├── init_db.sql              # 数据库建表脚本（可直接导入 MySQL）
├── start.bat                # Windows 一键启动脚本
└── README.md
```

## 数据库表设计

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| users | 用户 | 用户名、邮箱、密码哈希、角色 |
| resumes | 简历 | 文件路径、原始文本、学历/经验/技能 |
| interview_sessions | 面试会话 | 岗位、状态(pending/in_progress/completed)、总分 |
| questions | 题目 | 题目内容、类型(technical/behavioral/project)、难度 |
| answers | 回答 | 回答文本、音频路径、得分、评语 |
| reports | 报告 | 总分、各维度得分(JSON)、优缺点、建议 |

**表关系**：users → resumes → interview_sessions → questions → answers，interview_sessions → reports（一对一）。

## 业务流程

```
注册/登录 → 上传 PDF 简历 → 解析简历内容 → 选择岗位开始面试
    → AI 出 5 道题 → 逐题作答（文字/语音）→ AI 实时评分
    → 生成面试报告（总分、各维度得分、优缺点、建议）
```

## API 接口概览

### 认证 `/api/v1/auth`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /register | 注册 |
| POST | /login | 登录 |
| GET | /me | 获取当前用户 |

### 简历 `/api/v1/resume`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /upload | 上传 PDF |
| GET | /{id} | 查看详情 |
| POST | /{id}/parse | 解析内容 |

### 面试 `/api/v1/interview`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /start | 开始面试（AI 出题） |
| POST | /{session_id}/answer | 提交回答（AI 评分） |
| GET | /{session_id}/score | 得分汇总 |
| GET | /{session_id}/report | 生成报告 |

### 语音 `/api/v1/speech`
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /transcribe | 语音转文字 |
| POST | /synthesize | 文字转语音（返回 MP3） |
| GET | /voices | 发音人列表 |

### 报告 `/api/v1/report`
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /list | 历史面试列表 |
| GET | /{id} | 报告详情 |

### WebSocket `/ws/interview?token=xxx`

| 客户端 → 服务端 | 说明 |
|------------------|------|
| `{type: "start", resume_id, position}` | 开始面试 |
| `{type: "text_answer", question_id, text}` | 文字作答 |
| `{type: "voice_answer", question_id, audio}` | 语音作答（base64） |
| `{type: "report"}` | 请求生成报告 |
| `{type: "ping"}` | 心跳 |

| 服务端 → 客户端 | 说明 |
|------------------|------|
| `{type: "question", data}` | 推送题目（含语音） |
| `{type: "score", score, feedback}` | 返回评分和评语 |
| `{type: "feedback_audio", data}` | 评语语音 |
| `{type: "transcription", text}` | 语音识别结果 |
| `{type: "report", data}` | 推送报告 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| MYSQL_HOST | MySQL 地址 | 127.0.0.1 |
| MYSQL_PORT | MySQL 端口 | 3306 |
| MYSQL_USER | MySQL 用户名 | root |
| MYSQL_PASSWORD | MySQL 密码 | - |
| MYSQL_DATABASE | 数据库名 | ai_interview |
| REDIS_HOST | Redis 地址 | 127.0.0.1 |
| REDIS_PORT | Redis 端口 | 6379 |
| REDIS_PASSWORD | Redis 密码 | - |
| DEEPSEEK_API_KEY | DeepSeek API Key | - |
| DEEPSEEK_BASE_URL | API 地址 | https://api.deepseek.com/v1 |
| DEEPSEEK_MODEL | 模型名 | deepseek-chat |
| JWT_SECRET_KEY | JWT 签名密钥 | - |
| JWT_EXPIRE_MINUTES | Token 有效期（分钟） | 1440 |
| UPLOAD_DIR | 文件上传目录 | uploads |
| MAX_UPLOAD_SIZE_MB | 上传大小限制 | 10 |
