from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.scraping_service import ScrapingService
from services.gemini_service import GeminiService
from config.settings import settings
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Union

# ログ設定
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# サービスインスタンスをグローバル変数として定義
scraping_service = None
gemini_service = None

class TextCompressionRequest(BaseModel):
    """テキスト圧縮リクエストモデル"""
    text: str
    compression_ratio: float = 0.6
    remove_duplicates: bool = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    global scraping_service, gemini_service
    
    # 起動時
    try:
        settings.validate()
        scraping_service = ScrapingService()
        gemini_service = GeminiService()
        logger.info("サービス初期化完了")
        yield
    except Exception as e:
        logger.error(f"初期化エラー: {e}")
        raise
    finally:
        # 終了時
        logger.info("アプリケーション終了")

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

@app.get(f"{settings.API_PREFIX}/")
async def root():
    """ルートエンドポイント"""
    return {"message": f"{settings.APP_NAME} is running"}

@app.get(f"{settings.API_PREFIX}/health", response_model=HealthResponse)
async def health_check():
    """ヘルスチェックエンドポイント"""
    return HealthResponse(
        status="healthy",
        message="API is running normally"
    )

@app.post(f"{settings.API_PREFIX}/analyze", response_model=AnalysisResponse)
async def analyze_property(request: QueryRequest):
    """物件分析エンドポイント（テキスト圧縮機能付き）"""
    try:
        query = request.query.strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="クエリが空です")
        
        is_query_url = scraping_service.is_url(query)
        extracted_text = None
        original_length = None
        compressed_length = None
        compression_achieved = None
        
        if is_query_url:
            logger.info(f"URL分析開始: {query}")
            logger.info(f"圧縮設定: 有効={request.enable_compression}, 比率={request.compression_ratio}")
            
            # スクレイピング時の元の長さを記録するため、一時的に圧縮無効でスクレイピング
            temp_text = scraping_service.scrape_website(query, enable_compression=False)
            original_length = len(temp_text)
            
            # 圧縮が有効で、最小文字数を超えている場合のみ圧縮実行
            if (request.enable_compression and 
                original_length > settings.MIN_TEXT_LENGTH_FOR_COMPRESSION):
                
                extracted_text = scraping_service.text_compressor.compress_text(
                    temp_text,
                    max_length=int(settings.MAX_TEXT_LENGTH * request.compression_ratio),
                    compression_ratio=request.compression_ratio
                )
                compressed_length = len(extracted_text)
                compression_achieved = 1 - (compressed_length / original_length)
            else:
                extracted_text = temp_text[:settings.MAX_TEXT_LENGTH] if len(temp_text) > settings.MAX_TEXT_LENGTH else temp_text
                compressed_length = len(extracted_text)
                compression_achieved = 1 - (compressed_length / original_length) if original_length > 0 else 0
            
            analysis = gemini_service.analyze_property_from_url(extracted_text)
        else:
            logger.info(f"物件名分析開始: {query}")
            # 物件名の場合：直接Gemini分析
            analysis = gemini_service.analyze_property_by_name(query)
        
        return AnalysisResponse(
            query=query,
            is_url=is_query_url,
            extracted_text=extracted_text,
            original_text_length=original_length,
            compressed_text_length=compressed_length,
            compression_ratio_achieved=compression_achieved,
            analysis=analysis
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(f"{settings.API_PREFIX}/compress-text")
async def compress_text_only(request: TextCompressionRequest) -> Dict[str, Any]:
    """テキスト圧縮のみを行うエンドポイント"""
    try:
        from services.text_compression_service import TextCompressionService
        
        compressor = TextCompressionService()
        
        original_length = len(request.text)
        
        if request.remove_duplicates:
            compressed = compressor.compress_text(
                request.text,
                max_length=int(original_length * request.compression_ratio),
                compression_ratio=request.compression_ratio
            )
        else:
            # 単純な切り詰めのみ
            target_length = int(original_length * request.compression_ratio)
            compressed = request.text[:target_length] + "..." if len(request.text) > target_length else request.text
        
        compressed_length = len(compressed)
        actual_ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0
        
        return {
            "original_text": request.text,
            "compressed_text": compressed,
            "original_length": original_length,
            "compressed_length": compressed_length,
            "compression_ratio_achieved": actual_ratio,
            "compression_percentage": f"{actual_ratio * 100:.1f}%"
        }
        
    except Exception as e:
        logger.error(f"テキスト圧縮エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/stats")
async def get_compression_stats():
    """圧縮機能の統計情報を取得"""
    return {
        "max_text_length": settings.MAX_TEXT_LENGTH,
        "default_compression_ratio": settings.DEFAULT_COMPRESSION_RATIO,
        "min_text_length_for_compression": settings.MIN_TEXT_LENGTH_FOR_COMPRESSION,
        "compression_enabled": settings.ENABLE_COMPRESSION,
        "supported_compression_ratios": {
            "light": 0.8,  # 20%削減
            "medium": 0.6,  # 40%削減
            "heavy": 0.4,   # 60%削減
            "extreme": 0.2  # 80%削減
        }
    }

@app.post(f"{settings.API_PREFIX}/test-compression")
async def test_compression_levels(text: str):
    """異なる圧縮レベルでのテスト"""
    try:
        from services.text_compression_service import TextCompressionService
        
        compressor = TextCompressionService()
        original_length = len(text)
        
        results = {}
        compression_levels = {
            "none": 1.0,
            "light": 0.8,
            "medium": 0.6,
            "heavy": 0.4,
            "extreme": 0.2
        }
        
        for level_name, ratio in compression_levels.items():
            if level_name == "none":
                compressed = text
            else:
                compressed = compressor.compress_text(
                    text,
                    max_length=int(original_length * ratio),
                    compression_ratio=ratio
                )
            
            compressed_length = len(compressed)
            actual_ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0
            
            results[level_name] = {
                "compressed_text": compressed[:200] + "..." if len(compressed) > 200 else compressed,
                "original_length": original_length,
                "compressed_length": compressed_length,
                "compression_achieved": actual_ratio,
                "compression_percentage": f"{actual_ratio * 100:.1f}%"
            }
        
        return results
        
    except Exception as e:
        logger.error(f"圧縮テストエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)