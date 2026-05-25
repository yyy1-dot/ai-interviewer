"""
AI面试官 - 应用入口

启动方式：uvicorn app.main:app --reload --port 8000

本文件只做5件事：
  1. 读取配置
  2. 初始化数据库和Redis
  3. 创建FastAPI应用
  4. 注册所有API路由
  5. 管理应用生命周期（启动/关闭）
"""

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


# ===== Redis 连接池 =====

redis_pool = aioredis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD or None,
    db=settings.REDIS_DB,
    max_connections=50,
    decode_responses=True,
)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """获取Redis客户端（供其他模块使用）"""
    return aioredis.Redis(connection_pool=redis_pool)


async def init_redis():
    """启动时初始化Redis连接"""
    global _redis_client
    _redis_client = aioredis.Redis(connection_pool=redis_pool)
    await _redis_client.ping()


async def close_redis():
    """关闭时断开Redis连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    await redis_pool.disconnect()


# ===== 应用生命周期 =====

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的处理"""
    await init_redis()
    yield
    await close_redis()


# ===== 创建 FastAPI 应用 =====

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 注册所有路由 =====

from app.routes import router as api_router, interview_ws  # noqa: E402

app.include_router(api_router)
app.websocket("/ws/interview")(interview_ws)


# ===== 根路径 & 健康检查 =====

@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} v{settings.APP_VERSION}"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
