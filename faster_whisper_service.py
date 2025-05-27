import os
import time
import logging
from faster_whisper import WhisperModel
from typing import Optional, Dict, Any
from config import AppConfig
from models import APIError


class FasterWhisperService:
    """使用 faster-whisper 的高性能本地語音轉文字服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.model = None
        self.model_name = getattr(config, 'local_whisper_model', 'turbo')  # 預設使用 turbo 模型
        self.language = getattr(config, 'local_whisper_language', 'zh')  # 預設中文
        self.task = getattr(config, 'local_whisper_task', 'transcribe')  # 預設轉錄
        
        # faster-whisper 特有配置
        self.compute_type = self._get_compute_type()
        self.cpu_threads = os.cpu_count()  # 使用所有 CPU 核心
        
        logging.info(f"faster-whisper 配置:")
        logging.info(f"  模型: {self.model_name}")
        logging.info(f"  計算類型: {self.compute_type}")
        logging.info(f"  CPU 線程: {self.cpu_threads}")
        
        self._load_model()
    
    def _get_compute_type(self):
        """選擇最佳計算類型"""
        # 對於 Apple Silicon，使用 int8 量化以獲得最佳性能
        try:
            import platform
            if platform.processor() == 'arm' or 'arm64' in platform.machine().lower():
                return "int8"  # Apple Silicon 最佳選擇
            else:
                return "float16"  # Intel Mac 或其他平台
        except:
            return "int8"  # 安全選擇
    
    def _load_model(self):
        """載入 faster-whisper 模型"""
        try:
            start_time = time.time()
            logging.info(f"正在載入 faster-whisper 模型: {self.model_name}")
            
            # 載入模型
            self.model = WhisperModel(
                self.model_name,
                device="cpu",  # faster-whisper 在 CPU 上已經很快了
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                num_workers=1  # 單一工作線程避免競爭
            )
            
            load_time = time.time() - start_time
            logging.info(f"faster-whisper 模型載入完成，耗時: {load_time:.2f}秒")
            logging.info(f"使用優化: {self.compute_type} 量化, {self.cpu_threads} CPU 線程")
            
        except Exception as e:
            logging.error(f"載入 faster-whisper 模型失敗: {e}")
            raise APIError(f"無法載入 faster-whisper 模型: {e}")
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用 faster-whisper 轉換語音為文字"""
        try:
            start_time = time.time()
            
            # 檢查檔案是否存在
            if not os.path.exists(audio_file_path):
                raise APIError(f"音訊檔案不存在: {audio_file_path}")
            
            # 檢查檔案大小
            file_size = os.path.getsize(audio_file_path)
            logging.info(f"處理音訊檔案: {audio_file_path}, 大小: {file_size / (1024*1024):.1f}MB")
            
            # 確保模型已載入
            if self.model is None:
                self._load_model()
            
            # 進行轉錄
            segments, info = self.model.transcribe(
                audio_file_path,
                language=self.language,
                task=self.task,
                beam_size=5,  # 平衡速度和準確性
                best_of=5,
                temperature=0.0,  # 確定性輸出
                condition_on_previous_text=False  # 提高性能
            )
            
            # 收集所有段落的文字
            transcribed_text = ""
            for segment in segments:
                transcribed_text += segment.text
            
            processing_time = time.time() - start_time
            logging.info(f"faster-whisper 處理時間: {processing_time:.2f}秒")
            logging.info(f"轉錄文字長度: {len(transcribed_text)} 字符")
            logging.info(f"檢測語言: {info.language}")
            logging.info(f"語言概率: {info.language_probability:.2f}")
            
            return transcribed_text.strip()
            
        except Exception as e:
            logging.error(f"faster-whisper 轉錄失敗: {e}")
            raise APIError(f"faster-whisper 語音轉文字服務錯誤: {e}")
    
    def transcribe_with_timestamps(self, audio_file_path: str) -> Dict[str, Any]:
        """轉錄音訊並返回包含時間戳的詳細資訊"""
        try:
            start_time = time.time()
            
            if not os.path.exists(audio_file_path):
                raise APIError(f"音訊檔案不存在: {audio_file_path}")
            
            if self.model is None:
                self._load_model()
            
            # 進行轉錄
            segments, info = self.model.transcribe(
                audio_file_path,
                language=self.language,
                task=self.task,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                word_timestamps=True  # 啟用詞級時間戳
            )
            
            # 收集段落資訊
            segments_info = []
            full_text = ""
            
            for segment in segments:
                segments_info.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text += segment.text
            
            processing_time = time.time() - start_time
            logging.info(f"faster-whisper 詳細轉錄處理時間: {processing_time:.2f}秒")
            
            return {
                "text": full_text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": segments_info,
                "processing_time": processing_time,
                "audio_duration": info.duration,
                "speed_ratio": info.duration / processing_time if processing_time > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"faster-whisper 詳細轉錄失敗: {e}")
            raise APIError(f"faster-whisper 語音轉文字服務錯誤: {e}")
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            model_info = {
                "service": "Faster Whisper (高性能本地)",
                "model": self.model_name,
                "language": self.language,
                "task": self.task,
                "compute_type": self.compute_type,
                "cpu_threads": self.cpu_threads,
                "status": "ready" if self.model is not None else "not_loaded",
                "device_type": "CPU (優化版)",
                "acceleration": f"{self.compute_type} 量化",
                "performance": "4-8x faster than openai-whisper"
            }
            
            if self.model is not None:
                model_info["model_loaded"] = True
            else:
                model_info["model_loaded"] = False
            
            return model_info
            
        except Exception as e:
            logging.warning(f"獲取 faster-whisper 使用量失敗: {e}")
            return {
                "service": "Faster Whisper",
                "status": "error",
                "error": str(e)
            }
    
    def get_available_models(self) -> list:
        """獲取可用的模型列表"""
        return ["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo"]
    
    def benchmark_performance(self, audio_file_path: str) -> dict:
        """性能基準測試"""
        try:
            import psutil
            
            # 記錄初始狀態
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            start_time = time.time()
            result = self.transcribe_audio(audio_file_path)
            end_time = time.time()
            
            # 記錄最終狀態
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            processing_time = end_time - start_time
            
            return {
                "processing_time": processing_time,
                "text_length": len(result),
                "memory_used": final_memory - initial_memory,
                "peak_memory": final_memory,
                "words_per_second": len(result.split()) / processing_time if processing_time > 0 else 0
            }
            
        except Exception as e:
            logging.error(f"性能測試失敗: {e}")
            return {"error": str(e)} 