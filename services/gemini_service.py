# services/gemini_service.py
import base64
import logging
from typing import AsyncIterator, Dict, Any, Optional
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, HarmCategory, HarmBlockThreshold
import asyncio
from config.settings import settings
from models.schemas import GenerationConfig as ConfigSchema, UsageMetadata

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self._model = None
        self._initialize_vertex_ai()
    
    def _initialize_vertex_ai(self):
        """Vertex AIを初期化"""
        try:
            vertexai.init(
                project=settings.google_cloud_project_id,
                location=settings.google_cloud_location
            )
            logger.info(f"Vertex AI initialized for project: {settings.google_cloud_project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {str(e)}")
            raise
    
    def _get_model(self, model_name: str = None) -> GenerativeModel:
        """モデルインスタンスを取得"""
        if not self._model:
            model_name = model_name or settings.default_model
            
            # 安全設定
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            self._model = GenerativeModel(
                model_name,
                safety_settings=safety_settings
            )
            logger.info(f"Model initialized: {model_name}")
        
        return self._model
    
    def _build_generation_config(self, config: Optional[ConfigSchema] = None) -> GenerationConfig:
        """生成設定を構築"""
        if config:
            return GenerationConfig(
                max_output_tokens=config.max_output_tokens,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                stop_sequences=config.stop_sequences
            )
        
        return GenerationConfig(
            max_output_tokens=settings.max_tokens,
            temperature=settings.temperature,
            top_p=settings.top_p,
            top_k=settings.top_k
        )
    
    def _extract_usage_metadata(self, response) -> UsageMetadata:
        """使用量メタデータを抽出"""
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            return UsageMetadata(
                prompt_token_count=response.usage_metadata.prompt_token_count or 0,
                candidates_token_count=response.usage_metadata.candidates_token_count or 0,
                total_token_count=response.usage_metadata.total_token_count or 0
            )
        return UsageMetadata()
    
    async def generate_content(
        self, 
        message: str, 
        config: Optional[ConfigSchema] = None,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """コンテンツを生成"""
        try:
            model = self._get_model()
            generation_config = self._build_generation_config(config)
            
            # システム指示がある場合はモデルを再作成
            if system_instruction:
                model = GenerativeModel(
                    settings.default_model,
                    system_instruction=system_instruction
                )
            
            response = await asyncio.to_thread(
                model.generate_content,
                message,
                generation_config=generation_config
            )
            
            return {
                'success': True,
                'content': response.text,
                'usage': self._extract_usage_metadata(response),
                'finish_reason': response.candidates[0].finish_reason.name if response.candidates else None
            }
            
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            return {
                'success': False,
                'error': f'コンテンツ生成に失敗しました: {str(e)}'
            }
    
    async def generate_content_stream(
        self, 
        message: str, 
        config: Optional[ConfigSchema] = None,
        system_instruction: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """ストリーミングでコンテンツを生成"""
        try:
            model = self._get_model()
            generation_config = self._build_generation_config(config)
            
            if system_instruction:
                model = GenerativeModel(
                    settings.default_model,
                    system_instruction=system_instruction
                )
            
            responses = await asyncio.to_thread(
                model.generate_content,
                message,
                generation_config=generation_config,
                stream=True
            )
            
            for response in responses:
                if response.text:
                    yield {
                        'content': response.text,
                        'done': False
                    }
            
            yield {'done': True}
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {str(e)}")
            yield {'error': str(e)}
    
    async def chat(
        self, 
        messages: list, 
        config: Optional[ConfigSchema] = None,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """チャット機能"""
        try:
            model = self._get_model()
            generation_config = self._build_generation_config(config)
            
            if system_instruction:
                model = GenerativeModel(
                    settings.default_model,
                    system_instruction=system_instruction
                )
            
            chat_session = model.start_chat()
            
            # 過去のメッセージを送信（最後以外）
            for msg in messages[:-1]:
                if msg.role == 'user':
                    await asyncio.to_thread(
                        chat_session.send_message,
                        msg.content
                    )
            
            # 最新メッセージで応答取得
            last_message = messages[-1]
            if last_message.role == 'user':
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    last_message.content,
                    generation_config=generation_config
                )
                
                return {
                    'success': True,
                    'content': response.text,
                    'usage': self._extract_usage_metadata(response),
                    'finish_reason': response.candidates[0].finish_reason.name if response.candidates else None
                }
            
            return {
                'success': False,
                'error': '有効なユーザーメッセージが見つかりません'
            }
            
        except Exception as e:
            logger.error(f"Chat failed: {str(e)}")
            return {
                'success': False,
                'error': f'チャット処理に失敗しました: {str(e)}'
            }
    
    async def analyze_image(
        self, 
        image_data: str, 
        prompt: str, 
        mime_type: str = "image/jpeg",
        config: Optional[ConfigSchema] = None
    ) -> Dict[str, Any]:
        """画像を分析"""
        try:
            model = self._get_model()
            generation_config = self._build_generation_config(config)
            
            # Base64デコード
            image_bytes = base64.b64decode(image_data)
            image_part = Part.from_data(image_bytes, mime_type=mime_type)
            
            response = await asyncio.to_thread(
                model.generate_content,
                [prompt, image_part],
                generation_config=generation_config
            )
            
            return {
                'success': True,
                'content': response.text,
                'usage': self._extract_usage_metadata(response),
                'finish_reason': response.candidates[0].finish_reason.name if response.candidates else None
            }
            
        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            return {
                'success': False,
                'error': f'画像分析に失敗しました: {str(e)}'
            }

# シングルトンインスタンス
gemini_service = GeminiService()