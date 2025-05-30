#!/usr/bin/env python3
"""
测试新的分阶段推送通知系统
"""
import asyncio
import sys
from services.notifications.apns_service import apns_service

async def test_notifications():
    """测试所有类型的推送通知"""
    
    # 測試設備 Token（使用之前註冊的真實 token）
    test_device_token = "3473485c02278414c92f9827c7db6b71987ca23ad05de6259514a39e1d06aae7"
    test_recording_id = "test-recording-123"
    test_recording_title = "測試錄音"
    
    print("🧪 開始測試新的推送通知系統...")
    
    # 1. 測試逐字稿完成通知
    print("\n📝 測試逐字稿完成通知...")
    success1 = await apns_service.send_transcription_completed_notification(
        device_token=test_device_token,
        recording_id=test_recording_id,
        recording_title=test_recording_title,
        has_error=False
    )
    print(f"結果: {'✅ 成功' if success1 else '❌ 失敗'}")
    
    # 等待一下
    await asyncio.sleep(2)
    
    # 2. 測試摘要完成通知
    print("\n📋 測試摘要完成通知...")
    success2 = await apns_service.send_summary_completed_notification(
        device_token=test_device_token,
        recording_id=test_recording_id,
        recording_title=test_recording_title,
        has_error=False
    )
    print(f"結果: {'✅ 成功' if success2 else '❌ 失敗'}")
    
    # 等待一下
    await asyncio.sleep(2)
    
    # 3. 測試重新生成完成通知
    print("\n✅ 測試重新生成完成通知...")
    success3 = await apns_service.send_regeneration_notification(
        device_token=test_device_token,
        recording_id=test_recording_id,
        recording_title=test_recording_title,
        analysis_type="transcription",
        status="completed"
    )
    print(f"結果: {'✅ 成功' if success3 else '❌ 失敗'}")
    
    # 總結
    total_success = sum([success1, success2, success3])
    print(f"\n📊 測試總結: {total_success}/3 個通知發送成功")
    
    if total_success == 3:
        print("🎉 所有推送通知測試通過！")
        return True
    else:
        print("⚠️ 部分推送通知測試失敗")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_notifications())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        sys.exit(1)