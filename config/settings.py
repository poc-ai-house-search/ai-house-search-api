# config/settings.py
import os
from typing import Optional, List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Google Cloud設定
    google_cloud_project_id: str
    google_cloud_location: str = "us-central1"
    google_application_credentials: Optional[str] = None
    
    # API設定
    api_title: str = "Gemini API"
    api_version: str = "1.0.0"
    api_description: str = "FastAPI + Vertex AI Gemini Integration"
    
    # CORS設定
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # レート制限
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1時間
    
    # モデル設定
    default_model: str = "gemini-1.5-pro"
    max_tokens: int = 8192
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 40
    
    model_config = {
        "env_file": ".env"
    }

settings = Settings()