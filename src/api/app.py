"""
FastAPI 应用入口。

职责：
  - 定义 lifespan（启动/关闭 ConversationService）
  - 注册路由
  - CORS 配置（Tauri 前端本地访问）
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..application.conversation_service import ConversationService

_CHARACTER_PATH = Path("characters/asuka/personality.yaml")

# 全局服务实例（单例，lifespan 管理）
_service: Optional[ConversationService] = None


def get_service() -> ConversationService:
    """依赖注入函数，路由通过此函数获取 ConversationService 实例。"""
    if _service is None:
        raise RuntimeError("ConversationService 未初始化")
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    global _service
    _service = ConversationService(
        character_path=_CHARACTER_PATH,
        enable_perception=False,  # sidecar 模式下感知由前端事件驱动，暂不启用
    )
    yield
    _service = None  # 清理


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kokoro API",
        description="Kokoro AI 人格伴侣平台 sidecar API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import chat, state, stream
    app.include_router(chat.router)
    app.include_router(state.router)
    app.include_router(stream.router)

    return app


app = create_app()
