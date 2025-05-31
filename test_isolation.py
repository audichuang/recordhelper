#!/usr/bin/env python3
"""測試環境隔離效果"""
import sys
import subprocess
import site

print("🔍 環境隔離測試報告")
print("=" * 50)

# 1. Python 路徑
print(f"\n📍 Python 執行路徑:")
print(f"   {sys.executable}")

# 2. Python 版本
print(f"\n🐍 Python 版本:")
print(f"   {sys.version}")

# 3. 套件安裝路徑
print(f"\n📦 套件安裝路徑:")
for path in site.getsitepackages():
    print(f"   {path}")

# 4. 檢查特定套件
print(f"\n✅ 已安裝的關鍵套件:")
packages = ["fastapi", "uvicorn", "sqlalchemy", "assemblyai", "deepgram"]
for package in packages:
    try:
        __import__(package)
        print(f"   ✓ {package}")
    except ImportError:
        print(f"   ✗ {package} (未安裝)")

# 5. 環境變數
print(f"\n🌍 虛擬環境路徑:")
print(f"   VIRTUAL_ENV: {sys.prefix}")

# 6. pip 位置
result = subprocess.run(["which", "pip"], capture_output=True, text=True)
print(f"\n🔧 pip 路徑:")
print(f"   {result.stdout.strip()}")

print("\n" + "=" * 50)
print("✅ 環境隔離測試完成！")