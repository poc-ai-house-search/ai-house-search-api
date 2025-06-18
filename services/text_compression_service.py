import re
from typing import Set, List
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class TextCompressionService:
    """テキスト圧縮サービス - 重複排除と最適化"""
    
    def __init__(self):
        # 除外する一般的な単語（ストップワード）
        self.stop_words = {
            'の', 'に', 'は', 'を', 'が', 'で', 'と', 'から', 'まで', 'より', 'へ',
            'という', 'ある', 'いる', 'する', 'なる', 'れる', 'られる', 'です', 'ます',
            'である', 'により', 'について', 'として', 'において', 'による', 'ため',
            'こと', 'もの', 'それ', 'これ', 'その', 'この', 'あの', 'どの', 'など',
            'また', 'しかし', 'ただし', 'なお', 'さらに', 'そして', 'また', 'および',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can'
        }
        
        # 不要なパターン
        self.noise_patterns = [
            r'^\d+$',  # 数字のみ
            r'^[^\w\s]+$',  # 記号のみ
            r'^\s*$',  # 空白のみ
            r'^.{1,2}$',  # 1-2文字の短い単語
        ]
    
    def compress_text(self, text: str, max_length: int = 30000, compression_ratio: float = 0.7) -> str:
        """
        テキストを圧縮する
        
        Args:
            text: 圧縮対象のテキスト
            max_length: 最大文字数
            compression_ratio: 圧縮率（0.7 = 30%削減）
        
        Returns:
            圧縮されたテキスト
        """
        try:
            logger.info(f"テキスト圧縮開始: {len(text)}文字")
            
            # 1. 基本的なクリーニング
            cleaned_text = self._basic_cleaning(text)
            
            # 2. 重複文章の除去
            deduplicated_text = self._remove_duplicate_sentences(cleaned_text)
            
            # 3. 重要な情報の抽出と再構成
            compressed_text = self._extract_important_info(deduplicated_text)
            
            # 4. 最終的な長さ調整
            if len(compressed_text) > max_length:
                compressed_text = self._truncate_intelligently(compressed_text, max_length)
            
            logger.info(f"テキスト圧縮完了: {len(text)}文字 → {len(compressed_text)}文字 ({(1-len(compressed_text)/len(text))*100:.1f}% 削減)")
            
            return compressed_text
            
        except Exception as e:
            logger.error(f"テキスト圧縮エラー: {e}")
            # エラーの場合は元のテキストを制限長で返す
            return text[:max_length] + "..." if len(text) > max_length else text
    
    def _basic_cleaning(self, text: str) -> str:
        """基本的なテキストクリーニング"""
        # 連続する空白・改行を正規化
        text = re.sub(r'\s+', ' ', text)
        
        # 特殊文字・記号の正規化
        text = re.sub(r'[^\w\s\.\,\!\?\:\;\-\(\)\[\]\{\}\/\@\#\%\&\*\+\=\|\\\~\`\'\"]', ' ', text)
        
        # 連続する句読点を整理
        text = re.sub(r'[\.]{2,}', '...', text)
        text = re.sub(r'[!]{2,}', '!', text)
        text = re.sub(r'[?]{2,}', '?', text)
        
        return text.strip()
    
    def _remove_duplicate_sentences(self, text: str) -> str:
        """重複文章の除去"""
        sentences = re.split(r'[.!?。！？]\s*', text)
        unique_sentences = []
        seen_sentences = set()
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 文章の正規化（小文字化、空白除去）
            normalized = re.sub(r'\s+', '', sentence.lower())
            
            # 短すぎる文章や数字のみの文章をスキップ
            if len(normalized) < 10 or normalized.isdigit():
                continue
            
            # 類似文章の検出（70%以上一致）
            is_duplicate = False
            for seen in seen_sentences:
                if self._calculate_similarity(normalized, seen) > 0.7:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_sentences.append(sentence)
                seen_sentences.add(normalized)
        
        return '. '.join(unique_sentences)
    
    def _extract_important_info(self, text: str) -> str:
        """重要な情報の抽出"""
        # 物件情報に関連するキーワード
        important_keywords = {
            '物件': 3, '住所': 3, '価格': 3, '賃料': 3, '家賃': 3, '面積': 3, '間取り': 3,
            '最寄り': 2, '駅': 2, '徒歩': 2, '分': 2, '築': 2, '年': 2, '階': 2,
            '設備': 2, 'バス': 1, 'トイレ': 1, 'キッチン': 1, 'エアコン': 1, '駐車場': 1,
            '学校': 1, '病院': 1, 'コンビニ': 1, 'スーパー': 1, '公園': 1,
            'ペット': 1, '敷金': 2, '礼金': 2, '管理費': 2, '共益費': 2
        }
        
        sentences = re.split(r'[.!?。！？]\s*', text)
        scored_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
                
            # 文章のスコア計算
            score = 0
            for keyword, weight in important_keywords.items():
                count = sentence.lower().count(keyword.lower())
                score += count * weight
            
            # 数字が含まれている文章は重要度アップ
            if re.search(r'\d+', sentence):
                score += 1
                
            # 単位が含まれている文章は重要度アップ
            if re.search(r'(万円|円|㎡|m²|分|km|階|年|月)', sentence):
                score += 2
            
            scored_sentences.append((sentence, score))
        
        # スコア順にソートして上位を選択
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        # 上位80%の文章を選択
        selected_count = max(1, int(len(scored_sentences) * 0.8))
        important_sentences = [sentence for sentence, _ in scored_sentences[:selected_count]]
        
        return '. '.join(important_sentences)
    
    def _truncate_intelligently(self, text: str, max_length: int) -> str:
        """インテリジェントな切り詰め"""
        if len(text) <= max_length:
            return text
        
        # 文章単位で切り詰め
        sentences = re.split(r'[.!?。！？]\s*', text)
        result = ""
        
        for sentence in sentences:
            if len(result + sentence + '. ') <= max_length - 3:  # "..."の分を考慮
                result += sentence + '. '
            else:
                break
        
        return result.rstrip() + "..."
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """2つのテキストの類似度を計算"""
        if not text1 or not text2:
            return 0.0
        
        # 文字レベルでの類似度計算（簡易版）
        longer = text1 if len(text1) > len(text2) else text2
        shorter = text2 if len(text1) > len(text2) else text1
        
        if len(longer) == 0:
            return 1.0
        
        # 共通文字数をカウント
        common_chars = 0
        for char in shorter:
            if char in longer:
                common_chars += 1
                longer = longer.replace(char, '', 1)
        
        return common_chars / len(shorter)
    
    def remove_duplicate_words(self, text: str, preserve_order: bool = True) -> str:
        """
        重複単語の除去（語順保持オプション付き）
        
        Args:
            text: 処理対象のテキスト
            preserve_order: 語順を保持するか
        
        Returns:
            重複を除去したテキスト
        """
        # 単語に分割（日本語対応）
        words = re.findall(r'\w+', text)
        
        if preserve_order:
            # 語順を保持して重複除去
            seen = set()
            unique_words = []
            for word in words:
                word_lower = word.lower()
                if word_lower not in seen and word_lower not in self.stop_words:
                    if not self._is_noise_word(word):
                        unique_words.append(word)
                        seen.add(word_lower)
        else:
            # 頻度順に並び替え
            word_freq = Counter(word.lower() for word in words 
                              if word.lower() not in self.stop_words and not self._is_noise_word(word))
            unique_words = [word for word, _ in word_freq.most_common()]
        
        return ' '.join(unique_words)
    
    def _is_noise_word(self, word: str) -> bool:
        """ノイズ単語の判定"""
        for pattern in self.noise_patterns:
            if re.match(pattern, word):
                return True
        return False