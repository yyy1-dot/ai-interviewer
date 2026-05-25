"""
AI面试官 - API路由层

本文件包含：
  1. 请求/响应数据结构（Pydantic模型）
  2. 统一响应格式（success / fail）
  3. JWT认证中间件
  4. REST API路由（认证、简历、面试、报告、语音）
  5. WebSocket实时面试

路由结构：
  /api/v1/auth/*     —— 用户注册、登录
  /api/v1/resume/*   —— 简历上传、解析
  /api/v1/interview/* —— 面试流程
  /api/v1/report/*   —— 历史报告
  /api/v1/speech/*   —— 语音服务
  /ws/interview      —— WebSocket实时面试
"""

import json
import base64
import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, InterviewSession, Report
from app.services import (
    register_user, authenticate_user, create_access_token, decode_access_token,
    get_user_by_id, save_uploaded_file, get_resume, parse_and_update_resume,
    start_interview, submit_answer, get_score_summary, generate_final_report,
    transcribe_audio, synthesize_speech, VOICE_OPTIONS,
)


# ============================================================
#  1. 请求/响应数据结构
# ============================================================

class UserRegisterRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 32:
            raise ValueError("用户名长度需在2-32个字符之间")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 6 or len(v) > 64:
            raise ValueError("密码长度需在6-64个字符之间")
        return v


class UserLoginRequest(BaseModel):
    username: str
    password: str


class StartInterviewRequest(BaseModel):
    resume_id: int
    position: str


class AnswerRequest(BaseModel):
    question_id: int
    answer_text: str


# ============================================================
#  2. 统一响应格式
# ============================================================

def success(data: Any = None, message: str = "操作成功") -> JSONResponse:
    """返回成功响应 {code:200, message, data}"""
    return JSONResponse(status_code=200, content=jsonable_encoder({
        "code": 200, "message": message, "data": data,
    }))


def fail(message: str = "操作失败", code: int = 400, status_code: int = 400) -> JSONResponse:
    """返回失败响应 {code, message, data:null}"""
    return JSONResponse(status_code=status_code, content=jsonable_encoder({
        "code": code, "message": message, "data": None,
    }))


# ============================================================
#  3. JWT认证中间件
# ============================================================

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从HTTP请求头解析JWT令牌，返回当前登录用户"""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token无效或已过期")

    user_id = int(payload.get("sub"))
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# ============================================================
#  创建主路由
# ============================================================

router = APIRouter(prefix="/api/v1")


# ============================================================
#  4. REST API —— 认证模块 /api/v1/auth
# ============================================================

auth_router = APIRouter(prefix="/auth", tags=["用户认证"])


@auth_router.post("/register")
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    try:
        user = await register_user(db, req.username, req.email, req.password)
        token = create_access_token(user.id, user.username)
        return success(data={
            "access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "username": user.username,
                     "email": user.email, "role": user.role,
                     "created_at": str(user.created_at) if user.created_at else None},
        }, message="注册成功")
    except ValueError as e:
        return fail(message=str(e))


@auth_router.post("/login")
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    try:
        user = await authenticate_user(db, req.username, req.password)
        token = create_access_token(user.id, user.username)
        return success(data={
            "access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "username": user.username,
                     "email": user.email, "role": user.role,
                     "created_at": str(user.created_at) if user.created_at else None},
        }, message="登录成功")
    except ValueError as e:
        return fail(message=str(e))


@auth_router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return success(data={
        "id": current_user.id, "username": current_user.username,
        "email": current_user.email, "role": current_user.role,
        "created_at": str(current_user.created_at) if current_user.created_at else None,
    })


# ============================================================
#  5. REST API —— 简历模块 /api/v1/resume
# ============================================================

resume_router = APIRouter(prefix="/resume", tags=["简历管理"])


@resume_router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传PDF简历"""
    try:
        resume = await save_uploaded_file(db, current_user.id, file)
        return success(data={
            "id": resume.id, "filename": resume.filename,
            "original_filename": resume.original_filename, "status": "uploaded",
            "created_at": str(resume.created_at) if resume.created_at else None,
        }, message="简历上传成功")
    except ValueError as e:
        return fail(message=str(e))


