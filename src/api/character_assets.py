from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml


_CHARACTERS_DIR = Path("characters")


def _characters_root() -> Path:
    return _CHARACTERS_DIR.resolve()


def _character_dir(character_id: str) -> Path:
    return (_CHARACTERS_DIR / character_id).resolve()


def _is_within(root: Path, target: Path) -> bool:
    return target == root or root in target.parents


def _resolve_within(root: Path, target: Path) -> Path:
    resolved = target.resolve()
    if not _is_within(root, resolved):
        raise ValueError(f"path escapes characters root: {resolved}")
    return resolved


def load_manifest(character_id: str) -> dict[str, Any]:
    manifest_path = _character_dir(character_id) / "manifest.yaml"
    if not manifest_path.exists():
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _live2d_root(character_id: str, manifest: dict[str, Any]) -> Path:
    display = manifest.get("display", {})
    live2d = display.get("live2d", {})
    root_value = live2d.get("root")
    if not isinstance(root_value, str) or not root_value.strip():
        raise ValueError("live2d.root is missing")
    return _resolve_within(_characters_root(), _character_dir(character_id) / root_value)


def resolve_live2d_asset(character_id: str, asset_path: str) -> Path:
    manifest = load_manifest(character_id)
    asset_root = _live2d_root(character_id, manifest)
    file_path = _resolve_within(asset_root, asset_root / asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(file_path)
    return file_path


def build_character_display(character_id: str, base_url: str) -> dict[str, Any]:
    manifest = load_manifest(character_id)
    display = manifest.get("display", {})
    if display.get("mode") != "live2d":
        return {"mode": "placeholder"}

    live2d = display.get("live2d", {})
    asset_root = _live2d_root(character_id, manifest)
    model_file = live2d.get("model")
    if not isinstance(model_file, str) or not model_file.strip():
        return {"mode": "placeholder"}

    model_path = _resolve_within(asset_root, asset_root / model_file)
    if not model_path.exists() or not model_path.is_file():
        return {"mode": "placeholder"}

    asset_url = f"{base_url.rstrip('/')}/character-assets/{quote(character_id)}/{quote(model_file.replace('\\', '/'))}"
    return {
        "mode": "live2d",
        "live2d": {
            "model_url": asset_url,
            "scale": float(live2d.get("scale", 1.0)),
            "offset_x": float(live2d.get("offset_x", 0)),
            "offset_y": float(live2d.get("offset_y", 0)),
            "idle_group": str(live2d.get("idle_group", "Idle")),
            "tap_body_group": str(live2d.get("tap_body_group", "Tap@Body")),
            "mood_motions": {
                str(key): str(value)
                for key, value in (live2d.get("mood_motions", {}) or {}).items()
            },
        },
    }
