#!/usr/bin/env python3
"""
Kokoro — 桌面 AI 人格伴侣平台 CLI 入口

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
from src.character_defaults import resolve_default_character_path

_ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=_ENV_PATH)


def _configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def run_conversation(debug: bool, enable_perception: bool = False) -> None:
    from src.application.conversation_service import ConversationService

    service = ConversationService(
        character_path=resolve_default_character_path(),
        debug=debug,
        enable_perception=enable_perception,
    )
    service.run()


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
        if r.get("usage"):
            u = r["usage"]
            print(
                f"  usage: in={u.get('input_tokens', 0)} "
                f"out={u.get('output_tokens', 0)} "
                f"({u.get('provider', '')})"
            )
        print()


def main() -> None:
    _configure_stdio()
    parser = argparse.ArgumentParser(
        description="Kokoro – 桌面AI人格伴侣平台 CLI Demo（明日香）"
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--replay", metavar="LOG_FILE", help="回放指定会话日志")
    parser.add_argument("--perception", action="store_true", help="启用感知层（窗口监听/空闲检测）")
    args = parser.parse_args()

    if args.replay:
        run_replay(args.replay)
    else:
        run_conversation(args.debug, enable_perception=args.perception)


if __name__ == "__main__":
    main()
