"""核心應用程式中介軟體設定模組"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from config import AppConfig # 修正導入路徑

logger = logging.getLogger(__name__)

def setup_middleware(app: FastAPI, config: AppConfig): # 新增 config 參數
    """
    設定應用程式的中介軟體。

    :param app: FastAPI 應用程式實例
    :param config: 應用程式設定實例
    """
    # 設定 CORS 中介軟體
    # 注意：生產環境中應更嚴格地設定 allow_origins
    if config.ALLOWED_ORIGINS:
        allow_origins = config.ALLOWED_ORIGINS
        logger.info(f"CORS 允許的來源: {allow_origins}")
    else:
        allow_origins = ["*"] # 開發模式或未指定時允許所有
        logger.warning("CORS ALLOWED_ORIGINS 未設定，預設允許所有來源。建議在生產環境中明確設定。")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS 中介軟體設定完成。")

    # 設定 TrustedHost 中介軟體
    if config.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS
        )
        logger.info(f"TrustedHost 中介軟體設定完成，允許的主機: {config.ALLOWED_HOSTS}")
    else:
        logger.warning("ALLOWED_HOSTS 未設定，將不啟用 TrustedHost 中介軟體。建議在生產環境中明確設定。")
        # 如果需要在 ALLOWED_HOSTS 未設定時也添加一個預設值（例如 ["*"]），可以在此處處理
        # 但通常建議明確設定，或者不啟用此中介軟體以避免潛在安全問題

    # 可以在此處添加其他中介軟體，例如：
    # from starlette.middleware.sessions import SessionMiddleware
    # if config.SECRET_KEY:
    #     app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
    #     logger.info("Session 中介軟體設定完成。")
    # else:
    #     logger.warning("SECRET_KEY 未設定，Session 中介軟體將不會啟用。")

    logger.info("所有中介軟體設定完成。")
