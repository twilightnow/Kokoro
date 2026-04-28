"""
FastAPI 应用入口。

职责：
  - 定义 lifespan（启动/关闭 ConversationService）
  - 注册路由
  - CORS 配置（Tauri 前端本地访问）
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..application.conversation_service import ConversationService
from ..character_defaults import CHARACTERS_DIR, resolve_default_character_path
from ..runtime.companion_runtime import CompanionRuntime
from .schemas import StreamChunk
from .service_registry import get_service, get_runtime, set_runtime, set_service, switch_character  # noqa: F401 — re-exported
from .stream_manager import get_stream_manager

# 全局服务实例（单例，lifespan 管理）
_CHARACTER_PATH: Optional[Path] = None
_CHARACTERS_DIR: Path = CHARACTERS_DIR


def _resolve_initial_character_path() -> Path:
    if _CHARACTER_PATH is not None:
        return _CHARACTER_PATH
    if _CHARACTERS_DIR != CHARACTERS_DIR:
        if not _CHARACTERS_DIR.exists():
            raise FileNotFoundError(f"角色目录不存在: {_CHARACTERS_DIR}")

        for character_dir in sorted(_CHARACTERS_DIR.iterdir()):
            candidate = character_dir / "personality.yaml"
            if character_dir.is_dir() and candidate.exists():
                return candidate

        raise FileNotFoundError(f"未找到可用角色配置: {_CHARACTERS_DIR}/<id>/personality.yaml")
    return resolve_default_character_path()


def _env_flag_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    svc = ConversationService(
        character_path=_resolve_initial_character_path(),
        enable_perception=_env_flag_enabled("KOKORO_ENABLE_PERCEPTION"),
    )
    runtime = CompanionRuntime(
        get_service=get_service,
        publish=_broadcast_proactive_action,
    )
    set_service(svc)
    set_runtime(runtime)
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()
        await asyncio.to_thread(svc._on_session_end)
        set_service(None)  # 清理
        set_runtime(None)


async def _broadcast_proactive_action(action) -> None:
    chunk = StreamChunk(
        type="proactive",
        content=action.content,
        id=action.id,
        level=action.level,
        scene=action.scene,
        source=action.notify_source,
        urgency=action.urgency,
        expression=action.expression,
        actions=action.actions,
        mood=action.expression,
        emotion=action.metadata.get("emotion") or None,
    )
    await get_stream_manager().broadcast(chunk.model_dump_json())


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
        allow_origin_regex=r"https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import chat, state, stream, tts, notify
    from .routes.admin import router as admin_router
    app.include_router(chat.router)
    app.include_router(state.router)
    app.include_router(stream.router)
    app.include_router(tts.router)
    app.include_router(notify.router)
    app.include_router(admin_router)

    return app


app = create_app()
