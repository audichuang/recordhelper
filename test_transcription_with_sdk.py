#!/usr/bin/env python3
"""測試使用官方 SDK 的轉錄功能"""
import asyncio
import httpx
import os
from pathlib import Path

# 測試音訊檔案
TEST_AUDIO = "/Users/audi/Downloads/重陽橋30號_7.wav"
API_BASE = "http://localhost:9527"

async def test_transcription():
    """測試轉錄 API"""
    print(f"🎯 測試音訊檔案: {TEST_AUDIO}")
    
    if not os.path.exists(TEST_AUDIO):
        print("❌ 測試檔案不存在")
        return
    
    # 檢查檔案大小
    file_size = os.path.getsize(TEST_AUDIO) / 1024 / 1024
    print(f"📊 檔案大小: {file_size:.2f} MB")
    
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. 登入
        print("\n🔐 登入中...")
        login_response = await client.post(
            f"{API_BASE}/api/auth/login",
            json={
                "email": "audi51408@gmail.com",
                "password": "adminadmin"
            }
        )
        
        if login_response.status_code != 200:
            print(f"❌ 登入失敗: {login_response.text}")
            return
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ 登入成功")
        
        # 2. 上傳並轉錄
        print("\n📤 上傳音訊檔案...")
        with open(TEST_AUDIO, "rb") as f:
            files = {"file": (Path(TEST_AUDIO).name, f, "audio/wav")}
            data = {
                "title": "測試官方SDK轉錄",
                "srt_only": "true"  # 測試 SRT 格式
            }
            
            upload_response = await client.post(
                f"{API_BASE}/api/recordings/upload",
                files=files,
                data=data,
                headers=headers
            )
        
        if upload_response.status_code != 200:
            print(f"❌ 上傳失敗: {upload_response.text}")
            return
        
        result = upload_response.json()
        print("✅ 轉錄成功！")
        print(f"\n📝 結果:")
        print(f"   ID: {result.get('id')}")
        print(f"   標題: {result.get('title')}")
        print(f"   時長: {result.get('duration', 0):.2f} 秒")
        print(f"   提供商: {result.get('transcription_provider', 'N/A')}")
        
        # 顯示部分轉錄內容
        transcription = result.get('transcription', '')
        if transcription:
            print(f"\n📄 轉錄內容 (前200字):")
            print(f"   {transcription[:200]}...")
            
            # 檢查是否為 SRT 格式
            if transcription.strip().startswith('1\n'):
                print("\n✅ 成功返回 SRT 格式字幕")
        else:
            print("\n❌ 沒有轉錄內容")

if __name__ == "__main__":
    asyncio.run(test_transcription())