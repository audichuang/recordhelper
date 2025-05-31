#!/usr/bin/env python3
"""測試 FastAPI 服務是否可以正常啟動"""
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

def test_server():
    """測試服務器是否正常運行"""
    print("🚀 啟動 FastAPI 服務器...")
    process = run_server()
    
    # 等待服務器啟動
    print("⏳ 等待服務器啟動...")
    time.sleep(5)
    
    try:
        # 測試健康檢查端點
        print("🔍 測試健康檢查端點...")
        response = requests.get("http://localhost:9527/health")
        
        if response.status_code == 200:
            print("✅ 服務器啟動成功！")
            print(f"   回應: {response.json()}")
            return True
        else:
            print(f"❌ 健康檢查失敗: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 無法連接到服務器")
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
    success = test_server()
    sys.exit(0 if success else 1)