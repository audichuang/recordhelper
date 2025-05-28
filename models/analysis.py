# -*- coding: utf-8 -*-
"""
錄音分析結果的資料庫模型 (`AnalysisResult`) 定義。

此模組定義了 `AnalysisResult` SQLAlchemy 模型，用於儲存與特定錄音相關的
語音轉文字結果、AI 生成摘要以及其他分析元數據。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, ForeignKey, DateTime # SQLAlchemy 組件
from sqlalchemy.orm import relationship, Mapped, mapped_column # SQLAlchemy 2.0 風格組件
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON # PostgreSQL 特定類型

from . import Base # 從同目錄的 __init__.py 導入 Base 基類
from typing import Optional, Dict, Any # 用於類型註解

class AnalysisResult(Base):
    """
    錄音分析結果資料庫模型。

    代表資料庫中的 `analysis_results` 表格，儲存單一錄音的分析數據。
    每個分析結果都與一個 `Recording` 物件相關聯。

    Attributes:
        id (uuid.UUID): 分析結果的唯一識別碼 (主鍵)。
        recording_id (uuid.UUID): 相關錄音的 ID (外鍵，唯一，關聯至 `recordings` 表)。
        transcription (Optional[str]): 語音轉文字產生的完整文字稿。
        summary (Optional[str]): AI 模型生成的摘要內容。
        confidence_score (Optional[float]): 語音轉文字的整體信心度分數 (範圍通常為 0.0 到 1.0)。
        language (Optional[str]): 偵測到的主要語言代碼 (例如 'zh', 'en')。
        processing_time_seconds (Optional[float]): 完成此分析所花費的時間 (秒)。
        provider (Optional[str]): 提供分析服務的來源 (例如 'openai', 'google_gemini', 'local_whisper')。
        model_used (Optional[str]): 用於分析的具體模型名稱 (例如 'whisper-1', 'gemini-pro')。
        analysis_metadata (Optional[Dict[str, Any]]): 儲存其他與分析相關的元數據 (JSON 格式)，
                                                     例如分段時間戳、關鍵字、情緒分析結果等。
        created_at (datetime): 記錄創建時間 (UTC)。
        updated_at (datetime): 記錄最後更新時間 (UTC)。
        recording (Recording): 與此分析結果關聯的 `Recording` 物件 (SQLAlchemy 關聯)。
    """
    __tablename__ = 'analysis_results' # 資料庫中的表名

    # --- 表格欄位定義 ---
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="分析結果唯一識別碼 (UUID)")
    recording_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('recordings.id'), nullable=False, unique=True, index=True, comment="對應的錄音 ID (外鍵，唯一)")
    
    transcription: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="語音轉文字的完整文字稿") # 改為可為空，初始可能沒有
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="AI 生成的摘要") # 改為可為空
    
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="語音轉文字的整體信心度 (0.0-1.0)")
    language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="偵測到的主要語言 (例如 'zh-TW', 'en-US')") # 允許更長的語言代碼
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="分析處理時長 (秒)") # 欄位名更清晰
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="分析服務提供者 (例如 'OpenAI Whisper', 'Google Gemini')")
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="用於分析的具體模型名稱") # 新增欄位
    
    analysis_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True, comment="其他分析元數據 (JSON)")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄創建時間 (UTC)")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, comment="記錄最後更新時間 (UTC)")
    
    # --- SQLAlchemy 關聯關係 ---
    # `lazy="selectin"` 表示在查詢 AnalysisResult 時，會透過 JOIN 預先載入關聯的 Recording
    recording: Mapped["Recording"] = relationship("Recording", back_populates="analysis_result", lazy="selectin")

    def __init__(self, recording_id: uuid.UUID, transcription: Optional[str] = None, summary: Optional[str] = None, 
                 provider: Optional[str] = None, model_used: Optional[str] = None,
                 confidence_score: Optional[float] = None, language: Optional[str] = None, 
                 processing_time_seconds: Optional[float] = None, 
                 analysis_metadata: Optional[Dict[str, Any]] = None, **kwargs: Any):
        """
        AnalysisResult 模型的建構函式。

        Args:
            recording_id (uuid.UUID): 相關錄音的 ID。
            transcription (Optional[str], optional): 文字稿。預設為 None。
            summary (Optional[str], optional): AI 摘要。預設為 None。
            provider (Optional[str], optional): 分析服務提供者。預設為 None。
            model_used (Optional[str], optional): 使用的模型名稱。預設為 None。
            confidence_score (Optional[float], optional): 信心度分數。預設為 None。
            language (Optional[str], optional): 語言代碼。預設為 None。
            processing_time_seconds (Optional[float], optional): 處理時長 (秒)。預設為 None。
            analysis_metadata (Optional[Dict[str, Any]], optional): 其他元數據。預設為 None (內部會轉為 {} )。
            **kwargs: 其他 SQLAlchemy 模型參數。
        """
        super().__init__(**kwargs) # 調用基類的建構函式
        self.recording_id = recording_id
        self.transcription = transcription
        self.summary = summary
        self.provider = provider
        self.model_used = model_used
        self.confidence_score = confidence_score
        self.language = language
        self.processing_time_seconds = processing_time_seconds
        self.analysis_metadata = analysis_metadata if analysis_metadata is not None else {} # 確保預設為空字典
        
    def get_word_count(self) -> int:
        """
        計算文字稿中的字數 (以空格分隔的簡單計數)。

        Returns:
            int: 文字稿中的字數。如果文字稿為 None 或空，則返回 0。
        """
        if not self.transcription:
            return 0
        return len(self.transcription.split()) # 簡單以空格計數
        
    def get_summary_paragraph_count(self) -> int:
        """
        計算摘要中的段落數量 (以換行符 `\\n` 分隔)。

        Returns:
            int: 摘要中的段落數量。如果摘要為 None 或空，則返回 0。
        """
        if not self.summary:
            return 0
        return len(self.summary.split('\n'))
        
    def get_confidence_percentage_display(self) -> Optional[str]:
        """
        獲取格式化為百分比字串的信心度。

        Returns:
            Optional[str]: 例如 "95.5%"。如果信心度未設定，則返回 None。
        """
        if self.confidence_score is None:
            return None
        return f"{self.confidence_score * 100:.1f}%" # 格式化到小數點後一位
        
    def update_analysis_content(self, transcription: Optional[str] = None, summary: Optional[str] = None, 
                                confidence_score: Optional[float] = None, language: Optional[str] = None,
                                processing_time_seconds: Optional[float] = None,
                                provider: Optional[str] = None, model_used: Optional[str] = None,
                                analysis_metadata_update: Optional[Dict[str, Any]] = None) -> None:
        """
        更新分析結果的內容。

        允許部分更新，僅更新提供的參數值。
        `updated_at` 欄位會自動更新 (如果 ORM 設定了 onupdate)。

        Args:
            transcription (Optional[str], optional): 新的文字稿。
            summary (Optional[str], optional): 新的摘要。
            confidence_score (Optional[float], optional): 新的信心度分數。
            language (Optional[str], optional): 新的語言代碼。
            processing_time_seconds (Optional[float], optional): 新的處理時長。
            provider (Optional[str], optional): 新的服務提供者。
            model_used (Optional[str], optional): 新的模型名稱。
            analysis_metadata_update (Optional[Dict[str, Any]], optional): 要更新或添加到現有元數據中的鍵值對。
                                                                        注意：這是更新，不是替換。
        """
        if transcription is not None:
            self.transcription = transcription
        if summary is not None:
            self.summary = summary
        if confidence_score is not None:
            self.confidence_score = confidence_score
        if language is not None:
            self.language = language
        if processing_time_seconds is not None:
            self.processing_time_seconds = processing_time_seconds
        if provider is not None:
            self.provider = provider
        if model_used is not None:
            self.model_used = model_used
            
        if analysis_metadata_update: # 如果提供了要更新的元數據
            if self.analysis_metadata is None: # 如果現有元數據是 None，先初始化為空字典
                self.analysis_metadata = {}
            self.analysis_metadata.update(analysis_metadata_update) # 更新字典
            
        # self.updated_at = datetime.now(timezone.utc) # SQLAlchemy 的 onupdate 通常會自動處理此欄位
        # 但如果 onupdate 未如預期觸發，或需要在應用層面更精確控制，可以取消註解此行
        
    def to_dict(self) -> Dict[str, Any]:
        """
        將分析結果物件的資訊轉換為字典格式，以便於 API 回應。

        Returns:
            dict: 包含分析結果詳細資訊的字典。
        """
        return {
            'id': str(self.id), # 將 UUID 轉換為字串
            'recording_id': str(self.recording_id) if self.recording_id else None,
            'transcription': self.transcription,
            'summary': self.summary,
            'confidence_score': self.confidence_score,
            'confidence_percentage_display': self.get_confidence_percentage_display(), # 格式化後的信心度
            'language': self.language,
            'processing_time_seconds': self.processing_time_seconds,
            'provider': self.provider,
            'model_used': self.model_used,
            'word_count': self.get_word_count(), # 計算得到的字數
            'summary_paragraph_count': self.get_summary_paragraph_count(), # 計算得到的摘要段落數
            'analysis_metadata': self.analysis_metadata if self.analysis_metadata is not None else {}, # 確保返回字典
            'created_at': self.created_at.isoformat() if self.created_at else None, # 使用 ISO 格式
            'updated_at': self.updated_at.isoformat() if self.updated_at else None  # 使用 ISO 格式
        }
    
    def __repr__(self) -> str:
        """
        返回分析結果物件的字串表示，主要用於除錯和日誌記錄。
        """
        return f"<AnalysisResult(id={str(self.id)}, recording_id='{str(self.recording_id)}', provider='{self.provider}')>"