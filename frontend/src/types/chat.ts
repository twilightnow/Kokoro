export type Mood = string
export type ProactiveLevel = 'silent' | 'expression' | 'short' | 'full'

export interface ExpressionEventEmotion {
  name: string
  intensity: number
  keyword: string
  reason: string
}

export interface ExpressionEventMotion {
  name: string
  priority: number
}

export interface ExpressionEventSpeech {
  rate_delta: string
  volume_delta: string
  pause_ms: number
}

export interface ExpressionEventPlayback {
  intent: 'queue' | 'immediate' | string
}

export interface ExpressionEvent {
  emotion: ExpressionEventEmotion
  motion: ExpressionEventMotion
  speech: ExpressionEventSpeech
  playback: ExpressionEventPlayback
}

export interface EmotionSummary {
  mood: Mood
  keyword: string
  reason: string
  source: string
  intensity: number
  recovery_rate: number
  started_at_turn: number
  elapsed_turns: number
  estimated_remaining_turns: number
  phase: 'idle' | 'triggered' | 'steady' | 'recovering' | string
  rate_delta: string
  volume_delta: string
}

export interface Live2DDisplayConfig {
  model_url: string
  scale: number
  offset_x: number
  offset_y: number
  idle_group: string
  mood_motions: Record<string, string>
}

export interface ImageDisplayConfig {
  image_url: string
  scale: number
  offset_x: number
  offset_y: number
}

export interface Model3DVector3 {
  x: number
  y: number
  z: number
}

export interface Model3DCameraConfig {
  distance: number
  fov: number
  target: Model3DVector3
}

export interface Model3DLightConfig {
  ambient_intensity: number
  directional_intensity: number
  directional_position: Model3DVector3
}

export interface Model3DMorphWeight {
  name: string
  weight: number
}

export interface Model3DLipSyncConfig {
  names: string[]
  max_weight: number
  smoothing: number
}

export interface Model3DMorphConfig {
  mood_weights: Record<string, Model3DMorphWeight[]>
  lip_sync?: Model3DLipSyncConfig
}

export interface Model3DSkinConfig {
  label: string
  model_url: string
  vmd_url?: string
  mood_vmd_urls?: Record<string, string>
  procedural_motion?: string
  mood_procedural_motions?: Record<string, string>
  scale: number
  position: Model3DVector3
  rotation_deg: Model3DVector3
  camera: Model3DCameraConfig
  lights: Model3DLightConfig
  morphs?: Model3DMorphConfig
}

export interface Model3DAutoSwitchConfig {
  enabled: boolean
  prefer_manual: boolean
  mood_skins: Record<string, string>
}

export interface Model3DDisplayConfig {
  default_skin: string
  skin_order: string[]
  auto_switch: Model3DAutoSwitchConfig
  skins: Record<string, Model3DSkinConfig>
}

export interface CharacterDisplayConfig {
  mode: 'placeholder' | 'live2d' | 'model3d' | 'image' | string
  live2d?: Live2DDisplayConfig
  model3d?: Model3DDisplayConfig
  image?: ImageDisplayConfig
}

export interface ChatState {
  mood: Mood
  reply: string
  isThinking: boolean
}

export interface StreamChunk {
  type: 'thinking' | 'token' | 'done' | 'error' | 'proactive'
  content: string
  id?: string
  level?: ProactiveLevel
  scene?: string
  source?: string
  urgency?: string
  expression?: Mood
  actions?: string[]
  mood?: Mood
  flagged?: boolean
  emotion?: EmotionSummary
  expression_event?: ExpressionEvent
}
