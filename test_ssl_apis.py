#!/usr/bin/env python3
"""測試 API SSL 連接"""
import os
import certifi
import httpx
import asyncio

# 設定 SSL 證書
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['HTTPX_CA_BUNDLE'] = certifi.where()

async def test_apis():
    """測試各個 API 的連接"""
    print("🔍 測試 API SSL 連接...")
    
    # 測試的 API
    tests = [
        ("AssemblyAI", "https://api.assemblyai.com/v2/transcript", 
         {"authorization": "test"}),
        ("Deepgram", "https://api.deepgram.com/v1/listen",
         {"authorization": "Token test"}),
        ("Google", "https://www.google.com", {})
    ]
    
    async with httpx.AsyncClient(verify=certifi.where()) as client:
        for name, url, headers in tests:
            try:
                response = await client.get(url, headers=headers, timeout=5)
                if response.status_code == 401:
                    print(f"✅ {name}: SSL 連接成功 (需要有效的 API 金鑰)")
                elif response.status_code == 405:
                    print(f"✅ {name}: SSL 連接成功 (方法不允許)")
                elif response.status_code < 500:
                    print(f"✅ {name}: SSL 連接成功 (狀態碼: {response.status_code})")
                else:
                    print(f"⚠️ {name}: 伺服器錯誤 {response.status_code}")
            except httpx.ConnectError as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    print(f"❌ {name}: SSL 證書錯誤 - {str(e)}")
                else:
                    print(f"❌ {name}: 連接錯誤 - {str(e)}")
            except Exception as e:
                print(f"❌ {name}: 錯誤 - {str(e)}")
    
    print("\n✅ SSL 證書路徑:", certifi.where())

if __name__ == "__main__":
    asyncio.run(test_apis())