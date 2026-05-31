"""Pydantic request and response models for the public API."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, HttpUrl


class NewsFlashRequest(BaseModel):
    """Request model for creating news flashes."""

    broker: str
    title: str
    summary: str
    url: Optional[HttpUrl] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class NewsFlashResponse(BaseModel):
    """Response model for news flashes."""

    broker: str
    title: str
    summary: str
    url: Optional[str] = None
    date: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class NewsDeleteRequest(BaseModel):
    """Request model for deleting news flashes."""

    broker: str
    title: str


class ChatMessage(BaseModel):
    """A single message in conversation history."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Request model for the chatbot endpoint."""

    question: str
    history: Optional[List[ChatMessage]] = None
    model: Optional[str] = None
    lang: Optional[str] = "en"


class FeedbackRequest(BaseModel):
    """Request model for chat feedback."""

    trace_id: str
    rating: str  # "up" or "down"
    comment: Optional[str] = None


class EmailSendRequest(BaseModel):
    """Request model for manual email report trigger."""

    recipients: Optional[List[str]] = None
