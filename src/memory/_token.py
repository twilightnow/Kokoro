"""记忆层内部用 token 估算工具，不对外暴露。"""


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1.5 字/token）。"""
    return max(1, int(len(text) / 1.5))
