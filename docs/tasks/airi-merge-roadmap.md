---
tags:
  - Kokoro
  - AIRI
  - roadmap
status: draft
created: 2026-04-28
updated: 2026-04-28
---

# Kokoro x AIRI 合并路线

本文基于 `docs/AIRIAnalyze/` 的分析结果，按“做一个尽可能完整、稳定、有生命感的 AI 人格伴侣产品”来判断 AIRI 中哪些能力值得吸收，以及如何合并到 Kokoro。

核心判断：Kokoro 不应照搬 AIRI 的仓库形态和全部技术栈，而应吸收 AIRI 在“人格卡、表现事件、语音链路、Live2D 工程化、事件反应、记忆召回、computer-use 安全边界”上的产品设计。

## 相关路径
C:\WorkSpace\6_Source\2_VScode\99_gitProject\Kokoro\docs\AIRIAnalyze\overview.md
C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi

## 产品价值排序

| 优先级 | 能力 | 产品价值 | Kokoro 当前基础 | 合并判断 |
| --- | --- | --- | --- | --- |
| P0 | 角色卡系统 | 决定“她是谁”、是否可长期稳定相处 | 已有 `characters/*/personality.yaml` | 必须做，优先演进现有角色配置 |
| P0 | 表现层事件协议 | 决定文本、情绪、动作、声音是否一致 | 已有情绪状态、Live2D、3D、TTS | 必须做，作为表现层核心契约 |
| P0 | TTS 播放流水线 | 决定角色存在感和语音体验 | 已有 Edge TTS、分段播放、嘴型分析 | 必须做，升级为队列和打断系统 |
| P0 | 主动联系 / notify 事件入口 | 决定是否像桌面伴侣，而不是聊天框 | 已有 proactive、reminder、perception | 必须做，统一外部事件入口 |
| P1 | 长期记忆闭环 | 决定是否真正长期陪伴 | 已有工作/摘要/长期记忆和候选抽取 | 必须做，但先强化结构化记忆，不急上 pgvector |
| P1 | VAD + STT 语音输入 | 决定自然交互上限 | 已有浏览器语音识别和内部事件入口 | 应做，分阶段接入 |
| P1 | Live2D / 3D 身体运行时 | 决定沉浸感和角色身体质量 | 已有 Live2DCanvas、Model3DCanvas、角色资源 | 应做，逐步工程化 |
| P2 | 插件 / 外部事件生态 | 决定长期扩展能力 | sidecar/API 已有雏形 | 后做，先稳定内部事件协议 |
| P2 | computer-use 安全底座 | 决定能否陪用户完成真实任务 | 当前未作为主能力 | 谨慎做，必须审批、审计、权限隔离 |
| P3 | pgvector / 大规模 RAG | 决定大规模记忆检索能力 | 当前轻量本地存储 | 暂缓，等数据规模和召回需求增长 |

## P0-1：角色卡系统

### 价值判断

完美的 AI 伴侣首先需要稳定人格。角色卡不是单个 prompt，而应是角色的完整产品单元：灵魂、身体、声音、记忆策略、主动风格、行为边界的统一配置。

AIRI 值得吸收的点：

- Character Card 风格字段：身份、性格、场景、问候语、示例对话、历史后置指令。
- 模块绑定：LLM provider/model、TTS voice、Live2D/3D body。
- 激活角色时同步切换人格、声线和身体。

Kokoro 应避免的点：

- 不要直接把完整 AIRI prompt 塞进 `description`。
- 不要第一阶段完整兼容 Character Card V3 全字段。
- 不要为了生态兼容牺牲当前角色配置的可读性。

### 建议目标结构

```yaml
schema_version: "2"
name: "..."
identity:
  description: "..."
  scenario: "..."
personality:
  core_fear: "..."
  surface_trait: "..."
  hidden_trait: "..."
behavior:
  rules: []
  verbal_habits: []
  forbidden_words: []
dialogue:
  first_message: "..."
  examples: []
  post_history_instructions: "..."
emotion:
  mood_expressions: {}
  triggers: {}
  profiles: {}
modules:
  llm:
    provider: ""
    model: ""
  tts:
    provider: "edge-tts"
    voice: ""
  display:
    mode: "live2d"
memory:
  extraction_policy: "conservative"
  recall_style: "structured"
proactive:
  style: {}
```

### 实施步骤

