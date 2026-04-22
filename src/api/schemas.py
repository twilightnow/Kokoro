from typing import Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


class ChatResponse(BaseModel):
    reply: str
    mood: str
    mood_changed: bool
    flagged: bool
    turn: int
    usage: Optional[UsageInfo] = None


class Live2DDisplayConfig(BaseModel):
    model_url: str
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    idle_group: str = "Idle"
    tap_body_group: str = "Tap@Body"
    mood_motions: Dict[str, str] = Field(default_factory=dict)


class CharacterDisplayConfig(BaseModel):
    mode: str = "placeholder"
    live2d: Optional[Live2DDisplayConfig] = None


class SessionTokenTotal(BaseModel):
    input: int = 0
    output: int = 0


class StateResponse(BaseModel):
    character_id: str
    character_name: str
    display: CharacterDisplayConfig = Field(default_factory=CharacterDisplayConfig)
    mood: str
    persist_count: int
    turn: int
    memory_summary_count: int
    memory_fact_count: int
    session_token_total: Optional[SessionTokenTotal] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    character_id: str
    character: str
    version: str = ""


class SwitchCharacterResponse(BaseModel):
    character_id: str
    character_name: str
    display: CharacterDisplayConfig = Field(default_factory=CharacterDisplayConfig)
    status: str = "ok"


class StreamChunk(BaseModel):
    type: str
    content: str
    mood: Optional[str] = None
    flagged: Optional[bool] = None
