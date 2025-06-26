# config/settings.py (Vertex AI Search設定追加版)
import os
from typing import List, Optional

class Settings:
    # 既存の設定...
    APP_NAME: str = "Property Analysis API"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"
    
    # Google API設定
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    
    # Vertex AI Search設定
    VERTEX_AI_SEARCH_DATA_STORE_ID: str = os.getenv("VERTEX_AI_SEARCH_DATA_STORE_ID", "minatoku_1750066687052")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "global")
    VERTEX_AI_SEARCH_SERVING_CONFIG_ID: str = os.getenv("VERTEX_AI_SEARCH_SERVING_CONFIG_ID", "default_serving_config")
    ENABLE_VERTEX_AI_SEARCH: bool = os.getenv("ENABLE_VERTEX_AI_SEARCH", "true").lower() == "true"
    
    # GCS設定
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")
    GCS_CREDENTIALS_PATH: str = os.getenv("GCS_CREDENTIALS_PATH", "")
    ENABLE_GCS_STORAGE: bool = os.getenv("ENABLE_GCS_STORAGE", "false").lower() == "true"
    
    # スクレイピング設定
    MAX_TEXT_LENGTH: int = int(os.getenv("MAX_TEXT_LENGTH", "50000"))
    DEFAULT_COMPRESSION_RATIO: float = float(os.getenv("DEFAULT_COMPRESSION_RATIO", "0.6"))
    MIN_TEXT_LENGTH_FOR_COMPRESSION: int = int(os.getenv("MIN_TEXT_LENGTH_FOR_COMPRESSION", "10000"))
    ENABLE_COMPRESSION: bool = os.getenv("ENABLE_COMPRESSION", "true").lower() == "true"
    
    # CORS設定
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    def validate(self):
        """設定の検証"""
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required")
        
        if self.ENABLE_VERTEX_AI_SEARCH and not self.GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID is required when ENABLE_VERTEX_AI_SEARCH is True")
        
        if self.ENABLE_GCS_STORAGE and not self.GCS_BUCKET_NAME:
            raise ValueError("GCS_BUCKET_NAME is required when ENABLE_GCS_STORAGE is True")

settings = Settings()