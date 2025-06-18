from pydantic import BaseModel, Field
from typing import Optional

class QueryRequest(BaseModel):
    """クエリリクエストモデル"""
    query: str = Field(..., min_length=1, description="URLまたは物件名")
    enable_compression: Optional[bool] = Field(True, description="テキスト圧縮を有効にするか")
    compression_ratio: Optional[float] = Field(0.6, ge=0.1, le=1.0, description="圧縮率（0.1-1.0）")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "https://suumo.jp/chintai/jnc_000098936980/",
                "enable_compression": True,
                "compression_ratio": 0.6
            }
        }

class AnalysisResponse(BaseModel):
    """分析レスポンスモデル"""
    query: str = Field(..., description="入力されたクエリ")
    is_url: bool = Field(..., description="URLかどうか")
    extracted_text: Optional[str] = Field(None, description="抽出されたテキスト（URLの場合のみ）")
    original_text_length: Optional[int] = Field(None, description="元のテキスト文字数")
    compressed_text_length: Optional[int] = Field(None, description="圧縮後のテキスト文字数")
    compression_ratio_achieved: Optional[float] = Field(None, description="実際の圧縮率")
    analysis: str = Field(..., description="AI分析結果")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "https://example.com/property",
                "is_url": True,
                "extracted_text": "圧縮された物件情報のテキスト...",
                "original_text_length": 15000,
                "compressed_text_length": 9000,
                "compression_ratio_achieved": 0.4,
                "analysis": "この物件は..."
            }
        }

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンスモデル"""
    status: str = Field(..., description="ステータス")
    message: str = Field(..., description="メッセージ")