import google.generativeai as genai
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """Gemini AI分析サービス"""
    
    def __init__(self):
        if not settings.GOOGLE_API_KEY:
            raise ValueError("Google API Key is not configured")
        
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def analyze_property_from_url(self, text: str) -> str:
        """URLから抽出したテキストの物件分析"""
        prompt = f"""
        以下は不動産物件のWebサイトから抽出したテキストデータです。
        この物件について詳細な分析を行い、以下の項目について整理して回答してください：

        1. 物件の基本情報（物件名、住所、価格、面積など）
        2. 物件の特徴・設備
        3. 立地条件（最寄り駅、周辺環境など）
        4. この物件のメリット・デメリット
        5. 総合的な評価とおすすめ度

        抽出テキスト:
        {text}
        """
        
        return self._generate_analysis(prompt, "URL分析")
    
    def analyze_property_by_name(self, property_name: str) -> str:
        """物件名による分析"""
        prompt = f"""
        以下の物件名について調査・分析を行ってください：
        「{property_name}」

        以下の項目について可能な限り詳しく回答してください：

        1. 物件の基本情報（住所、価格帯、面積など）
        2. 物件の特徴・設備
        3. 立地条件（最寄り駅、周辺環境、アクセスなど）
        4. この物件のメリット・デメリット
        5. 総合的な評価とおすすめ度

        ※公開されている情報を基に分析し、不明な点は「情報が不足しています」と明記してください。
        """
        
        return self._generate_analysis(prompt, "物件名分析")
    
    def _generate_analysis(self, prompt: str, analysis_type: str) -> str:
        """AI分析を実行"""
        try:
            logger.info(f"{analysis_type}開始")
            response = self.model.generate_content(prompt)
            logger.info(f"{analysis_type}完了")
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini分析エラー ({analysis_type}): {e}")
            raise Exception(f"AI分析に失敗しました: {str(e)}")