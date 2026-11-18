from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    excerpt: str
    score: float


class ConversationSummary(BaseModel):
    id: str
    created_at: datetime


class MessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = Field(default_factory=list)
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    created_at: datetime
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: int | None = None
    ticket_id: str | None = None
    answer: str
    sources: list[Source]
    needs_human: bool
    confidence: float


class DocumentResponse(BaseModel):
    id: str
    filename: str
    chunk_count: int
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: Literal["customer", "admin"]


class TicketResponse(BaseModel):
    id: str
    conversation_id: str
    status: Literal["open", "in_progress", "resolved"]
    subject: str
    created_at: datetime
    updated_at: datetime


class TicketStatusRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


class AgentReplyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class FeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=1000)


class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    excerpt: str
    score: float
    vector_score: float
    keyword_score: float


class EvaluationCase(BaseModel):
    question: str
    expected_filename: str


class EvaluationResult(BaseModel):
    question: str
    expected_filename: str
    retrieved_filenames: list[str]
    passed: bool
