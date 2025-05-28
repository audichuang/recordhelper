# -*- coding: utf-8 -*-
"""
使用者認證相關 API 路由定義。

此模組包含使用者註冊、登入、登出、權杖刷新以及獲取目前使用者資訊等 API 端點。
它使用了 FastAPI 的 APIRouter 來組織路由，並依賴 Pydantic 進行資料驗證，
以及 SQLAlchemy 與資料庫互動。
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr # EmailStr 用於電子郵件格式驗證
from typing import Optional, Dict # Dict 用於 AuthResponse 中的 user 欄位
import logging
import uuid
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

# HTTP Bearer token 驗證機制實例
security = HTTPBearer()

# --- Pydantic 請求與回應模型 ---

class UserRegister(BaseModel):
    """使用者註冊請求模型"""
    email: EmailStr # 使用者電子郵件，使用 EmailStr 進行格式驗證
    password: str   # 使用者密碼
    username: str   # 使用者名稱

class UserLogin(BaseModel):
    """使用者登入請求模型"""
    email: EmailStr # 使用者電子郵件
    password: str   # 使用者密碼

class TokenRefresh(BaseModel):
    """權杖刷新請求模型"""
    refresh_token: str # 用於獲取新 Access Token 的 Refresh Token

class AuthResponse(BaseModel):
    """認證成功後的回應模型"""
    access_token: str  # JWT Access Token
    refresh_token: str # JWT Refresh Token
    token_type: str = "bearer" # 權杖類型，固定為 "bearer"
    user: Dict # 使用者資訊字典 (通常包含 id, email, username 等)

class MessageResponse(BaseModel):
    """通用訊息回應模型"""
    message: str # 回應訊息內容

# --- 依賴注入函數 ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), # 從請求標頭 Authorization: Bearer <token> 提取權杖
    db: AsyncSession = Depends(get_async_db_session) # 異步資料庫會話依賴
) -> User:
    """
    依賴注入函數，用於驗證 JWT 並獲取目前登入的使用者。

    此函數會被保護路由用作依賴項，以確保請求者已通過認證。
    它會解析 Authorization 標頭中的 Bearer Token，驗證其有效性，
    並從資料庫中查詢對應的使用者資訊。

    Args:
        credentials (HTTPAuthorizationCredentials): FastAPI 自動從請求標頭中提取的認證憑證。
        db (AsyncSession): 資料庫會話依賴。

    Raises:
        HTTPException: 如果權杖無效、使用者不存在或發生其他認證錯誤，則拋出 HTTP 401 未授權錯誤。

    Returns:
        User: 驗證成功後，返回對應的 User SQLAlchemy 模型實例。
    """
    try:
        token = credentials.credentials # 提取 JWT 字串
        payload = AuthService.decode_token(token) # 解碼 JWT，AuthService 應包含解碼邏輯和金鑰
        user_id_str = payload.get('user_id') # 從 payload 中獲取 user_id
        
        if not user_id_str:
            logger.warning("無效的 JWT：payload 中缺少 user_id。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的權杖或權杖格式錯誤" # 更具體的錯誤訊息
            )
        
        try:
            user_uuid = uuid.UUID(user_id_str) # 將 user_id 字串轉換為 UUID 物件
        except ValueError:
            logger.warning(f"無效的 JWT：user_id '{user_id_str}' 不是有效的 UUID 格式。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="權杖中的使用者 ID 格式無效"
            )

        # 從資料庫中異步查詢使用者
        result = await db.execute(
            select(User).where(User.id == user_uuid)
        )
        user = result.scalar_one_or_none() # 使用 scalar_one_or_none 以期盼單一結果或無結果
        
        if not user:
            logger.warning(f"無效的 JWT：找不到 user_id 為 {user_uuid} 的使用者。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="權杖對應的使用者不存在" # 使用者可能已被刪除
            )
        
        logger.debug(f"使用者 {user.email} (ID: {user.id}) 成功通過 JWT 認證。")
        return user # 返回 User 模型實例
        
    except HTTPException as http_exc: # 如果是已知的 HTTP 例外，直接重新拋出
        raise http_exc
    except Exception as e: # 捕獲其他可能的例外 (例如 JWT 解碼錯誤)
        logger.error(f"JWT 認證過程中發生未預期錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無法驗證您的身份，請重新登入" # 通用的認證失敗訊息
        )

# --- API 端點 ---

@auth_router.post("/register", response_model=AuthResponse, summary="使用者註冊", description="建立新的使用者帳號並返回認證權杖。")
async def register(
    user_data: UserRegister, # 請求主體，包含 email, password, username
    db: AsyncSession = Depends(get_async_db_session) # 資料庫會話依賴
):
    """
    處理新使用者註冊請求。

    Args:
        user_data (UserRegister): 包含使用者註冊資訊 (電子郵件、密碼、使用者名稱) 的請求主體。
        db (AsyncSession): 資料庫會話依賴。

    Raises:
        HTTPException: 如果電子郵件已被註冊 (400)，或發生其他伺服器錯誤 (500)。

    Returns:
        AuthResponse: 包含 access_token, refresh_token 及使用者基本資訊的回應。
    """
    logger.info(f"收到使用者註冊請求：電子郵件 {user_data.email}, 使用者名稱 {user_data.username}")
    try:
        # 檢查電子郵件是否已存在
        stmt_email_exists = select(User).where(User.email == user_data.email)
        result_email = await db.execute(stmt_email_exists)
        existing_user_by_email = result_email.scalar_one_or_none()
        
        if existing_user_by_email:
            logger.warning(f"註冊失敗：電子郵件 {user_data.email} 已被註冊。")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此電子郵件地址已被註冊，請嘗試使用其他地址。"
            )
        
        # 創建新使用者實例 (密碼應在 User 模型內部或 AuthService 中進行雜湊處理)
        new_user = User(
            email=user_data.email,
            username=user_data.username
        )
        new_user.set_password(user_data.password) # 假設 User 模型有 set_password 方法來處理密碼雜湊
        
        db.add(new_user) # 將新使用者加入資料庫會話
        await db.commit() # 提交事務以儲存使用者
        await db.refresh(new_user) # 刷新 new_user 實例以獲取例如自動產生的 ID 等資訊
        
        logger.info(f"使用者 {new_user.username} (ID: {new_user.id}) 註冊成功。")
        
        # 生成 JWT Access Token 和 Refresh Token
        access_token = AuthService.create_access_token(user_id=str(new_user.id))
        refresh_token = AuthService.create_refresh_token(user_id=str(new_user.id))
        
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=new_user.to_dict() # 假設 User 模型有 to_dict 方法返回安全的用戶資訊字典
        )
        
    except HTTPException as http_exc: # 重新拋出已知的 HTTP 例外
        raise http_exc
    except Exception as e: # 捕獲其他未預期錯誤
        logger.error(f"使用者註冊過程中發生錯誤 (使用者: {user_data.email}): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="註冊過程中發生內部錯誤，請稍後再試。"
        )


@auth_router.post("/login", response_model=AuthResponse, summary="使用者登入", description="使用電子郵件和密碼進行驗證並返回認證權杖。")
async def login(
    login_data: UserLogin, # 請求主體，包含 email 和 password
    db: AsyncSession = Depends(get_async_db_session) # 資料庫會話依賴
):
    """
    處理使用者登入請求。

    Args:
        login_data (UserLogin): 包含使用者登入憑證 (電子郵件、密碼) 的請求主體。
        db (AsyncSession): 資料庫會話依賴。

    Raises:
        HTTPException: 如果憑證無效 (401)，或發生其他伺服器錯誤 (500)。

    Returns:
        AuthResponse: 包含 access_token, refresh_token 及使用者基本資訊的回應。
    """
    logger.info(f"收到使用者登入請求：電子郵件 {login_data.email}")
    try:
        # 從資料庫查詢使用者
        stmt_get_user = select(User).where(User.email == login_data.email)
        result_user = await db.execute(stmt_get_user)
        user = result_user.scalar_one_or_none()
        
        # 驗證使用者是否存在以及密碼是否正確
        # User.check_password 方法應處理已雜湊密碼的比較
        if not user or not user.check_password(login_data.password):
            logger.warning(f"登入失敗：電子郵件 {login_data.email} 的憑證無效。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="電子郵件或密碼不正確，請檢查後重試。"
            )
        
        if not user.is_active:
            logger.warning(f"登入失敗：使用者 {login_data.email} 的帳號已被停用。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, # 403 Forbidden 可能比 401 更適合表示帳號已停用
                detail="您的帳號已被停用，請聯繫管理員。"
            )

        # 生成 JWT Access Token 和 Refresh Token
        access_token = AuthService.create_access_token(user_id=str(user.id))
        refresh_token = AuthService.create_refresh_token(user_id=str(user.id))
        
        logger.info(f"使用者 {user.email} (ID: {user.id}) 登入成功。")
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user.to_dict() # 返回使用者資訊
        )
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"使用者登入過程中發生錯誤 (使用者: {login_data.email}): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登入過程中發生內部錯誤，請稍後再試。"
        )


@auth_router.post("/refresh", response_model=AuthResponse, summary="刷新 Access Token", description="使用有效的 Refresh Token 獲取新的 Access Token 和 Refresh Token。")
async def refresh_token(
    token_data: TokenRefresh, # 請求主體，包含 refresh_token
    db: AsyncSession = Depends(get_async_db_session) # 資料庫會話依賴
):
    """
    使用 Refresh Token 刷新 Access Token。

    Args:
        token_data (TokenRefresh): 包含 refresh_token 的請求主體。
        db (AsyncSession): 資料庫會話依賴。

    Raises:
        HTTPException: 如果 refresh_token 無效或使用者不存在 (401)，或發生其他伺服器錯誤 (500)。

    Returns:
        AuthResponse: 包含新的 access_token, refresh_token 及使用者基本資訊的回應。
    """
    logger.info(f"收到權杖刷新請求。")
    try:
        # 驗證 Refresh Token 並從中提取使用者 ID
        payload = AuthService.decode_refresh_token(token_data.refresh_token) # AuthService 應處理 Refresh Token 的解碼
        user_id_str = payload.get('user_id')
        
        if not user_id_str:
            logger.warning("刷新權杖失敗：Refresh Token 中缺少 user_id。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的刷新權杖。"
            )
        
        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            logger.warning(f"刷新權杖失敗：Refresh Token 中的 user_id '{user_id_str}' 格式無效。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新權杖中的使用者 ID 格式無效。"
            )

        # 從資料庫獲取使用者資訊
        result = await db.execute(
            select(User).where(User.id == user_uuid)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"刷新權杖失敗：找不到 user_id 為 {user_uuid} 的使用者。")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="與刷新權杖關聯的使用者不存在。"
            )

        if not user.is_active:
            logger.warning(f"刷新權杖失敗：使用者 {user.email} (ID: {user.id}) 的帳號已被停用。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的帳號已被停用，無法刷新權杖。"
            )

        # 生成新的 Access Token 和 Refresh Token
        new_access_token = AuthService.create_access_token(user_id=str(user.id))
        new_refresh_token = AuthService.create_refresh_token(user_id=str(user.id)) # 通常也會刷新 Refresh Token
        
        logger.info(f"使用者 {user.email} (ID: {user.id}) 的權杖刷新成功。")
        return AuthResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            user=user.to_dict()
        )
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e: # 例如 JWTDecodeError
        logger.error(f"刷新權杖過程中發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, # 通常因權杖無效導致
            detail="刷新權杖失敗，可能是權杖已過期或無效。"
        )


@auth_router.post("/logout", response_model=MessageResponse, summary="使用者登出", description="（可選）使目前 Access Token 失效或執行其他登出操作。")
async def logout(current_user: User = Depends(get_current_user)): # 依賴 get_current_user 以確保只有已登入使用者可以登出
    """
    處理使用者登出請求。

    目前的實作僅返回成功訊息。在更複雜的系統中，
    此處可能需要實現權杖黑名單機制，以使當前的 Access Token 失效。

    Args:
        current_user (User): 由 `get_current_user` 依賴注入的目前使用者物件。

    Returns:
        MessageResponse: 確認登出成功的訊息。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求登出。")
    try:
        # 實際的登出邏輯（例如將 Token 加入黑名單）可以在 AuthService 中實現
        # AuthService.add_token_to_blacklist(access_token_from_header) # 假設可以獲取原始 token
        
        # 目前為簡單實現，僅返回成功訊息
        return MessageResponse(message="您已成功登出。")
        
    except Exception as e:
        logger.error(f"使用者登出過程中發生錯誤 (使用者: {current_user.email}): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出過程中發生內部錯誤，請稍後再試。"
        )


@auth_router.get("/me", response_model=Dict, summary="獲取目前使用者資訊", description="返回目前已認證使用者的詳細資訊。")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    獲取並返回目前已通過認證的使用者的資訊。

    Args:
        current_user (User): 由 `get_current_user` 依賴注入的目前使用者物件。

    Returns:
        Dict: 包含使用者資訊的字典 (通常透過 User 模型的 to_dict 方法轉換)。
    """
    logger.info(f"請求獲取目前使用者資訊，使用者: {current_user.email} (ID: {current_user.id})")
    # User 模型中的 to_dict() 方法應確保不返回敏感資訊，如密碼雜湊值
    return current_user.to_dict()