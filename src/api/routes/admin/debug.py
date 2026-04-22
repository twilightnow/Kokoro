"""
调试工具 API。

GET  /admin/debug/state         完整内部状态快照（含 system prompt）
POST /admin/debug/emotion       注入情绪（覆盖 EmotionState，不写日志）
POST /admin/debug/inject-fact   临时事实注入（不写磁盘，会话内有效）
DELETE /admin/debug/inject-fact  清除所有临时注入事实
POST /admin/debug/sandbox       LLM 沙盒调用（不写日志，不改内存状态）
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...service_registry import get_service
from ....application.conversation_service import ConversationService

router = APIRouter(prefix="/debug")

# 临时注入的事实（仅内存，会话级别）
_temp_facts: Dict[str, str] = {}


class DebugStateResponse(BaseModel):
    character_id: str
    character_name: str
    mood: str
    persist_count: int
    turn: int
    working_memory_count: int
    working_memory_truncation_count: int
    memory_summary_count: int
    memory_fact_count: int
    session_token_input: int
    session_token_output: int
    system_prompt: str
    temp_facts: Dict[str, str]


class EmotionInjectRequest(BaseModel):
    mood: str
    persist_count: int = 3


class TempFactInjectRequest(BaseModel):
    key: str
    value: str


class SandboxRequest(BaseModel):
    system_prompt: str
    user_message: str


class SandboxResponse(BaseModel):
    reply: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    elapsed_ms: float


@router.get("/state", response_model=DebugStateResponse)
async def debug_state(service: ConversationService = Depends(get_service)) -> DebugStateResponse:
    state = service.character_state
    mem_ctx = service.memory_context
    return DebugStateResponse(
        character_id=service.character_id,
        character_name=service.character.name,
        mood=state.mood,
        persist_count=state.persist_count,
        turn=service.turn,
        working_memory_count=service.working_memory_message_count,
        working_memory_truncation_count=service.working_memory_truncation_count,
        memory_summary_count=len(mem_ctx.summary_items),
        memory_fact_count=len(mem_ctx.long_term_items),
        session_token_input=service.session_token_total["input"],
        session_token_output=service.session_token_total["output"],
        system_prompt=service.last_system_prompt,
        temp_facts=dict(_temp_facts),
    )


@router.post("/emotion", status_code=200)
async def inject_emotion(
    body: EmotionInjectRequest,
    service: ConversationService = Depends(get_service),
) -> Dict[str, Any]:
    """注入情绪，直接修改 EmotionState 内存，不触发触发词检测，不写日志。"""
    state = service.character_state
    state.mood = body.mood
    state.persist_count = body.persist_count
    return {
        "status": "ok",
        "mood": state.mood,
        "persist_count": state.persist_count,
    }


@router.post("/inject-fact", status_code=200)
async def inject_temp_fact(body: TempFactInjectRequest) -> Dict[str, Any]:
    """临时注入事实（内存级别，重启 sidecar 后消失，不写 facts.json）。"""
    _temp_facts[body.key] = body.value
    return {"status": "ok", "key": body.key, "total": len(_temp_facts)}


@router.delete("/inject-fact", status_code=200)
async def clear_temp_facts(key: Optional[str] = None) -> Dict[str, Any]:
    """清除临时注入事实。指定 key 时只删一条，否则清空全部。"""
    if key:
        if key not in _temp_facts:
            raise HTTPException(status_code=404, detail=f"临时事实不存在: {key}")
        del _temp_facts[key]
        return {"status": "ok", "deleted": key}
    _temp_facts.clear()
    return {"status": "ok", "deleted": "all"}


@router.get("/inject-fact", response_model=Dict[str, str])
async def list_temp_facts() -> Dict[str, str]:
    return dict(_temp_facts)


@router.post("/sandbox", response_model=SandboxResponse)
async def sandbox(
    body: SandboxRequest,
    service: ConversationService = Depends(get_service),
) -> SandboxResponse:
    """直接发送自定义 system prompt + 消息到 LLM，不写日志，不改内存状态。"""
    import time
    messages = [{"role": "user", "content": body.user_message}]
    t0 = time.monotonic()
    try:
        result = service._llm.chat(body.system_prompt, messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {e}")
    elapsed = (time.monotonic() - t0) * 1000
    return SandboxResponse(
        reply=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        provider=result.provider,
        model=result.model,
        elapsed_ms=round(elapsed, 1),
    )
