"""
AI面试官 - 业务逻辑层

本文件包含所有核心业务逻辑，按功能分为5个区块：
  1. 认证服务 —— 密码加密、JWT令牌、用户注册登录
  2. 简历服务 —— PDF上传、文本提取、简历解析
  3. AI服务   —— 调用DeepSeek生成题目、评分、出报告
  4. 面试服务 —— 面试流程编排（开始→答题→评分→报告）
  5. 语音服务 —— Whisper语音识别、Edge-TTS语音合成
"""

import io
import os
import re
import json
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from PyPDF2 import PdfReader
from openai import OpenAI

from app.config import settings
from app.models import User, Resume, InterviewSession, Question, Answer, Report


# ============================================================
#  1. 认证服务 —— 密码加密、JWT令牌、用户注册登录
# ============================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """将明文密码加密为哈希值（存入数据库时用）"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证用户输入的密码是否与数据库中的哈希值匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, username: str) -> str:
    """生成JWT访问令牌，有效期为配置中设定的分钟数"""
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),      # subject = 用户ID
        "username": username,
        "exp": expire,            # 过期时间
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解析JWT令牌，成功返回payload字典，失败返回None"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


async def register_user(db: AsyncSession, username: str, email: str, password: str) -> User:
    """注册新用户：检查用户名/邮箱是否重复，创建记录，返回用户对象"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise ValueError("用户名已存在")

    # 检查邮箱是否已被注册
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise ValueError("邮箱已被注册")

    # 创建用户并保存到数据库
    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
    """验证用户登录：检查用户名和密码是否正确"""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """根据ID查询用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ============================================================
#  2. 简历服务 —— PDF上传、文本提取、简历解析
# ============================================================

ALLOWED_EXTENSIONS = {".pdf"}


