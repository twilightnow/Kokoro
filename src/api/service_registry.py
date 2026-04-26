"""
服务注册表 — 单例存储，解耦循环导入。

app.py 负责初始化和写入 _service；路由模块从此处读取，不直接导入 app.py。
"""
import asyncio
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..application.conversation_service import ConversationService
    from ..runtime.companion_runtime import CompanionRuntime

_service: Optional["ConversationService"] = None
_runtime: Optional["CompanionRuntime"] = None


def _env_flag_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_service() -> "ConversationService":
    """FastAPI 依赖注入函数：返回当前 ConversationService 实例。"""
    if _service is None:
        raise RuntimeError("ConversationService 未初始化")
    return _service


def set_service(svc: Optional["ConversationService"]) -> None:
    """由 app.py 的 lifespan 调用，设置/清除全局服务实例。"""
    global _service
    _service = svc


def get_runtime() -> "CompanionRuntime":
    if _runtime is None:
        raise RuntimeError("CompanionRuntime 未初始化")
    return _runtime


def set_runtime(runtime: Optional["CompanionRuntime"]) -> None:
    global _runtime
    _runtime = runtime


async def switch_character(name: str) -> tuple[str, str]:
    """当前会话存档 → 切换到新角色 → 返回 (角色 ID, 显示名称)。"""
    from ..application.conversation_service import ConversationService

    svc = get_service()
    char_path = Path(f"characters/{name}/personality.yaml")
    if not char_path.exists():
        raise ValueError(f"角色不存在: {name}")

    await asyncio.to_thread(svc._on_session_end)

    new_svc = ConversationService(
        character_path=char_path,
        enable_perception=_env_flag_enabled("KOKORO_ENABLE_PERCEPTION"),
    )
    set_service(new_svc)
    return new_svc.character_id, new_svc.character.name
