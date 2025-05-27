from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from models.async_models import User
from services.auth import AuthService
from config import AppConfig

logger = logging.getLogger(__name__)

# 創建路由器
auth_router = APIRouter()

# HTTP Bearer token scheme
security = HTTPBearer()

# Pydantic 模型
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class MessageResponse(BaseModel):
    message: str


# 依賴注入
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """獲取當前用戶"""
    try:
        token = credentials.credentials
        payload = AuthService.decode_token(token)
        user_id = payload.get('user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的令牌"
            )
        
        user = await User.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶不存在"
            )
        
        return user
        
    except Exception as e:
        logger.error(f"認證錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認證失敗"
        )


@auth_router.post("/register", response_model=AuthResponse)
async def register(user_data: UserRegister):
    """用戶註冊"""
    try:
        # 檢查用戶是否已存在
        existing_user = await User.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="該電子郵件已被註冊"
            )
        
        # 創建新用戶
        user = await User.create(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name
        )
        
        # 生成令牌
        access_token = AuthService.create_access_token(user.id)
        refresh_token = AuthService.create_refresh_token(user.id)
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"註冊錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="註冊失敗"
        )


@auth_router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin):
    """用戶登入"""
    try:
        # 驗證用戶
        user = await User.get_by_email(login_data.email)
        if not user or not user.check_password(login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="電子郵件或密碼錯誤"
            )
        
        # 生成令牌
        access_token = AuthService.create_access_token(user.id)
        refresh_token = AuthService.create_refresh_token(user.id)
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登入錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登入失敗"
        )


@auth_router.post("/refresh", response_model=AuthResponse)
async def refresh_token(token_data: TokenRefresh):
    """刷新令牌"""
    try:
        # 驗證刷新令牌
        payload = AuthService.decode_refresh_token(token_data.refresh_token)
        user_id = payload.get('user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的刷新令牌"
            )
        
        # 獲取用戶
        user = await User.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶不存在"
            )
        
        # 生成新令牌
        access_token = AuthService.create_access_token(user.id)
        refresh_token = AuthService.create_refresh_token(user.id)
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刷新令牌失敗"
        )


@auth_router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """用戶登出"""
    try:
        # 這裡可以實現令牌黑名單邏輯
        # 目前簡單返回成功訊息
        
        return MessageResponse(message="登出成功")
        
    except Exception as e:
        logger.error(f"登出錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失敗"
        )


@auth_router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """獲取當前用戶信息"""
    return current_user.to_dict() 