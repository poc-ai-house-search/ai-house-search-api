# services/gcs_service.py
from google.cloud import storage
from google.oauth2 import service_account
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from config.settings import settings

logger = logging.getLogger(__name__)

class GCSService:
    """Google Cloud Storage サービス"""
    
    def __init__(self):
        """GCSサービス初期化"""
        try:
            # 認証情報の設定
            if settings.GCS_CREDENTIALS_PATH:
                # サービスアカウントキーファイルを使用
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GCS_CREDENTIALS_PATH
                )
                self.client = storage.Client(credentials=credentials, project=settings.GCP_PROJECT_ID)
            elif settings.GCS_CREDENTIALS_JSON:
                # JSON文字列から認証情報を作成
                credentials_info = json.loads(settings.GCS_CREDENTIALS_JSON)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
                self.client = storage.Client(credentials=credentials, project=settings.GCP_PROJECT_ID)
            else:
                # デフォルトの認証情報を使用（Cloud Run環境など）
                self.client = storage.Client(project=settings.GCP_PROJECT_ID)
            
            self.bucket_name = settings.GCS_BUCKET_NAME
            self.bucket = self.client.bucket(self.bucket_name)
            
            logger.info(f"GCS サービス初期化完了 - バケット: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"GCS サービス初期化エラー: {e}")
            raise

    def create_folder(self, folder_name: str) -> bool:
        """フォルダを作成（実際にはプレフィックスとして動作）"""
        try:
            # GCSではフォルダは概念的なもので、実際にはプレフィックス付きのオブジェクトを作成
            folder_path = f"{folder_name}/.gitkeep"
            blob = self.bucket.blob(folder_path)
            blob.upload_from_string("")
            
            logger.info(f"GCSフォルダ作成完了: {folder_name}")
            return True
            
        except Exception as e:
            logger.error(f"GCSフォルダ作成エラー: {e}")
            return False

    def save_analysis_result(self, uuid: str, analysis_data: Dict[str, Any]) -> bool:
        """分析結果をJSONファイルとして保存"""
        try:
            # メタデータを追加
            enriched_data = {
                "uuid": uuid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
                "analysis_data": analysis_data
            }
            
            # ファイルパスを設定
            file_path = f"{uuid}/analysis_result.json"
            
            # GCSに保存
            blob = self.bucket.blob(file_path)
            blob.upload_from_string(
                json.dumps(enriched_data, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"分析結果保存完了: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"分析結果保存エラー: {e}")
            return False

    def save_extracted_text(self, uuid: str, extracted_text: str) -> bool:
        """抽出されたテキストを保存"""
        try:
            if not extracted_text:
                return True  # テキストがない場合はスキップ
                
            file_path = f"{uuid}/extracted_text.txt"
            
            blob = self.bucket.blob(file_path)
            blob.upload_from_string(
                extracted_text,
                content_type='text/plain; charset=utf-8'
            )
            
            logger.info(f"抽出テキスト保存完了: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"抽出テキスト保存エラー: {e}")
            return False

    def save_request_info(self, uuid: str, request_data: Dict[str, Any]) -> bool:
        """リクエスト情報を保存"""
        try:
            # メタデータを追加
            request_info = {
                "uuid": uuid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_data": request_data
            }
            
            file_path = f"{uuid}/request_info.json"
            
            blob = self.bucket.blob(file_path)
            blob.upload_from_string(
                json.dumps(request_info, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"リクエスト情報保存完了: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"リクエスト情報保存エラー: {e}")
            return False

    def get_analysis_result(self, uuid: str) -> Optional[Dict[str, Any]]:
        """保存された分析結果を取得"""
        try:
            file_path = f"{uuid}/analysis_result.json"
            blob = self.bucket.blob(file_path)
            
            if not blob.exists():
                logger.warning(f"分析結果が見つかりません: {file_path}")
                return None
            
            content = blob.download_as_text()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"分析結果取得エラー: {e}")
            return None

    def list_analysis_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """分析セッション一覧を取得"""
        try:
            sessions = []
            blobs = self.client.list_blobs(
                self.bucket_name, 
                delimiter='/',
                max_results=limit
            )
            
            # フォルダ（プレフィックス）のリストを取得
            for prefix in blobs.prefixes:
                uuid = prefix.rstrip('/')
                # 各セッションの基本情報を取得
                try:
                    analysis_data = self.get_analysis_result(uuid)
                    if analysis_data:
                        sessions.append({
                            "uuid": uuid,
                            "timestamp": analysis_data.get("timestamp"),
                            "query": analysis_data.get("analysis_data", {}).get("query"),
                            "is_url": analysis_data.get("analysis_data", {}).get("is_url"),
                        })
                except Exception as e:
                    logger.warning(f"セッション {uuid} の情報取得に失敗: {e}")
                    continue
            
            return sorted(sessions, key=lambda x: x.get("timestamp", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"セッション一覧取得エラー: {e}")
            return []

    def delete_analysis_session(self, uuid: str) -> bool:
        """分析セッションを削除"""
        try:
            # UUIDフォルダ内のすべてのファイルを削除
            blobs = self.client.list_blobs(self.bucket_name, prefix=f"{uuid}/")
            
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
            
            logger.info(f"分析セッション削除完了: {uuid} ({deleted_count}ファイル)")
            return True
            
        except Exception as e:
            logger.error(f"分析セッション削除エラー: {e}")
            return False

    def get_storage_stats(self) -> Dict[str, Any]:
        """ストレージ統計情報を取得"""
        try:
            blobs = self.client.list_blobs(self.bucket_name)
            
            total_size = 0
            file_count = 0
            session_count = set()
            
            for blob in blobs:
                total_size += blob.size or 0
                file_count += 1
                
                # UUIDを抽出してセッション数をカウント
                path_parts = blob.name.split('/')
                if len(path_parts) >= 2:
                    session_count.add(path_parts[0])
            
            return {
                "total_files": file_count,
                "total_sessions": len(session_count),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "bucket_name": self.bucket_name
            }
            
        except Exception as e:
            logger.error(f"ストレージ統計取得エラー: {e}")
            return {"error": str(e)}