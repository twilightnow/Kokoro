import json
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


def _model3d_root(character_id: str, manifest: dict[str, Any]) -> Path:
    display = manifest.get("display", {})
    model3d = display.get("model3d", {})
    root_value = model3d.get("root")
    if not isinstance(root_value, str) or not root_value.strip():
        raise ValueError("model3d.root is missing")
    return _resolve_within(_characters_root(), _character_dir(character_id) / root_value)


def _asset_url(character_id: str, asset_path: str, base_url: str) -> str:
    normalized = asset_path.replace("\\", "/")
    return f"{base_url.rstrip('/')}/character-assets/{quote(character_id)}/{quote(normalized)}"


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _vector3(value: Any, default: tuple[float, float, float]) -> dict[str, float]:
    if not isinstance(value, dict):
        return {"x": default[0], "y": default[1], "z": default[2]}
    return {
        "x": _as_float(value.get("x"), default[0]),
        "y": _as_float(value.get("y"), default[1]),
        "z": _as_float(value.get("z"), default[2]),
    }


def resolve_character_asset(character_id: str, asset_path: str) -> Path:
    manifest = load_manifest(character_id)
    display = manifest.get("display", {})
    mode = display.get("mode")
    if mode == "live2d":
        asset_root = _live2d_root(character_id, manifest)
    elif mode == "model3d":
        asset_root = _model3d_root(character_id, manifest)
    else:
        raise ValueError(f"character {character_id} does not expose asset mode: {mode}")
    file_path = _resolve_within(asset_root, asset_root / asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(file_path)
    return file_path


def _build_live2d_display(character_id: str, base_url: str, display: dict[str, Any]) -> dict[str, Any]:
    live2d = display.get("live2d", {})
    asset_root = _live2d_root(character_id, load_manifest(character_id))
    model_file = live2d.get("model")
    if not isinstance(model_file, str) or not model_file.strip():
        return {"mode": "placeholder"}

    model_path = _resolve_within(asset_root, asset_root / model_file)
    if not model_path.exists() or not model_path.is_file():
        return {"mode": "placeholder"}

    return {
        "mode": "live2d",
        "live2d": {
            "model_url": _asset_url(character_id, model_file, base_url),
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


def _build_model3d_display(character_id: str, base_url: str, display: dict[str, Any]) -> dict[str, Any]:
    model3d = display.get("model3d", {})
    asset_root = _model3d_root(character_id, load_manifest(character_id))
    raw_skins = model3d.get("skins", {}) or {}
    if not isinstance(raw_skins, dict):
        return {"mode": "placeholder"}

    skins: dict[str, Any] = {}
    for skin_id, raw_skin in raw_skins.items():
        if not isinstance(raw_skin, dict):
            continue

        scene_file = raw_skin.get("scene")
        if not isinstance(scene_file, str) or not scene_file.strip():
            continue

        scene_path = _resolve_within(asset_root, asset_root / scene_file)
        if not scene_path.exists() or not scene_path.is_file():
            continue

        try:
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue

        if not isinstance(scene, dict):
            continue

        model_file = scene.get("model")
        if not isinstance(model_file, str) or not model_file.strip():
            continue

        model_path = _resolve_within(asset_root, scene_path.parent / model_file)
        if not model_path.exists() or not model_path.is_file():
            continue

        model_relative = model_path.relative_to(asset_root).as_posix()
        camera = scene.get("camera")
        lights = scene.get("lights")

        vmd_url: str | None = None
        vmd_file = scene.get("vmd")
        if isinstance(vmd_file, str) and vmd_file.strip():
            vmd_path = _resolve_within(asset_root, scene_path.parent / vmd_file)
            if vmd_path.exists() and vmd_path.is_file():
                vmd_relative = vmd_path.relative_to(asset_root).as_posix()
                vmd_url = _asset_url(character_id, vmd_relative, base_url)

        mood_vmd_urls: dict[str, str] = {}
        raw_mood_vmds = scene.get("mood_vmds")
        if isinstance(raw_mood_vmds, dict):
            for mood, mood_vmd_file in raw_mood_vmds.items():
                if not isinstance(mood_vmd_file, str) or not mood_vmd_file.strip():
                    continue
                mood_vmd_path = _resolve_within(asset_root, scene_path.parent / mood_vmd_file)
                if mood_vmd_path.exists() and mood_vmd_path.is_file():
                    mood_vmd_relative = mood_vmd_path.relative_to(asset_root).as_posix()
                    mood_vmd_urls[str(mood)] = _asset_url(character_id, mood_vmd_relative, base_url)

        raw_morphs = scene.get("morphs")
        morphs: dict[str, Any] | None = None
        if isinstance(raw_morphs, dict):
            mood_weights: dict[str, list[dict[str, Any]]] = {}
            raw_mood_weights = raw_morphs.get("mood_weights")
            if isinstance(raw_mood_weights, dict):
                for mood, values in raw_mood_weights.items():
                    if not isinstance(values, list):
                        continue
                    normalized_values = []
                    for value in values:
                        if not isinstance(value, dict):
                            continue
                        name = value.get("name")
                        if not isinstance(name, str) or not name.strip():
                            continue
                        normalized_values.append({
                            "name": name,
                            "weight": _as_float(value.get("weight"), 0.0),
                        })
                    if normalized_values:
                        mood_weights[str(mood)] = normalized_values

            raw_lip_sync = raw_morphs.get("lip_sync")
            lip_sync: dict[str, Any] | None = None
            if isinstance(raw_lip_sync, dict):
                raw_names = raw_lip_sync.get("names")
                lip_sync = {
                    "names": [
                        str(name)
                        for name in (raw_names if isinstance(raw_names, list) else [])
                        if isinstance(name, str) and name.strip()
                    ],
                    "max_weight": _as_float(raw_lip_sync.get("max_weight"), 0.75),
                    "smoothing": _as_float(raw_lip_sync.get("smoothing"), 0.22),
                }
                if not lip_sync["names"]:
                    lip_sync = None

            if mood_weights or lip_sync:
                morphs = {}
                if mood_weights:
                    morphs["mood_weights"] = mood_weights
                if lip_sync:
                    morphs["lip_sync"] = lip_sync

        skins[str(skin_id)] = {
            "label": str(raw_skin.get("label") or scene.get("label") or skin_id),
            "model_url": _asset_url(character_id, model_relative, base_url),
            **({"vmd_url": vmd_url} if vmd_url else {}),
            "mood_vmd_urls": mood_vmd_urls,
            "procedural_motion": str(scene.get("procedural_motion") or "idle"),
            "mood_procedural_motions": {
                str(mood): str(mode)
                for mood, mode in (scene.get("mood_procedural_motions") or {}).items()
                if isinstance(mood, str) and isinstance(mode, str) and mode.strip()
            },
            "scale": _as_float(scene.get("scale"), 1.0),
            "position": _vector3(scene.get("position"), (0.0, -10.0, 0.0)),
            "rotation_deg": _vector3(scene.get("rotation_deg"), (0.0, 180.0, 0.0)),
            "camera": {
                "distance": _as_float((camera or {}).get("distance"), 30.0),
                "fov": _as_float((camera or {}).get("fov"), 30.0),
                "target": _vector3((camera or {}).get("target"), (0.0, 10.0, 0.0)),
            },
            "lights": {
                "ambient_intensity": _as_float((lights or {}).get("ambient_intensity"), 0.95),
                "directional_intensity": _as_float((lights or {}).get("directional_intensity"), 1.15),
                "directional_position": _vector3(
                    (lights or {}).get("directional_position"),
                    (5.0, 12.0, 9.0),
                ),
            },
            **({"morphs": morphs} if morphs else {}),
        }

    if not skins:
        return {"mode": "placeholder"}

    requested_order = model3d.get("skin_order")
    ordered_skin_ids: list[str] = []
    if isinstance(requested_order, list):
        ordered_skin_ids.extend(
            str(skin_id) for skin_id in requested_order if str(skin_id) in skins
        )
    ordered_skin_ids.extend(
        skin_id for skin_id in skins.keys() if skin_id not in ordered_skin_ids
    )

    default_skin = str(model3d.get("default_skin") or "")
    if default_skin not in skins:
        default_skin = ordered_skin_ids[0]

    auto_switch = model3d.get("auto_switch", {}) or {}
    mood_skins = auto_switch.get("mood_skins", {}) or {}
    if not isinstance(mood_skins, dict):
        mood_skins = {}

    return {
        "mode": "model3d",
        "model3d": {
            "default_skin": default_skin,
            "skin_order": ordered_skin_ids,
            "auto_switch": {
                "enabled": bool(auto_switch.get("enabled", True)),
                "prefer_manual": bool(auto_switch.get("prefer_manual", True)),
                "mood_skins": {
                    str(mood): str(skin_id)
                    for mood, skin_id in mood_skins.items()
                    if str(skin_id) in skins
                },
            },
            "skins": skins,
        },
    }


def build_character_display(character_id: str, base_url: str) -> dict[str, Any]:
    manifest = load_manifest(character_id)
    display = manifest.get("display", {})
    mode = display.get("mode")
    if mode == "live2d":
        return _build_live2d_display(character_id, base_url, display)
    if mode == "model3d":
        return _build_model3d_display(character_id, base_url, display)

    return {"mode": "placeholder"}
