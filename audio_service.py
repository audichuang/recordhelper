import os
import subprocess
import tempfile
import uuid
import logging
from typing import List
from models import AudioProcessingError


class TempFileManager:
    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.created_files: List[str] = []

    def create_temp_file(self, suffix: str = "") -> str:
        temp_file = os.path.join(self.temp_dir, f"{uuid.uuid4()}{suffix}")
        self.created_files.append(temp_file)
        return temp_file

    def cleanup(self):
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.warning(f"清理檔案失敗: {file_path}, 錯誤: {e}")
        self.created_files.clear()


class AudioService:
    @staticmethod
    def check_ffmpeg() -> bool:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5  # 降低超時時間
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def convert_audio(input_file: str, output_file: str, max_duration_hours: int = 4) -> bool:
        try:
            # 檢查檔案大小
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
            logging.info(f"音訊檔案大小: {file_size_mb:.1f}MB")
            
            # 根據檔案大小調整超時時間
            if file_size_mb > 50:
                timeout = 300  # 5分鐘
                logging.info("大檔案處理，延長轉換超時時間至5分鐘")
            elif file_size_mb > 20:
                timeout = 120  # 2分鐘
            else:
                timeout = 60   # 1分鐘
            
            # 優化音訊轉換：降低質量以減少檔案大小和處理時間
            cmd = [
                "ffmpeg", "-i", input_file,
                "-ar", "16000",  # 降低採樣率到16kHz（Whisper推薦）
                "-ac", "1",      # 轉換為單聲道
                "-ab", "64k",    # 降低位元率
                "-y", output_file,
                "-loglevel", "error"
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
            
            if result.returncode == 0:
                output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                logging.info(f"轉換完成，輸出檔案大小: {output_size_mb:.1f}MB")
                return True
            else:
                logging.error(f"FFmpeg 錯誤: {result.stderr.decode()}")
                return False
                
        except subprocess.TimeoutExpired:
            logging.error(f"音訊轉換超時（{timeout}秒）")
            return False
        except Exception as e:
            logging.error(f"轉換音訊時發生錯誤: {e}")
            return False 