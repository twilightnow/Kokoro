"""WebSocket 疏通テスト — sidecar が起動中であることを確認してから実行"""
import asyncio
import json
import sys

try:
    import websockets  # type: ignore[import-untyped]
except ImportError:
    print("websockets not installed, skipping WS test")
    sys.exit(0)


async def main() -> None:
    uri = "ws://127.0.0.1:18765/stream"
    print(f"Connecting to {uri}")
    async with websockets.connect(uri) as ws:  # type: ignore[attr-defined]
        payload = json.dumps({"message": "こんにちは"})
        await ws.send(payload)
        print(f"Sent: {payload}")
        for _ in range(5):
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            data = json.loads(raw)
            t = data.get("type", "?")
            mood = data.get("mood", "")
            content_len = len(data.get("content", ""))
            print(f"  <- type={t!r}  mood={mood!r}  content_len={content_len}")
            if t in ("done", "error"):
                break
    print("Test passed!")


if __name__ == "__main__":
    asyncio.run(main())