1. 新增 v2 角色 schema，兼容读取当前 v1 `personality.yaml`。
2. 重构 `build_system_prompt()`，明确拼接字段顺序。
3. 给默认角色补齐 `identity / dialogue / modules / memory / proactive` 字段。
4. API `state` 返回角色卡模块绑定信息，前端按角色切换展示资源。
5. 后续再做导入/导出 Character Card。

## P0-2：表现层事件协议

### 价值判断

人格伴侣不能只会输出文字。AIRI 的 `<|ACT:{...}|>` 价值在于把模型输出转成“可表演”的事件。Kokoro 应设计自己的表现协议，让文本、情绪、表情、动作、TTS 参数和打断策略一致。

### 建议事件模型

```json
{
  "type": "expression",
  "emotion": {
    "name": "happy",
    "intensity": 0.7,
    "reason": "user_praise"
  },
  "motion": {
    "name": "nod",
    "priority": 50
  },
  "speech": {
    "rate_delta": "+8%",
    "volume_delta": "+0%",
    "pause_ms": 120
  },
  "playback": {
    "intent": "queue"
  }
}
```

### 实施步骤

1. 后端定义 `ExpressionEvent` / `SpeechEvent` / `MotionEvent` schema。
2. prompt 中要求模型使用受控 token，或由后端情绪状态机生成事件。
3. 流式 API 增加 `event` chunk。
4. 前端建立 emotion/motion/speech queue。
5. Live2D、3D、Sprite 统一消费表现事件，不直接依赖文本 mood。

## P0-3：TTS 播放流水线

### 价值判断

声音是伴侣存在感的核心。Kokoro 当前已有 TTS 和嘴型基础，但还需要从“能播声音”升级为“可编排语音输出系统”。

AIRI 值得吸收的点：

- token 流切分为 TTS segment。
- 并发生成音频，按序播放。
- 支持 queue / interrupt / replace。
- 主动提醒、普通聊天、系统反馈使用不同优先级。
- 播放开始/结束驱动字幕、嘴型、speaking 状态。

### 实施步骤

1. 抽出前端 `SpeechPipeline`，从 `useSpeechOutput.ts` 中分离切分、请求、播放。
2. 支持 segment 预取：最多并发 2-3 个 TTS 请求。
3. 引入 playback intent：`queue`、`interrupt`、`replace`、`drop_if_busy`。
4. 加入 owner/priority：chat、proactive、reminder、system。
5. 保留现有 Edge TTS 后端，先不扩大 provider。

## P0-4：主动联系与 notify 事件入口

### 价值判断

陪伴产品和聊天机器人的关键区别是主动性。Kokoro 已有 proactive 系统，AIRI 的 `spark:notify` 值得吸收为统一事件入口。

### 目标结构

```text
perception / reminder / time / idle / app state / future plugins
  -> NotifyEvent
  -> privacy + DND + frequency policy
  -> proactive scheduler
  -> optional LLM reaction
  -> frontend event stream
  -> expression + TTS + quick actions
```

### 实施步骤

1. 定义统一 `NotifyEvent`，字段包括 source、scene、urgency、payload、privacy_level。
2. 将 reminder、perception、idle、long work 触发统一转换成 NotifyEvent。
3. 扩展 `ProactiveScheduler`，支持事件队列和 urgency。
4. 前端 stream 支持主动事件 chunk。
5. 管理界面展示主动事件日志和 suppression reason。

## P1-1：长期记忆闭环

### 价值判断

长期记忆的价值不在“存很多”，而在“记得准、可解释、可编辑、可遗忘”。AIRI 的消息向量召回有参考价值，但 Kokoro 当前更应该强化结构化记忆。

### 建议路线

1. 继续使用结构化记忆：fact、preference、boundary、event。
2. 增加 `importance`、`last_accessed`、`access_count`、`source_message_ids`。
3. 召回后 touch 记忆，形成使用强化。
4. prompt 注入保留类型、来源、置信度。
5. 管理界面支持确认、编辑、删除、归档候选记忆。
6. 当本地数据规模超过轻量检索能力后，再评估向量库。

### 暂不优先做

- PostgreSQL + pgvector。
- 多维 embedding 列设计。
- 大规模消息 RAG。

这些是技术手段，不是当前产品价值瓶颈。

## P1-2：VAD + STT 语音输入

### 价值判断

完美桌面伴侣应支持自然说话。AIRI 的 VAD + STT 链路成熟，Kokoro 可以分阶段吸收。

### 实施步骤

1. 保留当前浏览器 Web Speech API 作为基础语音输入。
2. 增加麦克风权限和设备选择 UI。
3. 引入本地 VAD，自动判断 speech start / speech end。
4. 录音结束后调用 STT provider。
5. 后续再做流式 STT 和唤醒词。

