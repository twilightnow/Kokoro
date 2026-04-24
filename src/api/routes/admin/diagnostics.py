"""
Diagnostics export API.

The export is intentionally conservative: it includes health/config metadata and
recent client-side diagnostic events, but excludes API keys and chat transcripts.
"""
import os
import platform
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ...service_registry import get_service
from ....application.conversation_service import ConversationService
from .debug import get_client_log_snapshot

router = APIRouter(prefix="/diagnostics")

_SENSITIVE_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_CONFIG_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_MAX_TOKENS",
    "TTS_PROVIDER",
    "TTS_VOICE",
    "TTS_RATE",
    "TTS_VOLUME",
    "KOKORO_DEFAULT_CHARACTER",
    "KOKORO_DATA_DIR",
    "MEMORY_TOKEN_BUDGET",
)


def _safe_env_snapshot() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key in _CONFIG_KEYS:
        value = os.environ.get(key)
        if value is None:
            result[key] = {"is_set": False, "value": ""}
            continue
        if any(marker in key for marker in _SENSITIVE_MARKERS):
            result[key] = {"is_set": bool(value), "value": ""}
        else:
            result[key] = {"is_set": bool(value), "value": value}
    return result


@router.get("/export")
async def export_diagnostics(
    service: ConversationService = Depends(get_service),
) -> JSONResponse:
    llm = getattr(service, "_llm", None)
    payload = {
        "exported_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "app": {
            "name": "Kokoro",
            "version": "0.1.0",
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "sidecar": {
            "status": "ok",
            "character_id": service.character_id,
            "character": service.character.name,
            "turn": service.turn,
        },
        "llm": {
            "provider": str(getattr(llm, "provider", "") or ""),
            "model": str(getattr(llm, "model", "") or ""),
            "configured": bool(getattr(llm, "provider", "") or ""),
        },
        "config": _safe_env_snapshot(),
        "recent_client_logs": get_client_log_snapshot(limit=50),
        "privacy": {
            "includes_api_keys": False,
            "includes_chat_transcripts": False,
            "includes_memory_values": False,
        },
    }
    filename = f"kokoro-diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return JSONResponse(
        payload,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
