import os
import sys
from pathlib import Path


def _default_characters_dir() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        candidate = Path(bundled_root) / "characters"
        if candidate.exists():
            return candidate
    return Path("characters")


CHARACTERS_DIR = _default_characters_dir()
DEFAULT_CHARACTER_ENV = "KOKORO_DEFAULT_CHARACTER"


def iter_character_ids() -> list[str]:
    if not CHARACTERS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in CHARACTERS_DIR.iterdir()
        if path.is_dir() and (path / "personality.yaml").exists()
    )


def resolve_character_path(character_id: str) -> Path:
    return CHARACTERS_DIR / character_id / "personality.yaml"


def get_configured_default_character_id() -> str | None:
    value = os.environ.get(DEFAULT_CHARACTER_ENV, "").strip()
    return value or None


def get_effective_default_character_id() -> str | None:
    configured = get_configured_default_character_id()
    available = iter_character_ids()
    if configured and configured in available:
        return configured
    if available:
        return available[0]
    return None


def resolve_default_character_path() -> Path:
    if not CHARACTERS_DIR.exists():
        raise FileNotFoundError(f"角色目录不存在: {CHARACTERS_DIR}")

    character_id = get_effective_default_character_id()
    if character_id is None:
        raise FileNotFoundError(f"未找到可用角色配置: {CHARACTERS_DIR}/<id>/personality.yaml")

    return resolve_character_path(character_id)