## P1-3：Live2D / 3D 身体运行时工程化

### 价值判断

身体系统决定沉浸感。Kokoro 已有 Live2D 和 3D 支持，但需要从组件级实现升级为 Display Runtime。

### 建议结构

```text
DisplayRuntime
  -> Live2DAdapter
  -> Model3DAdapter
  -> SpriteAdapter
  -> consumes ExpressionEvent / MotionEvent / LipSyncLevel
```

### 实施步骤

1. 抽象 display adapter 接口。
2. Live2D 增加 motion queue、idle、blink、focusAt。
3. 3D 增加统一 morph/motion 事件消费。
4. 模型加载失败时提供 fallback 和可诊断错误。
5. 角色卡绑定 display profile。

## P2：插件与 computer-use

### 插件事件生态

插件系统的价值在于接入日历、浏览器、IDE、游戏、系统状态等外部上下文。建议先稳定内部 NotifyEvent，再开放插件协议。

最小插件协议只需要：

- `notify`：外部事件通知角色。
- `query_state`：读取公开状态。
- `quick_action`：响应用户点击的快捷动作。

### computer-use

computer-use 潜在价值高，但风险也高。只有当前面 P0/P1 稳定后才建议做。

必须坚持：

- 所有高风险动作需要用户审批。
- 所有动作写审计日志。
- 终端、浏览器 DOM、桌面点击分层。
- 默认禁止操作 Kokoro 自身窗口和敏感应用。
- 任务记忆只记录当前任务，不进入人格长期记忆。

## 不建议合并的内容

### 不照搬 AIRI monorepo

Kokoro 当前 Python sidecar + Vue/Tauri 架构清晰，适合个人原型和快速产品化。AIRI 的 pnpm workspace 拆包方式适合更大规模多端工程，当前照搬会增加维护成本。

### 不急着上 pgvector

向量数据库不是产品价值本身。当前应先把记忆确认、召回、强化、遗忘、管理 UI 做好。

### 不直接复制 AIRI prompt

Kokoro 已有安全边界、关系状态、记忆注入和角色配置约束。AIRI prompt 只能作为字段设计参考，不能直接覆盖 Kokoro 的人格层。

## 推荐阶段计划

### Phase A：产品灵魂闭环

目标：让 Kokoro 的“人格、声音、身体、主动性”形成一条稳定链路。

- 角色卡 v2 schema。
- 表现层事件协议。
- TTS pipeline。
- NotifyEvent 主动入口。

验收标准：

- 切换角色会同步切换人格、声线、身体资源。
- LLM 回复或后端情绪变化能驱动表情、动作、TTS 参数。
- 主动提醒可以走同一条表现链路。
- 用户可打断当前语音。

### Phase B：长期陪伴闭环

目标：让 Kokoro 记得用户，并允许用户治理记忆。

- 记忆字段增加 importance/access/source。
- 召回后 touch。
- 记忆管理 UI。
- 主动事件日志 UI。
- 关系状态与记忆召回互相约束。

验收标准：

- 用户能看到、确认、编辑、删除记忆。
- 角色能稳定使用用户偏好和边界。
- 被删除或归档的记忆不会再进入 prompt。
- 主动联系有清晰 suppression reason。

### Phase C：自然交互和身体增强

目标：减少打字感，强化桌面存在感。

- VAD + STT。
- Live2D motion queue / blink / focus。
- 3D display adapter。
- 更完整的嘴型和 speaking 状态。

验收标准：

- 用户可以自然说话触发输入。
- 角色说话时字幕、嘴型、动作一致。
- 不同 display mode 共享同一表现事件协议。

### Phase D：生态与执行能力

目标：让 Kokoro 能接入外部世界，但保持安全边界。

- 插件 notify 协议。
- 外部应用事件接入。
- 低风险 quick action。
- computer-use dry-run / approval 原型。

验收标准：

- 插件不能绕过隐私和勿扰策略。
- 所有外部事件可追踪。
- computer-use 默认只在用户审批后执行。

## 当前最建议启动的任务

1. 新建角色卡 v2 schema 草案，并兼容现有角色。
2. 设计 `ExpressionEvent` / `MotionEvent` / `SpeechEvent` / `NotifyEvent` schema。
3. 重构 `useSpeechOutput.ts` 为可测试的播放流水线。
4. 将 reminder/proactive/perception 统一到 NotifyEvent。
5. 给长期记忆增加 access/importance/source 字段和管理 UI 路线。

