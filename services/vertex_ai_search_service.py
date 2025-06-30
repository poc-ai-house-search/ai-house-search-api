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
                                           os.environ.get("VERTEX_AI_SEARCH_SERVING_CONFIG_ID", "default_search"))
            
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
        指定された住所の財務状況に関する情報を検索（Answer APIを使用）
        
        Args:
            address (str): 検索対象の住所
            page_size (int): 取得する結果の数
            
        Returns:
            Dict[str, Any]: 検索結果
        """
        try:
            # 検索クエリを構築（財務状況に特化）
            query_text = f"{address}の財務状況について、良い悪いと根拠を含めて教えてください"
            
            logger.info(f"Vertex AI Search Answer API実行: {query_text}")
            logger.info(f"サービング設定パス: {self.serving_config_path}")
            
            # Answer APIリクエストの構築
            request = discoveryengine.AnswerRequest(
                serving_config=self.serving_config_path,
                query=discoveryengine.Query(text=query_text),
                # 検索仕様を追加
                search_spec=discoveryengine.AnswerRequest.SearchSpec(
                    search_params=discoveryengine.AnswerRequest.SearchSpec.SearchParams(
                        max_return_results=page_size,
                        # 検索結果の品質向上のための設定
                        boost_spec=None,
                        filter=""
                    ),
                    search_result_list=discoveryengine.AnswerRequest.SearchSpec.SearchResultList(
                        search_results=[]
                    )
                ),
                # 回答生成仕様
                answer_generation_spec=discoveryengine.AnswerRequest.AnswerGenerationSpec(
                    model_spec=discoveryengine.AnswerRequest.AnswerGenerationSpec.ModelSpec(
                        model_version="stable"
                    ),
                    prompt_spec=discoveryengine.AnswerRequest.AnswerGenerationSpec.PromptSpec(
                        preamble="""あなたは財務アナリストです。提供された情報を基に、以下のJSON形式で正確で詳細な財務分析を行ってください。

返答は必ず以下のJSON形式で行ってください：
{
  "positive_factors": [
    "良い点1の詳細説明",
    "良い点2の詳細説明"
  ],
  "negative_factors": [
    "悪い点1の詳細説明", 
    "悪い点2の詳細説明"
  ],
  "financial_indicators": {
    "revenue_total": "歳入総額（単位付き）",
    "expenditure_total": "歳出総額（単位付き）",
    "surplus_deficit": "収支状況",
    "debt_ratio": "借金比率",
    "financial_strength_index": "財政力指数"
  },
  "overall_assessment": "総合評価（良好/普通/懸念）",
  "summary": "財務状況の総括"
}

