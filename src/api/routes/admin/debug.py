"""
调试工具 API。

GET  /admin/debug/state         完整内部状态快照（含 system prompt）
GET  /admin/debug/token-history 当前会话 token 使用历史（仅内存）
GET  /admin/debug/working-memory 当前工作记忆内容
DELETE /admin/debug/working-memory 清空工作记忆
POST /admin/debug/reload-character 热重载当前角色 YAML
POST /admin/debug/emotion       注入情绪（覆盖 EmotionState，不写日志）
POST /admin/debug/inject-fact   临时事实注入（不写磁盘，会话内有效）
DELETE /admin/debug/inject-fact  清除所有临时注入事实
POST /admin/debug/sandbox       LLM 沙盒调用（不写日志，不改内存状态）
POST /admin/debug/client-log    前端/桌面端诊断日志，打印到 sidecar 控制台
GET  /admin/debug/client-logs   查询最近客户端诊断日志
"""
import json
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...service_registry import get_service
from ....application.conversation_service import ConversationService
from ....personality.prompt_builder import estimate_tokens

router = APIRouter(prefix="/debug")

# 临时注入的事实（仅内存，会话级别）
_temp_facts: Dict[str, str] = {}
_client_log_buffer: Deque[Dict[str, Any]] = deque(maxlen=200)


class DebugStateResponse(BaseModel):
    character_id: str
    character_name: str
    role_card: Dict[str, Any]
    mood: str
    persist_count: int
    keyword: str
    reason: str
    source: str
    intensity: float
    started_at_turn: int
    duration_turns: int
    elapsed_turns: int
    recovery_rate: float
    estimated_remaining_turns: int
    turn: int
    working_memory_count: int
    working_memory_truncation_count: int
    memory_summary_count: int
    memory_fact_count: int
    session_token_input: int
    session_token_output: int
    system_prompt: str
    system_prompt_estimated_tokens: int
    temp_facts: Dict[str, str]
    recent_events: List[Dict[str, Any]]
    recent_safety_events: List[Dict[str, Any]]
    current_segment: Optional[Dict[str, Any]]
    segments: List[Dict[str, Any]]


class EmotionInjectRequest(BaseModel):
    mood: str
    persist_count: int = 3
    keyword: str = ""
    reason: str = ""
    source: str = "debug_inject"
    intensity: Optional[float] = None
    recovery_rate: Optional[float] = None


class TempFactInjectRequest(BaseModel):
    key: str
    value: str


class SandboxRequest(BaseModel):
    system_prompt: str
    user_message: str
    include_working_memory: bool = False


class ClientLogRequest(BaseModel):
    source: str
    event: str
    level: str = "info"
    message: str = ""
    details: Optional[Dict[str, Any]] = None


class SandboxResponse(BaseModel):
    reply: str
    input_tokens: int
    output_tokens: int
    provider: str
    model: str
    elapsed_ms: float


class TokenHistoryItem(BaseModel):
    turn: int
    input_tokens: int
    output_tokens: int
    provider: str
    model: str


class TokenHistoryResponse(BaseModel):
    items: List[TokenHistoryItem]
    session_input_tokens: int
    session_output_tokens: int
    session_total_tokens: int


class WorkingMemoryItem(BaseModel):
    index: int
    role: str
    content: str


@router.get("/state", response_model=DebugStateResponse)
async def debug_state(service: ConversationService = Depends(get_service)) -> DebugStateResponse:
    state = service.character_state
    mem_ctx = service.memory_context
    system_prompt = service.last_system_prompt

    def serialize_segment(segment) -> Dict[str, Any]:
        return {
            "mood": segment.mood,
            "keyword": segment.keyword,
            "reason": segment.reason,
            "source": segment.source,
            "intensity": segment.intensity,
            "recovery_rate": segment.recovery_rate,
            "started_at_turn": segment.started_at_turn,
            "last_updated_turn": segment.last_updated_turn,
            "elapsed_turns": segment.elapsed_turns,
            "estimated_remaining_turns": segment.estimated_remaining_turns,
            "ended_at_turn": segment.ended_at_turn,
            "end_reason": segment.end_reason,
            "tts_rate_delta": segment.tts_rate_delta,
            "tts_volume_delta": segment.tts_volume_delta,
        }

    return DebugStateResponse(
        character_id=service.character_id,
        character_name=service.character.name,
        role_card=service.character.to_role_card_payload(),
        mood=state.mood,
        persist_count=state.persist_count,
        keyword=state.keyword,
        reason=state.reason,
        source=state.source,
        intensity=state.intensity,
        started_at_turn=state.started_at_turn,
        duration_turns=state.duration_turns,
        elapsed_turns=state.elapsed_turns,
        recovery_rate=state.recovery_rate,
        estimated_remaining_turns=state.estimated_remaining_turns,
        turn=service.turn,
        working_memory_count=service.working_memory_message_count,
        working_memory_truncation_count=service.working_memory_truncation_count,
        memory_summary_count=len(mem_ctx.summary_items),
        memory_fact_count=len(mem_ctx.long_term_items),
        session_token_input=service.session_token_total["input"],
        session_token_output=service.session_token_total["output"],
        system_prompt=system_prompt,
        system_prompt_estimated_tokens=estimate_tokens(system_prompt) if system_prompt else 0,
        temp_facts=dict(_temp_facts),
        recent_events=[record.__dict__ for record in state.recent_events],
        recent_safety_events=service.recent_safety_events,
        current_segment=serialize_segment(state.current_segment) if state.current_segment else None,
        segments=[serialize_segment(segment) for segment in reversed(state.timeline_segments)],
    )


