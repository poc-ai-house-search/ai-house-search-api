# services/gemini_service.py (修正版)
import google.generativeai as genai
from config.settings import settings
import logging
import json
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiService:
    """Google Gemini AI サービス"""
    
    def __init__(self):
        """サービス初期化"""
        try:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            
            # 現在利用可能なモデル名を試行
            model_names = [
                'gemini-1.5-flash',      # 最新の推奨モデル
                'gemini-1.5-pro',        # 高性能モデル
                'gemini-1.0-pro',        # 従来モデル
                'gemini-pro',            # 旧モデル名
            ]
            
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    logger.info(f"Gemini サービス初期化完了 - モデル: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"モデル {model_name} の初期化に失敗: {e}")
                    continue
            
            if self.model is None:
                # 利用可能なモデルを取得して表示
                try:
                    available_models = genai.list_models()
                    model_list = [model.name for model in available_models if 'generateContent' in model.supported_generation_methods]
                    logger.error(f"利用可能なモデル: {model_list}")
                    raise Exception(f"利用可能なGeminiモデルが見つかりません。利用可能なモデル: {model_list}")
                except Exception as list_error:
                    logger.error(f"モデル一覧の取得に失敗: {list_error}")
                    raise Exception("Geminiモデルの初期化に失敗しました")
                    
        except Exception as e:
            logger.error(f"Gemini サービス初期化エラー: {e}")
            raise

    def _get_json_prompt(self, content: str, is_url_analysis: bool = True) -> str:
        """JSON形式での分析用プロンプト"""
        base_prompt = f"""
以下の物件情報を分析して、必ずJSON形式で回答してください。

{content}

以下のJSON構造で回答してください：

{{
    "basic_info": {{
        "property_name": "物件名",
        "address": "住所",
        "room_number": "部屋番号（わかる場合）",
        "rent": "家賃",
        "management_fee": "管理費",
        "deposit": "敷金",
        "key_money": "礼金",
        "area": "面積",
        "layout": "間取り",
        "building_age": "築年数",
        "floor": "階数",
        "direction": "向き",
        "building_type": "建物種別"
    }},
    "features": {{
        "amenities": ["設備1", "設備2", "設備3"],
        "equipment": ["備品1", "備品2"],
        "special_features": ["特徴1", "特徴2"]
    }},
    "location": {{
        "nearest_stations": [
            {{"line": "路線名", "station": "駅名", "walking_time": "徒歩X分"}},
            {{"line": "路線名", "station": "駅名", "walking_time": "徒歩X分"}}
        ],
        "surrounding_environment": "周辺環境の説明"
    }},
    "evaluation": {{
        "advantages": ["メリット1", "メリット2", "メリット3"],
        "disadvantages": ["デメリット1", "デメリット2"],
        "overall_rating": 5,
        "recommendation_score": "★★★★☆ (4/5)",
        "summary": "総合的な評価とおすすめポイント"
    }}
}}

注意事項：
- 情報が不明な場合はnullを設定
- JSON形式以外の文字は含めない
- 必ず有効なJSONとして回答
- 数値は適切な型で設定（文字列の場合は引用符で囲む）
- overall_ratingは1-5の整数
"""
        return base_prompt

    def _get_text_prompt(self, content: str, is_url_analysis: bool = True) -> str:
        """テキスト形式での分析用プロンプト"""
        analysis_type = "URLから取得した物件情報" if is_url_analysis else "物件名"
        
        return f"""
以下の{analysis_type}について、詳細な物件分析を行ってください。

{content}

以下の構成で分析してください：

## 物件分析

**1. 物件の基本情報**
- 物件名、住所、価格、面積、間取り、築年数など

**2. 物件の特徴・設備**
- 設備、特徴、利便性など

**3. 立地条件**
- 最寄り駅、アクセス、周辺環境など

**4. この物件のメリット・デメリット**
- 良い点と注意点

**5. 総合的な評価とおすすめ度**
- 総合評価と★での評価（5段階）

詳細で具体的な分析をお願いします。
"""

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """JSONレスポンスをパース"""
        try:
            # JSONブロックを抽出（```json...```の場合）
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # 直接JSONの場合
                json_text = response_text.strip()
            
            # JSONをパース
            parsed = json.loads(json_text)
            logger.info("JSONレスポンスのパースに成功")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSONパースエラー: {e}")
            logger.error(f"レスポンステキスト: {response_text[:500]}...")
            
            # パースエラーの場合、基本的な構造を返す
            return {
                "basic_info": {
                    "property_name": "パース不可",
                    "summary": "JSONの解析に失敗しました"
                },
                "features": {"amenities": [], "equipment": [], "special_features": []},
                "location": {"nearest_stations": [], "surrounding_environment": None},
                "evaluation": {
                    "advantages": [],
                    "disadvantages": ["JSONパースエラー"],
                    "overall_rating": None,
                    "recommendation_score": None,
                    "summary": f"分析は完了しましたが、JSON形式での解析に失敗しました。元のレスポンス: {response_text[:200]}..."
                },
                "raw_response": response_text
            }

    def analyze_property_from_url(self, extracted_text: str, response_format: str = "json") -> Dict[str, Any]:
        """URLから抽出したテキストを基に物件分析"""
        try:
            if response_format.lower() == "json":
                prompt = self._get_json_prompt(extracted_text, is_url_analysis=True)
            else:
                prompt = self._get_text_prompt(extracted_text, is_url_analysis=True)
            
            logger.info(f"Gemini分析開始 (URL) - 形式: {response_format}")
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            if response_format.lower() == "json":
                return self._parse_json_response(response_text)
            else:
                return {
                    "basic_info": {"property_name": "URL分析"},
                    "evaluation": {"summary": response_text},
                    "raw_response": response_text
                }
                
        except Exception as e:
            logger.error(f"Gemini URL分析エラー: {e}")
            return {
                "basic_info": {"property_name": "分析エラー"},
                "evaluation": {"summary": f"分析中にエラーが発生しました: {str(e)}"},
                "error": str(e)
            }

    def analyze_property_by_name(self, property_name: str, response_format: str = "json") -> Dict[str, Any]:
        """物件名から分析"""
        try:
            content = f"物件名: {property_name}"
            
            if response_format.lower() == "json":
                prompt = self._get_json_prompt(content, is_url_analysis=False)
            else:
                prompt = self._get_text_prompt(content, is_url_analysis=False)
            
            logger.info(f"Gemini分析開始 (物件名) - 形式: {response_format}")
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            if response_format.lower() == "json":
                return self._parse_json_response(response_text)
            else:
                return {
                    "basic_info": {"property_name": property_name},
                    "evaluation": {"summary": response_text},
                    "raw_response": response_text
                }
                
        except Exception as e:
            logger.error(f"Gemini 物件名分析エラー: {e}")
            return {
                "basic_info": {"property_name": property_name},
                "evaluation": {"summary": f"分析中にエラーが発生しました: {str(e)}"},
                "error": str(e)
            }

    def analyze_financial_status(self, address: str, search_results: dict) -> dict:
        """
        住所の財務状況を分析
        
        Args:
            address (str): 住所
            search_results (dict): Vertex AI Searchの検索結果
            
        Returns:
            dict: 財務分析結果
        """
        try:
            # 検索結果からコンテンツを抽出
            search_content = ""
            if search_results.get("search_successful") and search_results.get("results"):
                search_content = "\n\n".join([
                    f"【{result.get('title', 'タイトルなし')}】\n{result.get('snippet', result.get('content', ''))}"
                    for result in search_results["results"][:5]  # 上位5件使用
                ])
            
            # プロンプトを構築
            prompt = f"""
以下の住所の財務状況について、検索結果をもとに詳細に分析してください。

**住所**: {address}

**検索結果からの関連情報**:
{search_content if search_content else "関連情報が見つかりませんでした。"}

**分析要求**:
上記の検索結果を詳細に分析し、以下のJSON形式で財務状況を評価してください。

**回答形式**（必ずこの形式のJSONで回答してください）:
```json
{{
    "financial_status": "良い/悪い/普通",
    "overall_score": 85,
    "analysis_summary": "財務状況の概要（200文字程度）",
    "positive_factors": [
        {{
            "factor": "良い要因のタイトル",
            "description": "詳細な説明",
            "evidence": "根拠となるデータや数値"
        }}
    ],
    "negative_factors": [
        {{
            "factor": "悪い要因のタイトル", 
            "description": "詳細な説明",
            "evidence": "根拠となるデータや数値"
        }}
    ],
    "financial_indicators": {{
        "revenue_total": "歳入総額（判明している場合）",
        "expenditure_total": "歳出総額（判明している場合）",
        "debt_ratio": "実質公債費比率などの債務指標"
    }},
    "data_reliability": {{
        "data_sources": {len(search_results.get('results', []))},
        "confidence_level": "high/medium/low"
    }}
}}
```
"""

            logger.info(f"財務分析開始: {address}")
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # JSONの抽出と解析
            try:
                # ```json と ``` で囲まれた部分を抽出
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    # JSON部分を探す
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_text = response_text[json_start:json_end]
                    else:
                        json_text = response_text
                
                financial_analysis = json.loads(json_text)
                
                # 基本的な検証とデフォルト値の設定
                required_fields = {
                    "financial_status": "普通",
                    "overall_score": 50,
                    "analysis_summary": "分析結果を取得しました",
                    "positive_factors": [],
                    "negative_factors": [],
                    "financial_indicators": {},
                    "data_reliability": {}
                }
                
                for field, default_value in required_fields.items():
                    if field not in financial_analysis:
                        financial_analysis[field] = default_value
                
                # データ信頼性情報を自動設定
                financial_analysis["data_reliability"].update({
                    "data_sources": len(search_results.get('results', [])),
                    "search_successful": search_results.get("search_successful", False),
                    "vertex_ai_search_used": True
                })
                
                logger.info(f"財務分析完了: {address} - {financial_analysis.get('financial_status')}")
                return financial_analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析エラー: {e}")
                return {
                    "financial_status": "分析中",
                    "overall_score": 50,
                    "analysis_summary": "JSON解析に失敗しましたが、分析は実行されました",
                    "positive_factors": [],
                    "negative_factors": [],
                    "financial_indicators": {},
                    "data_reliability": {
                        "data_sources": len(search_results.get('results', [])),
                        "confidence_level": "low",
                        "limitations": "JSON解析エラーが発生しました"
                    }
                }
                
        except Exception as e:
            logger.error(f"財務分析エラー: {e}")
            return {
                "financial_status": "エラー",
                "overall_score": 0,
                "analysis_summary": f"分析中にエラーが発生しました: {str(e)}",
                "positive_factors": [],
                "negative_factors": [],
                "financial_indicators": {},
                "data_reliability": {
                    "data_sources": 0,
                    "confidence_level": "low",
                    "limitations": "システムエラーにより分析できませんでした"
                }
            }