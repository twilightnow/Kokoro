from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ....application.conversation_service import ConversationService
from ....runtime.companion_runtime import CompanionRuntime
from ...service_registry import get_runtime, get_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderResponse(BaseModel):
    id: str
    character_id: str
    title: str
    note: str = ""
    due_at: str
    repeat_rule: str
    status: str
    created_at: str
    updated_at: str
    completed_at: str | None = None
    source: str = "admin"
    last_triggered_at: str | None = None


class ReminderListResponse(BaseModel):
    items: list[ReminderResponse]


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    note: str = Field(default="", max_length=400)
    due_at: str
    repeat_rule: str = Field(default="once", pattern="^(once|daily|weekly)$")
    source: str = Field(default="admin", max_length=40)


class ReminderUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=400)
    due_at: str | None = None
    repeat_rule: str | None = Field(default=None, pattern="^(once|daily|weekly)$")
    status: str | None = Field(default=None, pattern="^(scheduled|pending_ack|completed)$")


class ReminderSnoozeRequest(BaseModel):
    until: str


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="invalid datetime") from error


@router.get("", response_model=ReminderListResponse)
async def list_reminders(
    include_completed: bool = Query(default=True),
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ReminderListResponse:
    items = runtime.list_reminders(service.character_id, include_completed=include_completed)
    return ReminderListResponse(items=[ReminderResponse(**item) for item in items])


@router.post("", response_model=ReminderResponse)
async def create_reminder(
    body: ReminderCreateRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ReminderResponse:
    item = runtime.create_reminder(
        service.character_id,
        body.title,
        _parse_datetime(body.due_at),
        note=body.note,
        repeat_rule=body.repeat_rule,
        source=body.source,
    )
    return ReminderResponse(**item)


@router.put("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: str,
    body: ReminderUpdateRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ReminderResponse:
    try:
        item = runtime.update_reminder(
            service.character_id,
            reminder_id,
            title=body.title,
            note=body.note,
            due_at=_parse_datetime(body.due_at) if body.due_at else None,
            repeat_rule=body.repeat_rule,
            status=body.status,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="reminder not found") from error
    return ReminderResponse(**item)


@router.post("/{reminder_id}/complete", response_model=ReminderResponse)
async def complete_reminder(
    reminder_id: str,
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ReminderResponse:
    try:
        item = runtime.complete_reminder(service.character_id, reminder_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="reminder not found") from error
    return ReminderResponse(**item)


@router.post("/{reminder_id}/snooze", response_model=ReminderResponse)
async def snooze_reminder(
    reminder_id: str,
    body: ReminderSnoozeRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> ReminderResponse:
    try:
        item = runtime.snooze_reminder(service.character_id, reminder_id, _parse_datetime(body.until))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="reminder not found") from error
    return ReminderResponse(**item)


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: str,
    runtime: CompanionRuntime = Depends(get_runtime),
    service: ConversationService = Depends(get_service),
) -> dict[str, str]:
    deleted = runtime.delete_reminder(service.character_id, reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="reminder not found")
    return {"status": "ok"}