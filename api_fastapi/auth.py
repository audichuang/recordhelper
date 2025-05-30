from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
import uuid
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

# 更新導入，使用新的模型和資料庫會話
from models import User, get_async_db_session
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
    username: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

class AppleLogin(BaseModel):
    user_id: str
    email: Optional[EmailStr] = None
    full_name: str
    identity_token: str
    authorization_code: str

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class MessageResponse(BaseModel):
    message: str


# 依賴注入
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db_session)
):
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
        
        # 使用新的異步查詢
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶不存在"
            )
        
        return user
        
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        logger.error("JWT令牌已過期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已過期，請重新登入"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT令牌無效: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的令牌"
        )
    except Exception as e:
        logger.error(f"認證錯誤 - 類型: {type(e).__name__}, 詳情: {str(e)}")
        import traceback
        logger.error(f"錯誤堆疊: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"認證失敗: {str(e)}"
        )


@auth_router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_async_db_session)
):
    """用戶註冊"""
    try:
        # 檢查用戶是否已存在
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalars().first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="該電子郵件已被註冊"
            )
        
        # 創建新用戶
        user = User(
            email=user_data.email,
            username=user_data.username,
            password=user_data.password
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # 生成令牌
        access_token = AuthService.create_access_token(str(user.id))
        refresh_token = AuthService.create_refresh_token(str(user.id))
        
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
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_async_db_session)
):
    """用戶登入"""
    try:
        # 驗證用戶
        result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalars().first()
        
        if not user or not user.check_password(login_data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="電子郵件或密碼錯誤"
            )
        
        # 生成令牌
        access_token = AuthService.create_access_token(str(user.id))
        refresh_token = AuthService.create_refresh_token(str(user.id))
        
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


@auth_router.post("/apple", response_model=AuthResponse)
async def apple_login(
    apple_data: AppleLogin,
    db: AsyncSession = Depends(get_async_db_session)
):
    """Apple ID 登入"""
    try:
        # TODO: 這裡應該要驗證 Apple identity token
        # 在生產環境中，需要使用 Apple 的公鑰來驗證 JWT token
        # 這裡為了開發測試，暫時跳過驗證步驟
        
        # 檢查用戶是否已存在（使用 Apple User ID）
        result = await db.execute(
            select(User).where(
                or_(
                    User.apple_id == apple_data.user_id,
                    User.email == apple_data.email
                )
            )
        )
        user = result.scalars().first()
        
        if user:
            # 如果用戶已存在，更新 Apple ID（如果需要）
            if not user.apple_id:
                user.apple_id = apple_data.user_id
                await db.commit()
        else:
            # 創建新用戶
            # 生成一個唯一的用戶名
            base_username = apple_data.full_name.replace(" ", "_").lower()
            username = base_username
            counter = 1
            
            # 確保用戶名唯一
            while True:
                existing = await db.execute(
                    select(User).where(User.username == username)
                )
                if not existing.scalars().first():
                    break
                username = f"{base_username}_{counter}"
                counter += 1
            
            user = User(
                email=apple_data.email or f"{apple_data.user_id}@apple.local",
                username=username,
                apple_id=apple_data.user_id,
                full_name=apple_data.full_name,
                is_active=True
            )
            # Apple 用戶不需要密碼
            user.password_hash = None
            
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        # 生成令牌
        access_token = AuthService.create_access_token(str(user.id))
        refresh_token = AuthService.create_refresh_token(str(user.id))
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apple 登入錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Apple 登入失敗"
        )


@auth_router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_async_db_session)
):
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
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶不存在"
            )
        
        # 生成新令牌
        access_token = AuthService.create_access_token(str(user.id))
        refresh_token = AuthService.create_refresh_token(str(user.id))
        
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