@router.get("/token-history", response_model=TokenHistoryResponse)
async def token_history(
    service: ConversationService = Depends(get_service),
) -> TokenHistoryResponse:
    session_total = service.session_token_total
    items = [TokenHistoryItem(**item) for item in service.get_token_history()]
    return TokenHistoryResponse(
        items=items,
        session_input_tokens=session_total["input"],
        session_output_tokens=session_total["output"],
        session_total_tokens=session_total["input"] + session_total["output"],
    )


@router.get("/working-memory", response_model=List[WorkingMemoryItem])
async def working_memory(
    service: ConversationService = Depends(get_service),
) -> List[WorkingMemoryItem]:
    return [
        WorkingMemoryItem(index=index + 1, role=message["role"], content=message["content"])
        for index, message in enumerate(service.working_memory_messages)
    ]


@router.delete("/working-memory", status_code=200)
async def clear_working_memory(
    service: ConversationService = Depends(get_service),
) -> Dict[str, Any]:
    cleared = service.clear_working_memory()
    return {"status": "ok", "cleared": cleared}


@router.post("/reload-character", status_code=200)
async def reload_character(
    service: ConversationService = Depends(get_service),
) -> Dict[str, str]:
    try:
        config = service.reload_character_config()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "status": "ok",
        "character_id": service.character_id,
        "character_name": config.name,
    }


@router.post("/flush-session", status_code=200)
async def flush_session(
    service: ConversationService = Depends(get_service),
) -> Dict[str, Any]:
    flushed = service.flush_pending_memory()
    return {"status": "ok", "flushed": flushed}


@router.post("/emotion", status_code=200)
async def inject_emotion(
    body: EmotionInjectRequest,
    service: ConversationService = Depends(get_service),
) -> Dict[str, Any]:
    """注入情绪，直接修改 EmotionState 内存，不触发触发词检测，不写日志。"""
    state = service.character_state
    state.set_manual_state(
        body.mood,
        persist_count=body.persist_count,
        intensity=body.intensity,
        reason=body.reason,
        source=body.source,
        keyword=body.keyword,
        recovery_rate=body.recovery_rate,
        turn=service.turn,
    )
    return {
        "status": "ok",
        "mood": state.mood,
        "persist_count": state.persist_count,
        "intensity": state.intensity,
        "reason": state.reason,
        "source": state.source,
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


@router.post("/client-log", status_code=200)
async def client_log(body: ClientLogRequest) -> Dict[str, str]:
    """接收前端/桌面端诊断事件，并输出到 sidecar 控制台。"""
    level = body.level.upper()
    payload = {
        "time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": body.source,
        "event": body.event,
        "level": body.level,
        "message": body.message,
        "details": body.details or {},
    }
    _client_log_buffer.append(payload)
    print(
        f"[KokoroClientLog][{level}] {json.dumps(payload, ensure_ascii=False)}",
        file=sys.stderr,
        flush=True,
    )
    return {"status": "ok"}


def get_client_log_snapshot(limit: int = 50) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    return list(_client_log_buffer)[-limit:]


@router.get("/client-logs", response_model=List[Dict[str, Any]])
async def client_logs(limit: int = 100) -> List[Dict[str, Any]]:
    normalized_limit = max(1, min(limit, 200))
    return get_client_log_snapshot(normalized_limit)


@router.post("/sandbox", response_model=SandboxResponse)
async def sandbox(
    body: SandboxRequest,
    service: ConversationService = Depends(get_service),
) -> SandboxResponse:
    """直接发送自定义 system prompt + 消息到 LLM，不写日志，不改内存状态。"""
    import time
    messages = []
    if body.include_working_memory:
        messages.extend(service.working_memory_messages)
    messages.append({"role": "user", "content": body.user_message})
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
