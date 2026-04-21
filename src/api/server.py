"""
sidecar 启动入口。

用法：
    python -m src.api.server          # 开发模式（热重载）
    python -m src.api.server --prod   # 生产模式（无热重载）
"""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro sidecar API server")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=18765, help="监听端口")
    parser.add_argument("--prod", action="store_true", help="生产模式（禁用热重载）")
    args = parser.parse_args()

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
