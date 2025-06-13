# main.py
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exception_handlers import RequestValidationError
from contextlib import asynccontextmanager
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any
import base64

from config.settings import settings
from models.schemas import *
from services.gemini_service import gemini_service

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# レート制限用の簡単なメモリストア
rate_limit_store: Dict[str, list] = {}

def check_rate_limit(client_ip: str) -> bool:
    """簡単なレート制限チェック"""
    current_time = time.time()
    
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    
    # 期限切れのリクエストを削除
    rate_limit_store[client_ip] = [
        req_time for req_time in rate_limit_store[client_ip]
        if current_time - req_time < settings.rate_limit_window
    ]
    
    # レート制限チェック
    if len(rate_limit_store[client_ip]) >= settings.rate_limit_requests:
        return False
    
    # 現在のリクエストを記録
    rate_limit_store[client_ip].append(current_time)
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    logger.info("FastAPI application starting up...")
    logger.info(f"Google Cloud Project: {settings.google_cloud_project_id}")
    logger.info(f"Default Model: {settings.default_model}")
    yield
    logger.info("FastAPI application shutting down...")

# FastAPIアプリケーション初期化
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# カスタム例外ハンドラー
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail="リクエストの検証に失敗しました",
            error_code="VALIDATION_ERROR",
            timestamp=datetime.now().isoformat()
        ).dict()
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code="HTTP_ERROR",
            timestamp=datetime.now().isoformat()
        ).dict()
    )

# ミドルウェア
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """レート制限ミドルウェア"""
    client_ip = request.client.host
    
    # ヘルスチェックはレート制限から除外
    if request.url.path == "/api/health":
        response = await call_next(request)
        return response
    
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                detail="レート制限に達しました。しばらく待ってから再試行してください。",
                error_code="RATE_LIMIT_EXCEEDED",
                timestamp=datetime.now().isoformat()
            ).dict()
        )
    
    response = await call_next(request)
    return response

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """ログ記録ミドルウェア"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"Path: {request.url.path} | Method: {request.method} | "
        f"Status: {response.status_code} | Time: {process_time:.3f}s"
    )
    
    return response

# API エンドポイント
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """ヘルスチェック"""
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        timestamp=datetime.now().isoformat(),
        google_cloud_project=settings.google_cloud_project_id
    )

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_content(request: GenerateRequest):
    """テキスト生成"""
    try:
        result = await gemini_service.generate_content(
            message=request.message,
            config=request.config,
            system_instruction=request.system_instruction
        )
        
        if result['success']:
            return GenerateResponse(
                success=True,
                content=result['content'],
                usage=result['usage'],
                finish_reason=result.get('finish_reason')
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result['error']
            )
    
    except Exception as e:
        logger.error(f"Generate content error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"コンテンツ生成中にエラーが発生しました: {str(e)}"
        )

@app.post("/api/generate-stream")
async def generate_stream(request: GenerateRequest):
    """ストリーミングテキスト生成"""
    async def stream_generator():
        try:
            async for chunk in gemini_service.generate_content_stream(
                message=request.message,
                config=request.config,
                system_instruction=request.system_instruction
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream generation error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.post("/api/chat", response_model=GenerateResponse)
async def chat(request: ChatRequest):
    """チャット"""
    try:
        result = await gemini_service.chat(
            messages=request.messages,
            config=request.config,
            system_instruction=request.system_instruction
        )
        
        if result['success']:
            return GenerateResponse(
                success=True,
                content=result['content'],
                usage=result['usage'],
                finish_reason=result.get('finish_reason')
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result['error']
            )
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"チャット処理中にエラーが発生しました: {str(e)}"
        )

@app.post("/api/analyze-image", response_model=GenerateResponse)
async def analyze_image(request: ImageAnalyzeRequest):
    """画像分析"""
    try:
        result = await gemini_service.analyze_image(
            image_data=request.image_data,
            prompt=request.prompt,
            mime_type=request.mime_type,
            config=request.config
        )
        
        if result['success']:
            return GenerateResponse(
                success=True,
                content=result['content'],
                usage=result['usage'],
                finish_reason=result.get('finish_reason')
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result['error']
            )
    
    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"画像分析中にエラーが発生しました: {str(e)}"
        )

@app.post("/api/upload-image", response_model=FileUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """画像アップロード"""
    try:
        # ファイルタイプチェック
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="画像ファイルのみアップロード可能です"
            )
        
        # ファイルサイズチェック（10MB制限）
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="ファイルサイズは10MB以下にしてください"
            )
        
        # Base64エンコード
        image_base64 = base64.b64encode(content).decode('utf-8')
        
        return FileUploadResponse(
            success=True,
            file_uri=f"data:{file.content_type};base64,{image_base64}",
            file_size=len(content),
            mime_type=file.content_type
        )
    
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return FileUploadResponse(
            success=False,
            error=f"ファイルアップロードに失敗しました: {str(e)}"
        )

@app.get("/api/models")
async def list_models():
    """利用可能なモデルリスト"""
    return {
        "models": [
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "description": "最も高性能なマルチモーダルモデル"
            },
            {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash",
                "description": "高速で効率的なモデル"
            },
            {
                "id": "gemini-1.0-pro",
                "name": "Gemini 1.0 Pro",
                "description": "従来版のGeminiモデル"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )