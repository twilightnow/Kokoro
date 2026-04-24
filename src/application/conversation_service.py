"""
对话服务：编排主对话循环，连接人格层、记忆层、能力层、日志层。

架构位置：application 层（最高层），依赖所有下层模块，UI/CLI 入口调用此服务。
"""
import os
import sys
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from ..capability.llm import LLMResult, create_llm_client
from ..logger.session_log import SessionLogger
from ..memory.context import MemoryContext
from ..memory.memory_service import MemoryService
from ..perception.context import PerceptionContext
from ..personality.character import CharacterConfig
from ..personality.emotion import EmotionState, detect_event
from ..personality.loader import load_character
from ..personality.prompt_builder import PromptContext, build_system_prompt, estimate_tokens, _PROMPT_TOKEN_WARN, _PROMPT_TOKEN_HARD

if TYPE_CHECKING:
    from ..perception.engine import ProactiveEngine
    from ..perception.perception_log import PerceptionLog
    from ..perception.event import ProactiveEvent
    from ..perception.input_tracker import InputTracker


def _check_forbidden(reply: str, forbidden_words: list) -> bool:
    """回复中是否包含禁用词。"""
    return any(word in reply for word in forbidden_words)


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
        self._character_id = character_path.parent.name
        self._config: CharacterConfig = load_character(character_path)
        self._debug = debug
        self._state = EmotionState()
        self._memory = MemoryService(data_dir)
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

        # 感知层（可选）
        self._proactive_engine: Optional["ProactiveEngine"] = None
        self._perception_log: Optional["PerceptionLog"] = None
        self._input_tracker: Optional["InputTracker"] = None

        if enable_perception:
            self._init_perception()

    def _init_perception(self) -> None:
        """初始化感知引擎。导入失败时静默降级。"""
        try:
            from ..perception.input_tracker import InputTracker
            from ..perception.window_monitor import WindowMonitor
            from ..perception.collector import PerceptionCollector
            from ..perception.engine import ProactiveEngine
            from ..perception.perception_log import PerceptionLog

            tracker = InputTracker()
            tracker.start()
            monitor = WindowMonitor()
            collector = PerceptionCollector(tracker, monitor)
            self._proactive_engine = ProactiveEngine(collector)
            log_dir = (self._logger._log_dir.parent if hasattr(self._logger, "_log_dir")
                       else Path("./data")) / "perception"
            self._perception_log = PerceptionLog(log_dir)
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
    def character_state(self) -> EmotionState:
        return self._state

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def last_log_entry(self) -> Optional[dict]:
        """返回最近一条日志记录（用于 API 层取 flagged/usage 等信息）。"""
        return self._last_log_entry

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
                # 主动介入检查（仅在启用感知时）
                if self._proactive_engine:
                    event = self._proactive_engine.check()
                    if event:
                        proactive_reply = self._handle_proactive(event)
                        if proactive_reply:
                            print(f"{config.name}: {proactive_reply}")
                            print()

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
        system_prompt, mood_before = self._prepare_turn(user_input)
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
        system_prompt, mood_before = self._prepare_turn(user_input)
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

    def _prepare_turn(self, user_input: str) -> tuple[str, str]:
        self._turn += 1
        config = self._config
        mood_before = self._state.mood

        event = detect_event(user_input, config.emotion_triggers)
        self._state.update(event)
        mood_after = self._state.mood

        wm = self._memory.working_memory
        prev_len = len(wm)
        wm.truncate()
        if len(wm) < prev_len:
            self._working_memory_truncation_count += 1
        wm.add("user", user_input)

        character_id = self._character_id
        memory_ctx = self._memory.get_context(character_id, token_budget=self._MEMORY_TOKEN_BUDGET)
        self._last_memory_ctx = memory_ctx

        perception_ctx: Optional[PerceptionContext] = None
        if self._proactive_engine:
            perception_ctx = self._proactive_engine.last_perception()  # type: ignore[assignment]

        prompt_ctx = PromptContext(
            character=config,
            emotion=self._state,
            memory=memory_ctx,
            perception=perception_ctx,
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

    def _finalize_turn(self, user_input: str, mood_before: str, result: LLMResult) -> str:
        reply = result.text
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

        self._logger.log(
            turn=self._turn,
            user_input=user_input,
            mood_before=mood_before,
            mood_after=self._state.mood,
            persist_count=self._state.persist_count,
            reply=reply,
            flagged=flagged,
            usage=usage,
        )
        self._last_log_entry = {"flagged": flagged, "usage": usage}

        if self._debug:
            if flagged:
                print("[DEBUG] ⚠ 回复中出现禁用词")
            if usage:
                print(
                    f"[DEBUG] usage: in={usage['input_tokens']} "
                    f"out={usage['output_tokens']} "
                    f"({usage['provider']}/{usage['model']})"
                )

        return reply

    def _handle_proactive(self, event: "ProactiveEvent") -> Optional[str]:
        """根据主动介入事件生成角色台词。"""
        style = self._config.proactive_style
        style_hint = {
            "idle": style.idle_too_long,
            "late_night": style.user_working_late,
            "gaming": style.user_gaming,
            "long_work": style.user_working_late,
            "window_switch": style.idle_too_long,
        }.get(event.tag, "")

        if not style_hint:
            return None

        system = build_system_prompt(PromptContext(
            character=self._config,
            emotion=self._state,
        ))
        synthetic_message = [
            {"role": "user", "content": f"【场景】{style_hint}。请用一句简短的话自然开口，不要解释场景。"}
        ]
        try:
            result = self._llm.chat(system, synthetic_message)
            reply = result.text
            if self._perception_log:
                self._perception_log.record(
                    trigger_name=event.trigger_name,
                    reason=event.tag,
                    character_id=self._character_id,
                    proactive_reply=reply,
                )
            return reply
        except Exception:
            return None

    def _on_session_end(self) -> None:
        """会话结束钩子：生成摘要并保存到记忆层，停止感知追踪。"""
        if self._input_tracker:
            try:
                self._input_tracker.stop()
            except Exception:
                pass
        history = self._memory.working_memory.get_messages()
        self._memory.on_session_end(
            character_id=self._character_id,
            history=history,
            llm_chat_fn=self._llm.chat,
        )
