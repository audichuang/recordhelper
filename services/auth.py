"""
認證服務
處理JWT令牌的生成、驗證和管理
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from config import AppConfig

logger = logging.getLogger(__name__)


class AuthService:
    """認證服務類"""
    
    @staticmethod
    def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """創建訪問令牌"""
        config = AppConfig.from_env()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + config.jwt_access_token_expires
        
        payload = {
            'user_id': user_id,
            'exp': expire,
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        
        return jwt.encode(payload, config.jwt_secret_key, algorithm='HS256')
    
    @staticmethod
    def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """創建刷新令牌"""
        config = AppConfig.from_env()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + config.jwt_refresh_token_expires
        
        payload = {
            'user_id': user_id,
            'exp': expire,
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        
        return jwt.encode(payload, config.jwt_secret_key, algorithm='HS256')
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """解碼訪問令牌"""
        try:
            config = AppConfig.from_env()
            payload = jwt.decode(token, config.jwt_secret_key, algorithms=['HS256'])
            
            # 檢查令牌類型
            if payload.get('type') != 'access':
                raise jwt.InvalidTokenError('Invalid token type')
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token已過期")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"無效的token: {e}")
            raise
        except Exception as e:
            logger.error(f"Token解碼錯誤: {e}")
            raise jwt.InvalidTokenError('Token解碼失敗')
    
    @staticmethod
    def decode_refresh_token(token: str) -> Dict[str, Any]:
        """解碼刷新令牌"""
        try:
            config = AppConfig.from_env()
            payload = jwt.decode(token, config.jwt_secret_key, algorithms=['HS256'])
            
            # 檢查令牌類型
            if payload.get('type') != 'refresh':
                raise jwt.InvalidTokenError('Invalid token type')
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token已過期")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"無效的refresh token: {e}")
            raise
        except Exception as e:
            logger.error(f"Refresh token解碼錯誤: {e}")
            raise jwt.InvalidTokenError('Refresh token解碼失敗')
    
    @staticmethod
    def verify_token(token: str) -> bool:
        """驗證令牌是否有效"""
        try:
            AuthService.decode_token(token)
            return True
        except:
            return False 