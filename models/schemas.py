# models/schemas.py (Pydantic V2 現代的書き方)
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List

class QueryRequest(BaseModel):
    """クエリリクエストモデル"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "https://suumo.jp/chintai/jnc_000098936980/",
                "enable_compression": True,
                "compression_ratio": 0.6,
                "response_format": "json"
            }
        }
    )
    
    query: str = Field(..., min_length=1, description="URLまたは物件名")
    enable_compression: Optional[bool] = Field(True, description="テキスト圧縮を有効にするか")
    compression_ratio: Optional[float] = Field(0.6, ge=0.1, le=1.0, description="圧縮率（0.1-1.0）")
    response_format: Optional[str] = Field("json", description="レスポンス形式（json/text）")

class PropertyBasicInfo(BaseModel):
    """物件基本情報"""
    property_name: Optional[str] = None
    address: Optional[str] = None
    room_number: Optional[str] = None
    rent: Optional[str] = None
    management_fee: Optional[str] = None
    deposit: Optional[str] = None
    key_money: Optional[str] = None
    area: Optional[str] = None
    layout: Optional[str] = None
    building_age: Optional[str] = None
    floor: Optional[str] = None
    direction: Optional[str] = None
    building_type: Optional[str] = None

class PropertyFeatures(BaseModel):
    """物件設備・特徴"""
    amenities: List[str] = []
    equipment: List[str] = []
    special_features: List[str] = []

class LocationInfo(BaseModel):
    """立地情報"""
    nearest_stations: List[Dict[str, str]] = []
    surrounding_environment: Optional[str] = None

class PropertyEvaluation(BaseModel):
    """物件評価"""
    advantages: List[str] = []
    disadvantages: List[str] = []
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    recommendation_score: Optional[str] = None
    summary: Optional[str] = None

class StructuredAnalysis(BaseModel):
    """構造化された分析結果"""
    basic_info: PropertyBasicInfo
    features: PropertyFeatures
    location: LocationInfo
    evaluation: PropertyEvaluation

class AnalysisResponse(BaseModel):
    """分析レスポンスモデル"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "uuid": "550e8400-e29b-41d4-a716-446655440000",
                "query": "https://example.com/property",
                "is_url": True,
                "extracted_text": "圧縮された物件情報のテキスト...",
                "original_text_length": 15000,
                "compressed_text_length": 9000,
                "compression_ratio_achieved": 0.4,
                "analysis": {
                    "basic_info": {
                        "property_name": "サンプル物件",
                        "rent": "10万円"
                    },
                    "evaluation": {
                        "overall_rating": 4,
                        "summary": "この物件は..."
                    }
                },
                "response_format": "json",
                "storage_info": {
                    "gcs_enabled": True,
                    "saved_to_gcs": True,
                    "gcs_path": "550e8400-e29b-41d4-a716-446655440000/"
                }
            }
        }
    )
    
    uuid: str = Field(..., description="分析セッションのUUID")
    query: str = Field(..., description="入力されたクエリ")
    is_url: bool = Field(..., description="URLかどうか")
    extracted_text: Optional[str] = Field(None, description="抽出されたテキスト（URLの場合のみ）")
    original_text_length: Optional[int] = Field(None, description="元のテキスト文字数")
    compressed_text_length: Optional[int] = Field(None, description="圧縮後のテキスト文字数")
    compression_ratio_achieved: Optional[float] = Field(None, description="実際の圧縮率")
    analysis: Dict[str, Any] = Field(..., description="AI分析結果")
    raw_analysis: Optional[str] = Field(None, description="生の分析テキスト")
    response_format: str = Field("json", description="レスポンス形式")
    storage_info: Optional[Dict[str, Any]] = Field(None, description="ストレージ情報")

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンスモデル"""
    status: str = Field(..., description="ステータス")
    message: str = Field(..., description="メッセージ")