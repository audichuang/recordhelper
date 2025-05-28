# -*- coding: utf-8 -*-
"""
錄音資料庫模型 (`Recording`) 及其相關狀態列舉 (`RecordingStatus`) 定義。

此模組定義了：
- `RecordingStatus`: 一個 Python `Enum`，用於表示錄音檔案的處理狀態。
- `Recording`: SQLAlchemy 模型，代表資料庫中的一筆錄音記錄，包含音訊檔案本身的資訊、
               元數據、處理狀態，以及與使用者 (`User`) 和分析結果 (`AnalysisResult`) 的關聯。
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum # Python 原生的 Enum
from sqlalchemy import Column, String, BigInteger, Float, ForeignKey, Enum as SQLEnum, DateTime, LargeBinary # SQLAlchemy 組件
from sqlalchemy.orm import relationship, Mapped, mapped_column # SQLAlchemy 2.0 風格組件
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON # PostgreSQL 特定類型

from . import Base # 從同目錄的 __init__.py 導入 Base 基類
from typing import Optional, List, Dict, Any # 用於類型註解

class RecordingStatus(PyEnum):
    """
    錄音處理狀態列舉。

    用於表示錄音檔案在處理流程中所處的各個階段。
    """
    UPLOADING = "uploading"     # 上傳中：檔案正在從客戶端上傳到伺服器。
    PROCESSING = "processing"   # 處理中：檔案已上傳完成，正在進行語音轉文字、AI摘要等後續處理。
    COMPLETED = "completed"     # 已完成：所有處理步驟均已成功完成。
    FAILED = "failed"           # 處理失敗：在處理過程中的任何步驟發生錯誤。
    PENDING_REPROCESSING = "pending_reprocessing" # 等待重新處理：使用者已請求重新處理，但尚未開始。

class Recording(Base):
    """
    錄音資料庫模型。

    代表資料庫中的 `recordings` 表格，儲存每一筆錄音的詳細資訊。

    Attributes:
        id (uuid.UUID): 錄音的唯一識別碼 (主鍵)。
        user_id (uuid.UUID): 擁有此錄音的使用者的 ID (外鍵，關聯至 `users` 表)。
        title (str): 錄音的標題。
        original_filename (str): 上傳時的原始檔案名稱。
        audio_data (bytes): 錄音的原始音訊二進制數據，直接儲存在資料庫中。
        file_size (int): 錄音檔案的大小 (單位：bytes)。
        duration (Optional[float]): 錄音的時長 (單位：秒)。在語音轉文字處理後填入。
        format (str): 錄音檔案的格式 (例如 'mp3', 'wav')。
        mime_type (str): 錄音檔案的 MIME 類型 (例如 'audio/mpeg', 'audio/wav')。
        status (RecordingStatus): 錄音目前的處理狀態，使用 `RecordingStatus` 列舉。
        error_message (Optional[str]): 如果處理失敗，儲存相關的錯誤訊息。
        recording_metadata (Optional[dict]): 儲存與錄音本身相關的額外元數據 (JSON 格式)，例如錄製設備資訊。
        created_at (datetime): 記錄創建時間 (UTC)。
        updated_at (datetime): 記錄最後更新時間 (UTC)。
        user (User): 與此錄音關聯的 `User` 物件 (SQLAlchemy 關聯)。
        analysis_result (Optional["AnalysisResult"]): 與此錄音關聯的 `AnalysisResult` 物件 (SQLAlchemy 關聯，一對一)。
    """
    __tablename__ = 'recordings' # 資料庫中的表名
    
    # --- 表格欄位定義 ---
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="錄音唯一識別碼 (UUID)")
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True, comment="所屬使用者的 ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="錄音標題")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始檔案名稱")
    audio_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, comment="音訊的二進制數據") # 儲存實際音訊內容
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="檔案大小 (bytes)")
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="音訊時長 (秒)")
    format: Mapped[str] = mapped_column(String(20), nullable=False, comment="音訊格式 (例如 'mp3', 'wav')") # 欄位名從 format_str 改為 format
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="音訊的 MIME 類型")
    status: Mapped[RecordingStatus] = mapped_column(SQLEnum(RecordingStatus, name="recording_status_type", native_enum=False, length=50), default=RecordingStatus.UPLOADING, nullable=False, comment="錄音處理狀態")
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="處理失敗時的錯誤訊息") # 新增錯誤訊息欄位
    recording_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True, comment="錄音相關的元數據 (JSON)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄創建時間 (UTC)")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄最後更新時間 (UTC)")
    
    # --- SQLAlchemy 關聯關係 ---
    user: Mapped["User"] = relationship("User", back_populates="recordings", lazy="selectin")
    # `uselist=False` 表示這是一個一對一的關聯 (一個錄音對應一個分析結果)
    analysis_result: Mapped[Optional["AnalysisResult"]] = relationship(
        "AnalysisResult", 
        back_populates="recording", 
        uselist=False, 
        cascade="all, delete-orphan", # 刪除錄音時，其分析結果也一併刪除
        lazy="selectin" # 查詢錄音時，預先載入分析結果
    )
    
    def __init__(self, user_id: uuid.UUID, title: str, original_filename: str, audio_data: bytes, file_size: int, format: str, mime_type: str, status: RecordingStatus = RecordingStatus.UPLOADING, **kwargs: Any):
        """
        Recording 模型的建構函式。

        Args:
            user_id (uuid.UUID): 所屬使用者的 ID。
            title (str): 錄音標題。
            original_filename (str): 原始檔案名稱。
            audio_data (bytes): 音訊的二進制數據。
            file_size (int): 檔案大小 (bytes)。
            format (str): 音訊格式 (例如 'mp3', 'wav')。參數名從 format_str 改為 format。
            mime_type (str): 音訊的 MIME 類型。
            status (RecordingStatus, optional): 初始狀態。預設為 UPLOADING。
            **kwargs: 其他 SQLAlchemy 模型參數。
        """
        super().__init__(**kwargs) # 調用基類的建構函式
        self.user_id = user_id
        self.title = title
        self.original_filename = original_filename
        self.audio_data = audio_data
        self.file_size = file_size
        self.format = format.lower() # 確保格式字串為小寫
        self.mime_type = mime_type
        self.status = status
        self.recording_metadata = {} # 初始化為空字典
        
    def update_status(self, status: RecordingStatus, error_msg: Optional[str] = None) -> None:
        """
        更新錄音的處理狀態。

        Args:
            status (RecordingStatus): 新的處理狀態。
            error_msg (Optional[str], optional): 如果狀態為 FAILED，可以提供錯誤訊息。預設為 None。
        """
        self.status = status
        if status == RecordingStatus.FAILED and error_msg:
            self.error_message = error_msg
        elif status == RecordingStatus.COMPLETED:
            self.error_message = None # 處理完成時清除錯誤訊息
        self.updated_at = datetime.now(timezone.utc) # 手動更新 updated_at，因 onupdate 可能不總是被觸發
        logger.info(f"錄音 ID {self.id} 狀態更新為: {status.value}" + (f"，錯誤訊息: {error_msg}" if error_msg else ""))
        
    def set_duration(self, duration_seconds: float) -> None:
        """
        設定錄音的時長。

        Args:
            duration_seconds (float): 音訊時長 (單位：秒)。
        """
        self.duration = duration_seconds
        logger.debug(f"錄音 ID {self.id} 時長設定為: {duration_seconds:.2f} 秒。")
        
    def get_formatted_duration(self) -> str:
        """
        獲取格式化為 "MM:SS" 或 "HH:MM:SS" 的音訊時長字串。

        Returns:
            str: 格式化的時長字串。如果時長未設定，則返回 "未知"。
        """
        if self.duration is None:
            return "未知"
        
        total_seconds = int(self.duration)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
        
    def get_file_size_display(self) -> str:
        """
        獲取易於閱讀的檔案大小字串 (例如 KB, MB)。

        Returns:
            str: 格式化的檔案大小字串。
        """
        if self.file_size < 1024:
            return f"{self.file_size} Bytes"
        elif self.file_size < 1024**2:
            return f"{self.file_size / 1024:.2f} KB"
        elif self.file_size < 1024**3:
            return f"{self.file_size / (1024**2):.2f} MB"
        else:
            return f"{self.file_size / (1024**3):.2f} GB"
            
    def has_analysis(self) -> bool:
        """
        檢查此錄音是否已有相關聯的分析結果。

        Returns:
            bool: 如果存在分析結果則返回 True，否則返回 False。
        """
        return self.analysis_result is not None
        
    def to_dict(self, include_analysis: bool = False) -> Dict[str, Any]:
        """
        將錄音物件的資訊轉換為字典格式，以便於 API 回應。

        Args:
            include_analysis (bool, optional): 是否在結果中包含關聯的分析結果。預設為 False。

        Returns:
            dict: 包含錄音資訊的字典。不包含 `audio_data`。
        """
        data = {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'title': self.title,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_display': self.get_file_size_display(), # 使用易讀的檔案大小
            'duration_seconds': self.duration, # 保留原始秒數
            'duration_formatted': self.get_formatted_duration(), # 格式化後的時長
            'format': self.format,
            'mime_type': self.mime_type,
            'status': self.status.value if self.status else None, # 使用列舉的值
            'error_message': self.error_message, # 新增錯誤訊息欄位
            'recording_metadata': self.recording_metadata if self.recording_metadata is not None else {},
            'has_analysis': self.has_analysis(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # 不在此處包含 audio_data，因為它可能非常大。下載應透過專用端點。
        
        if include_analysis and self.analysis_result:
            data['analysis'] = self.analysis_result.to_dict() # 假設 AnalysisResult 也有 to_dict 方法
            
        return data
    
    def __repr__(self) -> str:
        """
        返回錄音物件的字串表示，主要用於除錯和日誌記錄。
        """
        return f"<Recording(id={str(self.id)}, title='{self.title}', status='{self.status.value}')>"