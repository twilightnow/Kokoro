export type Mood = string

export interface Live2DDisplayConfig {
  model_url: string
  scale: number
  offset_x: number
  offset_y: number
  idle_group: string
  tap_body_group: string
  mood_motions: Record<string, string>
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

export interface Model3DSkinConfig {
  label: string
  model_url: string
  scale: number
  position: Model3DVector3
  rotation_deg: Model3DVector3
  camera: Model3DCameraConfig
  lights: Model3DLightConfig
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
  mode: 'placeholder' | 'live2d' | 'model3d' | string
  live2d?: Live2DDisplayConfig
  model3d?: Model3DDisplayConfig
}

export interface ChatState {
  mood: Mood
  reply: string
  isThinking: boolean
}

export interface StreamChunk {
  type: 'thinking' | 'token' | 'done' | 'error' | 'proactive'
  content: string
  mood?: Mood
  flagged?: boolean
}
