"""
FastAPI 应用入口。

职责：
  - 定义 lifespan（启动/关闭 ConversationService）
  - 注册路由
  - CORS 配置（Tauri 前端本地访问）
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..application.conversation_service import ConversationService
from ..character_defaults import resolve_default_character_path
from .service_registry import get_service, set_service, switch_character  # noqa: F401 — re-exported

# 全局服务实例（单例，lifespan 管理）
_CHARACTER_PATH: Optional[Path] = None


def _resolve_initial_character_path() -> Path:
    if _CHARACTER_PATH is not None:
        return _CHARACTER_PATH
    return resolve_default_character_path()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    svc = ConversationService(
        character_path=_resolve_initial_character_path(),
        enable_perception=False,
    )
    set_service(svc)
    yield
    set_service(None)  # 清理


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
            "http://localhost:5173",   # Vite dev server
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import chat, state, stream
    from .routes.admin import router as admin_router
    app.include_router(chat.router)
    app.include_router(state.router)
    app.include_router(stream.router)
    app.include_router(admin_router)

    return app


app = create_app()
