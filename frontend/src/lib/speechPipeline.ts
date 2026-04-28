/**
 * SpeechPipeline — 可编排的语音输出系统
 *
 * 功能：
 * - 按段落队列顺序播放 TTS 音频
 * - 并发预取（最多 MAX_PREFETCH 个 TTS 请求同时在途）
 * - Playback intent：queue / interrupt / replace / drop_if_busy
 * - Owner/Priority：system > reminder > proactive > chat
 * - 播放状态驱动嘴型分析和 speaking 通知
 * - 修复了原实现中 audio.pause() 后 onended 永不触发导致 Promise hang 的问题
 */

import type { EmotionSummary } from '../types/chat'

// ─── Public types ─────────────────────────────────────────────────────────────

export type PlaybackIntent = 'queue' | 'interrupt' | 'replace' | 'drop_if_busy'
export type SpeechOwner = 'chat' | 'proactive' | 'reminder' | 'system'

export const OWNER_PRIORITY: Record<SpeechOwner, number> = {
  system: 300,
  reminder: 200,
  proactive: 150,
  chat: 100,
}

export interface SpeechRequest {
  text: string
  owner?: SpeechOwner
  intent?: PlaybackIntent
  emotion?: EmotionSummary | null
  pauseMs?: number
}

export interface SpeechPipelineCallbacks {
  /** 播放状态变化（true = 开始播放，false = 停止） */
  onSpeakingChange(speaking: boolean): void
  /** 嘴型分析幅度 [0, 1] */
  onLipSyncLevel(level: number): void
  /** 播放或 TTS 请求发生错误 */
  onError(message: string): void
  /** 请求 TTS 音频，返回 object URL 或 null */
  fetchAudio(text: string, emotion: EmotionSummary | null): Promise<string | null>
}

// ─── Internal types ────────────────────────────────────────────────────────────

interface QueuedSegment {
  readonly id: number
  readonly text: string
  readonly owner: SpeechOwner
  readonly priority: number
  readonly emotion: EmotionSummary | null
  readonly pauseMs: number
}

// ─── Constants ────────────────────────────────────────────────────────────────

/** 最多同时预取的 TTS 请求数 */
const MAX_PREFETCH = 3

// ─── Helpers ──────────────────────────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

// ─── SpeechPipeline ───────────────────────────────────────────────────────────

export class SpeechPipeline {
  private readonly callbacks: SpeechPipelineCallbacks

  // Queue
  private queue: QueuedSegment[] = []
  private prefetchCache = new Map<number, Promise<string | null>>()
  private nextSegmentId = 0

  // Loop control
  private revision = 0
  private isLoopRunning = false

  // Current playback
  private activeAudio: HTMLAudioElement | null = null
  private activeAudioUrl: string | null = null
  private resolvePlayback: (() => void) | null = null
  private currentPlayingPriority = 0

  // Lip-sync (Web Audio API)
  private audioContext: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private analyserBuffer: Uint8Array<ArrayBuffer> | null = null
  private lipSyncFrameId = 0

  // Enabled flag
  private _enabled = true

  constructor(callbacks: SpeechPipelineCallbacks) {
    this.callbacks = callbacks
  }

  // ─── Public API ─────────────────────────────────────────────────────────────

  get enabled(): boolean {
    return this._enabled
  }

  setEnabled(value: boolean): void {
    this._enabled = value
    if (!value) {
      this.stop()
    }
  }

  /**
   * 将一段文本加入播放管道。
   * intent 控制与当前队列/播放的关系，见 PlaybackIntent。
   */
  enqueue(req: SpeechRequest): void {
    const text = req.text.replace(/\s+/g, ' ').trim()
    if (!text || !this._enabled) {
      return
    }

    const owner = req.owner ?? 'chat'
    const segment: QueuedSegment = {
      id: this.nextSegmentId++,
      text,
      owner,
      priority: OWNER_PRIORITY[owner],
      emotion: req.emotion ?? null,
      pauseMs: req.pauseMs ?? 0,
    }

    const intent = req.intent ?? 'queue'

    switch (intent) {
      case 'interrupt':
        this._interruptAll(segment)
        break
      case 'replace':
        this._replaceByPriority(segment)
        break
      case 'drop_if_busy':
        if (this._isBusy()) {
          return
        }
        this.queue.push(segment)
        break
      default:
        this.queue.push(segment)
        break
    }

    this._schedulePrefetch()
    this._startLoop()
  }

