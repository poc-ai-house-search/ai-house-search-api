# services/vertex_ai_search_service.py (修正版)
import logging
from google.cloud import discoveryengine_v1 as discoveryengine
from google.api_core.client_options import ClientOptions
from config.settings import settings
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class VertexAISearchService:
    """Vertex AI Search サービス"""
    
    def __init__(self):
        """サービス初期化"""
        try:
            if not settings.ENABLE_VERTEX_AI_SEARCH:
                logger.info("Vertex AI Search は無効です")
                self.client = None
                return
            
            # クライアントオプションの設定
            client_options = None
            if settings.GCP_LOCATION != "global":
                client_options = ClientOptions(
                    api_endpoint=f"{settings.GCP_LOCATION}-discoveryengine.googleapis.com"
                )
            
            # クライアント初期化
            self.client = discoveryengine.SearchServiceClient(client_options=client_options)
            
            # サービング設定のパス構築
            self.serving_config = self.client.serving_config_path(
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_LOCATION,
                data_store=settings.VERTEX_AI_SEARCH_DATA_STORE_ID,
                serving_config="default_config"
            )
            
            logger.info(f"Vertex AI Search サービス初期化完了")
            logger.info(f"プロジェクト: {settings.GCP_PROJECT_ID}")
            logger.info(f"データストア: {settings.VERTEX_AI_SEARCH_DATA_STORE_ID}")
            logger.info(f"ロケーション: {settings.GCP_LOCATION}")
            
        except Exception as e:
            logger.error(f"Vertex AI Search サービス初期化エラー: {e}")
            self.client = None
            raise

    def search_financial_info(self, address: str) -> Dict[str, Any]:
        """
        住所の財務情報を検索
        
        Args:
            address (str): 検索対象の住所
            
        Returns:
            Dict[str, Any]: 検索結果
        """
        if not self.client:
            logger.warning("Vertex AI Search クライアントが初期化されていません")
            return {
                "search_successful": False,
                "results": [],
                "error": "Vertex AI Search サービスが利用できません",
                "query": f"{address}の財務状況について、良い悪いと根拠を含めて教えてください",
                "address": address
            }
        
        try:
            # 検索クエリの構築
            query_text = f"{address}の財務状況について、良い悪いと根拠を含めて教えてください"
            
            logger.info(f"Vertex AI Search 検索開始: {query_text}")
            
            # コンテンツ検索仕様の設定（重要：スニペットを有効化）
            content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
                snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    return_snippet=True,  # スニペットを返す
                    max_snippet_count=3   # 最大3つのスニペット
                ),
                summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                    summary_result_count=5,  # 要約に使用する結果数
                    include_citations=True,  # 引用を含める
                    ignore_adversarial_query=True,
                    ignore_non_summary_seeking_query=True
                ),
                extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                    max_extractive_answer_count=3,
                    max_extractive_segment_count=3
                )
            )
            
            # 検索リクエストの作成
            search_request = discoveryengine.SearchRequest(
                serving_config=self.serving_config,
                query=query_text,
                page_size=10,  # 取得する結果数
                content_search_spec=content_search_spec,
                query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                    condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO
                ),
                spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                    mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
                )
            )
            
            # 検索実行
            response = self.client.search(search_request)
            
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