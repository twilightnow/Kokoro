from fastapi import APIRouter, Depends, HTTPException, Response

from ...capability.tts import TTSDisabledError, create_tts_client
from ...application.conversation_service import ConversationService
from ..service_registry import get_service
from ..schemas import TTSRequest

router = APIRouter(tags=["tts"])


@router.post("/tts")
async def synthesize_tts(
    body: TTSRequest,
    service: ConversationService = Depends(get_service),
) -> Response:
    try:
        client = create_tts_client(
            provider=service.character.modules.tts.provider or None,
            voice=body.voice or service.character.modules.tts.voice or None,
            rate=body.rate,
            volume=body.volume,
        )
        result = await client.synthesize(body.text)
    except TTSDisabledError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EnvironmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(
        content=result.audio_bytes,
        media_type=result.content_type,
        headers={
            "X-TTS-Voice": result.voice,
            "Cache-Control": "no-store",
        },
    )