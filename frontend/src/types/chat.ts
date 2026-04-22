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

export interface CharacterDisplayConfig {
  mode: 'placeholder' | 'live2d' | string
  live2d?: Live2DDisplayConfig
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
