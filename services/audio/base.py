# -*- coding: utf-8 -*-
"""
音訊服務基礎模組。

此模組提供音訊處理相關的基礎工具和類別，例如：
- `TempFileManager`: 用於管理臨時檔案的創建和清理。
- `AudioService`: 包含音訊處理相關的靜態方法，如 FFmpeg 檢查和音訊轉換。
- `AudioProcessingError`: (雖然在此檔案未直接定義，但從 `models.base` 導入) 
                          是音訊處理過程中可能發生的自訂例外基類。
"""
import os
import subprocess # 用於執行外部命令，例如 FFmpeg
import tempfile # tempfile 未在此檔案直接使用，但其概念與 TempFileManager 相關
import uuid # 用於生成唯一的臨時檔案名稱
import logging
from typing import List, Tuple # Tuple 用於可能的返回類型

# 假設 AudioProcessingError 定義在 models.base 或其他可導入的路徑
# from models.base import AudioProcessingError 
# 如果 AudioProcessingError 不是自訂的，而是標準例外，則不需要此導入

logger = logging.getLogger(__name__)

class TempFileManager:
    """
    臨時檔案管理器類別。

    提供創建和清理臨時檔案的功能，主要用於音訊處理過程中需要暫存檔案的場景。
    所有創建的檔案路徑都會被追蹤，並可在處理完成後透過 `cleanup` 方法統一刪除。
    """
    def __init__(self, temp_dir: Optional[str] = None):
        """
        初始化臨時檔案管理器。

        Args:
            temp_dir (Optional[str], optional): 指定的臨時檔案目錄。
                                                如果為 None，則使用系統預設的臨時目錄。
                                                預設為 None。
        """
        # 如果未指定臨時目錄，則使用系統的臨時目錄
        self.temp_dir: str = temp_dir or tempfile.gettempdir()
        self.created_files: List[str] = [] # 用於追蹤由此實例創建的臨時檔案
        
        # 確保指定的臨時目錄存在
        if not os.path.exists(self.temp_dir):
            try:
                os.makedirs(self.temp_dir)
                logger.info(f"臨時檔案目錄已創建: {self.temp_dir}")
            except OSError as e:
                logger.error(f"創建臨時檔案目錄 {self.temp_dir} 失敗: {e}", exc_info=True)
                # 如果無法創建指定的臨時目錄，退回使用系統預設臨時目錄
                self.temp_dir = tempfile.gettempdir()
                logger.warning(f"臨時檔案目錄改用系統預設: {self.temp_dir}")
        logger.debug(f"TempFileManager 初始化完成，臨時目錄設定為: {self.temp_dir}")

    def create_temp_file(self, prefix: str = "audio_temp_", suffix: str = ".tmp") -> str:
        """
        在指定的臨時目錄中創建一個唯一的臨時檔案名稱。

        注意：此方法僅生成檔案路徑，並未實際創建檔案。檔案的創建由呼叫者負責。

        Args:
            prefix (str, optional): 臨時檔案名稱的前綴。預設為 "audio_temp_"。
            suffix (str, optional): 臨時檔案名稱的後綴 (擴展名)。預設為 ".tmp"。

        Returns:
            str: 生成的完整臨時檔案路徑。
        """
        # 生成一個基於 UUID 的唯一檔案名稱
        unique_filename = f"{prefix}{uuid.uuid4()}{suffix}"
        temp_file_path = os.path.join(self.temp_dir, unique_filename)
        self.created_files.append(temp_file_path) # 記錄此檔案路徑以便後續清理
        logger.debug(f"已生成臨時檔案路徑: {temp_file_path}")
        return temp_file_path

    def cleanup(self) -> None:
        """
        清理 (刪除) 所有由此管理器實例創建的臨時檔案。

        此方法會迭代 `created_files` 列表，並嘗試刪除每個存在的檔案。
        如果在刪除過程中發生錯誤，會記錄警告但不會中斷清理過程。
        清理完成後，會清空 `created_files` 列表。
        """
        logger.info(f"開始清理 {len(self.created_files)} 個臨時檔案...")
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"已成功刪除臨時檔案: {file_path}")
                else:
                    logger.debug(f"臨時檔案不存在，無需刪除: {file_path}")
            except OSError as e: # 更具體地捕獲作業系統相關的錯誤
                logger.warning(f"清理臨時檔案 {file_path} 失敗: {e}", exc_info=True)
            except Exception as e_general: # 捕獲其他可能的未知錯誤
                logger.error(f"清理臨時檔案 {file_path} 時發生未預期錯誤: {e_general}", exc_info=True)
        
        num_cleaned = len(self.created_files)
        self.created_files.clear() # 清理完成後清空列表
        logger.info(f"臨時檔案清理完成。共處理 {num_cleaned} 個檔案路徑。")

    def __enter__(self):
        """支援內容管理協議 (with statement)，返回自身實例。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支援內容管理協議，在退出 with 區塊時自動執行清理。"""
        self.cleanup()


