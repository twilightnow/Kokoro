#!/usr/bin/env python3
"""
人格稳定性复盘脚本

用法：
    python tools/analyze_session.py logs/session_xxx.jsonl
    python tools/analyze_session.py logs/session_xxx.jsonl --verbose

输出：
    总轮次 / 情绪分布 / 禁用词命中率 / 最长连续同情绪 / 平均回复长度
"""

import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

# Windows 终端强制 UTF-8 输出，避免 GBK 编码错误
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def load_records(path: Path) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[警告] 第 {i} 行解析失败，已跳过: {e}", file=sys.stderr)
    return records


def analyze(records: list, verbose: bool = False) -> None:
    if not records:
        print("日志为空，无可分析数据。")
        return

    total = len(records)
    mood_counts: defaultdict = defaultdict(int)
    flagged_turns = []
    reply_lengths = []
    max_streak = 1
    current_streak = 1
    last_mood = None

    # Token 用量
    total_input_tokens = 0
    total_output_tokens = 0
    providers: set = set()

    for r in records:
        mood_after = r.get("mood_after", "normal")
        mood_counts[mood_after] += 1

        if r.get("flagged"):
            flagged_turns.append(r["turn"])

        reply = r.get("reply", "")
        reply_lengths.append(len(reply))

        # 连续情绪统计
        if mood_after == last_mood:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
            last_mood = mood_after

        # token 用量
        usage = r.get("usage")
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
            if usage.get("provider"):
                providers.add(f"{usage['provider']}/{usage.get('model', '')}")

    flagged_count = len(flagged_turns)
    flagged_rate = flagged_count / total * 100
    avg_reply_len = sum(reply_lengths) / total if reply_lengths else 0
    max_reply_len = max(reply_lengths) if reply_lengths else 0

    # 情绪分布排序（从多到少）
    mood_sorted = sorted(mood_counts.items(), key=lambda x: -x[1])

    print("=" * 48)
    print(f"  人格稳定性复盘报告")
    print("=" * 48)
    print(f"  总轮次           : {total}")
    print()
    print("  情绪分布:")
    for mood, count in mood_sorted:
        bar = "█" * count
        pct = count / total * 100
        print(f"    {mood:<10} {count:>3} 轮  {pct:5.1f}%  {bar}")
    print()
    print(f"  禁用词命中次数   : {flagged_count} / {total}  ({flagged_rate:.1f}%)")
    if flagged_turns:
        print(f"  命中轮次         : {flagged_turns}")
    print()
    print(f"  最长连续同情绪   : {max_streak} 轮")
    print(f"  平均回复长度     : {avg_reply_len:.1f} 字")
    print(f"  最长回复         : {max_reply_len} 字")

    if total_input_tokens or total_output_tokens:
        print()
        print(f"  Token 用量:")
        print(f"    输入           : {total_input_tokens:,}")
        print(f"    输出           : {total_output_tokens:,}")
        if providers:
            print(f"    Provider       : {', '.join(sorted(providers))}")

    # 简单评估
    print()
    print("  评估:")
    issues = []
    if flagged_rate > 0:
        issues.append(f"禁用词触发率 {flagged_rate:.1f}%，需要检查 forbidden_words 配置或 system prompt 约束强度")
    if max_streak >= total * 0.7 and total >= 5:
        dominant = mood_sorted[0][0] if mood_sorted else "unknown"
        if dominant != "normal":
            issues.append(f"情绪 '{dominant}' 占据 {max_streak} 连续轮次，情绪变化可能过于单一")
    if avg_reply_len > 150:
        issues.append(f"平均回复长度 {avg_reply_len:.0f} 字，超出建议上限（桌面场景建议 ≤ 60 字）")

    if issues:
        for issue in issues:
            print(f"    ⚠  {issue}")
    else:
        print(f"    ✓  未发现明显问题")

    if verbose:
        print()
        print("  详细轮次记录:")
        print(f"  {'轮次':>4}  {'情绪变化':<20}  {'回复长度':>6}  {'禁用词'}")
        print("  " + "-" * 50)
        for r in records:
            mood_before = r.get("mood_before", "?")
            mood_after = r.get("mood_after", "?")
            mood_label = (
                f"{mood_before} → {mood_after}"
                if mood_before != mood_after
                else mood_before
            )
            reply_len = len(r.get("reply", ""))
            flagged_str = "⚠" if r.get("flagged") else ""
            print(f"  {r['turn']:>4}  {mood_label:<20}  {reply_len:>6} 字  {flagged_str}")

    print("=" * 48)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kokoro 人格稳定性复盘脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("log_file", help="JSONL 日志文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出详细轮次记录")
    args = parser.parse_args()

    path = Path(args.log_file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    if path.suffix != ".jsonl":
        print(f"警告: 文件扩展名不是 .jsonl，仍尝试解析。", file=sys.stderr)

    records = load_records(path)
    analyze(records, verbose=args.verbose)


if __name__ == "__main__":
    main()
