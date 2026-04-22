export type Mood = string

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
