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

# 全局服务实例（单例，lifespan 管理）
_service: Optional[ConversationService] = None
_CHARACTERS_DIR = Path("characters")
_CHARACTER_PATH: Optional[Path] = None


def _resolve_initial_character_path() -> Path:
    if _CHARACTER_PATH is not None:
        return _CHARACTER_PATH

    if not _CHARACTERS_DIR.exists():
        raise FileNotFoundError(f"角色目录不存在: {_CHARACTERS_DIR}")

    candidates = sorted(
        path / "personality.yaml"
        for path in _CHARACTERS_DIR.iterdir()
        if path.is_dir() and (path / "personality.yaml").exists()
    )
    if not candidates:
        raise FileNotFoundError(f"未找到可用角色配置: {_CHARACTERS_DIR}/<id>/personality.yaml")
    return candidates[0]


def get_service() -> ConversationService:
    """依赖注入函数，路由通过此函数获取 ConversationService 实例。"""
    if _service is None:
        raise RuntimeError("ConversationService 未初始化")
    return _service


async def switch_character(name: str) -> tuple[str, str]:
    """当前会话存档 → 切换到新角色 → 返回 (角色 ID, 显示名称)。"""
    global _service
    if _service is None:
        raise RuntimeError("ConversationService 未初始化")

    char_path = Path(f"characters/{name}/personality.yaml")
    if not char_path.exists():
        raise ValueError(f"角色不存在: {name}")

    # 保存当前会话摘要（同步操作，放到线程池避免阻塞事件循环）
    await asyncio.to_thread(_service._on_session_end)

    # 重新初始化
    _service = ConversationService(character_path=char_path, enable_perception=False)
    return _service.character_id, _service.character.name


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    global _service
    _service = ConversationService(
        character_path=_resolve_initial_character_path(),
        enable_perception=False,
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
            "http://localhost:5173",   # Vite dev server
            "http://127.0.0.1:5173",
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
