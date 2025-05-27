#!/usr/bin/env python3
"""
數據庫遷移腳本
"""

import os
import sys
from flask_migrate import init, migrate, upgrade, downgrade
from app import create_app
from config import AppConfig

def main():
    """主函數"""
    app = create_app()
    
    with app.app_context():
        command = sys.argv[1] if len(sys.argv) > 1 else 'upgrade'
        
        if command == 'init':
            print("初始化遷移...")
            init()
            
        elif command == 'migrate':
            message = sys.argv[2] if len(sys.argv) > 2 else 'Auto migration'
            print(f"創建遷移: {message}")
            migrate(message=message)
            
        elif command == 'upgrade':
            print("應用遷移...")
            upgrade()
            
        elif command == 'downgrade':
            print("回滾遷移...")
            downgrade()
            
        else:
            print("用法:")
            print("  python migrate_db.py init      # 初始化遷移")
            print("  python migrate_db.py migrate   # 創建遷移")
            print("  python migrate_db.py upgrade   # 應用遷移")
            print("  python migrate_db.py downgrade # 回滾遷移")

if __name__ == "__main__":
    main() 