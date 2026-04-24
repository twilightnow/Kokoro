from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ...application.conversation_service import ConversationService
from ...capability.tts import create_tts_client
from ..character_assets import build_character_display, load_manifest, resolve_character_asset
from ..service_registry import get_service, switch_character
from ..schemas import HealthResponse, SessionTokenTotal, StateResponse, SwitchCharacterResponse

router = APIRouter(tags=["state"])


@router.get("/state", response_model=StateResponse)
async def get_state(
    request: Request,
    service: ConversationService = Depends(get_service),
) -> StateResponse:
    state = service.character_state
    memory_ctx = service.memory_context
    token_total = service.session_token_total
    return StateResponse(
        character_id=service.character_id,
        character_name=service.character.name,
        display=build_character_display(service.character_id, str(request.base_url)),
        mood=state.mood,
        persist_count=state.persist_count,
        turn=service.turn,
        memory_summary_count=len(memory_ctx.summary_items),
        memory_fact_count=len(memory_ctx.long_term_items),
        session_token_total=SessionTokenTotal(
            input=token_total["input"],
            output=token_total["output"],
        ),
    )


@router.get("/health", response_model=HealthResponse)
async def health(
    service: ConversationService = Depends(get_service),
) -> HealthResponse:
    llm = getattr(service, "_llm", None)
    llm_provider = str(getattr(llm, "provider", "") or "")
    llm_model = str(getattr(llm, "model", "") or "")

    manifest = load_manifest(service.character_id)
    display = manifest.get("display", {}) if isinstance(manifest, dict) else {}
    display_mode = str(display.get("mode") or "placeholder")
    resource_ready = display_mode in {"live2d", "model3d"}

    try:
        tts_client = create_tts_client()
        tts_status = {
            "status": "ok",
            "provider": "edge-tts",
            "voice": str(getattr(tts_client, "voice", "")),
            "configured": True,
        }
    except Exception as exc:
        tts_status = {
            "status": "error",
            "provider": "edge-tts",
            "message": str(exc),
            "configured": False,
        }

    return HealthResponse(
        status="ok",
        character_id=service.character_id,
        character=service.character.name,
        version=service.character.version,
        sidecar={
            "status": "ok",
            "api": "FastAPI",
        },
        llm={
            "status": "ok" if llm_provider else "unconfigured",
            "provider": llm_provider,
            "model": llm_model,
            "message": str(getattr(llm, "message", "") or ""),
            "configured": bool(llm_provider),
        },
        character_resources={
            "status": "ok" if resource_ready else "fallback",
            "display_mode": display_mode,
            "configured": resource_ready,
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