  /** 停止一切播放并清空队列。 */
  stop(): void {
    this._interruptAll(null)
  }

  /** 当前是否正在播放或有待播段。 */
  isBusy(): boolean {
    return this._isBusy()
  }

  // ─── Intent handlers ────────────────────────────────────────────────────────

  private _isBusy(): boolean {
    return this.activeAudio !== null || this.queue.length > 0
  }

  /**
   * 中断所有内容（递增 revision，清空队列，停止当前音频）。
   * 如果 next 不为 null，将其插入队列。
   */
  private _interruptAll(next: QueuedSegment | null): void {
    this.revision++
    this._clearQueue()
    this._clearActiveAudio()
    if (next) {
      this.queue.push(next)
    }
  }

  /**
   * 替换优先级 ≤ segment.priority 的所有内容（队列 + 当前播放），
   * 将 segment 插入队列首位。
   */
  private _replaceByPriority(segment: QueuedSegment): void {
    const evicted = this.queue.filter(s => s.priority <= segment.priority)
    this.queue = this.queue.filter(s => s.priority > segment.priority)
    for (const s of evicted) {
      this._evictPrefetch(s.id)
    }

    if (this.activeAudio && this.currentPlayingPriority <= segment.priority) {
      this.revision++
      this._clearActiveAudio()
    }

    this.queue.unshift(segment)
  }

  // ─── Queue / prefetch helpers ────────────────────────────────────────────────

  private _clearQueue(): void {
    for (const s of this.queue) {
      this._evictPrefetch(s.id)
    }
    this.queue = []
  }

  private _evictPrefetch(segmentId: number): void {
    const p = this.prefetchCache.get(segmentId)
    this.prefetchCache.delete(segmentId)
    if (p) {
      void p.then(url => {
        if (url) {
          URL.revokeObjectURL(url)
        }
      })
    }
  }

  /**
   * 为队列中靠前的若干 segment 提前发起 TTS 请求，
   * 结果缓存在 prefetchCache，由 _run() 循环按序消费。
   */
  private _schedulePrefetch(): void {
    let count = 0
    for (const segment of this.queue) {
      if (count >= MAX_PREFETCH) {
        break
      }
      if (!this.prefetchCache.has(segment.id)) {
        const { text, emotion } = segment
        this.prefetchCache.set(
          segment.id,
          this.callbacks.fetchAudio(text, emotion).catch(() => null),
        )
      }
      count++
    }
  }

  // ─── Playback loop ───────────────────────────────────────────────────────────

  private _startLoop(): void {
    if (this.isLoopRunning) {
      return
    }
    this.isLoopRunning = true
    void this._run()
  }

  private async _run(): Promise<void> {
    try {
      while (this.queue.length > 0) {
        const segment = this.queue.shift()!
        const myRevision = this.revision

        // 每取出一段就预取后续段
        this._schedulePrefetch()

        // 段前停顿
        if (segment.pauseMs > 0) {
          await sleep(segment.pauseMs)
          if (this.revision !== myRevision) {
            continue
          }
        }

        // 获取音频 URL（优先使用预取缓存）
        const cached = this.prefetchCache.get(segment.id)
        this.prefetchCache.delete(segment.id)

        let audioUrl: string | null
        try {
          audioUrl = cached
            ? await cached
            : await this.callbacks.fetchAudio(segment.text, segment.emotion)
        } catch {
          audioUrl = null
        }

        if (this.revision !== myRevision) {
          if (audioUrl) {
            URL.revokeObjectURL(audioUrl)
          }
          continue
        }

        if (!audioUrl) {
          continue
        }

        this.currentPlayingPriority = segment.priority
        try {
          await this._playAudio(audioUrl, myRevision)
        } catch (error) {
          this.callbacks.onError(error instanceof Error ? error.message : '音频播放失败')
          this._clearActiveAudio()
        } finally {
          this.currentPlayingPriority = 0
        }
      }
    } finally {
      this.isLoopRunning = false
      // 如果在收尾期间有新段入队，重新启动循环
      if (this.queue.length > 0) {
        this._startLoop()
      }
    }
  }

