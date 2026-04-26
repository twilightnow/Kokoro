"""
对话服务：编排主对话循环，连接人格层、记忆层、能力层、日志层。

架构位置：application 层（最高层），依赖所有下层模块，UI/CLI 入口调用此服务。
"""
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

from ..capability.llm import LLMResult, create_llm_client
from ..logger.session_log import SessionLogger
from ..memory.context import MemoryContext
from ..memory.memory_service import MemoryService
from ..perception.context import PerceptionContext
from ..personality.character import CharacterConfig
from ..personality.emotion import EmotionState, detect_event
from ..personality.loader import load_character
from ..personality.prompt_builder import PromptContext, build_system_prompt, estimate_tokens, _PROMPT_TOKEN_WARN, _PROMPT_TOKEN_HARD
from ..runtime.relationship_service import RelationshipService, RelationshipState
from ..safety.policy import SafetyDecision, SafetyPolicy, SafetyRiskLevel

if TYPE_CHECKING:
    from ..perception.collector import PerceptionCollector
    from ..perception.input_tracker import InputTracker


def _check_forbidden(reply: str, forbidden_words: list) -> bool:
    """回复中是否包含禁用词。"""
    return any(word in reply for word in forbidden_words)


def _read_non_negative_env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


class _UnavailableLLM:
    provider = ""
    model = ""

    def __init__(self, message: str) -> None:
        self.message = message

    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> LLMResult:
        raise RuntimeError(self.message)

    def stream_chat(self, system_prompt: str, messages: list[dict[str, str]]):
        raise RuntimeError(self.message)


