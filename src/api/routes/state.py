"""
GET /state — 当前角色状态
GET /health — 服务健康检查
"""
from fastapi import APIRouter, Depends

from ..app import get_service
from ..schemas import HealthResponse, StateResponse
from ...application.conversation_service import ConversationService

router = APIRouter(tags=["state"])


@router.get("/state", response_model=StateResponse)
async def get_state(
    service: ConversationService = Depends(get_service),
) -> StateResponse:
    state = service.character_state
    memory_ctx = service.memory_context
    return StateResponse(
        character_name=service.character.name,
        mood=state.mood,
        persist_count=state.persist_count,
        turn=service.turn,
        memory_summary_count=len(memory_ctx.summary_items),
        memory_fact_count=len(memory_ctx.long_term_items),
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    service: ConversationService = Depends(get_service),
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        character=service.character.name,
        version=service.character.version,
    )
