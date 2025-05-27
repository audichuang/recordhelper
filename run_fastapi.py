#!/usr/bin/env python3
"""
FastAPI 錄音助手啟動腳本
"""

import os
import sys
import uvicorn
import coloredlogs
import logging
from main_fastapi import create_app
from config import AppConfig

# 設置彩色控制台輸出的ANSI轉義序列
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

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
        host = '0.0.0.0'  # 綁定到所有網絡接口
        port = int(os.environ.get('PORT', 9527))  # 特別的端口號
        reload = os.environ.get('RELOAD', 'false').lower() == 'true'
        workers = int(os.environ.get('WORKERS', 1))
        
        # 彩色啟動標語
        banner = f"""
{Colors.BRIGHT_CYAN}{Colors.BOLD}🚀 啟動 FastAPI 錄音助手{Colors.RESET}
{Colors.BRIGHT_BLUE}==========================================={Colors.RESET}
{Colors.BRIGHT_GREEN}📡 服務地址: {Colors.BRIGHT_WHITE}http://{host}:{port}{Colors.RESET}
{Colors.BRIGHT_GREEN}📡 Tailscale 地址: {Colors.BRIGHT_WHITE}http://audimacbookpro:{port}{Colors.RESET}
{Colors.BRIGHT_GREEN}📖 API文檔: {Colors.BRIGHT_WHITE}http://{host}:{port}/docs{Colors.RESET}
{Colors.BRIGHT_GREEN}🔄 自動重載: {Colors.BRIGHT_YELLOW + '開啟' if reload else Colors.BRIGHT_RED + '關閉'}{Colors.RESET}
{Colors.BRIGHT_GREEN}👥 工作進程: {Colors.BRIGHT_MAGENTA}{workers}{Colors.RESET}
{Colors.BRIGHT_BLUE}==========================================={Colors.RESET}
        """
        
        print(banner)
        
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
        print(f"\n{Colors.BRIGHT_YELLOW}👋 收到停止信號，正在關閉服務...{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.BRIGHT_RED}❌ 啟動失敗: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main() 