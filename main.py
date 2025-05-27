#!/usr/bin/env python3
"""
異步LINE Bot 錄音助手 - 主程序
支援語音轉文字、AI摘要、HTML美化顯示等功能
"""

import logging
import os
from flask import Flask

from config import AppConfig
from services.messaging.line_bot import AsyncLineBotService
from services.web.routes import create_web_routes


def setup_logging():
    """設置日誌配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('linebot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def create_app() -> Flask:
    """創建並配置 Flask 應用"""
    app = Flask(__name__)
    
    try:
        # 載入配置
        config = AppConfig.from_env()
        logging.info("配置載入成功")
        
        # 初始化 LINE Bot 服務
        linebot_service = AsyncLineBotService(config)
        logging.info("LINE Bot 服務初始化完成")
        
        # 創建 Web 路由
        create_web_routes(app, config, linebot_service)
        logging.info("Web 路由創建完成")
        
        # 記錄系統資訊
        logging.info(f"系統配置:")
        logging.info(f"  - 最大工作線程: {config.max_workers}")
        logging.info(f"  - Webhook超時: {config.webhook_timeout}秒")
        logging.info(f"  - API金鑰數量: {len(config.google_api_keys)}")
        logging.info(f"  - 完整分析: {'啟用' if config.full_analysis else '智能選取'}")
        logging.info(f"  - 最大分析段數: {config.max_segments_for_full_analysis}")
        
        return app
        
    except Exception as e:
        logging.error(f"應用初始化失敗: {e}")
        raise


def main():
    """主函數"""
    # 設置日誌
    setup_logging()
    logging.info("🚀 啟動異步LINE Bot 錄音助手")
    
    try:
        # 創建應用
        app = create_app()
        
        # 獲取端口設置
        port = int(os.environ.get('PORT', 5001))
        debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
        
        logging.info(f"服務器啟動在端口 {port}")
        logging.info(f"調試模式: {'開啟' if debug else '關閉'}")
        
        # 啟動服務器
        app.run(
            host='0.0.0.0',
            port=port,
            debug=debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logging.info("收到中斷信號，正在關閉服務...")
    except Exception as e:
        logging.error(f"服務器啟動失敗: {e}")
        raise
    finally:
        logging.info("服務已關閉")


if __name__ == "__main__":
    main()