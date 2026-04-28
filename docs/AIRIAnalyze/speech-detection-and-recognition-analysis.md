# AIRI 语音检测与语音识别分析

本文只分析 airi 主仓当前代码，不把 README 中引用的外部子项目当作仓内实现。

## 结论

- 语音输入主链路已经落地，而且是前端本地采集驱动的实现，不是纯文档占位。
- 当前主入口在 Stage Web 和 Stage Pocket 首页，流程是“麦克风流 -> VAD -> 录音或流式转写 -> chat ingest”。
- VAD 主实现位于 stage-ui，基于 Silero VAD ONNX 模型和 AudioWorklet。
- STT 同时支持两类模式：
  - 文件式转写：录音结束后调用 generateTranscription。
  - 流式转写：对支持 stream input 的 provider 持续推送 PCM 数据。
- “浏览器 Web Speech API”和“阿里云实时转写”都已经有专门接线。
- 仓内确实有一份 stage-pocket 私有 VAD worker，但首页主路径实际使用的是 stage-ui 的 VAD store 和 worklet。

## 主实现路径

### 1. 页面入口

主入口文件：

- apps/stage-web/src/pages/index.vue
- apps/stage-pocket/src/pages/index.vue

两个页面都使用同一套模式：

1. 从 settings audio device store 取得 MediaStream。
2. 用 useVAD 初始化说话检测。
3. 说话开始时：
   - 若 provider 支持 stream input，则直接开始流式转写。
   - 否则开始本地录音。
4. 说话结束时：
   - 流式模式下保持会话，交给 idle timer 回收。
   - 非流式模式下停止录音并上传录音结果转写。
5. 拿到文本后直接调用 chatStore.ingest，把语音输入转成聊天输入。

这说明 airi 的“耳朵”不是孤立 demo，而是接到了主聊天流程里。

### 2. VAD 主路径

关键文件：

- packages/stage-ui/src/stores/ai/models/vad.ts
- packages/stage-ui/src/workers/vad/vad.ts
- packages/stage-ui/src/workers/vad/process.worklet.ts
- packages/stage-ui/src/libs/audio/vad.ts

职责拆分：

- stores/ai/models/vad.ts
  - 暴露 useVAD。
  - 负责初始化模型、绑定 speech-start / speech-end 事件、管理阈值和状态。
- workers/vad/vad.ts
  - 真正的检测器实现。
  - 使用 @huggingface/transformers 加载 onnx-community/silero-vad。
  - 维护状态张量、概率阈值、前后 padding、最短语音和静音结束条件。
- workers/vad/process.worklet.ts
  - 把实时音频帧整理成最小 chunk 后发回主线程。
- libs/audio/vad.ts
  - 负责 AudioContext、MediaStreamSource、AudioWorkletNode 的音频图管理。

当前默认参数能看出这是可用型实现，不只是占位：

- sampleRate: 16000
- speechThreshold: 0.6 或 VAD 内部默认 0.3
- minSilenceDurationMs: 400
- minSpeechDurationMs: 250
- speechPadMs: 80

### 3. STT 主路径

关键文件：

- packages/stage-ui/src/stores/modules/hearing.ts
- packages/stage-ui/src/stores/providers/web-speech-api/index.ts
- packages/stage-ui/src/stores/providers/aliyun/stream-transcription.ts

hearing.ts 是真正的语音输入编排中心，负责：

- 维护当前 transcription provider / model 配置。
- 根据 provider feature 判断走 generate 还是 stream。
- 管理流式转写 session 生命周期。
- 在 provider 不支持 stream input 时退回录音文件转写。
- 提供 confidence threshold 过滤低置信度片段。

其中有几条明确的实现判断：

- generateTranscription 来自 @xsai/generate-transcription，说明非流式路径已经接到 xsAI/OpenAI-compatible 生态。
- STREAM_TRANSCRIPTION_EXECUTORS 至少接了阿里云实时转写。
- providerId 为 browser-web-speech-api 时，直接走浏览器原生 SpeechRecognition，而不是先录音再上传。
- 流式会话带 idle timeout 与 AbortController，说明实现考虑了麦克风常开时的资源回收。

## 相关依赖与 provider 能力

可确认的相关依赖：

- @huggingface/transformers
- @xsai/generate-transcription
- @xsai/stream-transcription
- unspeech
- onnxruntime-web

可确认的能力特征：

- providers store 内部保存 supportsStreamInput 等能力位。
- README 和 i18n 已经把 transcription / speech 作为一等 provider 类型暴露到设置页。
- stage-pocket、stage-web、stage-tamagotchi 的 package.json 都声明了 stream-transcription 和 unspeech 相关依赖。

## 辅助和重复实现

apps/stage-pocket/src/workers/vad 下也有一套 VAD 代码，但从首页接线看：

- 主页面实际 import 的是 @proj-airi/stage-ui/workers/vad/process.worklet。
- 实际调用的是 @proj-airi/stage-ui/stores/ai/models/vad 的 useVAD。

因此 stage-pocket/src/workers/vad 更像移动端实验/并行实现，不是当前主产品路径的唯一来源。

## 当前状态判断

可以判定为“已实现并接入主流程”，不是纯规划。

但仍有几个明显边界：

- 仓内没有看到统一的服务端 ASR 网关实现，更多是前端直接对 provider 发起调用。
- realtime / stream provider 的支持是分 provider 特判的，不是完全统一抽象。
- VAD 与转写已联动，但还没有看到更高层的“长时间监听 + 对话轮次调度 + 主动唤起”完整系统。

## 最值得关注的文件

- packages/stage-ui/src/stores/modules/hearing.ts
- packages/stage-ui/src/stores/ai/models/vad.ts
- packages/stage-ui/src/workers/vad/vad.ts
- apps/stage-web/src/pages/index.vue
- apps/stage-pocket/src/pages/index.vue
