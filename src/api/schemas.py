from typing import Dict, List, Optional

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


class Model3DVector3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Model3DCameraConfig(BaseModel):
    distance: float = 30.0
    fov: float = 30.0
    target: Model3DVector3 = Field(default_factory=Model3DVector3)


class Model3DLightConfig(BaseModel):
    ambient_intensity: float = 0.9
    directional_intensity: float = 1.1
    directional_position: Model3DVector3 = Field(default_factory=Model3DVector3)


class Model3DSkinConfig(BaseModel):
    label: str = ""
    model_url: str
    scale: float = 1.0
    position: Model3DVector3 = Field(default_factory=Model3DVector3)
    rotation_deg: Model3DVector3 = Field(default_factory=Model3DVector3)
    camera: Model3DCameraConfig = Field(default_factory=Model3DCameraConfig)
    lights: Model3DLightConfig = Field(default_factory=Model3DLightConfig)


class Model3DAutoSwitchConfig(BaseModel):
    enabled: bool = True
    prefer_manual: bool = True
    mood_skins: Dict[str, str] = Field(default_factory=dict)


class Model3DDisplayConfig(BaseModel):
    default_skin: str = ""
    skin_order: List[str] = Field(default_factory=list)
    auto_switch: Model3DAutoSwitchConfig = Field(default_factory=Model3DAutoSwitchConfig)
    skins: Dict[str, Model3DSkinConfig] = Field(default_factory=dict)


class CharacterDisplayConfig(BaseModel):
    mode: str = "placeholder"
    live2d: Optional[Live2DDisplayConfig] = None
    model3d: Optional[Model3DDisplayConfig] = None


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
