"""TTS provider abstraction."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import edge_tts


class TTSDisabledError(RuntimeError):
    """Raised when TTS is intentionally disabled by configuration."""


@dataclass
class TTSResult:
    audio_bytes: bytes
    content_type: str = "audio/mpeg"
    voice: str = ""


class TTSClient(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> TTSResult:
        raise NotImplementedError


class EdgeTTSClient(TTSClient):
    def __init__(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
    ) -> None:
        self.voice = voice or os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
        self.rate = rate or os.environ.get("TTS_RATE", "+0%")
        self.volume = volume or os.environ.get("TTS_VOLUME", "+0%")

    async def synthesize(self, text: str) -> TTSResult:
        audio_chunks: list[bytes] = []
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        try:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    data = chunk.get("data")
                    if isinstance(data, bytes):
                        audio_chunks.append(data)
        except Exception as exc:
            raise RuntimeError(f"TTS 合成失败: {exc}") from exc

        if not audio_chunks:
            raise RuntimeError("TTS 合成失败: 未生成音频数据")

        return TTSResult(
            audio_bytes=b"".join(audio_chunks),
            voice=self.voice,
        )


def read_tts_provider(provider: Optional[str] = None) -> str:
    resolved = (provider or os.environ.get("TTS_PROVIDER") or "edge-tts").strip().lower()
    return resolved or "edge-tts"


def resolve_tts_provider(provider: Optional[str] = None) -> str:
    resolved = read_tts_provider(provider)
    if resolved in {"edge-tts", "edge_tts", "edge"}:
        return "edge-tts"
    if resolved == "disabled":
        return "disabled"
    raise EnvironmentError(f"不支持的 TTS_PROVIDER: {resolved}")


def create_tts_client(
    provider: Optional[str] = None,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    volume: Optional[str] = None,
) -> TTSClient:
    resolved = resolve_tts_provider(provider)
    if resolved == "disabled":
        raise TTSDisabledError("TTS 已禁用")
    return EdgeTTSClient(voice=voice, rate=rate, volume=volume)