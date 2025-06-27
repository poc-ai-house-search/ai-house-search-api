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
                ),
                # ContentSearchSpecを追加してスニペットとサマリーを取得
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                        return_snippet=True,
                        max_snippet_count=3
                    ),
                    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                        summary_result_count=5,
                        include_citations=True,
                        ignore_adversarial_query=True,
                        ignore_non_summary_seeking_query=True
                    ),
                    extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                        max_extractive_answer_count=1,
                        max_extractive_segment_count=1,
                        return_extractive_segment_score=True
                    )
                )
            )
            
            # 検索の実行
            response = self.client.search(request)
            
            # 結果の処理
            results = []
            for result in response.results:
                document = result.document
                
                # スニペットの抽出（新しい方法）
                snippets = []
                if hasattr(result, 'document') and hasattr(result.document, 'derived_struct_data'):
                    derived_data = dict(result.document.derived_struct_data) if result.document.derived_struct_data else {}
                    
                    # スニペットの取得
                    if 'snippets' in derived_data:
                        for snippet_info in derived_data['snippets']:
                            if isinstance(snippet_info, dict):
                                snippet_text = snippet_info.get('snippet', '')
                                if snippet_text:
                                    snippets.append(snippet_text)
                    
                    # extractive_answersからも取得
                    if 'extractive_answers' in derived_data:
                        for answer in derived_data['extractive_answers']:
                            if isinstance(answer, dict) and 'content' in answer:
                                snippets.append(answer['content'])
                    
                    # extractive_segmentsからも取得
                    if 'extractive_segments' in derived_data:
                        for segment in derived_data['extractive_segments']:
                            if isinstance(segment, dict) and 'content' in segment:
                                snippets.append(segment['content'])
                
                # コンテンツの抽出
                content = ""
                if hasattr(document, 'struct_data') and document.struct_data:
                    struct_data = dict(document.struct_data)
                    content = struct_data.get('content', '')
                elif hasattr(document, 'derived_struct_data') and document.derived_struct_data:
                    derived_data = dict(document.derived_struct_data)
                    content = derived_data.get('content', '')
                
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
                    "title": title if title else "タイトル未取得",
                    "uri": uri,
                    "snippet": " | ".join(snippets) if snippets else "スニペット未生成",
                    "content": content,
                    "relevance_score": getattr(result, 'relevance_score', 0),
                    "metadata": {
                        "category": "",
                        "date": "",
                        "source": uri,
                        "snippet_count": len(snippets)
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
                "query": query,  # ← ここを修正: query_text → query
                "address": address,
                "summary": summary_text,
                "search_metadata": {
                    "data_store_id": self.data_store_id,  # ← settings経由での参照を修正
                    "location": self.location,           # ← settings経由での参照を修正
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
                page_size=page_size,
                # ContentSearchSpecを追加してスニペットを取得
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                        return_snippet=True,
                        max_snippet_count=2
                    )
                )
            )
            
            response = self.client.search(request)
            
            results = []
            for result in response.results:
                try:
                    # スニペットを適切に取得
                    snippet_text = "スニペット未生成"
                    if hasattr(result, 'document') and hasattr(result.document, 'derived_struct_data'):
                        derived_data = dict(result.document.derived_struct_data) if result.document.derived_struct_data else {}
                        
                        # 様々な場所からスニペットを取得
                        snippets = []
                        if 'snippets' in derived_data:
                            for snippet_info in derived_data['snippets']:
                                if isinstance(snippet_info, dict):
                                    snippet_text_item = snippet_info.get('snippet', '')
                                    if snippet_text_item:
                                        snippets.append(snippet_text_item)
                        
                        if snippets:
                            snippet_text = " | ".join(snippets)
                    
                    doc_data = result.document.derived_struct_data if result.document.derived_struct_data else {}
                    
                    data = {
                        "document_id": result.document.id,
                        "title": doc_data.get("title", "タイトル未取得"),
                        "uri": doc_data.get("uri", ""),
                        "snippet": snippet_text,
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
    
    def get_debug_info(self) -> Dict[str, Any]:
        """
        デバッグ情報を取得
        
        Returns:
            Dict[str, Any]: デバッグ情報
        """
        return {
            "project_id": self.project_id,
            "location": self.location,
            "data_store_id": self.data_store_id,
            "serving_config_id": self.serving_config_id,
            "serving_config_path": self.serving_config_path,
            "client_initialized": self.client is not None
        }