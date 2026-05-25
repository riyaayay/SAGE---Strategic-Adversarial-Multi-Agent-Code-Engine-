"""
SAGE-PRO SQLAlchemy Models
══════════════════════════
ORM models for users, conversations, messages, corrections, and agent weights.
Schema matches the DDL in SAGE_PRO_v2_Architecture.docx §4–§7.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean,
    ForeignKey, DateTime, JSON, ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_id = Column(String(128), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    avatar_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(16), nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    # Note: pgvector VECTOR(1536) column handled via raw DDL / migrations
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    original_response = Column(Text, nullable=False)
    corrected_content = Column(Text, nullable=True)
    responsible_agents = Column(ARRAY(String(64)), nullable=True)
    penalty_applied = Column(ARRAY(Float), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    batch_processed = Column(Boolean, default=False)


class AgentWeight(Base):
    __tablename__ = "agent_weights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(64), unique=True, nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    epsilon = Column(Float, nullable=False, default=0.15)
    total_corrections = Column(Integer, default=0)
    total_hard = Column(Integer, default=0)
    total_soft = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyUpdateLog(Base):
    __tablename__ = "daily_update_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date = Column(DateTime, nullable=False)
    corrections_count = Column(Integer, nullable=True)
    agents_penalised = Column(JSON, nullable=True)
    centroid_mutations = Column(Integer, nullable=True)
    new_clusters = Column(Integer, nullable=True)
    pruned_clusters = Column(Integer, nullable=True)
    q_table_delta_norm = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
