from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


class SafetySummary(BaseModel):
    level: str = "none"
    action: str = "allow"
    reason: str = ""
    rule_names: List[str] = Field(default_factory=list)
    relationship_type: str = ""
    replaced: bool = False


class EmotionSummaryResponse(BaseModel):
    mood: str = "normal"
    keyword: str = ""
    reason: str = ""
    source: str = ""
    intensity: float = 0.0
    recovery_rate: float = 0.2
    started_at_turn: int = 0
    elapsed_turns: int = 0
    estimated_remaining_turns: int = 0
    phase: str = "idle"
    rate_delta: str = ""
    volume_delta: str = ""


class RoleCardIdentityResponse(BaseModel):
    description: str = ""
    scenario: str = ""


class RoleCardPersonalityResponse(BaseModel):
    core_fear: str = ""
    surface_trait: str = ""
    hidden_trait: str = ""


class RoleCardBehaviorResponse(BaseModel):
    rules: List[str] = Field(default_factory=list)
    verbal_habits: List[str] = Field(default_factory=list)
    forbidden_words: List[str] = Field(default_factory=list)


class RoleCardDialogueResponse(BaseModel):
    first_message: str = ""
    examples: List[str] = Field(default_factory=list)
    post_history_instructions: str = ""


class RoleCardLLMModuleResponse(BaseModel):
    provider: str = ""
    model: str = ""


class RoleCardTTSModuleResponse(BaseModel):
    provider: str = ""
    voice: str = ""


class RoleCardDisplayModuleResponse(BaseModel):
    mode: str = ""


class RoleCardModulesResponse(BaseModel):
    llm: RoleCardLLMModuleResponse = Field(default_factory=RoleCardLLMModuleResponse)
    tts: RoleCardTTSModuleResponse = Field(default_factory=RoleCardTTSModuleResponse)
    display: RoleCardDisplayModuleResponse = Field(default_factory=RoleCardDisplayModuleResponse)


class RoleCardMemoryResponse(BaseModel):
    extraction_policy: str = ""
    recall_style: str = ""


class RoleCardProactiveStyleResponse(BaseModel):
    idle_too_long: str = ""
    user_working_late: str = ""
    user_gaming: str = ""


class RoleCardProactiveResponse(BaseModel):
    style: RoleCardProactiveStyleResponse = Field(default_factory=RoleCardProactiveStyleResponse)


class RoleCardResponse(BaseModel):
    schema_version: str = "1"
    identity: RoleCardIdentityResponse = Field(default_factory=RoleCardIdentityResponse)
    personality: RoleCardPersonalityResponse = Field(default_factory=RoleCardPersonalityResponse)
    behavior: RoleCardBehaviorResponse = Field(default_factory=RoleCardBehaviorResponse)
    dialogue: RoleCardDialogueResponse = Field(default_factory=RoleCardDialogueResponse)
    modules: RoleCardModulesResponse = Field(default_factory=RoleCardModulesResponse)
    memory: RoleCardMemoryResponse = Field(default_factory=RoleCardMemoryResponse)
    proactive: RoleCardProactiveResponse = Field(default_factory=RoleCardProactiveResponse)


class ChatResponse(BaseModel):
    reply: str
    mood: str
    mood_changed: bool
    flagged: bool
    turn: int
    usage: Optional[UsageInfo] = None
    emotion: Optional[EmotionSummaryResponse] = None
    safety: Optional[SafetySummary] = None
    expression_event: Optional["ExpressionEventResponse"] = None


class ExpressionEmotionResponse(BaseModel):
    name: str = "normal"
    intensity: float = 0.0
    keyword: str = ""
    reason: str = ""


class ExpressionMotionResponse(BaseModel):
    name: str = ""
    priority: int = 50


class ExpressionSpeechResponse(BaseModel):
    rate_delta: str = ""
    volume_delta: str = ""
    pause_ms: int = 0


class ExpressionPlaybackResponse(BaseModel):
    intent: str = "queue"


class ExpressionEventResponse(BaseModel):
    """表现层事件：统一情绪 / 动作 / TTS 参数，供 frontend 驱动动画和语音。"""

    emotion: ExpressionEmotionResponse = Field(default_factory=ExpressionEmotionResponse)
    motion: ExpressionMotionResponse = Field(default_factory=ExpressionMotionResponse)
    speech: ExpressionSpeechResponse = Field(default_factory=ExpressionSpeechResponse)
    playback: ExpressionPlaybackResponse = Field(default_factory=ExpressionPlaybackResponse)


