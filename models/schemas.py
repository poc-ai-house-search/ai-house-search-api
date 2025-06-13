# models/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class GenerationConfig(BaseModel):
    max_output_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=0.8, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=40, ge=1, le=100)
    stop_sequences: Optional[List[str]] = None

class GenerateRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    config: Optional[GenerationConfig] = None
    system_instruction: Optional[str] = None
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('メッセージは空にできません')
        return v.strip()

class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('コンテンツは空にできません')
        return v.strip()

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_items=1)
    config: Optional[GenerationConfig] = None
    system_instruction: Optional[str] = None
    
    @validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError('メッセージは少なくとも1つ必要です')
        
        # 最後のメッセージはユーザーからのものである必要がある
        if v[-1].role != MessageRole.USER:
            raise ValueError('最後のメッセージはユーザーからのものである必要があります')
        
        return v

class UsageMetadata(BaseModel):
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0

class GenerateResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[UsageMetadata] = None
    finish_reason: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    google_cloud_project: str

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: str

class ImageAnalyzeRequest(BaseModel):
    image_data: str = Field(..., description="Base64エンコードされた画像データ")
    prompt: str = Field(default="この画像について説明してください", max_length=1000)
    mime_type: str = Field(default="image/jpeg", pattern=r"^image/(jpeg|png|gif|webp)$")
    config: Optional[GenerationConfig] = None

class FileUploadResponse(BaseModel):
    success: bool
    file_uri: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    error: Optional[str] = None