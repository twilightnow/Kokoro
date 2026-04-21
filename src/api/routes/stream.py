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

from ..app import get_service
from ..schemas import StreamChunk
from ...application.conversation_service import ConversationService

router = APIRouter(tags=["stream"])


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    # WebSocket 路由不使用 Depends()，直接调用 get_service()
    service: ConversationService = get_service()
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
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

            # 发送"思考中"指示
            await websocket.send_text(
                StreamChunk(type="thinking", content="").model_dump_json()
            )

            # handle_turn() 是同步阻塞调用，用 asyncio.to_thread 避免阻塞事件循环
            reply = await asyncio.to_thread(service.handle_turn, message)

            if reply is None:
                await websocket.send_text(
                    StreamChunk(type="error", content="LLM 调用失败").model_dump_json()
                )
                continue

            last_log = service.last_log_entry or {}
            await websocket.send_text(
                StreamChunk(
                    type="done",
                    content=reply,
                    mood=service.character_state.mood,
                    flagged=last_log.get("flagged", False),
                ).model_dump_json()
            )

    except WebSocketDisconnect:
        pass
