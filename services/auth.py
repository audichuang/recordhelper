# -*- coding: utf-8 -*-
"""
使用者認證服務模組 (AuthService)。

此模組提供處理 JSON Web Tokens (JWT) 的核心邏輯，包括：
- 創建 Access Token 和 Refresh Token。
- 解碼並驗證 Access Token 和 Refresh Token。
- 檢查權杖類型和過期時間。

依賴 `PyJWT` 函式庫進行 JWT 操作，並從 `config.AppConfig` 獲取相關設定
(例如：JWT 密鑰、演算法、權杖過期時間)。
"""

import jwt # 用於 JWT 編碼和解碼
from datetime import datetime, timedelta, timezone # 用於處理權杖的過期時間和簽發時間
from typing import Optional, Dict, Any # 用於類型註解
import logging

from config import AppConfig # 導入應用程式組態

logger = logging.getLogger(__name__)

class AuthService:
    """
    認證服務類別。

    提供一組靜態方法，用於處理 JWT 的創建、解碼和驗證。
    這些方法封裝了與 JWT 相關的操作細節，使其他部分的程式碼可以更方便地使用認證功能。
    """
    
    @staticmethod
    def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        創建 JWT Access Token。

        Access Token 用於驗證使用者對受保護資源的訪問權限。它具有較短的生命週期。

        Args:
            user_id (str): 要包含在權杖中的使用者唯一識別碼。
            expires_delta (Optional[timedelta], optional): 權杖的有效時長。
                                                           如果未提供，則使用 `AppConfig` 中設定的預設過期時間。

        Returns:
            str: 編碼後的 JWT Access Token 字串。
        """
        config = AppConfig.from_env() # 載入應用程式組態
        
        # 設定權杖過期時間
        if expires_delta:
            expire_at = datetime.now(timezone.utc) + expires_delta # 使用 UTC 時間以避免時區問題
        else:
            # 從 AppConfig 獲取 ACCESS_TOKEN_EXPIRE_MINUTES 並轉換為 timedelta
            # 假設 AppConfig 中有 ACCESS_TOKEN_EXPIRE_MINUTES 屬性 (以分鐘為單位)
            expire_at = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # 準備 JWT 的 payload (負載)
        payload_to_encode = {
            'user_id': user_id,         # 使用者識別碼，用於識別權杖的擁有者
            'exp': expire_at,           # 'exp' (Expiration Time) 欄位，定義權杖的過期時間戳
            'iat': datetime.now(timezone.utc), # 'iat' (Issued At) 欄位，定義權杖的簽發時間戳
            'type': 'access'            # 自訂欄位，標識此權杖為 Access Token
        }
        
        # 使用 PyJWT 編碼 payload
        encoded_jwt = jwt.encode(
            payload_to_encode, 
            config.SECRET_KEY, # 從 AppConfig 獲取 JWT 簽名密鑰
            algorithm=config.ALGORITHM # 從 AppConfig 獲取 JWT 簽名演算法 (例如 'HS256')
        )
        logger.debug(f"為使用者 ID {user_id} 創建了新的 Access Token，過期時間: {expire_at.isoformat()}")
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        創建 JWT Refresh Token。

        Refresh Token 用於獲取新的 Access Token，通常具有比 Access Token 更長的生命週期。

        Args:
            user_id (str): 要包含在權杖中的使用者唯一識別碼。
            expires_delta (Optional[timedelta], optional): 權杖的有效時長。
                                                           如果未提供，則使用 `AppConfig` 中設定的預設過期時間。

        Returns:
            str: 編碼後的 JWT Refresh Token 字串。
        """
        config = AppConfig.from_env()
        
        if expires_delta:
            expire_at = datetime.now(timezone.utc) + expires_delta
        else:
            # 從 AppConfig 獲取 REFRESH_TOKEN_EXPIRE_DAYS 並轉換為 timedelta
            # 假設 AppConfig 中有 REFRESH_TOKEN_EXPIRE_DAYS 屬性 (以天為單位)
            expire_at = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
        
        payload_to_encode = {
            'user_id': user_id,
            'exp': expire_at,
            'iat': datetime.now(timezone.utc),
            'type': 'refresh' # 標識此權杖為 Refresh Token
        }
        
        encoded_jwt = jwt.encode(
            payload_to_encode, 
            config.SECRET_KEY, 
            algorithm=config.ALGORITHM
        )
        logger.debug(f"為使用者 ID {user_id} 創建了新的 Refresh Token，過期時間: {expire_at.isoformat()}")
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        解碼並驗證 JWT Access Token。

        Args:
            token (str): 要解碼的 JWT Access Token 字串。

        Returns:
            Dict[str, Any]: 解碼後的 JWT payload (包含 user_id, exp, iat, type 等資訊)。

        Raises:
            jwt.ExpiredSignatureError: 如果權杖已過期。
            jwt.InvalidTokenError: 如果權杖無效 (例如簽名不符、類型不正確等)。
        """
        config = AppConfig.from_env()
        try:
            payload = jwt.decode(
                token, 
                config.SECRET_KEY, 
                algorithms=[config.ALGORITHM] # 需要傳遞一個演算法列表
            )
            
            # 驗證權杖類型是否為 'access'
            if payload.get('type') != 'access':
                logger.warning(f"嘗試解碼的權杖類型無效：預期 'access'，實際為 '{payload.get('type')}'。")
                raise jwt.InvalidTokenError("無效的權杖類型：非 Access Token。")
            
            logger.debug(f"Access Token 解碼成功，使用者 ID: {payload.get('user_id')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("嘗試解碼的 Access Token 已過期。")
            raise # 重新拋出，讓上層處理
        except jwt.InvalidTokenError as e: # 捕獲 PyJWT 的其他無效權杖錯誤
            logger.warning(f"無效的 Access Token：{str(e)}")
            raise # 重新拋出
        except Exception as e: # 捕獲其他未預期的解碼錯誤
            logger.error(f"Access Token 解碼過程中發生未預期錯誤: {str(e)}", exc_info=True)
            # 將未知錯誤包裝為 InvalidTokenError，以便上層統一處理
            raise jwt.InvalidTokenError(f"Access Token 解碼失敗：{str(e)}")
    
    @staticmethod
    def decode_refresh_token(token: str) -> Dict[str, Any]:
        """
        解碼並驗證 JWT Refresh Token。

        Args:
            token (str): 要解碼的 JWT Refresh Token 字串。

        Returns:
            Dict[str, Any]: 解碼後的 JWT payload。

        Raises:
            jwt.ExpiredSignatureError: 如果權杖已過期。
            jwt.InvalidTokenError: 如果權杖無效。
        """
        config = AppConfig.from_env()
        try:
            payload = jwt.decode(
                token, 
                config.SECRET_KEY, 
                algorithms=[config.ALGORITHM]
            )
            
            # 驗證權杖類型是否為 'refresh'
            if payload.get('type') != 'refresh':
                logger.warning(f"嘗試解碼的權杖類型無效：預期 'refresh'，實際為 '{payload.get('type')}'。")
                raise jwt.InvalidTokenError("無效的權杖類型：非 Refresh Token。")
            
            logger.debug(f"Refresh Token 解碼成功，使用者 ID: {payload.get('user_id')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("嘗試解碼的 Refresh Token 已過期。")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"無效的 Refresh Token：{str(e)}")
            raise
        except Exception as e:
            logger.error(f"Refresh Token 解碼過程中發生未預期錯誤: {str(e)}", exc_info=True)
            raise jwt.InvalidTokenError(f"Refresh Token 解碼失敗：{str(e)}")
    
    @staticmethod
    def verify_token(token: str) -> bool:
        """
        驗證一個 Access Token 是否仍然有效 (未過期且可被正確解碼)。

        注意：此方法僅檢查 Access Token。

        Args:
            token (str): 要驗證的 JWT Access Token 字串。

        Returns:
            bool: 如果權杖有效則返回 True，否則返回 False。
        """
        try:
            # 嘗試使用 decode_token 方法解碼，該方法已包含類型和過期檢查
            AuthService.decode_token(token) 
            logger.debug("Token 驗證成功。")
            return True
        except jwt.PyJWTError: # 捕獲所有 PyJWT 相關的錯誤 (包括 ExpiredSignatureError, InvalidTokenError)
            logger.debug("Token 驗證失敗 (可能已過期或無效)。")
            return False
        except Exception as e: # 捕獲其他非預期的錯誤
            logger.error(f"Token 驗證過程中發生未預期錯誤: {str(e)}", exc_info=True)
            return False