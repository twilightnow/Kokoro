---
tags:
  - Kokoro
  - roadmap
  - perception
status: done
created: 2026-04-21
updated: 2026-04-24
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
- [x] **`BaseTrigger` 抽象与五类触发器**：`IdleTrigger`（空闲 2h）、`LateNightTrigger`（23:00-04:00）、`LongWorkTrigger`（连续工作 1h）、`WindowSwitchTrigger`（频繁切窗口 ≥10 次/分钟）、`GamingTrigger`（窗口标题关键词匹配）
- [x] **冷却机制**（`CooldownManager`）：全局冷却 30 分钟，同类触发器冷却期内不重复触发
- [x] **感知上下文注入 prompt**：`PromptContext.perception` 字段接入主流程，不为 None 时追加"当前场景"段
- [x] **感知日志**（`PerceptionLog`）：每次触发主动介入时写入日志
- [x] **游戏粗判**：`WindowMonitor.GAME_KEYWORDS` 关键词匹配，命中时场景标签为 `gaming`
- [x] **`ProactiveEngine`** 整合以上全部，通过 `ConversationService(enable_perception=True)` 接入主流程

## 验收标准

1. ✅ 深夜（23:00 后）连续使用 30 分钟，触发一次主动介入
2. ✅ 空闲 2 小时后重新操作，触发一次主动介入
3. ✅ 30 分钟内不重复触发同一类型

## 相关设计文档

- [感知层](../../desgin/感知层.md)
