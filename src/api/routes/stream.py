"""
WebSocket /stream — 流式对话接口。

当前阶段：LLM 调用仍为同步，WebSocket 用于保持长连接和推送完整回复。
真正的 token 级流式在 LLM provider 支持后扩展（不改变此接口协议）：
  - AnthropicClient 未来可添加 stream_chat() 返回 AsyncGenerator[str, None]
  - 届时改为逐 token 发送 StreamChunk(type="token", content=token)
  - done 帧始终作为结束标志，协议向后兼容
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..service_registry import get_service
from ..schemas import StreamChunk
from ...application.conversation_service import ConversationService

router = APIRouter(tags=["stream"])


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()

            # 每次收到消息都重新获取 service，确保角色切换后使用新实例
            service: ConversationService = get_service()

            try:
                payload = json.loads(data)
                message = payload.get("message", "").strip()
            except (json.JSONDecodeError, AttributeError):
                await websocket.send_text(
                    StreamChunk(
                        type="error",
                        content="消息格式错误，需要 JSON {message: ...}",
                    ).model_dump_json()
                )
                continue

            if not message:
                continue

            await websocket.send_text(
                StreamChunk(type="thinking", content="").model_dump_json()
            )

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[dict] = asyncio.Queue()

            def emit_token(token: str) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "token", "content": token})

            def worker() -> None:
                reply = service.handle_turn_stream(message, on_token=emit_token)
                if reply is None:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "error", "content": "LLM 调用失败"},
                    )
                    return

                last_log = service.last_log_entry or {}
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "type": "done",
                        "content": reply,
                        "mood": service.character_state.mood,
                        "flagged": last_log.get("flagged", False),
                    },
                )

            worker_task = asyncio.create_task(asyncio.to_thread(worker))

            while True:
                chunk = await queue.get()
                await websocket.send_text(StreamChunk(**chunk).model_dump_json())
                if chunk["type"] in {"done", "error"}:
                    break

            await worker_task

    except WebSocketDisconnect:
        pass
