---
tags:
  - Kokoro
  - roadmap
  - companion
  - relationship
  - runtime
status: planned
created: 2026-04-24
updated: 2026-04-24
---

# Phase 5 — 长期伴侣运行时 ❌

**架构关注点**：关系状态 / 主动调度 / 生活事件 / 安全边界

**目标**：把 Kokoro 从"有角色、有记忆、有形象的对话原型"升级为"可长期陪伴、能记住共同生活事件、会适度主动关心、并有清晰边界的桌面伴侣系统"。

## 背景判断

当前主链路仍以单轮对话为中心：

```text
用户输入 -> ConversationService -> 情绪 / 记忆 / prompt -> LLM -> 回复
```

这足够支撑角色聊天，但不够支撑"像真实伴侣一样持续生活在用户身边"。长期伴侣体验需要关系状态、生活事件、承诺提醒、情绪连续性、主动调度和安全边界成为一等模块，而不是全部塞进 prompt 或长期事实记忆。

## 原则

- 关系状态是结构化运行时状态，不是普通长期记忆
- 主动行为必须可节制、可关闭、可解释，避免打扰
- 记忆分层：事实、偏好、边界、事件、承诺分开存储
- 角色核心人格保持稳定，关系适应层允许缓慢变化
- 感知能力默认最小化，所有敏感感知必须可配置、可审计
- 亲密感越强，安全边界越要独立于 prompt

## 架构目标

```text
UI / Tauri
  |
FastAPI sidecar
  |
Application Layer
  |-- ConversationService        # 单轮对话
  |-- CompanionRuntime           # 长期运行时 / 生活循环
  |-- ProactiveScheduler         # 主动行为调度
  |-- RelationshipService        # 关系状态
  |-- RoutineReminderService     # 承诺 / 提醒 / 习惯
  |
Personality Layer
  |-- CharacterConfig
  |-- EmotionState
  |-- EmotionTimeline
  |-- RelationshipState
  |-- PromptBuilder
  |
Memory Layer
  |-- WorkingMemory
  |-- SummaryMemory
  |-- LongTermFactMemory
  |-- EventMemory
  |-- PreferenceMemory
  |-- BoundaryMemory
  |
Perception Layer
  |-- Window / Input / Time Context
  |-- ActivityClassifier
  |-- PrivacyFilter
  |
Capability Layer
  |-- LLM
  |-- TTS / STT
  |-- AnimationDriver
```

## 任务清单

- [ ] **RelationshipState schema**：定义亲密度、信任度、熟悉度、最近互动质量、关系称呼、边界偏好、依赖风险等字段
- [ ] **RelationshipService**：负责读取、更新、衰减、迁移关系状态，并提供 prompt 注入摘要
- [ ] **关系变化规则**：根据互动事件更新关系状态，避免由 LLM 直接任意修改核心数值
- [ ] **EventMemory**：记录共同经历、重要事件、纪念日、最近压力源、阶段性目标
- [ ] **PreferenceMemory**：记录用户喜欢的称呼、回复风格、提醒频率、语音/动作偏好
- [ ] **BoundaryMemory**：记录用户明确设定的禁区、敏感话题、"不要再提"、隐私偏好
- [ ] **Promise / Reminder model**：结构化保存"她答应过的事"、用户要求的提醒、习惯检查和计划跟进
- [ ] **RoutineReminderService**：支持一次性提醒、周期提醒、习惯检查、过期处理和完成确认
- [ ] **CompanionRuntime**：引入后台生活循环，统一驱动主动检查、提醒触发、状态衰减和轻量事件记录
- [ ] **ProactiveScheduler**：把当前触发器集合升级为主动行为调度器，决定沉默、表情、短句、完整对话四种介入等级
- [ ] **主动频率控制**：按时间段、用户活跃状态、关系阶段、当天已打扰次数、冷却策略控制主动行为
- [ ] **EmotionTimeline**：在现有 `EmotionState` 上增加情绪原因、强度、来源、开始时间、恢复速度和历史轨迹
- [ ] **情绪表现联动**：将情绪强度映射到回复语气、Live2D/3D 表情、VMD、TTS 语速和音量
- [ ] **ActivityClassifier**：在窗口标题、键鼠活跃、时间段基础上判断工作、游戏、休息、熬夜、空闲等高层状态
- [ ] **PrivacyFilter**：对窗口标题、应用名、敏感内容做过滤、黑名单和日志脱敏
- [ ] **SafetyPolicy / BoundaryEngine**：独立处理心理危机、过度依赖、情感操控、亲密边界、现实关系隔离等风险
- [ ] **PromptBuilder 扩展**：把关系状态、事件记忆、边界记忆、承诺提醒以受控摘要注入 prompt
- [ ] **API 扩展**：提供关系状态、提醒、边界、主动行为设置、隐私设置的查询和修改接口
- [ ] **管理 UI 扩展**：让用户能查看/编辑/删除关系状态、事件记忆、偏好、边界和提醒
- [ ] **迁移策略**：为新增运行时数据定义 schema_version 和向后兼容迁移入口

## 验收标准

1. 关系状态可持久化，重启后仍能正确影响称呼、主动频率和回复风格
2. 用户可以创建、查看、完成、删除提醒或承诺，系统能在合适时间主动触发
3. 主动行为不会只要触发就说话，而是能根据场景选择沉默、表情、短句或完整回复
4. 情绪有原因和强度，能持续一段时间并自然恢复，而不是固定 3 轮后直接清零
5. 用户可以查看、修改、删除偏好、边界和重要事件记忆
6. 感知日志可审计，敏感窗口或应用可加入黑名单
7. 心理危机、过度依赖、现实关系隔离等风险不会只依赖角色 prompt 处理

## 建议拆分

### Phase 5A — 关系与生活记忆

- RelationshipState
- EventMemory
- PreferenceMemory
- BoundaryMemory
- Prompt 注入摘要
- 管理 UI 最小编辑能力

### Phase 5B — 承诺与主动调度

- Promise / Reminder model
- RoutineReminderService
- CompanionRuntime
- ProactiveScheduler
- 主动频率控制

### Phase 5C — 情绪连续性与安全边界

- EmotionTimeline
- 情绪表现联动
- ActivityClassifier
- PrivacyFilter
- SafetyPolicy / BoundaryEngine

## 相关设计文档

- [人格层](../../desgin/02-人格层.md)
- [记忆层](../../desgin/03-记忆层.md)
- [感知层](../../desgin/04-感知层.md)
- [能力层](../../desgin/05-能力层.md)
