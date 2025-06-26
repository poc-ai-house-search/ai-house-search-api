# ai-house-search-api



# プロジェクト構造
<pre>
property-analysis-api/
├── main.py                     # メインアプリケーション
├── requirements.txt            # 依存関係
├── Dockerfile                  # Docker設定
├── .env.example               # 環境変数の例
├── .gitignore                 # Git無視ファイル
├── config/
│   ├── __init__.py
│   └── settings.py            # 設定管理
├── models/
│   ├── __init__.py
│   └── schemas.py             # Pydanticモデル
└── services/
    ├── __init__.py
    ├── gcs_service.py    # GCSサービス
    ├── scraping_service.py    # スクレイピングサービス
    ├── text_compression_service.py    # プロンプト圧縮サービス
    ├── vertex_ai_search_service.py    # Vertex AIサービス
    └── gemini_service.py      # Gemini AIサービス
</pre>