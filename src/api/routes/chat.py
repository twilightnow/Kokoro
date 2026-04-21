"""
POST /chat — 同步对话接口。

返回完整回复，适合前端轮询或一次性请求。
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from ..app import get_service
from ..schemas import ChatRequest, ChatResponse, UsageInfo
from ...application.conversation_service import ConversationService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ConversationService = Depends(get_service),
) -> ChatResponse:
    mood_before = service.character_state.mood
    # handle_turn() 是同步阻塞调用，用 asyncio.to_thread 避免阻塞事件循环
    reply = await asyncio.to_thread(service.handle_turn, request.message)

    if reply is None:
        raise HTTPException(status_code=503, detail="LLM 调用失败，请稍后重试")

    mood_after = service.character_state.mood
    last_log = service.last_log_entry or {}

    usage_info: UsageInfo | None = None
    raw_usage = last_log.get("usage")
    if raw_usage:
        usage_info = UsageInfo(
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
            provider=raw_usage.get("provider", ""),
            model=raw_usage.get("model", ""),
        )

    return ChatResponse(
        reply=reply,
        mood=mood_after,
        mood_changed=mood_before != mood_after,
        flagged=last_log.get("flagged", False),
        turn=service.turn,
        usage=usage_info,
    )
