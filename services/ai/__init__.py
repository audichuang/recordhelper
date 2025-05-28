# -*- coding: utf-8 -*-
"""
AI 服務模組 (AI Services)。

此套件負責整合和提供各種人工智慧相關的功能，
主要集中在內容生成、摘要以及可能的未來擴展如自然語言處理、機器學習模型推斷等。

目前包含的服務：
- `gemini_async.py`: 提供與 Google Gemini 模型互動的異步服務，用於生成文本摘要等。

使用方式：
開發者可以從此套件中導入所需的 AI 服務類別，並在應用程式的其他部分 (例如 API 路由處理器或背景任務) 中使用。
"""
# 範例：如果有一個 gemini_async.py 檔案且其中定義了 AsyncGeminiService
# from .gemini_async import AsyncGeminiService

# __all__ = [
#    "AsyncGeminiService",
# ]