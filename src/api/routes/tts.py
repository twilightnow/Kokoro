from fastapi import APIRouter, HTTPException, Response

from ...capability.tts import create_tts_client
from ..schemas import TTSRequest

router = APIRouter(tags=["tts"])


@router.post("/tts")
async def synthesize_tts(body: TTSRequest) -> Response:
    try:
        client = create_tts_client(
            voice=body.voice,
            rate=body.rate,
            volume=body.volume,
        )
        result = await client.synthesize(body.text)
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