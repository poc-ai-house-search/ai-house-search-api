# config/settings.py (GCS対応版)
import os
from typing import Optional, List

class Settings:
    """アプリケーション設定"""
    
    # API設定
    API_PREFIX: str = "/api"
    APP_NAME: str = "Property Analysis API"
    APP_VERSION: str = "1.0.0"
    
    # Google API設定
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    # GCS設定
    GCP_PROJECT_ID: Optional[str] = os.getenv("GCP_PROJECT_ID")
    GCS_BUCKET_NAME: Optional[str] = os.getenv("GCS_BUCKET_NAME", "property-analysis-storage")
    GCS_CREDENTIALS_PATH: Optional[str] = os.getenv("GCS_CREDENTIALS_PATH")  # サービスアカウントキーファイルのパス
    GCS_CREDENTIALS_JSON: Optional[str] = os.getenv("GCS_CREDENTIALS_JSON")  # JSON文字列として設定
    ENABLE_GCS_STORAGE: bool = os.getenv("ENABLE_GCS_STORAGE", "true").lower() == "true"
    
    # スクレイピング設定
    REQUEST_TIMEOUT: int = 30
    MAX_TEXT_LENGTH: int = 30000
    
    # テキスト圧縮設定
    DEFAULT_COMPRESSION_RATIO: float = 0.6  # 40%削減目標
    ENABLE_COMPRESSION: bool = True
    MIN_TEXT_LENGTH_FOR_COMPRESSION: int = 5000  # 5000文字以上で圧縮実行
    
    # CORS設定
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # ログ設定
    LOG_LEVEL: str = "INFO"
    
    def validate(self) -> None:
        """設定値の検証"""
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        if self.ENABLE_GCS_STORAGE:
            if not self.GCP_PROJECT_ID:
                raise ValueError("GCP_PROJECT_ID environment variable is required when GCS storage is enabled")
            if not self.GCS_BUCKET_NAME:
                raise ValueError("GCS_BUCKET_NAME environment variable is required when GCS storage is enabled")

settings = Settings()