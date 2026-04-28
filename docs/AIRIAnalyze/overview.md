# AIRI 分析总览

本文是 `docs/AIRIAnalyze` 目录下 AIRI 专题分析的总览入口，用于快速理解已分析的能力范围、成熟度判断，以及每类分析对应的原始数据来源路径。

## 数据来源

本目录分析基于本机 AIRI 主仓当前文件：

```text
C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi
```

分析文档位于 Kokoro 仓库：

```text
C:\WorkSpace\6_Source\2_VScode\99_gitProject\Kokoro\docs\AIRIAnalyze
```

主要信息来源包括：

| 来源类型 | 路径 | 用途 |
| --- | --- | --- |
| AIRI 根仓 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi` | 判断仓库形态、workspace、apps/packages/services 分布 |
| AIRI workspace 配置 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi\package.json`、`pnpm-workspace.yaml` | 确认 monorepo 包、应用、服务组织方式 |
| AIRI 应用层 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi\apps` | Stage Web、Stage Pocket、Stage Tamagotchi、server 等应用入口 |
| AIRI 共享包 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi\packages` | Stage UI、Live2D、音频流水线、角色卡、agent、插件协议等核心能力 |
| AIRI 独立服务 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi\services` | Telegram bot、Satori bot、Minecraft agent、computer-use-mcp 等服务侧实现 |
| AIRI 文档 | `C:\WorkSpace\6_Source\2_VScode\99_gitProject\airi\docs` | 对照 README、manual、DevLog 中的目标设计与实际代码 |
| Kokoro 分析输出 | `docs/AIRIAnalyze/*.md` | 已整理的专题分析结论 |

## 分析范围

当前目录已经形成 7 个专题：

| 专题 | 文档 | 核心判断 |
| --- | --- | --- |
| 人格 / 角色卡 / persona prompt | `personality-system-analysis.md` | Stage 主线人格由 AIRI Card store 驱动，角色卡、模块绑定、情绪 ACT token 已有清晰入口；但不同服务仍保留多套 persona prompt，部分 Character Card 字段未进入主对话 prompt。 |
| 记忆系统 | `memory-system-analysis.md` | 记忆相关实现分散在 Telegram bot、computer-use-mcp、Stage 设置页和 `memory-pgvector` 包中；Telegram bot 最接近长期/短期聊天记忆，Stage 记忆页和 memory-pgvector 仍偏占位。 |
| 语音检测与语音识别 | `speech-detection-and-recognition-analysis.md` | 语音输入主链路已落地：Stage Web/Pocket 通过麦克风流、VAD、录音/流式 STT 接入 chat ingest。 |
| 语音合成 | `speech-synthesis-analysis.md` | TTS 是完整输出链路，不只是单 API；包含 provider 配置、文本切分、并发生成、播放队列、中断策略和角色口型联动。 |
| Live2D | `live2d-analysis.md` | Live2D 是成熟能力线，有独立包、资源加载、动作/表情控制、待机、眨眼、注视、节拍和口型同步。 |
| 主动联系 / 主动反应 | `proactive-contact-analysis.md` | 当前主要是事件驱动的 `spark:notify` 主动反应入口；尚未形成面向用户生活节律的完整主动联系调度系统。 |
| 操作电脑 / computer use | `computer-operation-analysis.md` | `services/computer-use-mcp` 是成熟度较高的 MCP 执行底座，覆盖桌面、终端、浏览器 DOM、审批、审计、工作流和任务记忆；但执行器明显偏 macOS，Windows 本地后端不完整。 |

## AIRI 当前架构轮廓

AIRI 是 pnpm workspace monorepo，核心目录可以按运行面分成四层：

```text
apps/        产品入口和平台壳
packages/    前端 UI、agent、协议、音频、Live2D、角色卡、共享 SDK
services/    独立 bot、自动化和外部环境 agent
docs/        用户文档、开发文档和目标设计记录
```

从已分析能力看，AIRI 的主线产品形态大致是：

```text
Stage Web / Pocket / Tamagotchi
        |
        v
stage-ui stores + scenes
        |
        +-- AIRI Card / persona prompt / emotion ACT
        +-- hearing: VAD + STT
        +-- speech: TTS provider + playback pipeline
        +-- Live2D / VRM display model
        |
        v
core-agent / plugin protocol / server-shared events
        |
        +-- spark:notify event reaction
        +-- service-specific bots and agents
```

另有一条独立但相关的自动化能力：

```text
AIRI control plane
        |
        v
services/computer-use-mcp
        |
        +-- desktop observe/control
        +-- terminal execution
        +-- browser DOM control
        +-- approval / audit / workflow / task memory
```

## 成熟度分层

按当前代码落地程度，可以粗略分为：

| 成熟度 | 能力 | 判断 |
| --- | --- | --- |
| 较成熟 | Live2D、TTS、语音输入、computer-use-mcp | 有明确入口、运行路径、状态管理和工程化拆分。 |
| 中等成熟 | 人格 / 角色卡 / 情绪 ACT | 主线链路存在，产品入口清晰；但字段使用、服务侧 persona 统一性仍不完整。 |
| 部分实现 | 主动反应 | `spark:notify` 能处理外部事件并生成角色反应，但不是完整主动关怀 scheduler。 |
| 规划/占位较多 | Stage 记忆设置、`packages/memory-pgvector`、结构化长期记忆 | 表结构、入口或包名存在，但主运行链路尚未闭环。 |

## 对 Kokoro 的参考价值

对 Kokoro 当前原型最有直接参考价值的部分：

- 人格系统：参考 AIRI Card 的角色卡导入、模块绑定和激活机制，但 Kokoro 应避免把完整 prompt 塞进单一 `description` 字段。
- 情绪表达：AIRI 的 `<|ACT:{...}|>` 能同时驱动文本、表情和模型动作；Kokoro 可借鉴“模型输出 token -> 情绪队列 -> 表现层”的分层。
- TTS：AIRI 的文本切分、并发预取、播放顺序保证和中断策略，适合 Kokoro 后续升级桌面语音输出。
- Live2D：AIRI 已经把渲染、动作、表情、口型和节拍拆成独立包，适合作为 Kokoro 桌面表现层演进参考。
- 主动反应：`spark:notify` 适合作为“外部环境事件触发角色反应”的参考，但 Kokoro 的 idle / 时间段 / 长工作等主动联系机制需要另行设计。
- 记忆系统：AIRI 的 Telegram bot 消息向量召回有参考价值；但 Stage 记忆 UI 和 `memory-pgvector` 还不能直接视为完整实现。
- 操作电脑：`computer-use-mcp` 的审批、审计、策略和工作流设计可参考；但 Kokoro 如果面向 Windows/Tauri，需要重新评估本地执行器适配。

## 阅读顺序建议

如果目标是为 Kokoro 选型或迁移设计，建议按以下顺序阅读：

1. `personality-system-analysis.md`
2. `memory-system-analysis.md`
3. `speech-synthesis-analysis.md`
4. `speech-detection-and-recognition-analysis.md`
5. `live2d-analysis.md`
6. `proactive-contact-analysis.md`
7. `computer-operation-analysis.md`

这个顺序先覆盖 Kokoro 已有核心：人格、记忆、语音、桌面表现和主动交互，再看更重的 computer use 能力。
