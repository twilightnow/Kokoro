---
tags:
  - Kokoro
  - roadmap
  - api
  - ipc
status: in-progress
created: 2026-04-21
updated: 2026-04-24
---

# Phase 3A — 后端 sidecar 🔧

**架构关注点**：API / IPC

**目标**：将现有 CLI 逻辑封装为 FastAPI sidecar，为 Tauri UI 提供稳定的 IPC 接口。

**说明**：CLI 逻辑不重写，sidecar 是在已有 `ConversationService` 之上加一层 HTTP/WebSocket 壳。

## 任务清单

- [x] **FastAPI 应用骨架**：`src/api/app.py`，lifespan 管理、CORS 配置
- [ ] **IPC 协议文档**：定义 Tauri ↔ Python sidecar 的消息格式（见 `docs/desgin/07-IPC协议.md`，待完善）
- [x] **`POST /chat`**：接收用户输入，返回角色回复 + 当前情绪 + usage
- [x] **`GET /state`**：返回当前情绪、活跃角色、记忆摘要条数、角色显示配置（display mode / 皮肤 URL）
- [x] **`WebSocket /stream`**：长连接推送，同步 LLM + `asyncio.to_thread`；协议预留逐 token 扩展接口
- [x] **`GET /health`**：健康检查端点，返回角色名和版本
- [x] **`POST /switch-character`**：运行时热切换角色，返回新角色的完整 display 配置
- [x] **`GET /character-assets/{id}/{path}`**：PMX 模型、纹理、VMD、Live2D 模型等静态资源服务（path traversal 防护）
- [x] **角色资源构建**（`character_assets.py`）：从 `manifest.yaml` + `scene.json` 动态生成前端所需的皮肤 URL、摄像机、灯光参数
- [x] **管理后台路由**（`admin` router）：情绪统计、日志查看、记忆管理、Debug 面板
- [ ] **sidecar 打包脚本**：PyInstaller 打包，验证无外部依赖（待完成）

## 验收标准

1. ⬜ `curl` 能正常调用 `/chat` 并收到角色回复
2. ⬜ WebSocket 流式接口能推送完整回复
3. ⬜ PyInstaller 打包后在无 Python 环境的机器上正常运行

## 相关设计文档

- [IPC 协议](../../desgin/07-IPC协议.md)
- [管理界面](../../desgin/08-管理界面.md)