@resume_router.get("/{resume_id}")
async def get_resume_detail(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看简历详情"""
    resume = await get_resume(db, resume_id, current_user.id)
    if not resume:
        return fail(message="简历不存在", status_code=404)
    return success(data={
        "id": resume.id, "user_id": resume.user_id,
        "filename": resume.filename, "original_filename": resume.original_filename,
        "parsed_content": resume.parsed_content,
        "education": resume.education, "experience": resume.experience,
        "skills": resume.skills,
        "created_at": str(resume.created_at) if resume.created_at else None,
    })


@resume_router.post("/{resume_id}/parse")
async def parse_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解析简历内容（提取教育、技能、经验）"""
    try:
        resume = await parse_and_update_resume(db, resume_id, current_user.id)
        return success(data={
            "id": resume.id, "parsed_content": resume.parsed_content,
            "education": resume.education, "experience": resume.experience,
            "skills": resume.skills,
        }, message="简历解析完成")
    except ValueError as e:
        return fail(message=str(e))


# ============================================================
#  6. REST API —— 面试模块 /api/v1/interview
# ============================================================

interview_router = APIRouter(prefix="/interview", tags=["面试管理"])


@interview_router.post("/start")
async def start_interview_route(
    req: StartInterviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """开始面试（创建会话+AI出题）"""
    try:
        data = await start_interview(db, current_user.id, req.resume_id, req.position)
        return success(data=data, message="面试开始")
    except ValueError as e:
        return fail(message=str(e))


@interview_router.post("/{session_id}/answer")
async def submit_answer_route(
    session_id: int,
    req: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交回答（AI评分+返回下一题）"""
    try:
        data = await submit_answer(db, current_user.id, session_id, req.question_id, req.answer_text)
        return success(data=data, message="回答已提交")
    except ValueError as e:
        return fail(message=str(e))


@interview_router.get("/{session_id}/score")
async def get_score_route(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看得分汇总"""
    try:
        data = await get_score_summary(db, current_user.id, session_id)
        return success(data=data)
    except ValueError as e:
        return fail(message=str(e))


@interview_router.get("/{session_id}/report")
async def get_report_route(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成/查看面试报告"""
    try:
        data = await generate_final_report(db, current_user.id, session_id)
        return success(data=data)
    except ValueError as e:
        return fail(message=str(e))


# ============================================================
#  7. REST API —— 报告模块 /api/v1/report
# ============================================================

report_router = APIRouter(prefix="/report", tags=["面试报告"])


@report_router.get("/list")
async def list_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的历史面试列表"""
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    return success(data=[
        {
            "id": s.id, "position": s.position, "status": s.status,
            "total_score": s.total_score,
            "created_at": str(s.created_at) if s.created_at else None,
        }
        for s in sessions
    ])


@report_router.get("/{report_id}")
async def get_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看报告详情"""
    result = await db.execute(
        select(Report).where(Report.session_id == report_id, Report.user_id == current_user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        return fail(message="报告不存在", status_code=404)
    return success(data={
        "session_id": report.session_id, "total_score": report.total_score,
        "detail_scores": report.detail_scores, "strengths": report.strengths,
        "weaknesses": report.weaknesses, "suggestion": report.suggestion,
        "created_at": str(report.created_at) if report.created_at else None,
    })


# ============================================================
#  8. REST API —— 语音模块 /api/v1/speech
# ============================================================

speech_router = APIRouter(prefix="/speech", tags=["语音服务"])


@speech_router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """语音转文字（上传音频文件，返回识别文本）"""
    try:
        audio_data = await file.read()
        text = await transcribe_audio(audio_data, file.filename or "audio.webm")
        return success(data={"text": text}, message="语音识别完成")
    except Exception as e:
        return fail(message=f"语音识别失败: {str(e)}")


@speech_router.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    voice: str = Form(default="zh-CN-XiaoxiaoNeural"),
    current_user: User = Depends(get_current_user),
):
    """文字转语音（返回MP3音频流）"""
    try:
        audio_bytes = await synthesize_speech(text, voice)
        return Response(
            content=audio_bytes, media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except Exception as e:
        return fail(message=f"语音合成失败: {str(e)}")


@speech_router.get("/voices")
async def get_voices(current_user: User = Depends(get_current_user)):
    """获取可用发音人列表"""
    return success(data=VOICE_OPTIONS)


# 注册子路由
router.include_router(auth_router)
router.include_router(resume_router)
router.include_router(interview_router)
router.include_router(report_router)
router.include_router(speech_router)


# ============================================================
#  9. WebSocket —— 实时面试 /ws/interview
# ============================================================

async def interview_ws(websocket: WebSocket):
    """
    WebSocket实时面试处理器

    客户端消息类型：
      start       → 开始面试，参数: resume_id, position
      text_answer → 文字回答，参数: question_id, text
      voice_answer→ 语音回答，参数: question_id, audio(base64)
      report      → 请求生成报告
      ping        → 心跳

    服务端推送类型：
      connected / interview_started / question / score
      feedback_audio / transcription / report / all_answered / error
    """
    # ----- 认证 -----
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="missing token")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4002, reason="invalid token")
        return

    user_id = int(payload.get("sub"))
    await websocket.accept()

    # 辅助函数
    async def send_msg(msg_type: str, **kwargs):
        await websocket.send_text(json.dumps({"type": msg_type, **kwargs}, ensure_ascii=False))

    async def send_error(message: str):
        await send_msg("error", message=message)

    session_id = None
    audio_cache = {}  # 预缓存题目语音 {question_id: base64_audio}

    try:
        await send_msg("connected")

        from app.database import get_session
        async with get_session() as db:
            user = await get_user_by_id(db, user_id)
            if not user:
                await websocket.close(code=4003)
                return

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_error("invalid JSON")
                continue

            msg_type = msg.get("type")

            # ===== 开始面试 =====
            if msg_type == "start":
                resume_id = msg.get("resume_id")
                position = msg.get("position", "")
                if not resume_id or not position:
                    await send_error("missing resume_id or position")
                    continue

                async with get_session() as db:
                    try:
                        data = await start_interview(db, user_id, int(resume_id), position)
                    except ValueError as e:
                        await send_error(str(e))
                        continue

                session_id = data["session_id"]
                questions = data["questions"]

                # 预合成所有题目语音的辅助函数
                async def _synth(text):
                    try:
                        audio = await asyncio.wait_for(synthesize_speech(text), timeout=15)
                        return base64.b64encode(audio).decode()
                    except Exception:
                        return ""

                await send_msg("interview_started", session_id=session_id, position=position)

                # 先发第一题（带语音）
                if questions:
                    q = questions[0]
                    q0_audio = await _synth(q["question_text"])
                    await send_msg("question", data=q, question_audio=q0_audio,
                                   current=0, total=len(questions))

                # 后台并行合成剩余题目语音
                if len(questions) > 1:
                    async def _pre_synth_rest():
                        tasks = [_synth(q["question_text"]) for q in questions[1:]]
                        results = await asyncio.gather(*tasks)
                        for q, audio in zip(questions[1:], results):
                            audio_cache[q["id"]] = audio
                    asyncio.create_task(_pre_synth_rest())

            # ===== 文字回答 =====
            elif msg_type == "text_answer":
                if not session_id:
                    await send_error("interview not started")
                    continue
                question_id = msg.get("question_id")
                text = msg.get("text", "").strip()
                if not question_id or not text:
                    await send_error("missing question_id or text")
                    continue

                async with get_session() as db:
                    try:
                        result = await submit_answer(db, user_id, session_id, int(question_id), text)
                    except ValueError as e:
                        await send_error(str(e))
                        continue

                next_q = result.get("next_question")
                await send_msg("score", score=result["score"], feedback=result["feedback"])

                # 后台合成反馈语音
                if result.get("feedback"):
                    async def _send_fb_audio():
                        try:
                            fb = await asyncio.wait_for(synthesize_speech(result["feedback"]), timeout=12)
                            await send_msg("feedback_audio", data=base64.b64encode(fb).decode())
                        except Exception:
                            pass
                    asyncio.create_task(_send_fb_audio())

                # 发送下一题
                if next_q:
                    nq_audio = audio_cache.get(next_q["id"], "")
                    if not nq_audio:
                        try:
                            nq = await asyncio.wait_for(synthesize_speech(next_q["question_text"]), timeout=12)
                            nq_audio = base64.b64encode(nq).decode()
                            audio_cache[next_q["id"]] = nq_audio
                        except Exception:
                            pass
                    await send_msg("question", data=next_q, question_audio=nq_audio)
                else:
                    await send_msg("all_answered")

            # ===== 语音回答 =====
            elif msg_type == "voice_answer":
                if not session_id:
                    await send_error("interview not started")
                    continue
                question_id = msg.get("question_id")
                audio_b64 = msg.get("audio", "")
                if not question_id or not audio_b64:
                    await send_error("missing question_id or audio")
                    continue

                # 流式处理：先语音识别 → 发送识别文本 → 评分
                try:
                    audio_data = base64.b64decode(audio_b64)
                    text = await asyncio.wait_for(
                        transcribe_audio(audio_data, filename="answer.webm"), timeout=30
                    )
                except Exception as e:
                    await send_error(f"语音识别失败: {str(e)}")
                    continue

                await send_msg("transcription", text=text)

                async with get_session() as db:
                    try:
                        result = await submit_answer(db, user_id, session_id, int(question_id), text)
                    except ValueError as e:
                        await send_error(str(e))
                        continue

                next_q = result.get("next_question")
                await send_msg("score", score=result["score"], feedback=result["feedback"])

                if result.get("feedback"):
                    async def _send_fb2():
                        try:
                            fb = await asyncio.wait_for(synthesize_speech(result["feedback"]), timeout=12)
                            await send_msg("feedback_audio", data=base64.b64encode(fb).decode())
                        except Exception:
                            pass
                    asyncio.create_task(_send_fb2())

                if next_q:
                    nq_audio = audio_cache.get(next_q["id"], "")
                    if not nq_audio:
                        try:
                            nq = await asyncio.wait_for(synthesize_speech(next_q["question_text"]), timeout=12)
                            nq_audio = base64.b64encode(nq).decode()
                            audio_cache[next_q["id"]] = nq_audio
                        except Exception:
                            pass
                    await send_msg("question", data=next_q, question_audio=nq_audio)
                else:
                    await send_msg("all_answered")

            # ===== 生成报告 =====
            elif msg_type == "report":
                if not session_id:
                    await send_error("interview not started")
                    continue
                async with get_session() as db:
                    try:
                        report = await generate_final_report(db, user_id, session_id)
                    except ValueError as e:
                        await send_error(str(e))
                        continue
                await send_msg("report", data=report)

            elif msg_type == "ping":
                await send_msg("pong")

            else:
                await send_error(f"unknown type: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await send_error(str(e))
        except Exception:
            pass
