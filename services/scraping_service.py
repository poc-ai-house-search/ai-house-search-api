import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
from config.settings import settings
from services.text_compression_service import TextCompressionService

logger = logging.getLogger(__name__)

class ScrapingService:
    """Webスクレイピングサービス（テキスト圧縮機能付き）"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.text_compressor = TextCompressionService()
    
    @staticmethod
    def is_url(text: str) -> bool:
        """テキストがURLかどうかを判定"""
        try:
            result = urlparse(text)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def scrape_website(self, url: str, enable_compression: bool = True, compression_ratio: float = 0.6) -> str:
        """
        Webサイトからテキストデータをスクレイピング
        
        Args:
            url: スクレイピング対象のURL
            enable_compression: テキスト圧縮を有効にするか
            compression_ratio: 圧縮率（0.6 = 40%削減目標）
        
        Returns:
            抽出・圧縮されたテキスト
        """
        try:
            logger.info(f"スクレイピング開始: {url}")
            
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=settings.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 不要なタグを削除
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                tag.decompose()
            
            # より詳細な不要要素の除去
            for class_name in ['advertisement', 'ads', 'banner', 'popup', 'modal', 'cookie', 'privacy']:
                for element in soup.find_all(class_=lambda x: x and class_name in str(x).lower()):
                    element.decompose()
            
            # テキストを抽出
            text = soup.get_text()
            
            # 基本的なクリーニング
            text = self._basic_clean_text(text)
            
            logger.info(f"生テキスト抽出完了: {len(text)}文字")
            
            # テキスト圧縮
            if enable_compression:
                target_length = int(settings.MAX_TEXT_LENGTH * compression_ratio)
                text = self.text_compressor.compress_text(
                    text, 
                    max_length=target_length,
                    compression_ratio=compression_ratio
                )
            else:
                # 圧縮無効の場合は最大文字数でカット
                if len(text) > settings.MAX_TEXT_LENGTH:
                    text = text[:settings.MAX_TEXT_LENGTH] + "..."
            
            logger.info(f"最終テキスト: {len(text)}文字")
            return text
            
        except requests.RequestException as e:
            logger.error(f"スクレイピングエラー: {e}")
            raise Exception(f"スクレイピングに失敗しました: {str(e)}")
        except Exception as e:
            logger.error(f"予期せぬエラー: {e}")
            raise Exception(f"処理中にエラーが発生しました: {str(e)}")
    
    def _basic_clean_text(self, text: str) -> str:
        """基本的なテキストクリーニング"""
        import re
        
        # 連続する空白・改行を正規化
        text = re.sub(r'\s+', ' ', text)
        
        # 不要な文字列を除去
        unwanted_patterns = [
            r'Cookie.*?設定',
            r'プライバシーポリシー',
            r'利用規約',
            r'サイトマップ',
            r'ページトップ',
            r'メニュー',
            r'ナビゲーション',
            r'フッター',
            r'ヘッダー',
            r'広告',
            r'PR',
            r'スポンサー',
            r'関連記事',
            r'おすすめ',
            r'人気記事',
            r'ランキング',
            r'タグ:',
            r'カテゴリ:',
            r'投稿日:',
            r'更新日:',
            r'作成者:',
            r'シェア',
            r'ツイート',
            r'いいね',
            r'コメント',
            r'購読',
            r'登録',
            r'ログイン',
            r'ログアウト',
            r'マイページ',
            r'お気に入り',
            r'ブックマーク',
        ]
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def extract_property_specific_info(self, text: str) -> str:
        """物件情報に特化した情報抽出"""
        import re
        
        # 物件情報のキーワードパターン
        property_patterns = [
            r'物件名[：:\s]*[^\n]+',
            r'住所[：:\s]*[^\n]+',
            r'価格[：:\s]*[^\n]+',
            r'賃料[：:\s]*[^\n]+',
            r'家賃[：:\s]*[^\n]+',
            r'面積[：:\s]*[^\n]+',
            r'間取り[：:\s]*[^\n]+',
            r'築年数[：:\s]*[^\n]+',
            r'最寄り駅[：:\s]*[^\n]+',
            r'徒歩[：:\s]*\d+分',
            r'階[：:\s]*\d+階',
            r'駐車場[：:\s]*[^\n]+',
            r'設備[：:\s]*[^\n]+',
            r'敷金[：:\s]*[^\n]+',
            r'礼金[：:\s]*[^\n]+',
            r'管理費[：:\s]*[^\n]+',
            r'共益費[：:\s]*[^\n]+',
            r'\d+万円',
            r'\d+円',
            r'\d+㎡',
            r'\d+m²',
            r'\d+K|\d+DK|\d+LDK',
            r'築\d+年',
        ]
        
        extracted_info = []
        for pattern in property_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            extracted_info.extend(matches)
        
        # 重複除去と結合
        unique_info = list(dict.fromkeys(extracted_info))  # 順序を保持して重複除去
        
        return '\n'.join(unique_info) if unique_info else text