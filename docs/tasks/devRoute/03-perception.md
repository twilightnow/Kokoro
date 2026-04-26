---
tags:
  - Kokoro
  - roadmap
  - perception
status: done
created: 2026-04-21
updated: 2026-04-26
---

# Phase 2B — 轻感知 ✅

**架构关注点**：感知层

**目标**：让她知道用户在干什么、几点了、活不活跃，并在少数高价值场景主动开口。

## 设计原则

- 首版只做 Level 0（进程级，零成本，无截图无 OCR）
- 默认不打扰，有冷却机制，宁可少触发也不能烦人
- 感知层只输出结构化上下文标签，不直接干预人格判断

## 任务清单

- [x] **`PerceptionCollector`**（`collector.py`）：整合 `WindowMonitor`（pygetwindow）+ `InputTracker`（pynput）采集窗口标题、活跃状态、时间段
- [x] **感知上下文注入 prompt**：`PromptContext.perception` 字段接入主流程，不为 None 时追加"当前场景"段
- [x] **游戏粗判**：`WindowMonitor.GAME_KEYWORDS` 关键词匹配，命中时场景标签为 `gaming`
- [x] **`ProactiveSignalDetector` + `CompanionRuntime`**：由后台 loop 在 sidecar 模式下完成信号检测、抑制与主动广播
- [x] **主动策略持久化**：`ProactiveSettingsRepository`、`ProactivePolicy`、`ProactiveLogRepository` 接管模式、勿扰、每日上限与事件日志
- [x] **CLI `--perception` 收口**：`ConversationService(enable_perception=True)` 仅按轮采集最新快照注入 prompt，不再承担轮间主动开口

## 验收标准

1. ✅ 深夜（23:00 后）连续使用 30 分钟，触发一次主动介入
2. ✅ 空闲 2 小时后重新操作，触发一次主动介入
3. ✅ 30 分钟内不重复触发同一类型

## 相关设计文档

- [感知层](../../desgin/04-感知层.md)