class Live2DDisplayConfig(BaseModel):
    model_url: str
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    idle_group: str = "Idle"
    mood_motions: Dict[str, str] = Field(default_factory=dict)


class ImageDisplayConfig(BaseModel):
    image_url: str
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0


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
    class MorphWeight(BaseModel):
        name: str
        weight: float = 0.0

    class LipSyncConfig(BaseModel):
        names: List[str] = Field(default_factory=list)
        max_weight: float = 0.75
        smoothing: float = 0.22

    class MorphConfig(BaseModel):
        mood_weights: Dict[str, List["Model3DSkinConfig.MorphWeight"]] = Field(default_factory=dict)
        lip_sync: Optional["Model3DSkinConfig.LipSyncConfig"] = None

    label: str = ""
    model_url: str
    vmd_url: Optional[str] = None
    mood_vmd_urls: Dict[str, str] = Field(default_factory=dict)
    procedural_motion: str = "idle"
    mood_procedural_motions: Dict[str, str] = Field(default_factory=dict)
    scale: float = 1.0
    position: Model3DVector3 = Field(default_factory=Model3DVector3)
    rotation_deg: Model3DVector3 = Field(default_factory=Model3DVector3)
    camera: Model3DCameraConfig = Field(default_factory=Model3DCameraConfig)
    lights: Model3DLightConfig = Field(default_factory=Model3DLightConfig)
    morphs: Optional["Model3DSkinConfig.MorphConfig"] = None


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
    image: Optional[ImageDisplayConfig] = None


class SessionTokenTotal(BaseModel):
    input: int = 0
    output: int = 0


class RelationshipStateSnapshot(BaseModel):
    intimacy: int = 0
    trust: int = 0
    familiarity: int = 0
    interaction_quality_recent: int = 0
    preferred_addressing: str = ""
    relationship_type: str = "friend"
    boundaries_summary: str = ""
    dependency_risk: int = 0
    boundary_policy_summary: str = ""
    updated_at: str = ""
    change_reasons: List[str] = Field(default_factory=list)


class StateResponse(BaseModel):
    character_id: str
    character_name: str
    display: CharacterDisplayConfig = Field(default_factory=CharacterDisplayConfig)
    role_card: RoleCardResponse = Field(default_factory=RoleCardResponse)
    mood: str
    persist_count: int
    turn: int
    memory_summary_count: int
    memory_fact_count: int
    relationship: RelationshipStateSnapshot = Field(default_factory=RelationshipStateSnapshot)
    session_token_total: Optional[SessionTokenTotal] = None
    emotion: EmotionSummaryResponse = Field(default_factory=EmotionSummaryResponse)


class HealthResponse(BaseModel):
    status: str = "ok"
    character_id: str
    character: str
    version: str = ""
    role_card_modules: RoleCardModulesResponse = Field(default_factory=RoleCardModulesResponse)
    sidecar: Dict[str, str] = Field(default_factory=dict)
    llm: Dict[str, str | bool] = Field(default_factory=dict)
    character_resources: Dict[str, str | bool] = Field(default_factory=dict)
    tts: Dict[str, str | bool] = Field(default_factory=dict)


class SwitchCharacterResponse(BaseModel):
    character_id: str
    character_name: str
    display: CharacterDisplayConfig = Field(default_factory=CharacterDisplayConfig)
    status: str = "ok"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=400)
    voice: Optional[str] = Field(default=None, max_length=80)
    rate: Optional[str] = Field(default=None, max_length=16)
    volume: Optional[str] = Field(default=None, max_length=16)


class StreamChunk(BaseModel):
    type: str
    content: str
    id: Optional[str] = None
    level: Optional[str] = None
    scene: Optional[str] = None
    source: Optional[str] = None
    urgency: Optional[str] = None
    expression: Optional[str] = None
    actions: Optional[List[str]] = None
    mood: Optional[str] = None
    flagged: Optional[bool] = None
    emotion: Optional[EmotionSummaryResponse] = None
    expression_event: Optional[ExpressionEventResponse] = None
    safety: Optional[SafetySummary] = None


class NotifyEventRequest(BaseModel):
    """外部插件/API 推送主动事件的请求体。"""

    scene: str = Field(..., description="事件场景，合法值：late_night/long_work/idle_return/window_switch/gaming/reminder")
    urgency: str = Field(default="normal", description="紧急程度：low/normal/high/critical")
    payload: Dict[str, object] = Field(default_factory=dict, description="附加载荷，内容由来源决定")
    privacy_level: str = Field(default="public", description="隐私级别：public/private/sensitive")


Model3DSkinConfig.model_rebuild()
