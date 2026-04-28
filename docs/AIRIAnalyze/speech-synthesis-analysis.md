# AIRI 语音合成分析

本文分析 airi 主仓里的 TTS 实现、播放编排和与角色表现的联动关系。

## 结论

- 语音合成在 airi 里不是一个单独 API 封装，而是一条完整输出链：
  - 文本输出
  - TTS 切分
  - 并发生成
  - 播放排队
  - 播放打断策略
  - Live2D/角色口型联动
- 主实现中心在 stage-ui 的 speech store 和 Stage.vue。
- 生成层使用 @xsai/generate-speech，provider 层由 stage-ui providers store 管理。
- 播放层使用 packages/pipelines-audio，已经有清晰的调度、优先级和中断策略。
- TTS 与角色表现是耦合设计，不只是“播一个音频文件”。

## 主实现路径

### 1. Provider 与模型配置

关键文件：

- packages/stage-ui/src/stores/modules/speech.ts
- packages/stage-ui/src/stores/providers.ts
- packages/i18n/src/locales/*/settings.yaml

speech.ts 负责：

- 当前 speech provider / model / voice 的本地持久化。
- 拉取 provider 的 voice 列表。
- 根据 provider 能力判断是否支持 SSML。
- 统一调用 generateSpeech。
- 生成 SSML 文本。

从这层可以确认：

- TTS 是可配置 provider 模块，而不是硬编码单厂商。
- OpenAI-compatible speech provider 是一等公民。
- 语速、音高、SSML、语言选择都已经有状态位。

### 2. 语音生成与播放编排

关键文件：

- packages/stage-ui/src/components/scenes/Stage.vue
- packages/pipelines-audio/src/speech-pipeline.ts
- packages/pipelines-audio/src/managers/playback-manager.ts
- packages/pipelines-audio/src/processors/tts-chunker.ts

Stage.vue 把主聊天输出接到 speech pipeline：

- 使用 createSpeechPipeline 创建 TTS 流水线。
- 内部 tts 回调调用 generateSpeech，并把返回的 ArrayBuffer 解码成 AudioBuffer。
- 使用 createPlaybackManager 管理播放。
- 播放开始/结束时同步更新 speaking 状态、字幕广播和口型状态。

speech-pipeline.ts 的职责：

- 把 token 流切成适合 TTS 的文本段。
- 支持多并发 TTS 预取。
- 即使 TTS 完成顺序乱序，也按 sequence 保证播放顺序。
- 支持 intent 级别的 queue / interrupt / replace 行为。

playback-manager.ts 的职责：

- 控制最大并发 voice 数。
- 按 owner 限流。
- 提供 queue、reject、steal-oldest、steal-lowest-priority 等溢出策略。
- 对中断、结束、拒绝分别发事件。

这说明 airi 的 TTS 链路已经是“可编排音频输出系统”，而不是简单的 audio.play。

### 3. 与角色动作和口型同步的联动

关键文件：

- packages/stage-ui/src/components/scenes/Stage.vue
- packages/stage-ui-live2d/src/composables/live2d/beat-sync.ts
- packages/model-driver-lipsync（Stage.vue 中使用）

当前已实现的联动至少包括：

- 播放开始时进入 speaking 状态。
- 通过 createLive2DLipSync 读取音频能量并驱动 mouthOpenSize。
- playbackManager.onStart / onEnd 直接控制字幕叠加与说话状态。
- 特殊 token 会触发表情和延迟逻辑，而不仅是语音播放。

这意味着 TTS 已被纳入角色“身体表现层”。

## 相关依赖和生态位置

仓内能确认的相关依赖：

- @xsai/generate-speech
- unspeech
- @proj-airi/pipelines-audio
- @proj-airi/model-driver-lipsync

README 和 i18n 里还明确把以下类型当作 speech provider 生态的一部分：

- ElevenLabs
- Microsoft Speech / Azure Speech
- Kokoro TTS（本地）
- IndexTTS
- OpenAI-compatible speech

这说明仓库不是仅支持单个 TTS API，而是围绕 provider abstraction 在做产品化。

## 当前状态判断

可以判定为“已实现并接入主舞台”。

成熟度高于纯实验代码的证据：

- 有独立 store 管理 provider / model / voice。
- 有专门的 pipeline 包处理切分、并发和顺序。
- 有播放中断和 owner 优先级策略。
- 有与 Live2D/字幕/状态机联动的实际代码。

## 当前边界和缺口

- 仓内没有看到独立的后端 TTS 服务实现，更多是前端直接接 provider 或 unspeech 兼容端点。
- SSML 支持仍然是按 provider 白名单判断，不是完全统一能力协商。
- Stage.vue 仍承担了不少“生成 + 播放 + 口型 + 字幕”集成逻辑，后续可能继续拆分。

## 最值得关注的文件

- packages/stage-ui/src/stores/modules/speech.ts
- packages/stage-ui/src/components/scenes/Stage.vue
- packages/pipelines-audio/src/speech-pipeline.ts
- packages/pipelines-audio/src/managers/playback-manager.ts
- packages/pipelines-audio/src/processors/tts-chunker.ts
