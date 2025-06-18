import os
from typing import Optional

class Settings:
    """アプリケーション設定"""
    
    # API設定
    API_PREFIX: str = "/api"
    APP_NAME: str = "Property Analysis API"
    APP_VERSION: str = "1.0.0"
    
    # Google API設定
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    # スクレイピング設定
    REQUEST_TIMEOUT: int = 30
    MAX_TEXT_LENGTH: int = 30000
    
    # テキスト圧縮設定
    DEFAULT_COMPRESSION_RATIO: float = 0.6  # 40%削減目標
    ENABLE_COMPRESSION: bool = True
    MIN_TEXT_LENGTH_FOR_COMPRESSION: int = 5000  # 5000文字以上で圧縮実行
    
    # ログ設定
    LOG_LEVEL: str = "INFO"
    
    def validate(self) -> None:
        """設定値の検証"""
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

settings = Settings()