  // ─── Audio playback ──────────────────────────────────────────────────────────

  private async _playAudio(url: string, myRevision: number): Promise<void> {
    this._clearActiveAudio()

    if (this.revision !== myRevision) {
      URL.revokeObjectURL(url)
      return
    }

    const audio = new Audio(url)
    this.activeAudio = audio
    this.activeAudioUrl = url
    this.callbacks.onSpeakingChange(true)

    try {
      await this._connectAudioGraph(audio)
    } catch {
      // 嘴型分析为 best-effort，不阻塞播放
    }

    // 若在建立 AudioGraph 期间被中断，提前退出（activeAudio 已被清理）
    if (this.revision !== myRevision) {
      return
    }

    return new Promise<void>((resolve, reject) => {
      // 保存 resolve，让 _clearActiveAudio 可以在中断时提前结束 Promise
      this.resolvePlayback = resolve

      audio.onended = () => {
        this.resolvePlayback = null
        this._clearActiveAudio()
        resolve()
      }

      audio.onerror = () => {
        this.resolvePlayback = null
        reject(new Error('音频播放失败'))
      }

      void audio.play()
        .then(() => {
          this._startLipSync()
        })
        .catch(err => {
          this.resolvePlayback = null
          reject(err instanceof Error ? err : new Error('音频播放启动失败'))
        })
    })
  }

  /**
   * 清理当前音频播放状态。
   * 关键：通过 resolvePlayback() 主动结束挂起的 Promise，
   * 避免 audio.pause() 后 onended 永不触发而导致 Promise hang。
   */
  private _clearActiveAudio(): void {
    this.activeAudio?.pause()
    this.activeAudio = null

    if (this.activeAudioUrl) {
      URL.revokeObjectURL(this.activeAudioUrl)
      this.activeAudioUrl = null
    }

    // 主动结束挂起的播放 Promise
    if (this.resolvePlayback) {
      this.resolvePlayback()
      this.resolvePlayback = null
    }

    this._stopLipSync()
    this.callbacks.onSpeakingChange(false)
  }

  // ─── Web Audio / Lip-sync ────────────────────────────────────────────────────

  private async _connectAudioGraph(audio: HTMLAudioElement): Promise<void> {
    if (typeof AudioContext === 'undefined') {
      return
    }

    if (!this.audioContext) {
      this.audioContext = new AudioContext()
    }
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume()
    }

    // 断开并释放旧的 analyser
    if (this.analyser) {
      this.analyser.disconnect()
    }
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 512
    this.analyserBuffer = new Uint8Array(this.analyser.frequencyBinCount) as Uint8Array<ArrayBuffer>

    const source = this.audioContext.createMediaElementSource(audio)
    source.connect(this.analyser)
    this.analyser.connect(this.audioContext.destination)
  }

  private _startLipSync(): void {
    if (!this.analyser || !this.analyserBuffer) {
      this.callbacks.onLipSyncLevel(0)
      return
    }

    const tick = (): void => {
      if (!this.analyser || !this.analyserBuffer) {
        this.callbacks.onLipSyncLevel(0)
        return
      }
      this.analyser.getByteTimeDomainData(this.analyserBuffer)
      let sum = 0
      for (const v of this.analyserBuffer) {
        const centered = (v - 128) / 128
        sum += centered * centered
      }
      const rms = Math.sqrt(sum / this.analyserBuffer.length)
      this.callbacks.onLipSyncLevel(Math.min(1, rms * 6.5))
      this.lipSyncFrameId = window.requestAnimationFrame(tick)
    }

    this._stopLipSync()
    this.lipSyncFrameId = window.requestAnimationFrame(tick)
  }

  private _stopLipSync(): void {
    if (this.lipSyncFrameId) {
      window.cancelAnimationFrame(this.lipSyncFrameId)
      this.lipSyncFrameId = 0
    }
    this.callbacks.onLipSyncLevel(0)
  }
}
