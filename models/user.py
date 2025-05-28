# -*- coding: utf-8 -*-
"""
使用者資料庫模型定義。

此模組定義了 `User` SQLAlchemy 模型，用於表示應用程式中的使用者帳戶。
包含使用者基本資訊、密碼雜湊、帳戶狀態以及與其他模型 (如 `Recording`) 的關聯。
同時也提供了密碼設定和驗證的方法。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey # ForeignKey 未在此檔案直接使用，但保留以備未來模型擴展
from sqlalchemy.orm import relationship, Mapped, mapped_column # Mapped 和 mapped_column 用於 SQLAlchemy 2.0 風格的類型註解
from sqlalchemy.dialects.postgresql import UUID as PG_UUID # PostgreSQL 特有的 UUID 類型
from sqlalchemy.dialects.postgresql import JSON # PostgreSQL 特有的 JSON 類型
from passlib.context import CryptContext

from . import Base

# 初始化 passlib 的 CryptContext，用於密碼雜湊和驗證。
# 使用 bcrypt 作為主要的雜湊演算法。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    """
    使用者資料庫模型。

    代表應用程式中的一個使用者帳戶。

    Attributes:
        id (uuid.UUID): 使用者的唯一識別碼 (主鍵)，使用 UUID 格式。
        username (str): 使用者名稱，必須唯一且不可為空。
        email (str): 使用者電子郵件地址，必須唯一且不可為空。
        password_hash (str): 儲存使用者密碼的雜湊值，不可為空。
        is_active (bool): 指示使用者帳號是否啟用，預設為 True。
        profile_data (Optional[dict]): 儲存使用者額外設定檔資訊的 JSON 欄位，可為空。
        created_at (datetime): 記錄創建時間，自動設定為目前 UTC 時間。
        updated_at (datetime): 記錄最後更新時間，在記錄更新時自動更新為目前 UTC 時間。
        recordings (List["Recording"]): 與此使用者關聯的錄音記錄列表 (一對多關聯)。
                                         `lazy="selectin"` 表示在查詢使用者時，會透過 JOIN 預先載入關聯的錄音。
                                         `cascade="all, delete-orphan"` 表示當使用者被刪除時，其所有錄音也會被刪除。
    """
    __tablename__ = 'users' # 資料庫中的表名
    
    # --- 表格欄位定義 ---
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="使用者唯一識別碼 (UUID)")
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True, comment="使用者名稱，需唯一")
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True, comment="使用者電子郵件，需唯一")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="已雜湊的使用者密碼")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="帳號是否啟用")
    profile_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True, comment="使用者額外設定檔資料 (JSON)") # 允許 None，但資料庫預設為 {}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄創建時間 (UTC)")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄最後更新時間 (UTC)")
    
    # --- SQLAlchemy 關聯關係 ---
    # 'Recording' 是關聯模型的類別名稱 (字串形式以避免循環導入問題)
    # back_populates="user" 指向 Recording 模型中反向關聯的屬性名稱
    recordings: Mapped[List["Recording"]] = relationship(
        "Recording", 
        back_populates="user", 
        lazy="selectin", # 使用 selectin loading 策略以優化查詢
        cascade="all, delete-orphan" # 刪除使用者時，其所有錄音也一併刪除
    )
    
    def __init__(self, username: str, email: str, password: str, is_active: bool = True, profile_data: Optional[dict] = None, **kwargs):
        """
        使用者模型的建構函式。

        Args:
            username (str): 使用者名稱。
            email (str): 使用者電子郵件。
            password (str): 使用者提供的原始密碼 (將被雜湊處理)。
            is_active (bool, optional): 帳號是否啟用。預設為 True。
            profile_data (Optional[dict], optional): 使用者額外設定檔資料。預設為 None。
            **kwargs: 其他 SQLAlchemy 模型參數。
        """
        super().__init__(**kwargs) # 調用基類的建構函式
        self.username = username
        self.email = email.lower() # 電子郵件統一轉為小寫以方便比較和查詢
        self.set_password(password) # 設定並雜湊密碼
        self.is_active = is_active
        self.profile_data = profile_data if profile_data is not None else {} # 確保 profile_data 預設為空字典

    def set_password(self, password: str) -> None:
        """
        設定並雜湊使用者的密碼。

        使用 `pwd_context` (bcrypt) 將提供的原始密碼進行雜湊，
        並將結果儲存到 `password_hash` 屬性。

        Args:
            password (str): 使用者提供的原始密碼。
        """
        self.password_hash = pwd_context.hash(password)
        logger.debug(f"使用者 {self.username} 的密碼已設定並雜湊。")
        
    def check_password(self, password: str) -> bool:
        """
        驗證提供的密碼是否與儲存的密碼雜湊值相符。

        Args:
            password (str): 要驗證的原始密碼。

        Returns:
            bool: 如果密碼相符則返回 True，否則返回 False。
        """
        is_correct = pwd_context.verify(password, self.password_hash)
        if not is_correct:
            logger.debug(f"使用者 {self.username} 密碼驗證失敗。")
        return is_correct
        
    def to_dict(self) -> dict:
        """
        將使用者物件的資訊轉換為字典格式，以便於 API 回應。

        注意：此方法不應包含密碼雜湊等敏感資訊。

        Returns:
            dict: 包含使用者公開資訊的字典。
        """
        return {
            'id': str(self.id), # 將 UUID 轉換為字串
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'profile_data': self.profile_data if self.profile_data is not None else {}, # 確保返回字典
            'created_at': self.created_at.isoformat() if self.created_at else None, # 使用 ISO 格式
            'updated_at': self.updated_at.isoformat() if self.updated_at else None  # 使用 ISO 格式
        }
    
    def __repr__(self) -> str:
        """
        返回使用者物件的字串表示，主要用於除錯和日誌記錄。
        """
        return f"<User(id={str(self.id)}, username='{self.username}', email='{self.email}')>"