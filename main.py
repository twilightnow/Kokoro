#!/usr/bin/env python3
"""
Kokoro — 桌面 AI 人格伴侣平台 CLI Demo
目标角色：惣流·明日香·兰格雷

用法：
  python main.py               # 正常对话模式
  python main.py --debug       # 调试模式（额外打印情绪/prompt信息）
  python main.py --replay <日志文件>  # 离线回放会话日志
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.capability.llm import ClaudeClient
from src.logger.session_log import SessionLogger
from src.memory.working_memory import WorkingMemory
from src.personality.emotion import EmotionState
from src.personality.loader import load_character
from src.personality.prompt_builder import build_system_prompt

load_dotenv()

_CHARACTER_PATH = Path("characters/asuka/personality.yaml")


def _check_forbidden(reply: str, forbidden_words: list) -> bool:
    return any(word in reply for word in forbidden_words)


def run_conversation(debug: bool) -> None:
    config = load_character(_CHARACTER_PATH)
    state = EmotionState()
    memory = WorkingMemory(max_rounds=10)
    try:
        llm = ClaudeClient()
    except EnvironmentError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    logger = SessionLogger()

    print(f"=== {config.name} ===")
    print("对话开始。输入 'quit' 或 'exit' 结束。")
    if debug:
        print("[DEBUG] 调试模式已启用")
    print()

    turn = 0

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

            turn += 1
            mood_before = state.mood

            # 触发优先级：用户输入命中触发词 → 更新情绪；否则衰减
            state.update(user_input, config.emotion_triggers)
            mood_after = state.mood

            # history 截断在每轮发送前执行，截断后再追加当前输入
            memory.truncate()
            memory.add("user", user_input)

            system_prompt = build_system_prompt(config, state)

            if debug:
                mood_label = (
                    f"{mood_before} → {mood_after}"
                    if mood_before != mood_after
                    else mood_before
                )
                print(f"[DEBUG] mood: {mood_label}（persist={state.persist_count}）")
                print(f"[DEBUG] system prompt（前200字）: {system_prompt[:200]}...")
                print(f"[DEBUG] history 长度: {len(memory)} 条")

            reply = llm.chat(system_prompt, memory.get_messages())
            memory.add("assistant", reply)

            flagged = _check_forbidden(reply, config.forbidden_words)

            logger.log(
                turn=turn,
                user_input=user_input,
                mood_before=mood_before,
                mood_after=mood_after,
                persist_count=state.persist_count,
                reply=reply,
                flagged=flagged,
            )

            if debug and flagged:
                print("[DEBUG] ⚠ 回复中出现禁用词")
            print(f"{config.name}: {reply}")
            print()

    finally:
        logger.print_summary()


def run_replay(log_file: str) -> None:
    log_path = Path(log_file)
    if not log_path.exists():
        print(f"错误: 日志文件不存在: {log_path}", file=sys.stderr)
        sys.exit(1)

    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"=== 回放: {log_path.name} ===")
    print(f"共 {len(records)} 轮\n")

    for r in records:
        mood_label = (
            f"{r['mood_before']} → {r['mood_after']}"
            if r["mood_before"] != r["mood_after"]
            else r["mood_before"]
        )
        flagged_str = "  ⚠ 禁用词" if r["flagged"] else ""
        print(f"[轮次 {r['turn']}] {r['timestamp']}")
        print(f"  情绪: {mood_label}（persist={r['persist_count']}）")
        print(f"  用户: {r['user_input']}")
        print(f"  回复: {r['reply']}{flagged_str}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kokoro — 桌面AI人格伴侣平台 CLI Demo（明日香）"
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--replay", metavar="LOG_FILE", help="回放指定会话日志")
    args = parser.parse_args()

    if args.replay:
        run_replay(args.replay)
    else:
        run_conversation(args.debug)


if __name__ == "__main__":
    main()
