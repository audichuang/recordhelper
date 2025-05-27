from fastapi import FastAPI
from .auth import auth_router
from .users import users_router
from .recordings import recordings_router
from .analysis import analysis_router
from .system import system_router


def init_api_routes(app: FastAPI, config):
    """初始化所有API路由"""
    
    # 認證相關路由
    app.include_router(
        auth_router,
        prefix="/api/auth",
        tags=["認證"]
    )
    
    # 用戶相關路由
    app.include_router(
        users_router,
        prefix="/api/users",
        tags=["用戶"]
    )
    
    # 錄音相關路由
    app.include_router(
        recordings_router,
        prefix="/api/recordings",
        tags=["錄音"]
    )
    
    # 分析相關路由
    app.include_router(
        analysis_router,
        prefix="/api/analysis",
        tags=["分析"]
    )
    
    # 系統狀態路由
    app.include_router(
        system_router,
        prefix="/api/system",
        tags=["系統"]
    )


__all__ = ['init_api_routes'] 