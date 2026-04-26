"""
.env configuration management API.

GET  /admin/config
PUT  /admin/config
POST /admin/config/reload
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...service_registry import get_service
from ....application.conversation_service import ConversationService
from ....capability.llm import create_llm_client

router = APIRouter(prefix="/config")

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).resolve().parent
else:
    _ROOT = Path(__file__).resolve().parents[4]
_ENV_PATH = _ROOT / ".env"
_SENSITIVE_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "LLM_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "COPILOT_GITHUB_TOKEN",
}
_RESTART_REQUIRED_KEYS = {
    "KOKORO_DATA_DIR",
    "KOKORO_DEFAULT_CHARACTER",
    "KOKORO_ENABLE_PERCEPTION",
}
_KNOWN_DEFAULTS = {
    "LLM_PROVIDER": "",
    "LLM_MODEL": "",
    "LLM_MAX_TOKENS": "300",
    "PRICE_INPUT": "",
    "PRICE_OUTPUT": "",
    "TTS_PROVIDER": "edge-tts",
    "TTS_VOICE": "zh-CN-XiaoxiaoNeural",
    "TTS_RATE": "+0%",
    "TTS_VOLUME": "+0%",
    "KOKORO_DEFAULT_CHARACTER": "",
    "KOKORO_DATA_DIR": "./data",
    "MEMORY_TOKEN_BUDGET": "500",
    "KOKORO_START_ON_BOOT": "0",
    "KOKORO_ALWAYS_ON_TOP": "1",
    "KOKORO_ENABLE_PERCEPTION": "0",
}


class ConfigEntry(BaseModel):
    key: str
    value: str
    is_sensitive: bool = False
    is_set: bool = True


class ConfigResponse(BaseModel):
    entries: List[ConfigEntry]
    env_path: str


class ConfigUpdateRequest(BaseModel):
    updates: Dict[str, str]


def _read_env_file() -> Dict[str, str]:
    if not _ENV_PATH.exists():
        return {}

    result: Dict[str, str] = {}
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _write_env_file(updates: Dict[str, str]) -> None:
    existing_lines: List[str] = []
    if _ENV_PATH.exists():
        existing_lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated_keys = set()
    new_lines: List[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                value = updates[key]
                updated_keys.add(key)
                if value == "":
                    continue
                new_lines.append(f"{key}={value}")
                continue
        new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys and value != "":
            new_lines.append(f"{key}={value}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    env_data = _read_env_file()
    entries: List[ConfigEntry] = []
    merged_keys = list(dict.fromkeys([*env_data.keys(), *_KNOWN_DEFAULTS.keys()]))
    for key in merged_keys:
        value = env_data.get(key, _KNOWN_DEFAULTS.get(key, ""))
        if key in _SENSITIVE_KEYS:
            entries.append(
                ConfigEntry(key=key, value="", is_sensitive=True, is_set=bool(value))
            )
        else:
            entries.append(
                ConfigEntry(key=key, value=value, is_sensitive=False, is_set=True)
            )
    return ConfigResponse(entries=entries, env_path=str(_ENV_PATH.absolute()))


@router.put("", status_code=200)
async def update_config(body: ConfigUpdateRequest) -> Dict[str, Any]:
    existing = _read_env_file()
    changed_keys = [
        key
        for key, value in body.updates.items()
        if existing.get(key, _KNOWN_DEFAULTS.get(key, "")) != value
    ]
    _write_env_file(body.updates)
    restart_needed = bool(set(changed_keys) & _RESTART_REQUIRED_KEYS)
    return {
        "status": "saved",
        "restart_required": restart_needed,
        "updated_keys": changed_keys,
    }


@router.post("/reload", status_code=200)
async def reload_config(
    service: ConversationService = Depends(get_service),
) -> Dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=_ENV_PATH, override=True)

    applied: List[str] = []

    current_llm = getattr(service, "_llm", None)
    prev_provider = getattr(current_llm, "provider", None)
    prev_model = getattr(current_llm, "model", None)

    try:
        new_llm = create_llm_client()
    except EnvironmentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    service._llm = new_llm
    if getattr(new_llm, "provider", None) != prev_provider:
        applied.append("LLM_PROVIDER")
    if getattr(new_llm, "model", None) != prev_model:
        applied.append("LLM_MODEL")

    budget_str = os.environ.get("MEMORY_TOKEN_BUDGET")
    if budget_str:
        try:
            service._MEMORY_TOKEN_BUDGET = int(budget_str)
            applied.append("MEMORY_TOKEN_BUDGET")
        except ValueError:
            pass

    max_tokens_str = os.environ.get("LLM_MAX_TOKENS")
    if max_tokens_str:
        try:
            int(max_tokens_str)
            applied.append("LLM_MAX_TOKENS")
        except ValueError:
            pass

    return {"status": "ok", "applied": applied}


@router.post("/test-llm", status_code=200)
async def test_llm_config() -> Dict[str, Any]:
    try:
        client = create_llm_client()
    except EnvironmentError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "status": "ok",
        "provider": getattr(client, "provider", ""),
        "model": getattr(client, "model", ""),
    }