class ConversationService:
    """对话主循环编排：连接 CLI/UI 与人格、记忆、能力、日志各层。

    此类作为薄编排层，自身不做人格判断，不直接拼接 prompt。
    """

    _MEMORY_TOKEN_BUDGET: int = 500

    def __init__(
        self,
        character_path: Path,
        debug: bool = False,
        data_dir: Optional[Path] = None,
        enable_perception: bool = False,
    ) -> None:
        self._character_path = character_path
        self._character_id = character_path.parent.name
        self._config: CharacterConfig = load_character(character_path)
        self._debug = debug
        self._state = EmotionState()
        self._memory = MemoryService(data_dir)
        self._relationship = RelationshipService(data_dir)
        self._safety = SafetyPolicy()
        self._logger = SessionLogger()
        self._MEMORY_TOKEN_BUDGET = int(os.environ.get("MEMORY_TOKEN_BUDGET", 500))
        try:
            self._llm = create_llm_client()
        except EnvironmentError as e:
            print(f"[警告] LLM 未配置，聊天功能暂不可用: {e}", file=sys.stderr)
            self._llm = _UnavailableLLM(str(e))
        self._turn = 0
        self._last_log_entry: Optional[dict] = None
        self._last_memory_ctx: MemoryContext = MemoryContext()
        self._last_system_prompt: str = ""
        self._session_token_input: int = 0
        self._session_token_output: int = 0
        self._working_memory_truncation_count: int = 0
        self._last_persisted_message_count: int = 0
        self._turns_since_persist: int = 0
        self._last_activity_at: float = time.monotonic()
        self._auto_persist_lock = threading.RLock()
        self._auto_persist_timer: Optional[threading.Timer] = None
        self._memory_idle_seconds: int = _read_non_negative_env_int("KOKORO_MEMORY_IDLE_SECONDS", 900)
        self._memory_settle_turns: int = _read_non_negative_env_int("KOKORO_MEMORY_SETTLE_TURNS", 10)
        self._latest_perception: Optional[PerceptionContext] = None
        self._recent_safety_events: list[dict[str, Any]] = []

        # 感知层（可选）：仅采集最新感知快照注入 prompt，不再负责轮间主动开口
        self._perception_collector: Optional["PerceptionCollector"] = None
        self._input_tracker: Optional["InputTracker"] = None

        if enable_perception:
            self._init_perception()

    def _init_perception(self) -> None:
        """初始化感知采集器。导入失败时静默降级。"""
        try:
            from ..perception.input_tracker import InputTracker
            from ..perception.window_monitor import WindowMonitor
            from ..perception.collector import PerceptionCollector

            tracker = InputTracker()
            tracker.start()
            monitor = WindowMonitor()
            self._perception_collector = PerceptionCollector(tracker, monitor)
            self._input_tracker = tracker
        except Exception as e:
            print(f"[警告] 感知层初始化失败，已降级: {e}", file=sys.stderr)

    @property
    def character(self) -> CharacterConfig:
        return self._config

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def character_path(self) -> Path:
        return self._character_path

    @property
    def character_state(self) -> EmotionState:
        return self._state

    @property
    def current_emotion_summary(self):
        return self._state.emotion_summary

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def relationship_state(self) -> RelationshipState:
        return self._relationship.get_state(self._character_id)

    @property
    def relationship_service(self) -> RelationshipService:
        return self._relationship

    @property
    def last_log_entry(self) -> Optional[dict]:
        """返回最近一条日志记录（用于 API 层取 flagged/usage 等信息）。"""
        return self._last_log_entry

    @property
    def recent_safety_events(self) -> list[dict[str, Any]]:
        """返回最近安全事件摘要，不包含原始用户危机文本。"""
        return list(self._recent_safety_events)

    @property
    def memory_context(self) -> MemoryContext:
        """返回最近一次 get_context() 的缓存结果。"""
        return self._last_memory_ctx

    @property
    def last_system_prompt(self) -> str:
        """返回最近一次发送给 LLM 的完整 system prompt。"""
        return self._last_system_prompt

    @property
    def session_token_total(self) -> dict:
        """本次会话累计 token 用量。"""
        return {
            "input": self._session_token_input,
            "output": self._session_token_output,
        }

    @property
    def working_memory_message_count(self) -> int:
        """当前工作记忆消息条数。"""
        return len(self._memory.working_memory)

    @property
    def working_memory_truncation_count(self) -> int:
        """本次会话工作记忆截断累计次数。"""
        return self._working_memory_truncation_count

    @property
    def working_memory_messages(self) -> list[dict[str, str]]:
        """返回当前工作记忆中的完整消息列表。"""
        return self._memory.working_memory.get_messages()

    def get_token_history(self) -> list[dict[str, Any]]:
        """返回当前会话内已记录的 token 使用历史。"""
        history: list[dict[str, Any]] = []
        for record in self._logger.records:
            usage = record.get("usage")
            if not usage:
                continue
            history.append({
                "turn": int(record.get("turn", 0)),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "provider": str(usage.get("provider", "")),
                "model": str(usage.get("model", "")),
            })
        return history

    def clear_working_memory(self) -> int:
        """清空工作记忆，重置本轮对话上下文缓存。"""
        current_size = len(self._memory.working_memory)
        self._cancel_auto_persist_timer()
        self._memory.working_memory.clear()
        self._last_memory_ctx = MemoryContext()
        self._last_system_prompt = ""
        self._last_log_entry = None
        self._last_persisted_message_count = 0
        self._turns_since_persist = 0
        return current_size

    def flush_pending_memory(self) -> bool:
        """将上次结算后新增的消息刷入摘要/长期记忆。"""
        return self._persist_pending_memory()

    def reload_character_config(self) -> CharacterConfig:
        """重新读取当前角色配置文件，不重置会话状态。"""
        self._config = load_character(self._character_path)
        return self._config

    def set_perception_context(self, perception_ctx: Optional[PerceptionContext]) -> None:
        """设置最近一次感知快照，供 prompt 注入与后台主动陪伴复用。"""
        self._latest_perception = perception_ctx

    def run(self) -> None:
        """启动交互式对话循环（阻塞直到用户退出）。"""
        config = self._config
        print(f"=== {config.name} ===")
        print("对话开始。输入 'quit' 或 'exit' 结束。")
        if self._debug:
            print("[DEBUG] 调试模式已启用")
        print()

        try:
            while True:
                try:
                    user_input = input("你: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "退出", "再见"):
                    break

                reply = self.handle_turn(user_input)
                if reply is None:
                    break
                print(f"{config.name}: {reply}")
                print()
        finally:
            self._on_session_end()
            self._logger.print_summary()

    def handle_turn(self, user_input: str) -> Optional[str]:
        """处理单轮对话，返回角色回复文本；LLM 调用出错时返回 None。

        此方法可供测试直接调用，无需走完整的 run() 循环。
        """
        input_safety = self._safety.evaluate_input(user_input, self.relationship_state)
        if input_safety.level == SafetyRiskLevel.CRISIS:
            return self._handle_safety_short_circuit(input_safety)

        system_prompt, mood_before = self._prepare_turn(user_input, input_safety)
        try:
            result: LLMResult = self._llm.chat(
                system_prompt,
                self._memory.working_memory.get_messages(),
            )
        except RuntimeError as e:
            print(f"错误: {e}", file=sys.stderr)
            return None
        return self._finalize_turn(user_input, mood_before, result)

    def handle_turn_stream(
        self,
        user_input: str,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """处理单轮对话，并在回复生成过程中通过回调输出增量 token。"""
        input_safety = self._safety.evaluate_input(user_input, self.relationship_state)
        if input_safety.level == SafetyRiskLevel.CRISIS:
            reply = self._handle_safety_short_circuit(input_safety)
            if on_token:
                on_token(reply)
            return reply

        system_prompt, mood_before = self._prepare_turn(user_input, input_safety)
        parts: list[str] = []

        try:
            stream = self._llm.stream_chat(
                system_prompt,
                self._memory.working_memory.get_messages(),
            )
            while True:
                try:
                    token = next(stream)
                except StopIteration as stop:
                    result = stop.value
                    break
                if not token:
                    continue
                parts.append(token)
                if on_token:
                    on_token(token)
        except RuntimeError as e:
            print(f"错误: {e}", file=sys.stderr)
            return None

        if result is None:
            result = LLMResult(
                text="".join(parts).strip(),
                model=getattr(self._llm, "model", ""),
                provider=getattr(self._llm, "provider", ""),
            )
        elif not result.text:
            result.text = "".join(parts).strip()

        return self._finalize_turn(user_input, mood_before, result)

    def _prepare_turn(
        self,
        user_input: str,
        safety_decision: Optional[SafetyDecision] = None,
    ) -> tuple[str, str]:
        if safety_decision is None:
            safety_decision = self._safety.evaluate_input(user_input, self.relationship_state)
        self._turn += 1
        config = self._config
        mood_before = self._state.mood

        event = detect_event(
            user_input,
            config.emotion_triggers,
            config.emotion_profiles,
            relationship_context=self.relationship_state,
            previous_state=self._state,
        )
        self._state.update(event, turn=self._turn)
        mood_after = self._state.mood

        wm = self._memory.working_memory
        if wm.would_truncate():
            self._persist_pending_memory()
        prev_len = len(wm)
        wm.truncate()
        if self._last_persisted_message_count > len(wm):
            self._last_persisted_message_count = len(wm)
        if len(wm) < prev_len:
            self._working_memory_truncation_count += 1
        wm.add("user", user_input)

        character_id = self._character_id
        memory_ctx = self._memory.get_context(character_id, token_budget=self._MEMORY_TOKEN_BUDGET)
        self._last_memory_ctx = memory_ctx

        perception_ctx = self._collect_perception_context()

        prompt_ctx = PromptContext(
            character=config,
            emotion=self._state,
            memory=memory_ctx,
            perception=perception_ctx,
            relationship_summary=self._relationship.summary_for_prompt(character_id),
            safety_notice=safety_decision.prompt_notice,
        )
        system_prompt = build_system_prompt(prompt_ctx)
        self._last_system_prompt = system_prompt

        if self._debug:
            mood_label = (
                f"{mood_before} → {mood_after}"
                if mood_before != mood_after
                else mood_before
            )
            print(f"[DEBUG] mood: {mood_label}（persist={self._state.persist_count}）")
            token_est = estimate_tokens(system_prompt)
            token_warn = ""
            if token_est >= _PROMPT_TOKEN_HARD:
                token_warn = "  ⚠⚠ 超出硬限制，建议精简角色配置"
            elif token_est >= _PROMPT_TOKEN_WARN:
                token_warn = "  ⚠ 较长，建议检查角色配置"
            print(f"[DEBUG] system prompt: ~{token_est} tokens{token_warn}")
            print(f"[DEBUG] system prompt（前200字）: {system_prompt[:200]}...")
            print(f"[DEBUG] history 长度: {len(wm)} 条")

        return system_prompt, mood_before

    def _collect_perception_context(self) -> Optional[PerceptionContext]:
        """返回当前可用的感知快照。

        CLI 的 `--perception` 只负责按轮采集一次快照注入 prompt；
        sidecar 模式则由后台 runtime 通过 `set_perception_context()` 推送最新快照。
        """
        if self._perception_collector is not None:
            try:
                perception_ctx = self._perception_collector.collect()
            except Exception:
                return self._latest_perception
            self._latest_perception = perception_ctx
            return perception_ctx
        return self._latest_perception

    def _finalize_turn(self, user_input: str, mood_before: str, result: LLMResult) -> str:
        output_safety = self._safety.evaluate_output(result.text, self.relationship_state)
        reply = output_safety.safe_reply if output_safety.action == "replace_reply" else result.text
        self._memory.working_memory.add("assistant", reply)
        self._session_token_input += result.input_tokens
        self._session_token_output += result.output_tokens

        flagged = _check_forbidden(reply, self._config.forbidden_words)
        usage = None
        if result.input_tokens or result.output_tokens:
            usage = {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "model": result.model,
                "provider": result.provider,
            }
        safety_summary = output_safety.to_summary() if output_safety.triggered else None

        self._logger.log(
            turn=self._turn,
            user_input=user_input,
            mood_before=mood_before,
            mood_after=self._state.mood,
            persist_count=self._state.persist_count,
            reply=reply,
            flagged=flagged,
            usage=usage,
            safety=safety_summary,
        )
        if safety_summary:
            self._record_safety_event(safety_summary)
        self._last_log_entry = {"flagged": flagged, "usage": usage, "safety": safety_summary}
        self._relationship.record_interaction(
            self._character_id,
            user_input=user_input,
            reply=reply,
            flagged=flagged,
            turn=self._turn,
        )

        self._turns_since_persist += 1
        self._last_activity_at = time.monotonic()
        auto_persisted = False
        if self._memory_settle_turns > 0 and self._turns_since_persist >= self._memory_settle_turns:
            auto_persisted = self._persist_pending_memory()
        if not auto_persisted:
            self._schedule_idle_persist()

        if self._debug:
            if flagged:
                print("[DEBUG] ⚠ 回复中出现禁用词")
            if safety_summary:
                print(f"[DEBUG] safety: {safety_summary['level']} / {safety_summary['action']}")
            if usage:
                print(
                    f"[DEBUG] usage: in={usage['input_tokens']} "
                    f"out={usage['output_tokens']} "
                    f"({usage['provider']}/{usage['model']})"
                )

        return reply

    def _handle_safety_short_circuit(self, decision: SafetyDecision) -> str:
        self._turn += 1
        reply = decision.safe_reply
        safety_summary = decision.to_summary()
        self._logger.log(
            turn=self._turn,
            user_input="[safety_redacted]",
            mood_before=self._state.mood,
            mood_after=self._state.mood,
            persist_count=self._state.persist_count,
            reply=reply,
            flagged=False,
            usage=None,
            safety=safety_summary,
        )
        self._record_safety_event(safety_summary)
        self._last_log_entry = {"flagged": False, "usage": None, "safety": safety_summary}
        self._turns_since_persist = 0
        self._last_activity_at = time.monotonic()
        if self._debug:
            print(f"[DEBUG] safety: {safety_summary['level']} / {safety_summary['action']}")
        return reply

    def _record_safety_event(self, summary: dict[str, Any]) -> None:
        event = {
            "turn": self._turn,
            "level": summary.get("level", "none"),
            "action": summary.get("action", ""),
            "reason": summary.get("reason", ""),
            "rule_names": list(summary.get("rule_names", [])),
            "relationship_type": summary.get("relationship_type", ""),
        }
        self._recent_safety_events = (self._recent_safety_events + [event])[-20:]

    def _cancel_auto_persist_timer_locked(self) -> None:
        timer = self._auto_persist_timer
        self._auto_persist_timer = None
        if timer is not None:
            timer.cancel()

    def _cancel_auto_persist_timer(self) -> None:
        with self._auto_persist_lock:
            self._cancel_auto_persist_timer_locked()

    def _persist_pending_memory(self) -> bool:
        with self._auto_persist_lock:
            self._cancel_auto_persist_timer_locked()
            history = self._memory.working_memory.get_messages()
            start_index = min(self._last_persisted_message_count, len(history))
            pending_history = history[start_index:]
            if not pending_history:
                return False

            self._memory.on_session_end(
                character_id=self._character_id,
                history=pending_history,
                llm_chat_fn=self._llm.chat,
            )
            self._last_persisted_message_count = len(history)
            self._turns_since_persist = 0
            return True

    def _schedule_idle_persist(self) -> None:
        if self._memory_idle_seconds <= 0:
            return

        with self._auto_persist_lock:
            if self._last_persisted_message_count >= len(self._memory.working_memory):
                return
            self._cancel_auto_persist_timer_locked()
            timer = threading.Timer(self._memory_idle_seconds, self._handle_idle_timeout)
            timer.daemon = True
            self._auto_persist_timer = timer
            timer.start()

    def _handle_idle_timeout(self) -> None:
        with self._auto_persist_lock:
            self._auto_persist_timer = None
            if self._memory_idle_seconds <= 0:
                return
            if time.monotonic() - self._last_activity_at < self._memory_idle_seconds:
                return

        self._persist_pending_memory()

    def generate_proactive_reply(
        self,
        scene: str,
        style_hint: str,
        scene_context: str | None = None,
    ) -> Optional[str]:
        """生成不进入普通 turn 的主动短句。"""
        relationship_summary = self._relationship.summary_for_prompt(self._character_id)

        system = build_system_prompt(PromptContext(
            character=self._config,
            emotion=self._state,
            perception=self._latest_perception,
            relationship_summary=relationship_summary,
            safety_notice=self._safety.prompt_notice(self.relationship_state),
        ))
        synthetic_message = [
            {
                "role": "user",
                "content": (
                    f"【主动陪伴场景】{scene}。"
                    f"【角色意图】{style_hint or '自然地主动关心用户'}。"
                    f"【附加上下文】{scene_context or '无'}。"
                    "请用角色口吻主动开口，限制在两句以内，不要写成长对话，不要解释系统设定。"
                ),
            }
        ]
        try:
            result = self._llm.chat(system, synthetic_message)
            reply = result.text.strip()
            return reply or None
        except Exception:
            return None

    def _on_session_end(self) -> None:
        """会话结束钩子：生成摘要并保存到记忆层，停止感知追踪。"""
        self._cancel_auto_persist_timer()
        if self._input_tracker:
            try:
                self._input_tracker.stop()
            except Exception:
                pass
        self._persist_pending_memory()
