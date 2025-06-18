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
    ├── scraping_service.py    # スクレイピングサービス
    └── gemini_service.py      # Gemini AIサービス
</pre>