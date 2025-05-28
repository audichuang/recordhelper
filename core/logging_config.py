"""核心應用程式日誌設定模組"""
import logging
import os
import sys
import coloredlogs

LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"
LEVEL_STYLES = {
    'debug': {'color': 'green'},
    'info': {'color': 'cyan'},
    'warning': {'color': 'yellow'},
    'error': {'color': 'red'},
    'critical': {'color': 'magenta'}
}
FIELD_STYLES = {
    'asctime': {'color': 'blue'},
    'hostname': {'color': 'magenta'},
    'levelname': {'color': 'black', 'bold': True},
    'name': {'color': 'yellow'},
    'programname': {'color': 'cyan'},
    'username': {'color': 'yellow'}
}

def setup_logging(log_level: str = "INFO", log_dir: str = "logs", log_filename: str = "app.log"):
    """
    設定應用程式的日誌記錄。

    :param log_level: 日誌級別 (例如, "INFO", "DEBUG")
    :param log_dir: 日誌檔案存放目錄
    :param log_filename: 日誌檔案名稱
    """
    # 設定 coloredlogs
    coloredlogs.install(
        level=log_level,
        fmt=LOG_FORMAT,
        level_styles=LEVEL_STYLES,
        field_styles=FIELD_STYLES,
        stream=sys.stdout  # 使用 sys.stdout 以確保在所有環境中都能正確輸出
    )

    # 取得根日誌記錄器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 建立日誌目錄 (如果不存在)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 設定檔案日誌處理器
    log_file_path = os.path.join(log_dir, log_filename)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 設定一個日誌記錄器實例供本模組使用
    # logger = logging.getLogger(__name__) # 這一行會創建一個名為 'logger' 的局部變數，它會遮蔽全域的 logger
    # 若要讓此模組也使用已配置的根日誌記錄器，可以直接調用 logging.getLogger() 或 logging.info()
    logging.getLogger(__name__).info("日誌設定完成。") # 使用 getLogger(__name__) 取得此模組的 logger

# 可以在這裡設定一個預設的日誌記錄器實例，如果其他模組需要直接從這裡 import
# default_logger = logging.getLogger("core.logging_config") # 例如，若其他模組要 import 此 logger