def _validate_pdf(file: UploadFile) -> None:
    """验证上传文件是否为PDF格式"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持PDF格式文件")


def _validate_file_size(file: UploadFile) -> None:
    """验证文件大小是否超过限制"""
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        raise ValueError(f"文件大小不能超过{settings.MAX_UPLOAD_SIZE_MB}MB")


def _get_upload_dir() -> Path:
    """获取上传目录，不存在则自动创建"""
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _extract_text_from_pdf(file_path: str) -> str:
    """从PDF文件中提取所有文本内容"""
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n".join(text_parts)


def _basic_parse_resume(text: str) -> dict:
    """用正则表达式从简历文本中提取教育背景、技能和工作经验"""
    result = {"education": "", "experience": "", "skills": ""}

    # 提取教育背景
    education_patterns = [
        r"(教育背景|学历|教育经历)[\s\S]*",
        r"(大学|学院|本科|硕士|博士|大专).*",
    ]
    for pattern in education_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["education"] = match.group(0)[:500]
            break

    # 提取技能关键词
    skill_keywords = [
        "Python", "Java", "Go", "C\\+\\+", "JavaScript", "TypeScript", "SQL", "MySQL",
        "Redis", "Docker", "Kubernetes", "Linux", "Git", "AWS", "机器学习", "深度学习",
        "NLP", "数据挖掘", "TensorFlow", "PyTorch", "FastAPI", "Django", "Flask",
        "Vue", "React", "Node", "Spring", "微服务", "分布式", "Hadoop", "Spark",
    ]
    found_skills = []
    for skill in skill_keywords:
        if re.search(skill, text, re.IGNORECASE):
            found_skills.append(skill.replace("\\", ""))
    result["skills"] = ", ".join(found_skills)[:1000]

    # 提取工作经验
    experience_patterns = [
        r"(工作经历|项目经验|实习经历|工作经验)[\s\S]*",
        r"(公司|企业|单位).*(任职|工作|负责|参与).*",
    ]
    for pattern in experience_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["experience"] = match.group(0)[:2000]
            break

    return result


async def save_uploaded_file(db: AsyncSession, user_id: int, file: UploadFile) -> Resume:
    """保存上传的PDF文件到磁盘，并在数据库中创建简历记录"""
    _validate_pdf(file)
    _validate_file_size(file)

    upload_dir = _get_upload_dir()
    unique_name = f"{uuid.uuid4().hex}.pdf"
    file_path = upload_dir / unique_name

    content = await file.read()
    file_path.write_bytes(content)

    resume = Resume(
        user_id=user_id,
        filename=unique_name,
        original_filename=file.filename or "unknown.pdf",
        file_path=str(file_path),
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return resume


async def get_resume(db: AsyncSession, resume_id: int, user_id: int) -> Resume | None:
    """查询指定简历，确保属于当前用户"""
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def parse_and_update_resume(db: AsyncSession, resume_id: int, user_id: int) -> Resume:
    """解析简历PDF内容，提取字段并更新到数据库"""
    resume = await get_resume(db, resume_id, user_id)
    if not resume:
        raise ValueError("简历不存在")

    # 从PDF提取文本 → 正则解析 → 存入数据库
    full_text = _extract_text_from_pdf(resume.file_path)
    parsed = _basic_parse_resume(full_text)

    resume.parsed_content = full_text[:5000]
    resume.education = parsed["education"]
    resume.experience = parsed["experience"]
    resume.skills = parsed["skills"]

    await db.flush()
    await db.refresh(resume)
    return resume


# ============================================================
#  3. AI服务 —— 调用DeepSeek API生成题目、评分、出报告
# ============================================================

_ai_client: OpenAI | None = None


def _get_ai_client() -> OpenAI:
    """获取OpenAI客户端（全局单例，兼容DeepSeek API）"""
    global _ai_client
    if _ai_client is None:
        _ai_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _ai_client


def _call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """调用DeepSeek大模型的统一入口"""
    response = _get_ai_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def generate_questions(parsed_resume: str, position: str, count: int = 5) -> list[dict]:
    """根据简历内容和应聘岗位，让AI生成面试题目"""
    system_prompt = (
        f"你是一位资深{position}面试官。你需要根据候选人的简历内容，"
        f"生成{count}道专业面试题目。题目应覆盖技术能力、项目经验和综合素质三个维度，"
        f"难度由浅入深。请严格以JSON数组格式返回，每道题包含以下字段："
        f'question_text(题目内容)、question_type(类型: technical/behavioral/project)、'
        f'difficulty(难度: easy/medium/hard)。'
    )
    user_prompt = f"候选人简历内容：\n{parsed_resume[:3000]}"

    content = _call_deepseek(system_prompt, user_prompt, temperature=0.8)
    # 从AI返回内容中提取JSON数组
    try:
        json_start = content.find("[")
        json_end = content.rfind("]") + 1
        if json_start != -1 and json_end > json_start:
            return json.loads(content[json_start:json_end])
    except (json.JSONDecodeError, IndexError):
        pass
    return []


def score_answer(question: str, answer_text: str, position: str) -> dict:
    """让AI给候选人的回答打分（0-100分）+ 给出评价"""
    system_prompt = (
        f"你是一位严格的{position}面试评分官。请根据面试题目和候选人的回答，"
        f"给出0-100分的评分和简要评价。评分标准：技术准确性(40分)、表达清晰度(30分)、"
        f"实践深度(30分)。严格以JSON格式返回："
        f'{{"score": 数字, "feedback": "评价内容"}}'
    )
    user_prompt = f"面试题目：{question}\n候选人回答：{answer_text}"

    content = _call_deepseek(system_prompt, user_prompt, temperature=0.3)
    try:
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            return json.loads(content[json_start:json_end])
    except (json.JSONDecodeError, IndexError):
        pass
    return {"score": 0, "feedback": "评分异常"}


def generate_report(position: str, qa_pairs: list[dict]) -> dict:
    """让AI根据所有问答记录生成综合面试评估报告"""
    qa_text = ""
    for idx, qa in enumerate(qa_pairs, 1):
        qa_text += (
            f"第{idx}题 [{qa.get('question_type', '')}/{qa.get('difficulty', '')}]: "
            f"{qa.get('question_text', '')}\n"
            f"回答: {qa.get('answer_text', '无')}\n"
            f"得分: {qa.get('score', 0)}\n\n"
        )

    system_prompt = (
        f"你是一位资深的{position}面试评估专家。请根据完整的面试问答记录，"
        f"生成一份全面的面试评估报告。严格以JSON格式返回：\n"
        f'{{"total_score": 数字(0-100), '
        f'"detail_scores": {{"技术能力": 数字, "沟通表达": 数字, "项目经验": 数字, "综合素质": 数字}}, '
        f'"strengths": "优点描述", '
        f'"weaknesses": "不足描述", '
        f'"suggestion": "建议"}}'
    )
    user_prompt = f"应聘岗位：{position}\n\n面试记录：\n{qa_text}"

    content = _call_deepseek(system_prompt, user_prompt, temperature=0.5)
    try:
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            return json.loads(content[json_start:json_end])
    except (json.JSONDecodeError, IndexError):
        pass
    return {
        "total_score": 0, "detail_scores": {},
        "strengths": "报告生成异常", "weaknesses": "", "suggestion": "",
    }


# ============================================================
#  4. 面试服务 —— 面试流程编排
# ============================================================

async def start_interview(db: AsyncSession, user_id: int, resume_id: int, position: str) -> dict:
    """开始面试：创建会话 → AI出题 → 保存题目 → 返回题目列表"""
    # 验证简历存在且属于当前用户
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise ValueError("简历不存在")
    if not resume.parsed_content:
        raise ValueError("请先解析简历后再开始面试")

    # 创建面试会话
    session = InterviewSession(
        user_id=user_id, resume_id=resume_id, position=position, status="pending",
    )
    db.add(session)
    await db.flush()

    # 调用AI生成题目
    questions_data = generate_questions(resume.parsed_content, position, count=5)
    if not questions_data:
        raise ValueError("AI生成题目失败，请稍后重试")

    # 保存题目到数据库
    questions = []
    for idx, qd in enumerate(questions_data):
        q = Question(
            session_id=session.id,
            question_text=qd.get("question_text", ""),
            question_type=qd.get("question_type", "technical"),
            difficulty=qd.get("difficulty", "medium"),
            order_index=idx + 1,
        )
        db.add(q)
        questions.append(q)

    session.status = "in_progress"
    session.start_time = datetime.utcnow()

    await db.flush()
    for q in questions:
        await db.refresh(q)
    await db.refresh(session)

    return {
        "session_id": session.id,
        "position": position,
        "questions": [
            {
                "id": q.id, "question_text": q.question_text,
                "question_type": q.question_type, "difficulty": q.difficulty,
                "order_index": q.order_index,
            }
            for q in questions
        ],
    }


async def submit_answer(
    db: AsyncSession, user_id: int, session_id: int, question_id: int, answer_text: str
) -> dict:
    """提交回答：AI评分 → 保存答案 → 返回下一题"""
    # 验证会话
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("面试会话不存在")
    if session.status == "completed":
        raise ValueError("面试已完成")
    if session.status == "pending":
        session.status = "in_progress"

    # 验证题目
    result = await db.execute(
        select(Question).where(Question.id == question_id, Question.session_id == session_id)
    )
    question = result.scalar_one_or_none()
    if not question:
        raise ValueError("题目不存在")

    # 防止重复答题
    result = await db.execute(
        select(Answer).where(Answer.question_id == question_id, Answer.session_id == session_id)
    )
    if result.scalar_one_or_none():
        raise ValueError("该题已经回答过")

    # AI评分
    score_data = score_answer(question.question_text, answer_text, session.position)
    score = score_data.get("score", 0)
    feedback = score_data.get("feedback", "")

    # 保存回答
    answer = Answer(
        question_id=question_id, session_id=session_id,
        answer_text=answer_text, score=float(score), feedback=feedback,
    )
    db.add(answer)
    await db.flush()

    # 查找下一题（按order_index升序）
    result = await db.execute(
        select(Question)
        .where(Question.session_id == session_id, Question.order_index > question.order_index)
        .order_by(Question.order_index.asc())
        .limit(1)
    )
    next_question = result.scalar_one_or_none()

    # 检查是否所有题都答完了
    result = await db.execute(select(Answer).where(Answer.session_id == session_id))
    all_answers = result.scalars().all()
    result = await db.execute(select(Question).where(Question.session_id == session_id))
    all_questions = result.scalars().all()

    if len(all_answers) >= len(all_questions):
        session.status = "completed"
        session.end_time = datetime.utcnow()

    await db.flush()

    next_q_data = None
    if next_question and session.status != "completed":
        next_q_data = {
            "id": next_question.id, "question_text": next_question.question_text,
            "question_type": next_question.question_type, "difficulty": next_question.difficulty,
            "order_index": next_question.order_index,
        }

    return {
        "score": score, "feedback": feedback,
        "next_question": next_q_data, "session_status": session.status,
    }


async def get_score_summary(db: AsyncSession, user_id: int, session_id: int) -> dict:
    """获取面试得分汇总"""
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("面试会话不存在")

    result = await db.execute(select(Answer).where(Answer.session_id == session_id))
    answers = result.scalars().all()
    result = await db.execute(select(Question).where(Question.session_id == session_id))
    questions = result.scalars().all()

    answer_list = []
    for ans in answers:
        q = next((q for q in questions if q.id == ans.question_id), None)
        answer_list.append({
            "question_id": ans.question_id,
            "question_text": q.question_text if q else "",
            "question_type": q.question_type if q else "",
            "answer_text": ans.answer_text,
            "score": ans.score, "feedback": ans.feedback,
        })

    total = sum(a.score for a in answers if a.score) / max(len(answers), 1) if answers else 0

    return {
        "session_id": session_id, "status": session.status,
        "total_score": round(total, 1),
        "question_count": len(questions), "answered_count": len(answers),
        "answers": answer_list,
    }


async def generate_final_report(db: AsyncSession, user_id: int, session_id: int) -> dict:
    """生成最终面试报告（已有报告则直接返回）"""
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id, InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("面试会话不存在")
    if session.status != "completed":
        raise ValueError("面试尚未完成，无法生成报告")

    # 已有报告直接返回
    result = await db.execute(select(Report).where(Report.session_id == session_id))
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "session_id": existing.session_id, "position": session.position,
            "total_score": existing.total_score,
            "detail_scores": json.loads(existing.detail_scores) if existing.detail_scores else {},
            "strengths": existing.strengths or "",
            "weaknesses": existing.weaknesses or "",
            "suggestion": existing.suggestion or "",
            "created_at": str(existing.created_at) if existing.created_at else None,
        }

    # 收集所有问答对
    result = await db.execute(select(Answer).where(Answer.session_id == session_id))
    answers = result.scalars().all()
    result = await db.execute(
        select(Question).where(Question.session_id == session_id).order_by(Question.order_index)
    )
    questions = result.scalars().all()

    qa_pairs = []
    for q in questions:
        ans = next((a for a in answers if a.question_id == q.id), None)
        qa_pairs.append({
            "question_text": q.question_text, "question_type": q.question_type,
            "difficulty": q.difficulty,
            "answer_text": ans.answer_text if ans else "未作答",
            "score": ans.score if ans else 0,
        })

    # AI生成报告
    report_data = generate_report(session.position, qa_pairs)

    total_score = report_data.get("total_score", 0)
    if not total_score and answers:
        total_score = round(sum(a.score for a in answers if a.score) / len(answers), 1)

    report = Report(
        session_id=session_id, user_id=user_id, total_score=float(total_score),
        detail_scores=json.dumps(report_data.get("detail_scores", {}), ensure_ascii=False),
        strengths=report_data.get("strengths", ""),
        weaknesses=report_data.get("weaknesses", ""),
        suggestion=report_data.get("suggestion", ""),
    )
    db.add(report)

    session.total_score = float(total_score)
    session.overall_feedback = report_data.get("strengths", "")

    await db.flush()
    await db.refresh(report)

    return {
        "session_id": report.session_id, "position": session.position,
        "total_score": report.total_score,
        "detail_scores": json.loads(report.detail_scores) if isinstance(report.detail_scores, str) else {},
        "strengths": report.strengths or "",
        "weaknesses": report.weaknesses or "",
        "suggestion": report.suggestion or "",
        "created_at": str(report.created_at) if report.created_at else None,
    }


# ============================================================
#  5. 语音服务 —— Whisper语音识别 + Edge-TTS语音合成
# ============================================================

WHISPER_MODEL = None
WHISPER_MODEL_NAME = "tiny"  # tiny=最快, base=均衡, small=更准


def _get_whisper_model():
    """懒加载Whisper模型（首次使用时加载，之后复用）"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        import whisper
        WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME)
    return WHISPER_MODEL


async def transcribe_audio(audio_data: bytes, filename: str = "audio.webm") -> str:
    """语音转文字（Whisper），支持中文"""
    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        model = _get_whisper_model()
        result = model.transcribe(tmp_path, language="zh", fp16=False)
        return result["text"].strip()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def synthesize_speech(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """文字转语音（Edge-TTS），返回MP3音频字节"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    return b"".join(audio_chunks)


# 可选发音人列表
VOICE_OPTIONS = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓(女)", "gender": "female"},
    {"id": "zh-CN-YunxiNeural",    "name": "云希(男)", "gender": "male"},
    {"id": "zh-CN-XiaoyiNeural",   "name": "晓伊(女)", "gender": "female"},
    {"id": "zh-CN-YunjianNeural",  "name": "云健(男)", "gender": "male"},
]
