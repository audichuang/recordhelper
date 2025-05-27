import os
import time
import logging
import whisper
import torch
from typing import Optional, Dict, Any
from config import AppConfig
from models.base import APIError


class LocalWhisperService:
    """使用官方 openai-whisper 庫的本地語音轉文字服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.model = None
        self.model_name = getattr(config, 'local_whisper_model', 'turbo')  # 預設使用 turbo 模型
        self.language = getattr(config, 'local_whisper_language', 'zh')  # 預設中文
        self.task = getattr(config, 'local_whisper_task', 'transcribe')  # 預設轉錄
        self.device_preference = getattr(config, 'local_whisper_device', 'auto')  # 設備偏好
        
        # 選擇計算設備
        self.device = self._get_device()
        logging.info(f"選擇的計算設備: {self.device}")
        
        self._load_model()
    
    def _get_device(self):
        """根據配置和可用性選擇計算設備"""
        if self.device_preference != "auto":
            # 使用指定設備
            if self.device_preference == "mps" and torch.backends.mps.is_available():
                return "mps"
            elif self.device_preference == "cuda" and torch.cuda.is_available():
                return "cuda"
            elif self.device_preference == "cpu":
                return "cpu"
            else:
                logging.warning(f"指定設備 {self.device_preference} 不可用，自動選擇最佳設備")
        
        # 自動選擇最佳設備（優先使用 MPS，然後 CUDA，最後 CPU）
        if torch.backends.mps.is_available():
            return "mps"  # Apple Silicon GPU
        elif torch.cuda.is_available():
            return "cuda"  # NVIDIA GPU
        else:
            return "cpu"
    
    def _load_model(self):
        """載入 Whisper 模型"""
        try:
            start_time = time.time()
            logging.info(f"正在載入 Whisper 模型: {self.model_name} 到設備: {self.device}")
            
            # 載入模型並移動到指定設備
            self.model = whisper.load_model(self.model_name, device=self.device)
            
            load_time = time.time() - start_time
            logging.info(f"Whisper 模型載入完成，耗時: {load_time:.2f}秒")
            
            # 顯示設備資訊
            if self.device == "mps":
                logging.info("使用 Apple Silicon GPU (Metal Performance Shaders) 加速")
            elif self.device == "cuda":
                logging.info(f"使用 NVIDIA GPU 加速: {torch.cuda.get_device_name()}")
            else:
                logging.info("使用 CPU 運算")
            
        except Exception as e:
            logging.error(f"載入 Whisper 模型失敗: {e}")
            # 如果指定設備失敗，嘗試使用 CPU
            if self.device != "cpu":
                logging.warning(f"設備 {self.device} 失敗，回退到 CPU")
                self.device = "cpu"
                try:
                    self.model = whisper.load_model(self.model_name, device="cpu")
                    logging.info("成功使用 CPU 載入模型")
                except Exception as cpu_error:
                    raise APIError(f"無法載入 Whisper 模型: {cpu_error}")
            else:
                raise APIError(f"無法載入 Whisper 模型: {e}")
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用本地 Whisper 轉換語音為文字"""
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
            result = self.model.transcribe(
                audio_file_path,
                language=self.language,
                task=self.task,
                verbose=False  # 減少輸出
            )
            
            processing_time = time.time() - start_time
            logging.info(f"本地 Whisper 處理時間: {processing_time:.2f}秒")
            
            # 獲取轉錄文字
            transcribed_text = result["text"].strip()
            logging.info(f"轉錄文字長度: {len(transcribed_text)} 字符")
            logging.info(f"檢測語言: {result.get('language', '未知')}")
            
            return transcribed_text
            
        except Exception as e:
            logging.error(f"本地 Whisper 轉錄失敗: {e}")
            raise APIError(f"本地語音轉文字服務錯誤: {e}")
    
    def transcribe_with_timestamps(self, audio_file_path: str) -> Dict[str, Any]:
        """轉錄音訊並返回包含時間戳的詳細資訊"""
        try:
            start_time = time.time()
            
            if not os.path.exists(audio_file_path):
                raise APIError(f"音訊檔案不存在: {audio_file_path}")
            
            if self.model is None:
                self._load_model()
            
            # 進行轉錄
            result = self.model.transcribe(
                audio_file_path,
                language=self.language,
                task=self.task,
                verbose=False
            )
            
            processing_time = time.time() - start_time
            logging.info(f"本地 Whisper 詳細轉錄處理時間: {processing_time:.2f}秒")
            
            # 格式化輸出
            segments_info = []
            for segment in result.get("segments", []):
                segments_info.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip()
                })
            
            return {
                "text": result["text"].strip(),
                "language": result.get("language", "unknown"),
                "segments": segments_info,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logging.error(f"本地 Whisper 詳細轉錄失敗: {e}")
            raise APIError(f"本地語音轉文字服務錯誤: {e}")
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            model_info = {
                "service": "Local OpenAI Whisper",
                "model": self.model_name,
                "language": self.language,
                "task": self.task,
                "device": self.device,
                "status": "ready" if self.model is not None else "not_loaded"
            }
            
            # 添加設備相關資訊
            device_info = {}
            if self.device == "mps":
                device_info = {
                    "device_type": "Apple Silicon GPU",
                    "acceleration": "Metal Performance Shaders",
                    "fp16_support": True
                }
            elif self.device == "cuda":
                device_info = {
                    "device_type": "NVIDIA GPU",
                    "acceleration": "CUDA",
                    "fp16_support": True
                }
            else:
                device_info = {
                    "device_type": "CPU",
                    "acceleration": "None",
                    "fp16_support": False
                }
            
            model_info.update(device_info)
            
            # 如果模型已載入，添加更多資訊
            if self.model is not None:
                model_info["model_loaded"] = True
                model_info["available_languages"] = list(whisper.tokenizer.LANGUAGES.keys())
            else:
                model_info["model_loaded"] = False
            
            return model_info
            
        except Exception as e:
            logging.warning(f"獲取本地 Whisper 使用量失敗: {e}")
            return {
                "service": "Local OpenAI Whisper",
                "status": "error",
                "error": str(e)
            }
    
    def get_available_models(self) -> list:
        """獲取可用的模型列表"""
        return ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo"]
    
    def get_available_languages(self) -> dict:
        """獲取支援的語言列表"""
        try:
            return whisper.tokenizer.LANGUAGES
        except Exception as e:
            logging.warning(f"獲取語言列表失敗: {e}")
            return {"zh": "chinese", "en": "english", "ja": "japanese"} 