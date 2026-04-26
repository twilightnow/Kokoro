"""
人格层单元测试：emotion.py / loader.py / prompt_builder.py

覆盖：情绪触发、衰减、边界情况；角色配置加载与校验；prompt 组装。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.personality.character import CharacterConfig, EmotionProfileConfig, PersonalityConfig
from src.personality.emotion import EmotionEvent, EmotionState, detect_event
from src.personality.loader import load_character, validate_character
from src.personality.prompt_builder import (
    PromptContext,
    build_system_prompt,
    estimate_tokens,
)


# ── 辅助工厂 ──────────────────────────────────────────────────────────────────

def _make_config(**kwargs) -> CharacterConfig:
    defaults = dict(
        name="测试角色",
        forbidden_words=["禁用词A"],
        emotion_triggers={"happy": ["开心"], "angry": ["生气"]},
        mood_expressions={"happy": "很开心", "angry": "很愤怒", "normal": "平静"},
        behavior_rules=["规则一"],
        verbal_habits=["口癖"],
        emotion_profiles={},
        personality=PersonalityConfig(
            core_fear="害怕被遗忘",
            surface_trait="冷漠",
            hidden_trait="渴望关注",
        ),
    )
    defaults.update(kwargs)
    return CharacterConfig(**defaults)


def _make_yaml(tmp_dir: str, data: dict) -> str:
    path = str(Path(tmp_dir) / "test_char.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)
    return path


# ── EmotionState 测试 ─────────────────────────────────────────────────────────

class TestEmotionState(unittest.TestCase):

    def test_initial_state_is_normal(self):
        state = EmotionState()
        self.assertEqual(state.mood, "normal")
        self.assertEqual(state.persist_count, 0)
        self.assertEqual(state.intensity, 0.0)

    def test_trigger_sets_mood_and_persist_count(self):
        state = EmotionState()
        state.trigger("happy")
        self.assertEqual(state.mood, "happy")
        self.assertEqual(state.persist_count, 3)
        self.assertEqual(state.reason, "")
        self.assertAlmostEqual(state.intensity, 0.6)

    def test_trigger_overwrites_existing_mood(self):
        state = EmotionState()
        state.trigger("happy")
        state.trigger("angry")
        self.assertEqual(state.mood, "angry")
        self.assertEqual(state.persist_count, 3)

    def test_decay_decrements_persist_count(self):
        state = EmotionState()
        state.trigger("happy")
        state.decay()
        self.assertEqual(state.mood, "happy")
        self.assertEqual(state.persist_count, 2)

    def test_decay_to_normal_after_three_rounds(self):
        state = EmotionState()
        state.trigger("happy")
        state.decay()
        state.decay()
        state.decay()
        self.assertEqual(state.mood, "normal")
        self.assertEqual(state.persist_count, 0)

    def test_decay_on_normal_state_is_noop(self):
        state = EmotionState()
        state.decay()
        self.assertEqual(state.mood, "normal")
        self.assertEqual(state.persist_count, 0)

    def test_update_with_event_triggers(self):
        state = EmotionState()
        state.update("happy")
        self.assertEqual(state.mood, "happy")
        self.assertEqual(state.persist_count, 3)

    def test_update_without_event_decays(self):
        state = EmotionState()
        state.trigger("happy")
        state.update(None)
        self.assertEqual(state.mood, "happy")
        self.assertEqual(state.persist_count, 2)
        self.assertAlmostEqual(state.intensity, 0.4)

    def test_update_without_event_eventually_returns_to_normal(self):
        state = EmotionState()
        state.trigger("angry")
        for _ in range(3):
            state.update(None)
        self.assertEqual(state.mood, "normal")

    def test_persist_count_does_not_go_negative(self):
        state = EmotionState()
        # normal 状态连续 decay 不应出现负数
        for _ in range(5):
            state.decay()
        self.assertEqual(state.persist_count, 0)

    def test_update_with_structured_event_tracks_reason_and_turn(self):
        state = EmotionState()
        state.update(
            EmotionEvent(
                mood="shy",
                keyword="谢谢你",
                reason="用户提到“谢谢你”",
            ),
            turn=4,
        )

        self.assertEqual(state.mood, "shy")
        self.assertEqual(state.reason, "用户提到“谢谢你”")
        self.assertEqual(state.keyword, "谢谢你")
        self.assertEqual(state.source, "user_input")
        self.assertEqual(state.started_at_turn, 4)
        self.assertEqual(state.duration_turns, 3)
        self.assertEqual(len(state.recent_events), 1)

    def test_manual_state_preserves_requested_persist_count(self):
        state = EmotionState()

        state.set_manual_state("happy", persist_count=8)

        self.assertEqual(state.persist_count, 8)
        self.assertEqual(state.estimated_remaining_turns, 8)
        self.assertAlmostEqual(state.intensity, 1.6)

    def test_timeline_keeps_recent_segments_when_mood_changes(self):
        state = EmotionState()

        state.update(EmotionEvent(mood="happy", keyword="开心", reason="用户提到“开心”"), turn=2)
        state.update(EmotionEvent(mood="angry", keyword="生气", reason="用户提到“生气”", intensity=0.9), turn=3)

        self.assertEqual(state.mood, "angry")
        self.assertEqual(len(state.timeline.segments), 1)
        self.assertEqual(state.timeline.segments[0].mood, "happy")
        self.assertEqual(state.timeline.segments[0].end_reason, "overridden_by:angry")

    def test_timeline_decay_records_elapsed_turns_and_recovers_naturally(self):
        state = EmotionState()
        state.update(
            EmotionEvent(
                mood="happy",
                keyword="开心",
                reason="用户提到“开心”",
                intensity=0.8,
                recovery_rate=0.2,
                profile=EmotionProfileConfig(min_duration_turns=1, max_duration_turns=8),
            ),
            turn=1,
        )

        state.timeline.update(None, turn=2)
        state._sync_from_timeline()
        self.assertEqual(state.elapsed_turns, 1)
        self.assertEqual(state.persist_count, 3)

        state.timeline.update(None, turn=6)
        state._sync_from_timeline()
        self.assertEqual(state.mood, "normal")
        self.assertEqual(state.timeline.segments[-1].end_reason, "recovered")


# ── detect_event 测试 ─────────────────────────────────────────────────────────

class TestDetectEvent(unittest.TestCase):

    _TRIGGERS = {
        "happy": ["开心", "太棒了"],
        "angry": ["生气", "讨厌"],
        "shy":   ["夸", "厉害"],
    }

    def test_detects_matching_keyword(self):
        result = detect_event("今天真的太开心了", self._TRIGGERS)
        self.assertIsNotNone(result)
        self.assertEqual(result.mood, "happy")
        self.assertEqual(result.keyword, "开心")
        self.assertEqual(result.reason, "用户提到“开心”")

    def test_returns_none_when_no_match(self):
        result = detect_event("今天天气不错", self._TRIGGERS)
        self.assertIsNone(result)

    def test_detects_first_matching_emotion(self):
        # triggers 遍历顺序由字典插入顺序决定（Python 3.7+），应返回第一个命中
        result = detect_event("厉害", self._TRIGGERS)
        self.assertIsNotNone(result)
        self.assertEqual(result.mood, "shy")

    def test_empty_input_returns_none(self):
        result = detect_event("", self._TRIGGERS)
        self.assertIsNone(result)

    def test_empty_triggers_returns_none(self):
        result = detect_event("开心", {})
        self.assertIsNone(result)

    def test_keyword_as_substring_matches(self):
        # 触发词以子串匹配，不要求完整单词
        result = detect_event("这件事让我很生气啊", self._TRIGGERS)
        self.assertIsNotNone(result)
        self.assertEqual(result.mood, "angry")

    def test_detect_event_uses_emotion_profile_and_relationship_context(self):
        profiles = {
            "happy": EmotionProfileConfig(base_intensity=0.7, recovery_rate=0.1, stacking=0.5),
        }
        state = EmotionState()
        state.update("happy")

        result = detect_event(
            "今天真的很开心",
            self._TRIGGERS,
            profiles,
            relationship_context={"trust": 80, "intimacy": 60, "familiarity": 70},
            previous_state=state,
        )

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.recovery_rate, 0.1)
        self.assertGreater(result.intensity, 0.7)


# ── validate_character / load_character 测试 ─────────────────────────────────

class TestValidateCharacter(unittest.TestCase):

    def test_valid_config_passes(self):
        config = _make_config()
        validate_character(config)  # 不抛异常

    def test_empty_name_raises(self):
        config = _make_config(name="")
        with self.assertRaises(ValueError) as ctx:
            validate_character(config)
        self.assertIn("name", str(ctx.exception))

    def test_invalid_emotion_triggers_type_raises(self):
        config = _make_config(emotion_triggers=["wrong_type"])
        with self.assertRaises(ValueError) as ctx:
            validate_character(config)
        self.assertIn("emotion_triggers", str(ctx.exception))

    def test_invalid_forbidden_words_type_raises(self):
        config = _make_config(forbidden_words="not_a_list")
        with self.assertRaises(ValueError) as ctx:
            validate_character(config)
        self.assertIn("forbidden_words", str(ctx.exception))

    def test_invalid_mood_expressions_type_raises(self):
        config = _make_config(mood_expressions="not_a_dict")
        with self.assertRaises(ValueError) as ctx:
            validate_character(config)
        self.assertIn("mood_expressions", str(ctx.exception))

    def test_multiple_errors_reported_together(self):
        config = _make_config(name="", forbidden_words="bad")
        with self.assertRaises(ValueError) as ctx:
            validate_character(config)
        msg = str(ctx.exception)
        self.assertIn("name", msg)
        self.assertIn("forbidden_words", msg)


class TestLoadCharacter(unittest.TestCase):

    def test_load_valid_yaml(self):
        data = {
            "name": "测试角色",
            "forbidden_words": ["禁用词"],
            "emotion_triggers": {"happy": ["开心"]},
            "mood_expressions": {"happy": "很开心", "normal": "平静"},
            "behavior_rules": ["规则"],
            "verbal_habits": ["口癖"],
            "personality": {
                "core_fear": "恐惧",
                "surface_trait": "表面",
                "hidden_trait": "内心",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            config = load_character(path)
        self.assertEqual(config.name, "测试角色")
        self.assertEqual(config.personality.core_fear, "恐惧")
        self.assertEqual(config.emotion_triggers, {"happy": ["开心"]})

    def test_missing_name_raises_value_error(self):
        data = {
            "forbidden_words": ["禁用词"],
            "emotion_triggers": {"happy": ["开心"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            with self.assertRaises(ValueError) as ctx:
                load_character(path)
        self.assertIn("name", str(ctx.exception))

    def test_missing_emotion_triggers_raises_value_error(self):
        data = {"name": "角色", "forbidden_words": ["禁用词"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            with self.assertRaises(ValueError) as ctx:
                load_character(path)
        self.assertIn("emotion_triggers", str(ctx.exception))

    def test_missing_forbidden_words_raises_value_error(self):
        data = {"name": "角色", "emotion_triggers": {"happy": ["开心"]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            with self.assertRaises(ValueError) as ctx:
                load_character(path)
        self.assertIn("forbidden_words", str(ctx.exception))

    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_character("/nonexistent/path/char.yaml")

    def test_missing_optional_fields_use_defaults(self):
        data = {
            "name": "简单角色",
            "forbidden_words": [],
            "emotion_triggers": {"happy": ["开心"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            config = load_character(path)
        self.assertEqual(config.behavior_rules, [])
        self.assertEqual(config.verbal_habits, [])
        self.assertEqual(config.version, "")

    def test_load_character_parses_emotion_profiles(self):
        data = {
            "name": "简单角色",
            "forbidden_words": [],
            "emotion_triggers": {"happy": ["开心"]},
            "emotion_profiles": {
                "happy": {
                    "base_intensity": 0.75,
                    "recovery_rate": 0.15,
                    "min_duration_turns": 2,
                    "max_duration_turns": 6,
                    "stacking": 0.4,
                    "tts": {"rate_delta": "+10%", "volume_delta": "+5%"},
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_yaml(tmp, data)
            config = load_character(path)

        self.assertIn("happy", config.emotion_profiles)
        self.assertEqual(config.emotion_profiles["happy"].tts.rate_delta, "+10%")


# ── build_system_prompt 测试 ──────────────────────────────────────────────────

class TestBuildSystemPrompt(unittest.TestCase):

    def _make_ctx(self, mood="normal", **kwargs) -> PromptContext:
        config = _make_config(**kwargs)
        state = EmotionState()
        if mood != "normal":
            state.trigger(mood)
        return PromptContext(character=config, emotion=state)

    def test_prompt_contains_character_name(self):
        ctx = self._make_ctx()
        prompt = build_system_prompt(ctx)
        self.assertIn("测试角色", prompt)

    def test_prompt_contains_forbidden_words(self):
        ctx = self._make_ctx()
        prompt = build_system_prompt(ctx)
        self.assertIn("禁用词A", prompt)

    def test_prompt_contains_behavior_rules(self):
        ctx = self._make_ctx()
        prompt = build_system_prompt(ctx)
        self.assertIn("规则一", prompt)

    def test_prompt_uses_mood_expression_not_raw_mood(self):
        ctx = self._make_ctx(mood="happy")
        prompt = build_system_prompt(ctx)
        # 应注入 mood_expressions["happy"] 的描述，而不是裸写 "happy"
        self.assertIn("很开心", prompt)

    def test_prompt_includes_emotion_reason_and_intensity_hint(self):
        config = _make_config()
        state = EmotionState()
        state.trigger(
            EmotionEvent(
                mood="happy",
                keyword="开心",
                reason="用户提到“开心”",
            ),
            turn=2,
        )

        prompt = build_system_prompt(PromptContext(character=config, emotion=state))

        self.assertIn("强度：中", prompt)
        self.assertIn("原因：用户提到“开心”", prompt)

    def test_prompt_falls_back_to_raw_mood_when_no_expression(self):
        ctx = self._make_ctx(mood="normal", mood_expressions={"happy": "描述"})
        state = EmotionState()  # normal, no expression defined
        ctx2 = PromptContext(character=_make_config(mood_expressions={"happy": "描述"}), emotion=state)
        prompt = build_system_prompt(ctx2)
        # 无 normal 表达时应回退到原始 mood 名
        self.assertIn("normal", prompt)

    def test_prompt_with_memory_context_includes_facts(self):
        from src.memory.context import MemoryContext
        ctx = self._make_ctx()
        ctx.memory = MemoryContext(
            long_term_items={"用户名字": "小明"},
            summary_items=["上次聊了天气"],
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("小明", prompt)
        self.assertIn("上次聊了天气", prompt)

    def test_prompt_keeps_identity_lock_and_typed_memory_sections(self):
        from src.memory.context import MemoryContext

        ctx = self._make_ctx()
        ctx.memory = MemoryContext(
            preference_items={"reply_style": "简短"},
            boundary_items={"sensitive_topic": "不要再提工作细节"},
            event_items={"recent_goal": "本周要完成论文"},
        )

        prompt = build_system_prompt(ctx)

        self.assertIn("身份锁定", prompt)
        self.assertIn("【用户偏好】", prompt)
        self.assertIn("【用户边界】", prompt)
        self.assertIn("【近期重要事件】", prompt)

    def test_prompt_without_memory_is_clean(self):
        ctx = self._make_ctx()
        prompt = build_system_prompt(ctx)
        self.assertNotIn("背景记忆", prompt)

    def test_prompt_returns_string(self):
        ctx = self._make_ctx()
        result = build_system_prompt(ctx)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


# ── estimate_tokens 测试 ──────────────────────────────────────────────────────

class TestEstimateTokens(unittest.TestCase):

    def test_empty_string_returns_one(self):
        self.assertEqual(estimate_tokens(""), 1)

    def test_longer_text_returns_more_tokens(self):
        short = estimate_tokens("你好")
        long = estimate_tokens("你好，今天天气真不错，我们出去走走吧，反正也没什么事情要做。")
        self.assertGreater(long, short)

    def test_result_is_positive(self):
        self.assertGreater(estimate_tokens("test"), 0)

    def test_100_chinese_chars_roughly_67_tokens(self):
        text = "测" * 100
        est = estimate_tokens(text)
        # 100 chars / 1.5 = 66.6 → 66
        self.assertEqual(est, 66)


class TestDefaultCharacterResolution(unittest.TestCase):

    def test_resolve_initial_character_path_picks_valid_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broken").mkdir()
            valid = root / "rei"
            valid.mkdir()
            (valid / "personality.yaml").write_text("name: 丽\nforbidden_words: []\nemotion_triggers: {}\n", encoding="utf-8")

            import src.api.app as app_module

            with patch.object(app_module, "_CHARACTERS_DIR", root):
                with patch.object(app_module, "_CHARACTER_PATH", None):
                    path = app_module._resolve_initial_character_path()

            self.assertEqual(path, valid / "personality.yaml")

    def test_resolve_initial_character_path_prefers_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            override = root / "custom.yaml"
            override.write_text("name: Override\nforbidden_words: []\nemotion_triggers: {}\n", encoding="utf-8")

            import src.api.app as app_module

            with patch.object(app_module, "_CHARACTER_PATH", override):
                path = app_module._resolve_initial_character_path()

            self.assertEqual(path, override)


if __name__ == "__main__":
    unittest.main()
