#!/usr/bin/env python3
"""
Token 用量与成本统计脚本

用法：
    python tools/cost_summary.py               # 统计 logs/ 目录下所有会话
    python tools/cost_summary.py logs/          # 指定目录
    python tools/cost_summary.py logs/xxx.jsonl # 单个文件

输出：
    每个会话的 token 用量 + 跨会话汇总 + 估算费用
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

# 估算费用（USD per 1M tokens），仅供参考，以实际账单为准
# 来源：各平台公开定价，可能滞后于最新价格
_PRICE_TABLE = {
    # (input $/1M, output $/1M)
    "anthropic": {
        "claude-haiku-4-5-20251001": (0.80, 4.00),
        "claude-sonnet-4-6":         (3.00, 15.00),
        "claude-opus-4-6":           (15.00, 75.00),
        "default":                   (3.00, 15.00),
    },
    "openai": {
        "gpt-4o-mini":  (0.15, 0.60),
        "gpt-4o":       (2.50, 10.00),
        "gpt-4.1":      (2.00, 8.00),
        "default":      (2.50, 10.00),
    },
    "deepseek": {
        "deepseek-chat": (0.27, 1.10),
        "default":       (0.27, 1.10),
    },
    "gemini": {
        "gemini-2.5-flash": (0.15, 0.60),
        "gemini-2.5-pro":   (1.25, 10.00),
        "default":          (0.15, 0.60),
    },
    "openrouter": {
        "default": (1.00, 3.00),  # 取中位数估算
    },
    "copilot": {
        "default": (0.00, 0.00),  # 订阅制，无 per-token 计费
    },
}


def _estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """估算单次费用（USD）。"""
    provider_prices = _PRICE_TABLE.get(provider, {})
    in_price, out_price = provider_prices.get(model, provider_prices.get("default", (0, 0)))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def load_session(path: Path) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def summarize_session(path: Path) -> dict | None:
    """返回单个会话的统计数据，没有 usage 字段时返回 None。"""
    records = load_session(path)
    if not records:
        return None

    total_input = 0
    total_output = 0
    provider_model_counts: defaultdict = defaultdict(int)
    has_usage = False

    for r in records:
        usage = r.get("usage")
        if not usage:
            continue
        has_usage = True
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        total_input += inp
        total_output += out
        key = (usage.get("provider", "unknown"), usage.get("model", "unknown"))
        provider_model_counts[key] += 1

    if not has_usage:
        return None

    # 主要 provider/model（按轮次最多的）
    main_provider, main_model = max(provider_model_counts, key=provider_model_counts.get) if provider_model_counts else ("unknown", "unknown")
    cost = _estimate_cost(main_provider, main_model, total_input, total_output)

    return {
        "file": path.name,
        "turns": len(records),
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "provider": main_provider,
        "model": main_model,
        "cost_usd": cost,
    }


def find_jsonl_files(target: Path) -> list:
    if target.is_file():
        return [target]
    if target.is_dir():
        files = sorted(target.glob("*.jsonl"))
        return files
    print(f"错误: 路径不存在: {target}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro Token 用量与成本统计")
    parser.add_argument(
        "target",
        nargs="?",
        default="logs",
        help="日志目录或单个 .jsonl 文件（默认: logs/）",
    )
    args = parser.parse_args()

    files = find_jsonl_files(Path(args.target))
    if not files:
        print("未找到任何 .jsonl 文件。")
        return

    sessions = []
    skipped = 0
    for f in files:
        result = summarize_session(f)
        if result:
            sessions.append(result)
        else:
            skipped += 1

    if not sessions:
        print("所有日志均无 usage 数据（CLI 模式不记录 token 用量）。")
        return

    # 打印表头
    print()
    print(f"{'文件':<35}  {'轮':>4}  {'输入':>8}  {'输出':>8}  {'合计':>8}  {'估算费用(USD)':>14}  {'Provider/Model'}")
    print("-" * 110)

    total_in = total_out = total_cost = total_turns = 0

    for s in sessions:
        cost_str = f"${s['cost_usd']:.4f}" if s["cost_usd"] > 0 else "订阅制"
        pm = f"{s['provider']}/{s['model']}"
        print(
            f"{s['file']:<35}  "
            f"{s['turns']:>4}  "
            f"{s['input_tokens']:>8,}  "
            f"{s['output_tokens']:>8,}  "
            f"{s['total_tokens']:>8,}  "
            f"{cost_str:>14}  "
            f"{pm}"
        )
        total_in += s["input_tokens"]
        total_out += s["output_tokens"]
        total_cost += s["cost_usd"]
        total_turns += s["turns"]

    print("-" * 110)
    total_cost_str = f"${total_cost:.4f}" if total_cost > 0 else "—"
    print(
        f"{'汇总':<35}  "
        f"{total_turns:>4}  "
        f"{total_in:>8,}  "
        f"{total_out:>8,}  "
        f"{total_in + total_out:>8,}  "
        f"{total_cost_str:>14}"
    )

    if skipped:
        print(f"\n（{skipped} 个文件无 usage 数据，已跳过。CLI 模式下 token 用量不计入。）")

    print()
    print("注：费用为估算值，以各平台实际账单为准。订阅制（copilot / CLI 模式）不计入费用。")


if __name__ == "__main__":
    main()