データが不足している場合は「データ不足」と記載してください。"""
                    ),
                    include_citations=True,
                    answer_language_code="ja"
                )
            )
            
            # Answer APIの実行
            response = self.client.answer(request)
            
            # Answer APIの結果を処理
            answer_text = ""
            search_results = []
            citations = []
            parsed_financial_data = None
            
            if hasattr(response, 'answer') and response.answer:
                answer_text = response.answer.answer_text
                
                # JSON形式の回答をパースして構造化
                try:
                    # JSONとして解析を試行
                    import json
                    import re
                    
                    # コードブロックやマークダウンから JSON を抽出
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', answer_text, re.DOTALL)
                    if json_match:
                        json_text = json_match.group(1)
                    else:
                        # 直接JSONを探す
                        json_match = re.search(r'\{.*\}', answer_text, re.DOTALL)
                        if json_match:
                            json_text = json_match.group(0)
                        else:
                            json_text = answer_text
                    
                    parsed_financial_data = json.loads(json_text)
                    logger.info("Vertex AI Search の回答をJSON形式で解析成功")
                    
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(f"JSON解析に失敗、テキスト形式で処理: {e}")
                    # JSON解析に失敗した場合はテキストのまま処理
                    parsed_financial_data = {
                        "positive_factors": [],
                        "negative_factors": [],
                        "financial_indicators": {},
                        "overall_assessment": "解析不能",
                        "summary": answer_text,
                        "raw_response": answer_text
                    }
                
                # ステップ情報から検索結果を抽出
                if hasattr(response.answer, 'steps'):
                    for step in response.answer.steps:
                        if hasattr(step, 'actions'):
                            for action in step.actions:
                                if hasattr(action, 'observation') and hasattr(action.observation, 'search_results'):
                                    for search_result in action.observation.search_results:
                                        result_item = {
                                            "document_id": getattr(search_result, 'document', ''),
                                            "title": getattr(search_result, 'title', ''),
                                            "uri": getattr(search_result, 'uri', ''),
                                            "snippet": getattr(search_result, 'snippet', ''),
                                            "content": "",  # Answer APIでは詳細コンテンツは通常含まれない
                                            "relevance_score": 0,
                                            "metadata": {
                                                "category": "",
                                                "date": "",
                                                "source": getattr(search_result, 'uri', '')
                                            }
                                        }
                                        search_results.append(result_item)
                
                # 引用情報を抽出
                if hasattr(response.answer, 'citations'):
                    for citation in response.answer.citations:
                        citations.append({
                            "start_index": getattr(citation, 'start_index', 0),
                            "end_index": getattr(citation, 'end_index', 0),
                            "sources": [source.reference_id for source in getattr(citation, 'sources', [])]
                        })
            
            logger.info(f"Vertex AI Search Answer API 完了: 回答長={len(answer_text)}, 検索結果={len(search_results)}件")
            
            return {
                "search_successful": True,
                "results": search_results,
                "total_size": len(search_results),
                "query": query_text,
                "address": address,
                "summary": answer_text,  # 元の文章形式
                "answer_text": answer_text,  # Answer API固有のフィールド
                "structured_data": parsed_financial_data,  # 構造化されたJSON形式のデータ
                "citations": citations,
                "search_metadata": {
                    "data_store_id": self.data_store_id,
                    "location": self.location,
                    "results_count": len(search_results),
                    "api_type": "answer",
                    "json_parsed": parsed_financial_data is not None and "raw_response" not in parsed_financial_data
                }
            }
            
        except Exception as e:
            logger.error(f"Vertex AI Search Answer API エラー: {e}")
            # エラーの場合は従来のSearch APIにフォールバック
            logger.info("Answer APIに失敗したため、Search APIにフォールバック")
            return self._search_financial_info_fallback(address, page_size)
    
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
    
    def _search_financial_info_fallback(self, address: str, page_size: int = 5) -> Dict[str, Any]:
        """
        従来のSearch APIを使用したフォールバック検索
        """
        try:
            query = f"{address}の財務状況について、良い悪いと根拠を含めて教えてください"
            
            request = discoveryengine.SearchRequest(
                serving_config=self.serving_config_path,
                query=query,
                page_size=page_size,
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                        return_snippet=True,
                        max_snippet_count=3
                    ),
                    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                        summary_result_count=5,
                        include_citations=True
                    )
                )
            )
            
            response = self.client.search(request)
            
            results = []
            for result in response.results:
                result_item = {
                    "document_id": result.document.id,
                    "title": "タイトル未取得",
                    "uri": "",
                    "snippet": "スニペット未生成",
                    "content": "",
                    "relevance_score": 0,
                    "metadata": {"category": "", "date": "", "source": ""}
                }
                results.append(result_item)
            
            summary_text = ""
            if hasattr(response, 'summary') and response.summary:
                summary_text = response.summary.summary_text
            
            return {
                "search_successful": True,
                "results": results,
                "total_size": len(results),
                "query": query,
                "address": address,
                "summary": summary_text,
                "search_metadata": {
                    "data_store_id": self.data_store_id,
                    "location": self.location,
                    "results_count": len(results),
                    "api_type": "search_fallback"
                }
            }
            
        except Exception as e:
            logger.error(f"フォールバック検索もエラー: {e}")
            return {
                "search_successful": False,
                "results": [],
                "error": str(e),
                "query": f"{address}の近隣の治安、行政、近くの病院、子育てに関する情報について教えてください。",
                "address": address
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