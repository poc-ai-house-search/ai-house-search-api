# services/vertex_ai_search_service.py
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
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
    
    def search_for_answer(self, query: str, page_size: int = 5) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Vertex AI Search を使用して、指定されたクエリに対する要約された回答と引用を生成します。

        Args:
            query (str): 回答を生成するための検索クエリ。
            page_size (int): 要約の生成に使用する内部検索結果の最大数（直接的な検索結果数ではない）。

        Returns:
            Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
                生成された回答テキストと、その回答の根拠となった引用のリストを返します。
                回答が生成されなかった場合は (None, None) を返します。
                引用リストの各辞書には、'uri' (元のドキュメントのURI) と 'snippet' (引用元のテキスト) が含まれます。
        """
        try:
            logger.info(f"Vertex AI Search (Answer) 実行: {query}")
            logger.info(f"サービング設定パス: {self.serving_config_path}")

            request = discoveryengine.SearchRequest(
                serving_config=self.serving_config_path,
                query=query,
                page_size=page_size,  # 要約生成のための内部的な結果数
                query_expansion_spec=discoveryengine.SearchRequest.QueryExpansionSpec(
                    condition=discoveryengine.SearchRequest.QueryExpansionSpec.Condition.AUTO
                ),
                spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                    mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
                ),
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                        summary_result_count=page_size,  # 要約生成に使用するドキュメント数
                        include_citations=True,         # 引用を含める
                        ignore_adversarial_query=True,  # 敵対的クエリを無視
                        ignore_non_summary_seeking_query=True, # 要約を求めないクエリを無視
                        model_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ModelSpec(
                            version="default"  # または "gemini-1.0-pro" などの特定のモデルバージョン
                        ),
                        # 回答と引用をより厳密に制御したい場合
                        # extractive_answers_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ExtractiveAnswersSpec(
                        #     max_extractive_answer_count=1,
                        #     min_extractive_answer_score=0.7 # 0.0 から 1.0 の範囲
                        # ),
                        # extractive_segments_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec.ExtractiveSegmentsSpec(
                        #     max_extractive_segment_count=3
                        # )
                    ),
                    # Answer生成に特化する場合、snippet_specやextractive_content_specは直接的な回答には影響しないことが多い
                    # 必要であれば残しても問題ないが、回答取得が主目的なら重要度は低い
                    # snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                    #     return_snippet=True,
                    #     max_snippet_count=3
                    # ),
                )
            )
            
            response = self.client.search(request)
            
            answer_text = None
            citations_list = []

            if response.summary and response.summary.summary_text:
                answer_text = response.summary.summary_text
                logger.info(f"Generated Answer: {answer_text[:200]}...") # 長すぎる場合を考慮

                if response.summary.citation_metadata:
                    for citation_source in response.summary.citation_metadata.citations:
                        for ref in citation_source.references:
                            # ref.document は Document オブジェクト
                            citation_info = {
                                "uri": "",
                                "title": "",
                                "snippet": ""
                            }
                            if ref.document:
                                if hasattr(ref.document, 'derived_struct_data'):
                                    derived_data = dict(ref.document.derived_struct_data)
                                    citation_info['uri'] = derived_data.get('link', derived_data.get('uri', ''))
                                    citation_info['title'] = derived_data.get('title', derived_data.get('htmlTitle', ''))
                                elif hasattr(ref.document, 'struct_data'):
                                    struct_data = dict(ref.document.struct_data)
                                    citation_info['title'] = struct_data.get('title', '')
                                    
                                # 引用内のスニペットを取得 (summary.citation_metadata.citations.references.snippets)
                                if ref.snippets:
                                    citation_info['snippet'] = " | ".join([s.snippet for s in ref.snippets if s.snippet])
                                    
                            citations_list.append(citation_info)
            
            logger.info(f"Vertex AI Search (Answer) 完了。回答の有無: {answer_text is not None}, 引用数: {len(citations_list)}")

            return answer_text, citations_list
            
        except Exception as e:
            logger.error(f"Vertex AI Search (Answer) エラー: {e}")
            return None, None
            
    def search_financial_info(self, address: str, page_size: int = 5) -> Dict[str, Any]:
        """
        指定された住所の財務状況に関する情報をVertex AI Searchから要約された形で取得します。
        このメソッドは、`search_for_answer` を特化したものです。
        
        Args:
            address (str): 検索対象の住所
            page_size (int): 要約生成に使用する内部検索結果の最大数。

        Returns:
            Dict[str, Any]: 検索結果（要約された回答、引用など）
        """
        query = f"{address}の財務状況について、良い悪いと根拠を含めて教えてください"
        answer_text, citations = self.search_for_answer(query, page_size)

        if answer_text:
            return {
                "search_successful": True,
                "query": query,
                "address": address,
                "summary": answer_text,
                "citations": citations, # 引用情報を追加
                "search_metadata": {
                    "data_store_id": self.data_store_id,
                    "location": self.location,
                    "answer_generated": True
                }
            }
        else:
            return {
                "search_successful": False,
                "query": query,
                "address": address,
                "summary": "指定された住所の財務状況に関する回答を生成できませんでした。",
                "citations": [],
                "search_metadata": {
                    "data_store_id": self.data_store_id,
                    "location": self.location,
                    "answer_generated": False
                }
            }

    def search_general(self, query: str, page_size: int = 5) -> Dict[str, Any]:
        """
        一般的な検索を実行し、個々のドキュメント結果を返します。
        Answer ではなく、検索結果のリストが欲しい場合に利用します。
        
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
                    snippet_text = "スニペット未生成"
                    if hasattr(result, 'document') and hasattr(result.document, 'derived_struct_data'):
                        derived_data = dict(result.document.derived_struct_data) if result.document.derived_struct_data else {}
                        
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
                page_size=1,
                # is_availableチェックなので、summary_specは必須ではない
                content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                    summary_spec=discoveryengine.SearchRequest.ContentSearchSpec.SummarySpec(
                        summary_result_count=1,
                        include_citations=False # テストなので引用は不要
                    )
                )
            )
            
            response = self.client.search(request)
            # Answerが生成されたかどうかで判断することもできる
            if response.summary and response.summary.summary_text:
                logger.info("Vertex AI Search 接続テスト成功 (Answer生成可能)")
            else:
                logger.info("Vertex AI Search 接続テスト成功 (回答は生成されませんでしたが接続は確認できました)")

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
