"""
AI面试官 - 数据库模型（6张表）

表关系：
  users (1) ──→ (N) resumes         一个用户有多份简历
  users (1) ──→ (N) interview_sessions  一个用户有多场面试
  resumes (1) ──→ (N) interview_sessions 一份简历可对应多场面试
  interview_sessions (1) ──→ (N) questions  一场面试有多道题
  questions (1) ──→ (N) answers         一道题有一次回答
  interview_sessions (1) ──→ (1) reports   一场面试生成一份报告
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, func

from app.database import Base  # 从 database.py 引入基类，确保 Alembic 能正确识别


# ===== 用户表 =====
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(16), default="user", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ===== 简历表 =====
class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    original_filename = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False)
    parsed_content = Column(Text)        # PDF提取的原始文本
    education = Column(Text)             # 解析出的教育背景
    experience = Column(Text)            # 解析出的工作/项目经验
    skills = Column(Text)                # 解析出的技能列表
    created_at = Column(DateTime, server_default=func.now())


# ===== 面试会话表 =====
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    position = Column(String(128), nullable=False, comment="应聘岗位")
    status = Column(String(16), default="pending", comment="pending/in_progress/completed")
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_score = Column(Float, nullable=True)
    overall_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ===== 题目表 =====
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(32), default="technical", comment="technical/behavioral/project")
    difficulty = Column(String(16), default="medium", comment="easy/medium/hard")
    order_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())


# ===== 回答表 =====
class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    answer_text = Column(Text, nullable=True)
    audio_path = Column(String(512), nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ===== 报告表 =====
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_score = Column(Float, nullable=False)
    detail_scores = Column(Text, comment="各维度得分JSON")
    strengths = Column(Text)
    weaknesses = Column(Text)
    suggestion = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
