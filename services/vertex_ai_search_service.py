# services/vertex_ai_search_service.py
import os
import logging
from typing import Dict, List, Optional, Any
from google.cloud import discoveryengine_v1beta as discoveryengine
from config.settings import settings

logger = logging.getLogger(__name__)

class VertexAISearchService:
    """Vertex AI Search サービス"""
    
    def __init__(self):
        """初期化"""
        try:
            # 環境変数またはsettingsから設定を取得
            self.project_id = getattr(settings, 'GCP_PROJECT_ID', os.environ.get("GCP_PROJECT_ID"))
            self.location = getattr(settings, 'GCP_LOCATION', os.environ.get("GCP_LOCATION", "global"))
            self.data_store_id = getattr(settings, 'VERTEX_AI_SEARCH_DATA_STORE_ID', 
                                       os.environ.get("VERTEX_AI_SEARCH_DATA_STORE_ID", "hakkason_1750328643745"))
            self.serving_config_id = getattr(settings, 'VERTEX_AI_SEARCH_SERVING_CONFIG_ID',
                                           os.environ.get("VERTEX_AI_SEARCH_SERVING_CONFIG_ID", "default_serving_config"))
            
            if not self.project_id:
                raise ValueError("GCP_PROJECT_ID が設定されていません")
            
            # クライアントを初期化
            self.client = discoveryengine.SearchServiceClient()
            
            # サービング設定のパスを構築
            self.serving_config_path = self.client.serving_config_path(
                project=self.project_id,
                location=self.location,
                data_store=self.data_store_id,
                serving_config=self.serving_config_id,
            )
            
            logger.info(f"Vertex AI Search サービス初期化完了")
            logger.info(f"データストアID: {self.data_store_id}")
            logger.info(f"プロジェクトID: {self.project_id}")
            logger.info(f"ロケーション: {self.location}")
            
        except Exception as e:
            logger.error(f"Vertex AI Search サービス初期化エラー: {e}")
            raise
    
    def search_financial_info(self, address: str, page_size: int = 5) -> Dict[str, Any]:
        """
        指定された住所の財務状況に関する情報を検索
        
        Args:
            address (str): 検索対象の住所
            page_size (int): 取得する結果の数
            
        Returns:
            Dict[str, Any]: 検索結果
        """
        try:
            # 検索クエリを構築（財務状況に特化）
            query = f"{address}の財務状況について、良い悪いと根拠を含めて教えてください"
            
            logger.info(f"Vertex AI Search実行: {query}")
            
            # 検索リクエストの構築
            request = discoveryengine.SearchRequest(
                serving_config=self.serving_config_path,
                query=query,
                page_size=page_size,
                # 検索結果の品質向上のための設定
                query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                    condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO
                ),
                spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                    mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
                )
            )
            
            # 検索の実行
            response = self.client.search(request)
            
            # 結果の処理
            results = []
            for result in response.results:
                document = result.document
                
                # スニペットの抽出
                snippets = []
                if hasattr(document, 'derived_struct_data') and document.derived_struct_data:
                    # derived_struct_dataからスニペットを取得
                    derived_data = dict(document.derived_struct_data)
                    if 'snippets' in derived_data:
                        for snippet_data in derived_data['snippets']:
                            if isinstance(snippet_data, dict) and 'snippet' in snippet_data:
                                snippets.append(snippet_data['snippet'])
                            elif isinstance(snippet_data, str):
                                snippets.append(snippet_data)
                
                # コンテンツの抽出
                content = ""
                if hasattr(document, 'struct_data') and document.struct_data:
                    struct_data = dict(document.struct_data)
                    content = struct_data.get('content', '')
                
                # URIの抽出
                uri = ""
                if hasattr(document, 'derived_struct_data') and document.derived_struct_data:
                    derived_data = dict(document.derived_struct_data)
                    uri = derived_data.get('link', derived_data.get('uri', ''))
                
                # タイトルの抽出
                title = ""
                if hasattr(document, 'derived_struct_data') and document.derived_struct_data:
                    derived_data = dict(document.derived_struct_data)
                    title = derived_data.get('title', derived_data.get('htmlTitle', ''))
                
                if not title and hasattr(document, 'struct_data') and document.struct_data:
                    struct_data = dict(document.struct_data)
                    title = struct_data.get('title', '')
                
                result_item = {
                    "document_id": document.id,
                    "title": title,
                    "uri": uri,
                    "snippet": " ".join(snippets) if snippets else "スニペットなし",
                    "content": content,
                    "relevance_score": getattr(result, 'relevance_score', 0),
                    "metadata": {
                        "category": "",
                        "date": "",
                        "source": uri
                    }
                }
                results.append(result_item)
            
            # 検索サマリーの取得
            summary_text = ""
            if hasattr(response, 'summary') and response.summary:
                summary_text = response.summary.summary_text
            
            logger.info(f"Vertex AI Search 検索完了: {len(results)}件の結果")
            
            return {
                "search_successful": True,
                "results": results,
                "total_size": getattr(response, 'total_size', len(results)),
                "query": query_text,
                "address": address,
                "summary": summary_text,
                "search_metadata": {
                    "data_store_id": settings.VERTEX_AI_SEARCH_DATA_STORE_ID,
                    "location": settings.GCP_LOCATION,
                    "results_count": len(results)
                }
            }
            
        except Exception as e:
            logger.error(f"Vertex AI Search 検索エラー: {e}")
            return {
                "search_successful": False,
                "results": [],
                "error": str(e),
                "query": f"{address}の財務状況について、良い悪いと根拠を含めて教えてください",
                "address": address
            }
    
    def search_general(self, query: str, page_size: int = 5) -> Dict[str, Any]:
        """
        一般的な検索を実行
        
        Args:
            query (str): 検索クエリ
            page_size (int): 取得する結果の数
            
        Returns:
            Dict[str, Any]: 検索結果
        """
        try:
            logger.info(f"一般検索実行: {query}")
            
            request = discoveryengine.SearchRequest(
                serving_config=self.serving_config_path,
                query=query,
                page_size=page_size
            )
            
            response = self.client.search(request)
            
            results = []
            for result in response.results:
                try:
                    doc_data = result.document.derived_struct_data if result.document.derived_struct_data else {}
                    
                    data = {
                        "document_id": result.document.id,
                        "title": doc_data.get("title", "タイトルなし"),
                        "uri": doc_data.get("uri", ""),
                        "snippet": doc_data.get("snippet", "スニペットなし"),
                        "content": doc_data.get("content", ""),
                        "relevance_score": getattr(result, 'relevance_score', 0.0)
                    }
                    results.append(data)
                    
                except Exception as e:
                    logger.warning(f"検索結果の処理でエラー: {e}")
                    continue
            
            return {
                "query": query,
                "results": results,
                "total_size": getattr(response, 'total_size', 0),
                "search_successful": True
            }
            
        except Exception as e:
            logger.error(f"一般検索エラー: {e}")
            return {
                "query": query,
                "results": [],
                "total_size": 0,
                "search_successful": False,
                "error": str(e)
            }
    
    def is_available(self) -> bool:
        """
        Vertex AI Search サービスが利用可能かチェック
        
        Returns:
            bool: 利用可能な場合True
        """
        try:
            # 簡単なテスト検索を実行
            test_query = "test"
            request = discoveryengine.SearchRequest(
                serving_config=self.serving_config_path,
                query=test_query,
                page_size=1
            )
            
            response = self.client.search(request)
            logger.info("Vertex AI Search 接続テスト成功")
            return True
            
        except Exception as e:
            logger.error(f"Vertex AI Search 接続テスト失敗: {e}")
            return False