"""核心應用程式錯誤處理設定模組"""
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

async def http_exception_handler(request: Request, exc: HTTPException):
    """
    處理 HTTP 例外情況。

    :param request: FastAPI 請求對象
    :param exc: HTTP 例外實例
    :return: JSONResponse 包含錯誤詳細資訊
    """
    logger.error(f"HTTP 例外發生: {exc.status_code} - {exc.detail} (請求路徑: {request.url.path})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

async def general_exception_handler(request: Request, exc: Exception):
    """
    處理一般未捕獲的例外情況。

    :param request: FastAPI 請求對象
    :param exc: 例外實例
    :return: JSONResponse 包含內部伺服器錯誤訊息
    """
    logger.critical(f"未捕獲的例外: {exc} (請求路徑: {request.url.path})", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "內部伺服器錯誤，請聯繫管理員。"},
    )

def setup_error_handlers(app: FastAPI):
    """
    設定應用程式的錯誤處理程序。

    :param app: FastAPI 應用程式實例
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    logger.info("錯誤處理程序設定完成。")
