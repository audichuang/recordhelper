#!/usr/bin/env python3
"""修復 macOS SSL 證書問題"""
import ssl
import certifi
import os

print("🔧 修復 SSL 證書問題...")

# 1. 檢查當前狀態
print("\n📍 當前 SSL 證書路徑:")
print(f"   預設: {ssl.get_default_verify_paths().cafile}")
print(f"   Certifi: {certifi.where()}")

# 2. 設定環境變數
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

print("\n✅ 已設定環境變數:")
print(f"   SSL_CERT_FILE={certifi.where()}")
print(f"   REQUESTS_CA_BUNDLE={certifi.where()}")

# 3. 測試連接
import urllib.request

print("\n🔍 測試 HTTPS 連接...")
test_urls = [
    "https://api.assemblyai.com",
    "https://api.deepgram.com",
    "https://www.google.com"
]

for url in test_urls:
    try:
        response = urllib.request.urlopen(url, timeout=5)
        print(f"   ✅ {url} - 成功")
    except Exception as e:
        print(f"   ❌ {url} - 失敗: {str(e)}")

print("\n💡 修復建議已生成在 setup_ssl.sh 中")