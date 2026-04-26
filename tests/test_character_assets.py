import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.character_assets import build_character_display, resolve_character_asset, validate_character_manifest


class TestCharacterAssets(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.characters_root = Path(self.tmp.name) / "characters"
        self.character_dir = self.characters_root / "firefly"
        (self.character_dir / "assets" / "model3d" / "base").mkdir(parents=True)
        (self.character_dir / "assets" / "model3d" / "combat").mkdir(parents=True)

        manifest = {
            "display": {
                "mode": "model3d",
                "model3d": {
                    "root": "assets/model3d",
                    "default_skin": "base",
                    "skin_order": ["base", "combat"],
                    "auto_switch": {
                        "enabled": True,
                        "prefer_manual": True,
                        "mood_skins": {
                            "happy": "base",
                            "angry": "combat",
                        },
                    },
                    "skins": {
                        "base": {
                            "label": "常态流萤",
                            "scene": "base/scene.json",
                        },
                        "combat": {
                            "label": "萨姆装甲",
                            "scene": "combat/scene.json",
                        },
                    },
                },
            },
        }
        (self.character_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        base_scene = {
            "model": "firefly-base.pmx",
            "scale": 0.084,
            "position": {"x": 0, "y": -11, "z": 0},
            "rotation_deg": {"x": 0, "y": 180, "z": 0},
            "camera": {
                "distance": 31,
                "fov": 28,
                "target": {"x": 0, "y": 10, "z": 0},
            },
            "lights": {
                "ambient_intensity": 0.92,
                "directional_intensity": 1.18,
                "directional_position": {"x": 5, "y": 12, "z": 9},
            },
        }
        combat_scene = {
            "model": "firefly-combat.pmx",
        }
        (self.character_dir / "assets" / "model3d" / "base" / "scene.json").write_text(
            json.dumps(base_scene, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.character_dir / "assets" / "model3d" / "combat" / "scene.json").write_text(
            json.dumps(combat_scene, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.character_dir / "assets" / "model3d" / "base" / "firefly-base.pmx").write_text(
            "pmx",
            encoding="utf-8",
        )
        (self.character_dir / "assets" / "model3d" / "combat" / "firefly-combat.pmx").write_text(
            "pmx",
            encoding="utf-8",
        )

        self.characters_patch = patch("src.api.character_assets._CHARACTERS_DIR", self.characters_root)
        self.characters_patch.start()

    def tearDown(self):
        self.characters_patch.stop()
        self.tmp.cleanup()

    def test_build_character_display_returns_model3d_config(self):
        display = build_character_display("firefly", "http://localhost:18765")

        self.assertEqual(display["mode"], "model3d")
        self.assertEqual(display["model3d"]["default_skin"], "base")
        self.assertEqual(display["model3d"]["skin_order"], ["base", "combat"])
        self.assertEqual(display["model3d"]["auto_switch"]["mood_skins"]["angry"], "combat")
        self.assertEqual(
            display["model3d"]["skins"]["base"]["model_url"],
            "http://localhost:18765/character-assets/firefly/base/firefly-base.pmx",
        )
        self.assertEqual(display["model3d"]["skins"]["base"]["camera"]["distance"], 31.0)

    def test_resolve_character_asset_supports_model3d(self):
        path = resolve_character_asset("firefly", "combat/firefly-combat.pmx")

        self.assertTrue(path.exists())
        self.assertEqual(path.name, "firefly-combat.pmx")

    def test_build_character_display_falls_back_to_image(self):
        manifest = {
            "display": {
                "mode": "live2d",
                "live2d": {
                    "root": "live2d/runtime",
                    "model": "missing.model3.json",
                },
                "image": {
                    "root": "assets/portrait",
                    "file": "idle.png",
                    "scale": 1.1,
                },
            },
        }
        (self.character_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (self.character_dir / "assets" / "portrait").mkdir(parents=True, exist_ok=True)
        (self.character_dir / "assets" / "portrait" / "idle.png").write_text("png", encoding="utf-8")

        display = build_character_display("firefly", "http://localhost:18765")
        validation = validate_character_manifest("firefly")

        self.assertEqual(display["mode"], "image")
        self.assertEqual(validation["resolved_mode"], "image")
        self.assertTrue(validation["warnings"])

    def test_resolve_character_asset_uses_fallback_image_root(self):
        manifest = {
            "display": {
                "mode": "live2d",
                "live2d": {
                    "root": "live2d/runtime",
                    "model": "missing.model3.json",
                },
                "image": {
                    "root": "assets/portrait",
                    "file": "idle.png",
                },
            },
        }
        (self.character_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (self.character_dir / "assets" / "portrait").mkdir(parents=True, exist_ok=True)
        (self.character_dir / "assets" / "portrait" / "idle.png").write_text("png", encoding="utf-8")

        path = resolve_character_asset("firefly", "idle.png")

        self.assertTrue(path.exists())
        self.assertEqual(path.name, "idle.png")


if __name__ == "__main__":
    unittest.main()