# -*- coding: utf-8 -*-
"""
服務層模組 (Service Layer)。

此套件包含所有應用程式的核心業務邏輯服務。
每個子模組或檔案通常代表一個特定領域的服務，例如使用者認證、錄音處理、AI 分析等。
服務層的目的是將業務邏輯與 API 路由處理和資料庫模型分離，以提高模組化和可維護性。
"""
# 可以在此處選擇性地匯出特定服務，以方便從 `from services import ...` 導入
# 例如:
# from .auth_service import AuthService
# from .recording_processing_service import process_recording_async

# __all__ = [
#     "AuthService",
#     "process_recording_async",
# ]