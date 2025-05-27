#!/usr/bin/env python3
"""
FastAPI 錄音助手啟動腳本
"""

import os
import sys
import uvicorn
from main_fastapi import create_app
from config import AppConfig

def main():
    """啟動FastAPI應用"""
    
    # 設置環境
    os.environ.setdefault('PYTHONPATH', '.')
    
    try:
        # 載入配置
        config = AppConfig.from_env()
        
        # 創建應用
        app = create_app(config)
        
        # 啟動參數
        host = os.environ.get('HOST', '0.0.0.0')
        port = int(os.environ.get('PORT', 9527))  # 更特別的端口號
        reload = os.environ.get('RELOAD', 'false').lower() == 'true'
        workers = int(os.environ.get('WORKERS', 1))
        
        print(f"""
🚀 啟動 FastAPI 錄音助手
==========================================
📡 服務地址: http://{host}:{port}
📖 API文檔: http://{host}:{port}/docs
🔄 自動重載: {'開啟' if reload else '關閉'}
👥 工作進程: {workers}
==========================================
        """)
        
        # 啟動服務器
        uvicorn.run(
            "main_fastapi:create_app",
            factory=True,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,  # reload模式只能用1個worker
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        print("\n👋 收到停止信號，正在關閉服務...")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 