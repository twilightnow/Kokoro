from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ...application.conversation_service import ConversationService
from ...capability.tts import create_tts_client, read_tts_provider, resolve_tts_provider
from ..character_assets import build_character_display, load_manifest, resolve_character_asset, validate_character_manifest
from ..service_registry import get_service, switch_character
from ..schemas import EmotionSummaryResponse, HealthResponse, RelationshipStateSnapshot, SessionTokenTotal, StateResponse, SwitchCharacterResponse

router = APIRouter(tags=["state"])


@router.get("/state", response_model=StateResponse)
async def get_state(
    request: Request,
    service: ConversationService = Depends(get_service),
) -> StateResponse:
    state = service.character_state
    relationship = service.relationship_state
    memory_ctx = service.memory_context
    token_total = service.session_token_total
    return StateResponse(
        character_id=service.character_id,
        character_name=service.character.name,
        display=build_character_display(service.character_id, str(request.base_url)),
        role_card=service.character.to_role_card_payload(),
        mood=state.mood,
        persist_count=state.persist_count,
        turn=service.turn,
        memory_summary_count=len(memory_ctx.summary_items),
        memory_fact_count=len(memory_ctx.long_term_items),
        relationship=RelationshipStateSnapshot(
            intimacy=relationship.intimacy,
            trust=relationship.trust,
            familiarity=relationship.familiarity,
            interaction_quality_recent=relationship.interaction_quality_recent,
            preferred_addressing=relationship.preferred_addressing,
            relationship_type=relationship.relationship_type,
            boundaries_summary=relationship.boundaries_summary,
            dependency_risk=relationship.dependency_risk,
            updated_at=relationship.updated_at,
            change_reasons=relationship.change_reasons,
        ),
        session_token_total=SessionTokenTotal(
            input=token_total["input"],
            output=token_total["output"],
        ),
        emotion=EmotionSummaryResponse(**service.current_emotion_summary.__dict__),
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    service: ConversationService = Depends(get_service),
) -> HealthResponse:
    llm = getattr(service, "_llm", None)
    llm_provider = str(getattr(llm, "provider", "") or "")
    llm_model = str(getattr(llm, "model", "") or "")
    role_card_modules = service.character.to_role_card_payload()["modules"]
    requested_llm_provider = service.character.modules.llm.provider or llm_provider
    requested_llm_model = service.character.modules.llm.model or llm_model

    manifest = load_manifest(service.character_id)
    display = manifest.get("display", {}) if isinstance(manifest, dict) else {}
    validation = validate_character_manifest(service.character_id)
    display_mode = str(
        service.character.modules.display.mode
        or validation.get("requested_mode")
        or display.get("mode")
        or "placeholder"
    )
    resolved_mode = str(validation.get("resolved_mode") or "placeholder")
    resource_ready = resolved_mode in {"live2d", "model3d", "image"}
    validation_notes = validation.get("warnings") or validation.get("errors") or []

    requested_tts_provider = read_tts_provider(service.character.modules.tts.provider or None)
    try:
        resolved_tts_provider = resolve_tts_provider(requested_tts_provider)
        if resolved_tts_provider == "disabled":
            tts_status = {
                "status": "disabled",
                "provider": "disabled",
                "message": "TTS 已禁用",
                "configured": False,
            }
        else:
            tts_client = create_tts_client(
                provider=resolved_tts_provider,
                voice=service.character.modules.tts.voice or None,
            )
            tts_status = {
                "status": "ok",
                "provider": resolved_tts_provider,
                "voice": str(getattr(tts_client, "voice", "")),
                "configured": True,
            }
    except Exception as exc:
        tts_status = {
            "status": "error",
            "provider": requested_tts_provider,
            "message": str(exc),
            "configured": False,
        }

    return HealthResponse(
        status="ok",
        character_id=service.character_id,
        character=service.character.name,
        version=service.character.version,
        role_card_modules=role_card_modules,
        sidecar={
            "status": "ok",
            "api": "FastAPI",
        },
        llm={
            "status": "ok" if llm_provider else "unconfigured",
            "provider": llm_provider,
            "model": llm_model,
            "requested_provider": requested_llm_provider,
            "requested_model": requested_llm_model,
            "message": str(getattr(llm, "message", "") or ""),
            "configured": bool(llm_provider),
        },
        character_resources={
            "status": "ok" if resource_ready and resolved_mode == display_mode and not validation_notes else "fallback",
            "display_mode": display_mode,
            "resolved_mode": resolved_mode,
            "configured": resource_ready,
            "message": "；".join(str(item) for item in validation_notes[:2]),
        },
        tts=tts_status,
    )


@router.get("/character-assets/{character_id}/{asset_path:path}", name="get_character_asset")
async def get_character_asset(character_id: str, asset_path: str) -> FileResponse:
    try:
        file_path = resolve_character_asset(character_id, asset_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="asset not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return FileResponse(file_path)


@router.post("/switch-character", response_model=SwitchCharacterResponse)
async def post_switch_character(request: Request, name: str) -> SwitchCharacterResponse:
    try:
        character_id, char_name = await switch_character(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return SwitchCharacterResponse(
        character_id=character_id,
        character_name=char_name,
        display=build_character_display(character_id, str(request.base_url)),
        status="ok",
    )
