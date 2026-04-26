"""Relationship state management API."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ....application.conversation_service import ConversationService
from ....runtime.relationship_service import RelationshipState
from ....safety.policy import SafetyPolicy
from ...schemas import RelationshipStateSnapshot
from ...service_registry import get_service

router = APIRouter(prefix="/relationship", tags=["relationship"])


class RelationshipAdminResponse(RelationshipStateSnapshot):
    character_id: str


class RelationshipUpdateRequest(BaseModel):
    relationship_type: str = Field(default="friend", min_length=1, max_length=24)
    preferred_addressing: str = Field(default="", max_length=40)
    boundaries_summary: str = Field(default="", max_length=240)


def _to_response(character_id: str, state: RelationshipState) -> RelationshipAdminResponse:
    return RelationshipAdminResponse(
        character_id=character_id,
        intimacy=state.intimacy,
        trust=state.trust,
        familiarity=state.familiarity,
        interaction_quality_recent=state.interaction_quality_recent,
        preferred_addressing=state.preferred_addressing,
        relationship_type=state.relationship_type,
        boundaries_summary=state.boundaries_summary,
        dependency_risk=state.dependency_risk,
        boundary_policy_summary=SafetyPolicy().boundary_summary(state.relationship_type),
        updated_at=state.updated_at,
        change_reasons=state.change_reasons,
    )


@router.get("/{character_id}", response_model=RelationshipAdminResponse)
async def get_relationship(
    character_id: str,
    service: ConversationService = Depends(get_service),
) -> RelationshipAdminResponse:
    return _to_response(character_id, service.relationship_service.get_state(character_id))


@router.put("/{character_id}", response_model=RelationshipAdminResponse)
async def update_relationship(
    character_id: str,
    body: RelationshipUpdateRequest,
    service: ConversationService = Depends(get_service),
) -> RelationshipAdminResponse:
    state = service.relationship_service.update_profile(
        character_id,
        relationship_type=body.relationship_type,
        preferred_addressing=body.preferred_addressing,
        boundaries_summary=body.boundaries_summary,
    )
    return _to_response(character_id, state)


@router.post("/{character_id}/reset", response_model=RelationshipAdminResponse)
async def reset_relationship(
    character_id: str,
    service: ConversationService = Depends(get_service),
) -> RelationshipAdminResponse:
    return _to_response(character_id, service.relationship_service.reset_state(character_id))
