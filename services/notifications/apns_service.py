"""
Apple Push Notification Service (APNS) 實現
"""
import os
import jwt
import time
import httpx
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class APNSService:
    def __init__(self):
        # JWT token 緩存
        self._token = None
        self._token_timestamp = 0
        
        # 延遲加載配置
        self._config_loaded = False
        
    def _load_config(self):
        """延遲加載 APNS 配置"""
        if self._config_loaded:
            return
            
        # APNS 配置
        self.key_id = os.getenv("APNS_KEY_ID")
        self.team_id = os.getenv("APNS_TEAM_ID")
        self.bundle_id = os.getenv("APNS_BUNDLE_ID", "com.audichuang.app")
        self.key_path = os.getenv("APNS_AUTH_KEY_PATH")
        
        # 開發/生產環境
        self.use_sandbox = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"
        self.apns_host = "api.sandbox.push.apple.com" if self.use_sandbox else "api.push.apple.com"
        
        self._config_loaded = True
        print(f"🔧 APNS 配置加載完成: key_id={self.key_id}, team_id={self.team_id}, bundle_id={self.bundle_id}, key_path={self.key_path}")
        
    def _get_auth_token(self) -> str:
        """生成 APNS JWT token"""
        self._load_config()  # 確保配置已加載
        
        current_time = time.time()
        
        # 如果 token 還有效（小於 50 分鐘），返回緩存的 token
        if self._token and current_time - self._token_timestamp < 3000:
            return self._token
            
        # 讀取私鑰
        print(f"🔍 檢查 APNS 金鑰: key_path='{self.key_path}', exists={os.path.exists(self.key_path) if self.key_path else False}")
        if not self.key_path:
            raise ValueError("APNS auth key path not configured")
        if not os.path.exists(self.key_path):
            raise ValueError(f"APNS auth key file not found at: {self.key_path}")
            
        with open(self.key_path, "r") as f:
            auth_key = f.read()
            
        # 生成 JWT
        token_data = {
            "iss": self.team_id,
            "iat": int(current_time)
        }
        
        headers = {
            "alg": "ES256",
            "kid": self.key_id
        }
        
        self._token = jwt.encode(
            token_data,
            auth_key,
            algorithm="ES256",
            headers=headers
        )
        self._token_timestamp = current_time
        
        return self._token
        
    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        badge: Optional[int] = None,
        sound: str = "default",
        category: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> bool:
        """
        發送推送通知
        
        Args:
            device_token: 設備 token
            title: 通知標題
            body: 通知內容
            data: 自定義數據
            badge: 應用圖標上的數字
            sound: 通知聲音
            category: 通知類別（用於操作按鈕）
            thread_id: 通知分組 ID
            
        Returns:
            是否發送成功
        """
        try:
            # 構建通知 payload
            payload = {
                "aps": {
                    "alert": {
                        "title": title,
                        "body": body
                    },
                    "sound": sound,
                    "content-available": 1  # 支援背景更新
                }
            }
            
            if badge is not None:
                payload["aps"]["badge"] = badge
                
            if category:
                payload["aps"]["category"] = category
                
            if thread_id:
                payload["aps"]["thread-id"] = thread_id
                
            # 添加自定義數據
            if data:
                payload.update(data)
                
            # 獲取認證 token
            auth_token = self._get_auth_token()
            
            # 發送請求
            url = f"https://{self.apns_host}/3/device/{device_token}"
            headers = {
                "authorization": f"bearer {auth_token}",
                "apns-topic": self.bundle_id,
                "apns-push-type": "alert",
                "apns-priority": "10"
            }
            
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ 成功發送推送通知到設備: {device_token[:10]}...")
                    return True
                else:
                    error_data = response.json() if response.content else {}
                    logger.error(f"❌ 推送通知失敗: {response.status_code} - {error_data}")
                    
                    # 處理特定錯誤
                    if response.status_code == 410:
                        # 設備 token 無效，應該從資料庫移除
                        logger.warning(f"設備 token 已失效: {device_token[:10]}...")
                        
                    return False
                    
        except Exception as e:
            logger.error(f"❌ 發送推送通知時發生錯誤: {str(e)}")
            return False
            
    async def send_transcription_completed_notification(
        self,
        device_token: str,
        recording_id: str,
        recording_title: str,
        has_error: bool = False
    ):
        """發送逐字稿完成通知"""
        if has_error:
            title = "逐字稿處理失敗"
            body = f"「{recording_title}」的逐字稿生成失敗，請重試"
            status = "transcription_failed"
        else:
            title = "逐字稿完成"
            body = f"「{recording_title}」的逐字稿已生成，正在生成摘要..."
            status = "transcription_completed"
            
        data = {
            "type": "transcription_update",
            "recordingId": recording_id,
            "status": status
        }
        
        return await self.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
            sound="default" if not has_error else "error.wav",
            thread_id=f"recording-{recording_id}"
        )
    
    async def send_summary_completed_notification(
        self,
        device_token: str,
        recording_id: str,
        recording_title: str,
        has_error: bool = False
    ):
        """發送摘要完成通知"""
        if has_error:
            title = "摘要處理失敗"
            body = f"「{recording_title}」的摘要生成失敗，但逐字稿可用"
            status = "summary_failed"
        else:
            title = "處理完成"
            body = f"「{recording_title}」的逐字稿和摘要已全部完成"
            status = "all_completed"
            
        data = {
            "type": "summary_update",
            "recordingId": recording_id,
            "status": status
        }
        
        return await self.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
            sound="success.wav" if not has_error else "error.wav",
            thread_id=f"recording-{recording_id}"
        )

    async def send_regeneration_notification(
        self,
        device_token: str,
        recording_id: str,
        recording_title: str,
        analysis_type: str,  # "transcription" or "summary"
        status: str,  # "completed", "failed" (不再支援 "started")
    ):
        """發送重新生成通知（僅完成和失敗狀態）"""
        type_name = "逐字稿" if analysis_type == "transcription" else "摘要"
        
        if status == "completed":
            title = f"{type_name}更新完成"
            body = f"「{recording_title}」的{type_name}已重新生成完成"
        else:  # failed
            title = f"{type_name}生成失敗"
            body = f"「{recording_title}」的{type_name}重新生成失敗，請重試"
            
        data = {
            "type": "regeneration_update",
            "recordingId": recording_id,
            "analysisType": analysis_type,
            "status": status
        }
        
        return await self.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            data=data,
            sound="success.wav" if status == "completed" else "error.wav",
            thread_id=f"recording-{recording_id}"
        )
    
    async def send_recording_completed_notification(
        self,
        device_token: str,
        recording_id: str,
        recording_title: str,
        has_error: bool = False
    ):
        """發送錄音處理完成通知（向後兼容）"""
        return await self.send_summary_completed_notification(
            device_token, recording_id, recording_title, has_error
        )
        
    async def send_batch_notifications(
        self,
        device_tokens: list[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """批量發送通知"""
        results = []
        for token in device_tokens:
            success = await self.send_notification(token, title, body, data)
            results.append((token, success))
        return results


# 單例實例
apns_service = APNSService()