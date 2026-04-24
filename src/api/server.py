"""
sidecar 启动入口。

用法：
    python -m src.api.server          # 开发模式（热重载）
    python -m src.api.server --prod   # 生产模式（无热重载）
"""
import argparse
import json
import socket
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).resolve().parent
else:
    _ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ROOT / ".env")


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _get_existing_sidecar_health(host: str, port: int) -> dict | None:
    url = f"http://{host}:{port}/health"
    try:
        with urlopen(url, timeout=0.8) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None

    if payload.get("status") != "ok":
        return None
    if "character_id" not in payload or "character" not in payload:
        return None
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro sidecar API server")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=18765, help="监听端口")
    parser.add_argument("--prod", action="store_true", help="生产模式（禁用热重载）")
    parser.add_argument(
        "--no-reuse-existing",
        action="store_true",
        help="端口上已有健康 Kokoro sidecar 时仍视为冲突",
    )
    args = parser.parse_args()

    if _is_port_in_use(args.host, args.port):
        if not args.no_reuse_existing:
            health = _get_existing_sidecar_health(args.host, args.port)
            if health is not None:
                print(
                    f"sidecar 已在 {args.host}:{args.port} 运行，"
                    f"复用现有进程（角色：{health.get('character', '')}）。"
                )
                raise SystemExit(0)

        print(
            f"ERROR: sidecar 无法启动，{args.host}:{args.port} 已被占用。\n"
            "如果这是已运行的 Kokoro sidecar，请去掉 --no-reuse-existing 后重试；"
            "否则请关闭占用该端口的进程，或改用其他端口后再启动。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,
        log_level="info",
    )


if __name__ == "__main__":
    main()
