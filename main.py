# main.py（UUID&GCS対応版）
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from models.schemas import QueryRequest, AnalysisResponse, HealthResponse
from services.scraping_service import ScrapingService
from services.gemini_service import GeminiService
from services.gcs_service import GCSService
from config.settings import settings
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Union

# ログ設定
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# サービスインスタンスをグローバル変数として定義
scraping_service = None
gemini_service = None
gcs_service = None

class TextCompressionRequest(BaseModel):
    """テキスト圧縮リクエストモデル"""
    text: str
    compression_ratio: float = 0.6
    remove_duplicates: bool = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    global scraping_service, gemini_service, gcs_service
    
    # 起動時
    try:
        logger.info("サービス初期化開始")
        settings.validate()
        scraping_service = ScrapingService()
        gemini_service = GeminiService()
        
        # GCS サービスの初期化（オプション）
        if settings.ENABLE_GCS_STORAGE:
            try:
                gcs_service = GCSService()
                logger.info("GCS サービス初期化完了")
            except Exception as e:
                logger.warning(f"GCS サービス初期化に失敗（無効化されます）: {e}")
                gcs_service = None
        else:
            logger.info("GCS ストレージは無効化されています")
            gcs_service = None
            
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
    """物件分析エンドポイント（UUID&GCS保存機能付き）"""
    # UUIDを生成
    analysis_uuid = str(uuid.uuid4())
    
    try:
        query = request.query.strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="クエリが空です")
        
        logger.info(f"分析開始: {query} (UUID: {analysis_uuid})")
        
        # GCSにフォルダ作成
        gcs_folder_created = False
        if gcs_service:
            try:
                gcs_folder_created = gcs_service.create_folder(analysis_uuid)
                logger.info(f"GCSフォルダ作成: {analysis_uuid}")
            except Exception as e:
                logger.warning(f"GCSフォルダ作成に失敗: {e}")
        
        # リクエスト情報をGCSに保存
        if gcs_service and gcs_folder_created:
            try:
                request_data = {
                    "query": query,
                    "enable_compression": request.enable_compression,
                    "compression_ratio": request.compression_ratio,
                    "response_format": request.response_format
                }
                gcs_service.save_request_info(analysis_uuid, request_data)
            except Exception as e:
                logger.warning(f"リクエスト情報のGCS保存に失敗: {e}")
        
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
            
            # 抽出されたテキストをGCSに保存
            if gcs_service and gcs_folder_created and extracted_text:
                try:
                    gcs_service.save_extracted_text(analysis_uuid, extracted_text)
                except Exception as e:
                    logger.warning(f"抽出テキストのGCS保存に失敗: {e}")
            
            analysis = gemini_service.analyze_property_from_url(extracted_text, request.response_format)
        else:
            logger.info(f"物件名分析開始: {query}")
            # 物件名の場合：直接Gemini分析
            analysis = gemini_service.analyze_property_by_name(query, request.response_format)
        
        # レスポンス形式に応じた処理
        raw_analysis = None
        if request.response_format == "text" and "raw_response" in analysis:
            raw_analysis = analysis.get("raw_response")
        
        # レスポンスオブジェクトを作成
        response_data = AnalysisResponse(
            uuid=analysis_uuid,
            query=query,
            is_url=is_query_url,
            extracted_text=extracted_text,
            original_text_length=original_length,
            compressed_text_length=compressed_length,
            compression_ratio_achieved=compression_achieved,
            analysis=analysis,
            raw_analysis=raw_analysis,
            response_format=request.response_format,
            storage_info={
                "gcs_enabled": settings.ENABLE_GCS_STORAGE,
                "saved_to_gcs": False,
                "gcs_path": f"{analysis_uuid}/" if gcs_service else None
            }
        )
        
        # 分析結果をGCSに保存
        if gcs_service and gcs_folder_created:
            try:
                save_success = gcs_service.save_analysis_result(analysis_uuid, response_data.model_dump())
                if save_success:
                    response_data.storage_info["saved_to_gcs"] = True
                    logger.info(f"分析結果をGCSに保存完了: {analysis_uuid}")
            except Exception as e:
                logger.warning(f"分析結果のGCS保存に失敗: {e}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分析エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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

@app.get(f"{settings.API_PREFIX}/storage/debug")
async def debug_gcs_storage():
    """GCS ストレージの詳細情報をデバッグ用に取得"""
    try:
        if not gcs_service:
            return {"error": "GCS サービスが利用できません"}
        
        # 基本的なバケット情報
        bucket_info = {
            "bucket_name": gcs_service.bucket_name,
            "bucket_exists": gcs_service.bucket.exists()
        }
        
        # 全ブロブのリスト（先頭50件）
        all_blobs = list(gcs_service.client.list_blobs(gcs_service.bucket_name, max_results=50))
        blobs_info = []
        for blob in all_blobs:
            blobs_info.append({
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created.isoformat() if blob.time_created else None
            })
        
        # delimiterを使用してプレフィックス取得を試す
        delimiter_blobs = gcs_service.client.list_blobs(
            gcs_service.bucket_name, 
            delimiter='/',
            max_results=50
        )
        
        prefixes_found = []
        pages_info = []
        
        for page_num, page in enumerate(delimiter_blobs.pages):
            page_info = {
                "page_number": page_num,
                "prefixes": list(page.prefixes) if hasattr(page, 'prefixes') else [],
                "items_count": len(list(page))
            }
            pages_info.append(page_info)
            
            if hasattr(page, 'prefixes') and page.prefixes:
                prefixes_found.extend(page.prefixes)
                
            # 最初のページだけで止める（デバッグ用）
            if page_num >= 2:
                break
        
        return {
            "gcs_service_status": "OK",
            "bucket_info": bucket_info,
            "total_blobs_found": len(blobs_info),
            "all_blobs": blobs_info,
            "delimiter_analysis": {
                "prefixes_found": prefixes_found,
                "prefixes_count": len(prefixes_found),
                "pages_analyzed": len(pages_info),
                "pages_info": pages_info
            }
        }
        
    except Exception as e:
        logger.error(f"GCS デバッグエラー: {e}")
        return {"error": str(e)}

@app.get(f"{settings.API_PREFIX}/storage/sessions")
async def list_analysis_sessions(
    limit: int = 100,
    is_url: Optional[bool] = None,
    query_contains: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """保存された分析セッション一覧を取得（フィルタリング機能付き）"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        sessions = gcs_service.list_analysis_sessions(limit)
        
        # フィルタリング
        filtered_sessions = sessions
        
        if is_url is not None:
            filtered_sessions = [s for s in filtered_sessions if s.get('is_url') == is_url]
        
        if query_contains:
            filtered_sessions = [
                s for s in filtered_sessions 
                if query_contains.lower() in str(s.get('query', '')).lower()
            ]
        
        if start_date:
            filtered_sessions = [
                s for s in filtered_sessions 
                if s.get('timestamp', '') >= start_date
            ]
        
        if end_date:
            filtered_sessions = [
                s for s in filtered_sessions 
                if s.get('timestamp', '') <= end_date
            ]
        
        return {
            "sessions": filtered_sessions,
            "total_count": len(filtered_sessions),
            "original_count": len(sessions),
            "limit": limit,
            "filters": {
                "is_url": is_url,
                "query_contains": query_contains,
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"セッション一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/storage/search")
async def search_analysis_sessions(
    q: str,
    limit: int = 50
):
    """分析セッションをクエリで検索"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        sessions = gcs_service.list_analysis_sessions(limit * 2)  # 余裕を持って取得
        
        # 検索クエリに基づくフィルタリング
        search_results = []
        for session in sessions:
            query_text = str(session.get('query', '')).lower()
            uuid_text = str(session.get('uuid', '')).lower()
            
            if (q.lower() in query_text or 
                q.lower() in uuid_text):
                search_results.append(session)
                
            if len(search_results) >= limit:
                break
        
        return {
            "search_query": q,
            "results": search_results,
            "result_count": len(search_results),
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"セッション検索エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/storage/session/{{session_uuid}}/files")
async def get_session_files(session_uuid: str):
    """特定セッションの保存ファイル一覧を取得"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        # GCSからファイル一覧を取得
        blobs = gcs_service.client.list_blobs(
            gcs_service.bucket_name, 
            prefix=f"{session_uuid}/"
        )
        
        files = []
        for blob in blobs:
            if blob.name != f"{session_uuid}/":  # フォルダ自体は除外
                files.append({
                    "name": blob.name.split('/')[-1],
                    "full_path": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None
                })
        
        return {
            "session_uuid": session_uuid,
            "files": files,
            "file_count": len(files)
        }
        
    except Exception as e:
        logger.error(f"セッションファイル取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/storage/session/{{session_uuid}}/download/{{file_name}}")
async def download_session_file(session_uuid: str, file_name: str):
    """特定セッションのファイルをダウンロード"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        file_path = f"{session_uuid}/{file_name}"
        blob = gcs_service.bucket.blob(file_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="ファイルが見つかりません")
        
        content = blob.download_as_text()
        
        # ファイル形式に応じてレスポンス
        if file_name.endswith('.json'):
            return json.loads(content)
        else:
            return {
                "file_name": file_name,
                "content": content,
                "content_type": blob.content_type
            }
        
    except json.JSONDecodeError:
        # JSONパースエラーの場合は生のコンテンツを返す
        return {
            "file_name": file_name,
            "content": content,
            "content_type": "text/plain"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ファイルダウンロードエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/storage/session/{{session_uuid}}")
async def get_analysis_session(session_uuid: str):
    """特定の分析セッションを取得"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        session_data = gcs_service.get_analysis_result(session_uuid)
        if not session_data:
            raise HTTPException(status_code=404, detail="セッションが見つかりません")
        
        return session_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"セッション取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete(f"{settings.API_PREFIX}/storage/session/{{session_uuid}}")
async def delete_analysis_session(session_uuid: str):
    """分析セッションを削除"""
    try:
        if not gcs_service:
            raise HTTPException(status_code=503, detail="GCSストレージが利用できません")
        
        success = gcs_service.delete_analysis_session(session_uuid)
        if not success:
            raise HTTPException(status_code=500, detail="セッションの削除に失敗しました")
        
        return {"message": f"セッション {session_uuid} を削除しました"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"セッション削除エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/storage/stats")
async def get_storage_stats():
    """ストレージ統計情報を取得"""
    try:
        if not gcs_service:
            return {
                "gcs_enabled": False,
                "message": "GCSストレージは無効化されています"
            }
        
        stats = gcs_service.get_storage_stats()
        stats["gcs_enabled"] = True
        return stats
        
    except Exception as e:
        logger.error(f"ストレージ統計取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(f"{settings.API_PREFIX}/gemini-models")
async def list_gemini_models():
    """利用可能なGeminiモデルを一覧表示"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        
        models = genai.list_models()
        model_info = []
        
        for model in models:
            model_info.append({
                "name": model.name,
                "display_name": model.display_name,
                "description": model.description,
                "supported_methods": model.supported_generation_methods,
                "input_token_limit": getattr(model, 'input_token_limit', 'N/A'),
                "output_token_limit": getattr(model, 'output_token_limit', 'N/A')
            })
        
        # generateContentをサポートするモデルのみフィルタ
        compatible_models = [
            model for model in model_info 
            if 'generateContent' in model.get('supported_methods', [])
        ]
        
        return {
            "total_models": len(model_info),
            "compatible_models_count": len(compatible_models),
            "compatible_models": compatible_models,
            "all_models": model_info
        }
        
    except Exception as e:
        logger.error(f"Geminiモデル一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"モデル一覧の取得に失敗: {str(e)}")

@app.post(f"{settings.API_PREFIX}/test-json-parsing")
async def test_json_parsing():
    """JSON解析のテスト"""
    sample_text = """
    ## 三田ガーデンヒルズ イーストヒル 1310号室 物件分析

    **1. 物件の基本情報**
    * **物件名:** 三田ガーデンヒルズ イーストヒル
    * **住所:** 東京都港区三田１丁目
    * **部屋番号:** 1310号室
    * **価格:** 賃料 90万円、敷金 180万円、礼金 90万円
    * **面積:** 専有面積 72.51㎡
    * **間取り:** 2LDK
    * **築年数:** 2025年3月築（新築）
    """
    
    try:
        from services.gemini_service import GeminiService
        gemini_svc = GeminiService()
        
        # JSON形式でテスト
        json_result = gemini_svc.analyze_property_from_url(sample_text, "json")
        
        # TEXT形式でテスト
        text_result = gemini_svc.analyze_property_from_url(sample_text, "text")
        
        return {
            "json_analysis": json_result,
            "text_analysis": text_result,
            "message": "JSON解析テスト完了"
        }
        
    except Exception as e:
        logger.error(f"JSON解析テストエラー: {e}")
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

# Dockerfileで起動する場合、この部分は削除
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)