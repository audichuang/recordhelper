"""測試重新生成功能"""
import asyncio
import httpx
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 測試配置
BASE_URL = "http://localhost:9527/api"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"

async def test_regenerate():
    """測試重新生成功能"""
    async with httpx.AsyncClient() as client:
        # 1. 登錄獲取 token
        logger.info("🔐 登錄測試用戶...")
        login_response = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        if login_response.status_code != 200:
            logger.error(f"❌ 登錄失敗: {login_response.text}")
            return
            
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ 登錄成功")
        
        # 2. 獲取錄音列表
        logger.info("📋 獲取錄音列表...")
        recordings_response = await client.get(
            f"{BASE_URL}/recordings/",
            headers=headers
        )
        
        if recordings_response.status_code != 200:
            logger.error(f"❌ 獲取錄音列表失敗: {recordings_response.text}")
            return
            
        recordings = recordings_response.json()["recordings"]
        if not recordings:
            logger.warning("⚠️ 沒有找到任何錄音")
            return
            
        # 選擇第一個已完成的錄音
        completed_recording = None
        for rec in recordings:
            if rec["status"] == "completed" and rec["transcript"] and rec["summary"]:
                completed_recording = rec
                break
                
        if not completed_recording:
            logger.warning("⚠️ 沒有找到已完成的錄音")
            return
            
        recording_id = completed_recording["id"]
        logger.info(f"✅ 找到錄音: {completed_recording['title']} (ID: {recording_id})")
        logger.info(f"  - 原始逐字稿長度: {len(completed_recording['transcript'] or '')}")
        logger.info(f"  - 原始摘要長度: {len(completed_recording['summary'] or '')}")
        
        # 3. 測試重新生成逐字稿
        logger.info("🔄 測試重新生成逐字稿...")
        regen_trans_response = await client.post(
            f"{BASE_URL}/analysis/{recording_id}/regenerate-transcription",
            headers=headers,
            json={"provider": "gemini"}
        )
        
        if regen_trans_response.status_code == 200:
            result = regen_trans_response.json()
            logger.info(f"✅ 逐字稿重新生成已開始: {result['message']}")
            logger.info(f"  - 歷史記錄ID: {result['history_id']}")
            
            # 等待一段時間後檢查結果
            logger.info("⏳ 等待 10 秒後檢查結果...")
            await asyncio.sleep(10)
            
            # 重新獲取錄音詳情
            detail_response = await client.get(
                f"{BASE_URL}/recordings/{recording_id}",
                headers=headers
            )
            
            if detail_response.status_code == 200:
                updated_recording = detail_response.json()
                logger.info(f"📊 更新後的逐字稿長度: {len(updated_recording['transcript'] or '')}")
                
                # 檢查歷史記錄
                history_response = await client.get(
                    f"{BASE_URL}/analysis/{recording_id}/history?analysis_type=transcription",
                    headers=headers
                )
                
                if history_response.status_code == 200:
                    histories = history_response.json()
                    logger.info(f"📜 逐字稿歷史記錄數: {len(histories)}")
                    for h in histories[:3]:  # 顯示最近3條
                        logger.info(f"  - 版本 {h['version']}: {h['status']} (當前: {h['is_current']})")
        else:
            logger.error(f"❌ 重新生成逐字稿失敗: {regen_trans_response.text}")
            
        # 4. 測試重新生成摘要
        logger.info("\n🔄 測試重新生成摘要...")
        regen_summary_response = await client.post(
            f"{BASE_URL}/analysis/{recording_id}/regenerate-summary",
            headers=headers,
            json={"provider": "gemini"}
        )
        
        if regen_summary_response.status_code == 200:
            result = regen_summary_response.json()
            logger.info(f"✅ 摘要重新生成已開始: {result['message']}")
            logger.info(f"  - 歷史記錄ID: {result['history_id']}")
            
            # 等待一段時間後檢查結果
            logger.info("⏳ 等待 10 秒後檢查結果...")
            await asyncio.sleep(10)
            
            # 重新獲取錄音詳情
            detail_response = await client.get(
                f"{BASE_URL}/recordings/{recording_id}",
                headers=headers
            )
            
            if detail_response.status_code == 200:
                updated_recording = detail_response.json()
                logger.info(f"📊 更新後的摘要長度: {len(updated_recording['summary'] or '')}")
                
                # 檢查歷史記錄
                history_response = await client.get(
                    f"{BASE_URL}/analysis/{recording_id}/history?analysis_type=summary",
                    headers=headers
                )
                
                if history_response.status_code == 200:
                    histories = history_response.json()
                    logger.info(f"📜 摘要歷史記錄數: {len(histories)}")
                    for h in histories[:3]:  # 顯示最近3條
                        logger.info(f"  - 版本 {h['version']}: {h['status']} (當前: {h['is_current']})")
        else:
            logger.error(f"❌ 重新生成摘要失敗: {regen_summary_response.text}")

if __name__ == "__main__":
    asyncio.run(test_regenerate())