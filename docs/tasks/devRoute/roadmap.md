---
tags:
  - Kokoro
  - roadmap
status: active
created: 2026-04-21
updated: 2026-04-24
---

# Kokoro 开发路线图

> 原则：先稳人格，再加记忆，再加感知，最后上 UI。每个阶段有独立验收标准，不跨阶段堆功能。

## 文档职责边界

`docs/tasks/devRoute/` 只维护交付计划，不重复解释底层架构设计。

本目录负责：

- 阶段优先级
- 任务清单
- 当前状态
- v1 范围
- 验收标准
- 下一步建议

本目录不负责：

- 详细模块边界
- 跨层数据契约
- 存储格式设计细节
- API / UI / 能力层的长期架构说明

这些内容统一放在 `docs/desgin/`。如果路线图需要引用设计，只链接到对应设计文档，不在路线图里复制完整设计说明。

本目录按设计架构拆分路线图。`roadmap.md` 只保留全局优先级和导航，阶段细节放在同目录独立文件中。

## 优先级

| 优先级 | 阶段 | 架构关注点 | 目标 | 状态 | 详情 |
|--------|------|------------|------|------|------|
| **P0** | 1.5 — CLI 收尾 | 人格层 / CLI 验收 | 补全 Phase 1 遗留缺口，让 CLI 版本真正"可用于验收" | ✅ 已完成 | [01-cli-personality.md](01-cli-personality.md) |
| **P1** | 2A — 轻记忆 | 记忆层 | 会话摘要 + 少量长期记忆注入，让她"记得你说过什么" | ✅ 已完成 | [02-memory.md](02-memory.md) |
| **P2** | 2B — 轻感知 | 感知层 | Level 0 感知（窗口标题、活跃状态、时间段）+ 主动介入触发器 | ✅ 已完成 | [03-perception.md](03-perception.md) |
| **P3** | 3A — 后端 sidecar | API / IPC | FastAPI sidecar + IPC 协议，为 UI 提供接口 | 🔧 接口完成，打包待做 | [04-sidecar-api.md](04-sidecar-api.md) |
| **P4** | 3B — 桌面 UI | UI 层 / 桌面壳 | Tauri 壳 + Vue 气泡 UI + 立绘切换 | ✅ 已完成 | [05-desktop-ui.md](05-desktop-ui.md) |
| **P5** | 3C — 表现增强 | 能力层 / 表现层 | Live2D ✅ · 3D 模型 ✅ · VMD 动画 🔧 · TTS ❌ | 🔧 进行中 | [06-presentation-capability.md](06-presentation-capability.md) |
| **P6** | 4 — 扩展与分发 | 扩展与迁移 | 角色包格式、install/export/import、创意工坊雏形 | ❌ 未开始 | [07-extension-distribution.md](07-extension-distribution.md) |
| **P7** | 5 — 长期伴侣运行时 | 关系状态 / 主动调度 / 生活事件 / 安全边界 | 从角色聊天升级为可长期陪伴、适度主动、可治理记忆和边界的伴侣系统 | ❌ 未开始 | [08-companion-runtime.md](08-companion-runtime.md) |

## 状态与建议

- [当前版本可运行功能汇总](status.md)
- [下一步优先建议](next.md)

## 相关设计文档

- [系统设计总览](../../desgin/00-系统设计总览.md)
- [人格层](../../desgin/02-人格层.md)
- [记忆层](../../desgin/03-记忆层.md)
- [感知层](../../desgin/04-感知层.md)
- [IPC 协议](../../desgin/07-IPC协议.md)
- [UI 层](../../desgin/06-UI层.md)
- [能力层](../../desgin/05-能力层.md)
- [扩展与迁移](../../desgin/11-扩展与迁移.md)
- [长期伴侣运行时](../../desgin/01-长期伴侣运行时.md)
- [安全与边界](../../desgin/10-安全与边界.md)
