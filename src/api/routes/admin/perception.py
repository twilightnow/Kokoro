from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ....perception.privacy import PrivacySettings
from ....runtime.companion_runtime import CompanionRuntime
from ...service_registry import get_runtime

router = APIRouter(prefix="/perception")


class PerceptionSettingsResponse(BaseModel):
    settings: dict[str, Any]


class PerceptionSettingsRequest(BaseModel):
    settings: dict[str, Any]


class PerceptionAuditResponse(BaseModel):
    items: list[dict[str, Any]]


@router.get("/settings", response_model=PerceptionSettingsResponse)
async def get_settings(
    runtime: CompanionRuntime = Depends(get_runtime),
) -> PerceptionSettingsResponse:
    return PerceptionSettingsResponse(settings=runtime.get_privacy_settings().to_dict())


@router.put("/settings", response_model=PerceptionSettingsResponse)
async def update_settings(
    body: PerceptionSettingsRequest,
    runtime: CompanionRuntime = Depends(get_runtime),
) -> PerceptionSettingsResponse:
    current = runtime.get_privacy_settings().to_dict()
    current.update(body.settings)
    settings = PrivacySettings.from_mapping(current)
    saved = runtime.update_privacy_settings(settings)
    return PerceptionSettingsResponse(settings=saved.to_dict())


@router.get("/audit", response_model=PerceptionAuditResponse)
async def get_audit(
    limit: int = Query(default=50, ge=1, le=200),
    runtime: CompanionRuntime = Depends(get_runtime),
) -> PerceptionAuditResponse:
    return PerceptionAuditResponse(items=runtime.get_perception_audit(limit=limit))


@router.get("/status")
async def get_status(
    runtime: CompanionRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    return runtime.get_perception_status()
