from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...service_registry import get_runtime, get_service
from ....application.conversation_service import ConversationService
from ....proactive.profile import ProactiveSettings
from ....runtime.companion_runtime import CompanionRuntime

router = APIRouter(prefix="/proactive")


class ProactiveSettingsResponse(BaseModel):
    settings: dict[str, Any]


class ProactiveSettingsRequest(BaseModel):
    settings: dict[str, Any]


class ProactiveLogsResponse(BaseModel):
    items: list[dict[str, Any]]


class ProactiveFeedbackRequest(BaseModel):
    event_id: str
    feedback: str | None = None
    responded: bool = True


@router.get("/settings", response_model=ProactiveSettingsResponse)
async def get_settings(
    runtime: CompanionRuntime = Depends(get_runtime),
) -> ProactiveSettingsResponse:
    return ProactiveSettingsResponse(settings=runtime.get_settings().to_dict())


@router.put("/settings", response_model=ProactiveSettingsResponse)
async def update_settings(
    body: ProactiveSettingsRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
) -> ProactiveSettingsResponse:
    current = runtime.get_settings().to_dict()
    current.update(body.settings)
    settings = ProactiveSettings.from_mapping(current)
    saved = runtime.update_settings(settings)
    return ProactiveSettingsResponse(settings=saved.to_dict())


@router.get("/status")
async def get_status(
    runtime: CompanionRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    return runtime.get_status()


@router.get("/logs", response_model=ProactiveLogsResponse)
async def get_logs(
    limit: int = Query(default=50, ge=1, le=200),
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ProactiveLogsResponse:
    return ProactiveLogsResponse(items=runtime.get_logs(limit=limit, character_id=service.character_id))


@router.post("/test")
async def send_test_action(
    runtime: CompanionRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    action = await runtime.send_test_action()
    return action.to_dict()


@router.post("/feedback")
async def record_feedback(
    body: ProactiveFeedbackRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
) -> dict[str, str]:
    updated = runtime.record_feedback(body.event_id, body.feedback, body.responded)
    if not updated:
        raise HTTPException(status_code=404, detail="proactive event not found")
    return {"status": "ok"}