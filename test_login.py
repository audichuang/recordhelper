#!/usr/bin/env python3
"""測試登入功能是否正常"""
import asyncio
import sys
import time
import subprocess
import requests
from threading import Thread

def run_server():
    """在背景執行服務器"""
    process = subprocess.Popen(
        [sys.executable, "run_fastapi.py"],
        env={**subprocess.os.environ, "RELOAD": "FALSE"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

async def test_login():
    """測試登入功能"""
    print("🚀 啟動 FastAPI 服務器...")
    process = run_server()
    
    # 等待服務器啟動
    print("⏳ 等待服務器啟動...")
    time.sleep(5)
    
    try:
        # 測試登入
        print("🔐 測試登入功能...")
        response = requests.post(
            "http://localhost:9527/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "password"
            }
        )
        
        if response.status_code == 200:
            print("✅ 登入成功！")
            data = response.json()
            print(f"   用戶: {data.get('user', {}).get('email')}")
            print(f"   Token: {data.get('access_token', '')[:20]}...")
            return True
        else:
            print(f"❌ 登入失敗: {response.status_code}")
            print(f"   回應: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        # 讀取錯誤輸出
        stderr = process.stderr.read().decode() if process.stderr else ""
        if stderr:
            print(f"錯誤輸出:\n{stderr[:1000]}")
        return False
        
    finally:
        # 停止服務器
        print("🛑 停止服務器...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    success = asyncio.run(test_login())
    sys.exit(0 if success else 1)