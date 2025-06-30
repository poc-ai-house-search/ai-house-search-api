# services/reasoning_engine_service.py
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from google.auth import default
from google.auth.transport.requests import Request
from config.settings import settings

logger = logging.getLogger(__name__)

class ReasoningEngineService:
    """Vertex AI Reasoning Engine サービス（浸水リスク分析用）"""
    
    def __init__(self):
        """初期化"""
        try:
            # 設定の取得
            self.project_id = getattr(settings, 'GCP_PROJECT_ID', os.environ.get("GCP_PROJECT_ID"))
            self.location = getattr(settings, 'REASONING_ENGINE_LOCATION', 
                                  os.environ.get("REASONING_ENGINE_LOCATION", "us-central1"))
            self.reasoning_engine_id = getattr(settings, 'REASONING_ENGINE_ID',
                                             os.environ.get("REASONING_ENGINE_ID", "917300560820961280"))
            
            if not self.project_id:
                raise ValueError("GCP_PROJECT_ID が設定されていません")
            
            if not self.reasoning_engine_id:
                raise ValueError("REASONING_ENGINE_ID が設定されていません")
            
            # Google Cloud認証の設定
            self.credentials, self.project = default()
            
            # エンドポイントURL（セッション管理用）
            self.base_url = (
                f"https://{self.location}-aiplatform.googleapis.com/v1/"
                f"projects/{self.project_id}/locations/{self.location}/"
                f"reasoningEngines/{self.reasoning_engine_id}"
            )
            
            # 現在のセッション管理
            self.current_session_id = None
            
            logger.info(f"Reasoning Engine サービス初期化完了")
            logger.info(f"プロジェクトID: {self.project_id}")
            logger.info(f"ロケーション: {self.location}")
            logger.info(f"Reasoning Engine ID: {self.reasoning_engine_id}")
            
        except Exception as e:
            logger.error(f"Reasoning Engine サービス初期化エラー: {e}")
            raise
    
    def _get_access_token(self) -> str:
        """アクセストークンを取得"""
        try:
            if not self.credentials.valid:
                self.credentials.refresh(Request())
            return self.credentials.token
        except Exception as e:
            logger.error(f"アクセストークン取得エラー: {e}")
            raise
    
    def create_session(self) -> str:
        """
        新しいセッションを作成
        
        Returns:
            str: セッションID
        """
        try:
            url = f"{self.base_url}:create_session"
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            # セッション作成のペイロード
            payload = {}
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                session_id = result.get("session_id")
                if session_id:
                    self.current_session_id = session_id
                    logger.info(f"セッション作成成功: {session_id}")
                    return session_id
                else:
                    raise Exception("セッションIDが返されませんでした")
            else:
                raise Exception(f"セッション作成失敗: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"セッション作成エラー: {e}")
            raise
    
    def query_session(self, session_id: str, query: str) -> Dict[str, Any]:
        """
        セッションに対してクエリを実行
        
        Args:
            session_id: セッションID
            query: クエリ文字列
            
        Returns:
            Dict[str, Any]: クエリ結果
        """
        try:
            # セッション固有のエンドポイント（推測）
            # 実際のエンドポイントはドキュメントを確認する必要があります
            url = f"{self.base_url}/sessions/{session_id}:query"
            
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "input": query
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"クエリ実行失敗: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"セッションクエリエラー: {e}")
            raise
    
    def delete_session(self, session_id: str) -> bool:
        """
        セッションを削除
        
        Args:
            session_id: セッションID
            
        Returns:
            bool: 削除成功の場合True
        """
        try:
            url = f"{self.base_url}/sessions/{session_id}:delete_session"
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"セッション削除成功: {session_id}")
                if self.current_session_id == session_id:
                    self.current_session_id = None
                return True
            else:
                logger.error(f"セッション削除失敗: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"セッション削除エラー: {e}")
            return False
    def analyze_flood_risk(self, address: str) -> Dict[str, Any]:
        """
        指定された住所の浸水リスクを分析（セッションベース）
        
        Args:
            address (str): 分析対象の住所
            
        Returns:
            Dict[str, Any]: 浸水リスク分析結果
        """
        session_id = None
        try:
            query = f"{address}の浸水リスクを教えて"
            logger.info(f"浸水リスク分析開始: {query}")
            
            # セッションを作成
            session_id = self.create_session()
            
            # セッションに対してクエリを実行
            result = self.query_session(session_id, query)
            
            logger.info(f"浸水リスク分析完了: {address}")
            
            # レスポンスを解析して構造化
            return self._parse_flood_risk_response(result, address, query)
            
        except Exception as e:
            logger.error(f"浸水リスク分析エラー: {e}")
            return {
                "analysis_successful": False,
                "error": str(e),
                "address": address,
                "query": f"{address}の浸水リスクを教えて"
            }
        finally:
            # セッションをクリーンアップ
            if session_id:
                try:
                    self.delete_session(session_id)
                except Exception as cleanup_error:
                    logger.warning(f"セッションクリーンアップエラー: {cleanup_error}")
    
    def analyze_flood_risk_direct(self, address: str) -> Dict[str, Any]:
        """
        直接的なReasoning Engine呼び出し（別のアプローチ）
        
        Args:
            address (str): 分析対象の住所
            
        Returns:
            Dict[str, Any]: 浸水リスク分析結果
        """
        try:
            query = f"{address}の浸水リスクを教えて"
            logger.info(f"浸水リスク分析開始（直接呼び出し）: {query}")
            
            # 直接的なReasoning Engine API呼び出し
            url = f"{self.base_url}:predict"  # または適切なエンドポイント
            
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "instances": [{"input": query}],
                "parameters": {}
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"浸水リスク分析完了（直接呼び出し）: {address}")
                return self._parse_flood_risk_response(result, address, query)
            else:
                logger.error(f"直接呼び出しAPI エラー: {response.status_code} - {response.text}")
                return {
                    "analysis_successful": False,
                    "error": f"API エラー: {response.status_code}",
                    "address": address,
                    "query": query,
                    "response_text": response.text
                }
                
        except Exception as e:
            logger.error(f"直接呼び出し浸水リスク分析エラー: {e}")
            return {
                "analysis_successful": False,
                "error": str(e),
                "address": address,
                "query": f"{address}の浸水リスクを教えて"
            }
    
    def _parse_flood_risk_response(self, raw_response: Dict[str, Any], address: str, query: str) -> Dict[str, Any]:
        """
        Reasoning Engineのレスポンスを解析して構造化
        
        Args:
            raw_response: APIからの生レスポンス
            address: 分析対象住所
            query: 実行されたクエリ
            
        Returns:
            Dict[str, Any]: 構造化された浸水リスク情報
        """
        try:
            # レスポンスから回答テキストを抽出
            answer_text = ""
            if "output" in raw_response:
                answer_text = str(raw_response["output"])
            elif "result" in raw_response:
                answer_text = str(raw_response["result"])
            else:
                answer_text = str(raw_response)
            
            # テキストから浸水リスク情報を抽出
            flood_risk_data = self._extract_flood_risk_info(answer_text)
            
            return {
                "analysis_successful": True,
                "address": address,
                "query": query,
                "raw_response": raw_response,
                "answer_text": answer_text,
                "flood_risk_assessment": flood_risk_data,
                "metadata": {
                    "reasoning_engine_id": self.reasoning_engine_id,
                    "location": self.location,
                    "analysis_type": "flood_risk"
                }
            }
            
        except Exception as e:
            logger.error(f"レスポンス解析エラー: {e}")
            return {
                "analysis_successful": False,
                "error": f"レスポンス解析エラー: {str(e)}",
                "address": address,
                "query": query,
                "raw_response": raw_response
            }
    
    def _extract_flood_risk_info(self, answer_text: str) -> Dict[str, Any]:
        """
        回答テキストから浸水リスク情報を抽出
        
        Args:
            answer_text: Reasoning Engineからの回答テキスト
            
        Returns:
            Dict[str, Any]: 抽出された浸水リスク情報
        """
        try:
            import re
            
            # 基本的な浸水リスク情報を抽出
            risk_info = {
                "overall_risk_level": "不明",
                "risk_factors": [],
                "safety_measures": [],
                "hazard_maps": [],
                "evacuation_info": [],
                "summary": answer_text
            }
            
            # リスクレベルの抽出
            risk_patterns = [
                r"リスク(?:レベル)?[：:]?\s*([高中低])",
                r"浸水リスク[：:]?\s*([高中低])",
                r"危険度[：:]?\s*([高中低])"
            ]
            
            for pattern in risk_patterns:
                match = re.search(pattern, answer_text)
                if match:
                    risk_info["overall_risk_level"] = match.group(1)
                    break
            
            # リスク要因の抽出
            risk_factor_keywords = [
                "河川氾濫", "内水氾濫", "高潮", "津波", "土砂災害", 
                "地盤沈下", "低地", "河川近く", "海抜が低い"
            ]
            
            for keyword in risk_factor_keywords:
                if keyword in answer_text:
                    risk_info["risk_factors"].append(keyword)
            
            # 安全対策の抽出
            safety_keywords = [
                "避難場所", "避難経路", "防災グッズ", "水害対策", 
                "土のう", "止水板", "浸水対策"
            ]
            
            for keyword in safety_keywords:
                if keyword in answer_text:
                    risk_info["safety_measures"].append(keyword)
            
            # ハザードマップ情報の抽出
            if "ハザードマップ" in answer_text:
                risk_info["hazard_maps"].append("洪水ハザードマップ参照推奨")
            
            # 避難情報の抽出
            if any(word in answer_text for word in ["避難", "緊急", "警報"]):
                risk_info["evacuation_info"].append("避難計画の確認が必要")
            
            return risk_info
            
        except Exception as e:
            logger.error(f"浸水リスク情報抽出エラー: {e}")
            return {
                "overall_risk_level": "解析エラー",
                "risk_factors": [],
                "safety_measures": [],
                "hazard_maps": [],
                "evacuation_info": [],
                "summary": answer_text,
                "extraction_error": str(e)
            }
    
    def is_available(self) -> bool:
        """
        Reasoning Engine サービスが利用可能かチェック
        
        Returns:
            bool: 利用可能な場合True
        """
        try:
            # セッション一覧取得でテスト
            url = f"{self.base_url}:list_sessions"
            headers = {
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Reasoning Engine 接続テスト失敗: {e}")
            return False
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        デバッグ情報を取得
        
        Returns:
            Dict[str, Any]: デバッグ情報
        """
        return {
            "project_id": self.project_id,
            "location": self.location,
            "reasoning_engine_id": self.reasoning_engine_id,
            "base_url": self.base_url,
            "credentials_valid": self.credentials.valid if self.credentials else False,
            "current_session_id": self.current_session_id
        }