class AudioServiceError(Exception):
    """音訊服務相關操作的自訂例外基類。"""
    pass

class FFmpegError(AudioServiceError):
    """FFmpeg 執行相關的錯誤。"""
    pass

class AudioConversionError(AudioServiceError):
    """音訊轉換失敗的錯誤。"""
    pass


class AudioService:
    """
    音訊服務類別。

    提供與音訊處理相關的靜態方法，例如檢查 FFmpeg 是否可用、轉換音訊格式等。
    這些方法通常作為其他音訊處理服務的底層工具。
    """

    @staticmethod
    def check_ffmpeg() -> bool:
        """
        檢查系統環境中 FFmpeg 是否已安裝且可執行。

        透過執行 `ffmpeg -version` 命令並檢查其返回碼來判斷。

        Returns:
            bool: 如果 FFmpeg 可用則返回 True，否則返回 False。
        """
        logger.debug("正在檢查 FFmpeg 是否可用...")
        try:
            # 執行 ffmpeg -version 命令
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE, # 捕獲標準輸出
                stderr=subprocess.PIPE, # 捕獲標準錯誤
                timeout=5,              # 設定超時時間 (秒)，防止命令卡死
                check=False             # 不在返回碼非零時拋出 CalledProcessError
            )
            if result.returncode == 0:
                logger.info("FFmpeg 已安裝且可執行。")
                return True
            else:
                logger.warning(f"FFmpeg 可能未正確安裝或配置。命令返回碼: {result.returncode}，錯誤訊息: {result.stderr.decode('utf-8', errors='ignore')}")
                return False
        except FileNotFoundError:
            logger.error("FFmpeg 未找到。請確保 FFmpeg 已安裝並在系統 PATH 環境變數中。")
            return False
        except subprocess.TimeoutExpired:
            logger.error("檢查 FFmpeg 版本時發生超時。")
            return False
        except Exception as e:
            logger.error(f"檢查 FFmpeg 時發生未預期錯誤: {e}", exc_info=True)
            return False

    @staticmethod
    def convert_audio(input_file: str, output_file: str, target_format: str = "wav", 
                      audio_codec: str = "pcm_s16le", sample_rate: int = 16000, 
                      channels: int = 1, bitrate: Optional[str] = "64k") -> bool:
        """
        使用 FFmpeg 轉換音訊檔案格式、採樣率、聲道和位元率。

        Args:
            input_file (str): 輸入音訊檔案的路徑。
            output_file (str): 轉換後輸出的音訊檔案路徑。
            target_format (str, optional): 目標音訊格式 (例如 "wav", "mp3")。預設為 "wav"。
            audio_codec (str, optional): 目標音訊編解碼器。對於 WAV，通常使用 "pcm_s16le"。預設為 "pcm_s16le"。
            sample_rate (int, optional): 目標採樣率 (Hz)。預設為 16000 (推薦用於多數 STT 服務)。
            channels (int, optional): 目標聲道數 (1 為單聲道，2 為立體聲)。預設為 1。
            bitrate (Optional[str], optional): 目標音訊位元率 (例如 "64k", "128k")。
                                               如果為 None，則不特別指定位元率。預設為 "64k"。

        Returns:
            bool: 如果轉換成功則返回 True，否則返回 False。
        
        Raises:
            FFmpegError: 如果 FFmpeg 命令執行失敗。
            AudioConversionError: 如果發生其他轉換相關錯誤。
        """
        if not os.path.exists(input_file):
            logger.error(f"音訊轉換失敗：輸入檔案不存在 -> {input_file}")
            raise FileNotFoundError(f"輸入檔案不存在: {input_file}")

        logger.info(f"開始音訊轉換：從 '{input_file}' 到 '{output_file}' (格式: {target_format})")
        
        try:
            # 檢查檔案大小以調整處理超時
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
            logger.debug(f"輸入音訊檔案大小: {file_size_mb:.2f}MB")
            
            # 根據檔案大小動態設定 FFmpeg 超時時間
            if file_size_mb > 100:  # 超過 100MB
                timeout_seconds = 600  # 10 分鐘
            elif file_size_mb > 50: # 超過 50MB
                timeout_seconds = 300  # 5 分鐘
            elif file_size_mb > 10: # 超過 10MB
                timeout_seconds = 120  # 2 分鐘
            else:
                timeout_seconds = 60   # 1 分鐘
            logger.debug(f"FFmpeg 轉換操作超時設定為: {timeout_seconds} 秒。")
            
            # FFmpeg 命令參數列表
            # -y: 自動覆蓋輸出檔案
            # -loglevel error: 僅輸出錯誤訊息，保持日誌清潔
            cmd = [
                "ffmpeg", "-i", input_file,
                "-ar", str(sample_rate), # 設定採樣率
                "-ac", str(channels),    # 設定聲道數
                "-f", target_format,     # 強制指定輸出格式
            ]
            # 根據目標格式和編解碼器需求添加特定參數
            if audio_codec:
                 cmd.extend(["-acodec", audio_codec])
            if bitrate:
                cmd.extend(["-b:a", bitrate]) # 設定音訊位元率
            
            cmd.extend(["-y", output_file, "-loglevel", "error"])
            
            logger.debug(f"執行 FFmpeg 命令: {' '.join(cmd)}")
            
            # 執行 FFmpeg 命令
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE, # 捕獲標準輸出
                stderr=subprocess.PIPE, # 捕獲標準錯誤
                timeout=timeout_seconds, # 設定超時
                check=False # 手動檢查返回碼
            )
            
            if result.returncode == 0:
                output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                logger.info(f"音訊轉換成功完成。輸出檔案: '{output_file}', 大小: {output_size_mb:.2f}MB")
                return True
            else:
                # FFmpeg 執行失敗，記錄詳細錯誤訊息
                ffmpeg_error_message = result.stderr.decode('utf-8', errors='ignore').strip()
                logger.error(f"FFmpeg 命令執行失敗 (返回碼: {result.returncode})。錯誤訊息:\n{ffmpeg_error_message}")
                raise FFmpegError(f"FFmpeg 轉換失敗: {ffmpeg_error_message}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"音訊轉換處理超時 ({timeout_seconds}秒)。輸入檔案: '{input_file}'")
            raise AudioConversionError(f"音訊轉換超時 ({timeout_seconds}秒)。")
        except FFmpegError: # 重新拋出已捕獲的 FFmpegError
            raise
        except Exception as e: # 捕獲其他所有未預期錯誤
            logger.error(f"音訊轉換過程中發生未預期錯誤: {str(e)}。輸入檔案: '{input_file}'", exc_info=True)
            raise AudioConversionError(f"未預期的音訊轉換錯誤: {str(e)}")
        
        return False # 理論上不會執行到這裡，因為錯誤會被拋出