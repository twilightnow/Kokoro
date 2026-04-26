---
tags:
  - Kokoro
  - roadmap
  - ui
  - tauri
status: done
created: 2026-04-21
updated: 2026-04-24
---

# Phase 3B — 桌面 UI ✅

**架构关注点**：UI 层 / 桌面壳

**目标**：搭出最小可用的桌面悬浮窗，能对话、有表情、低打扰常驻。

**技术栈**：Tauri 2.x + Vue 3 + TypeScript + Vite + Pinia

## 任务清单

- [x] **Tauri 项目初始化**：`frontend/` + `src-tauri/`，透明窗口、无边框、始终置顶、系统托盘
- [x] **点击穿透**：`set_passthrough` command，鼠标离开有效区域时透明部分穿透到底层
- [x] **气泡组件**（`BubbleBox.vue`）：漫画对白框，5 秒后淡出；主动介入附带快捷回应按钮
- [x] **输入框组件**（`InputBar.vue`）：点击立绘后淡入，失焦后淡出
- [x] **立绘面板统一抽象**（`SpritePanel.vue`）：按 manifest `display.mode` 自动切换 Live2D / 3D 模型 / 静态占位；情绪驱动皮肤自动切换，支持手动皮肤选择
- [x] **Live2D 画布**（`Live2DCanvas.vue`）：`pixi-live2d-display`，情绪驱动动作/表情参数
- [x] **3D 模型画布**（`Model3DCanvas.vue`）：Three.js WebGL 渲染 PMX 模型，MMDLoader + MMDAnimationHelper，支持 VMD 动画；摄像机/灯光/缩放由 `scene.json` 配置驱动
- [x] **皮肤切换系统**：多套皮肤（base / combat 等），情绪自动切换 + 手动覆盖，支持"自动"模式
- [x] **管理控制台**（admin 窗口）：独立 Tauri WebView + HTML 入口，包含情绪统计、日志、记忆、角色切换、设置面板
- [x] **托盘菜单**（`tray.rs`）：显示/隐藏、角色切换（读取 characters/ 目录）、退出
- [x] **边缘吸附**（`useEdgeSnap.ts`）：拖至屏幕边缘时窗口缩进，鼠标进入时滑出
- [x] **WebSocket 接入**（`useChat.ts`）：连接 sidecar `/stream`，流式 token 追加、断线重连（3 次指数退避）、健康检查
- [x] **主动介入气泡**：接收 `proactive` 帧，显示快捷回应按钮
- [x] **窗口位置持久化**（`useWindowPosition.ts`）：移动时写 localStorage，启动时复原
- [x] **状态管理**：`stores/chat.ts`，Pinia setup 写法
- [x] **Rust commands 分层**：`commands.rs`（IPC）+ `tray.rs`（托盘）

## 验收标准

1. ⬜ 启动 sidecar 后发消息 → 流式回复出现在气泡 → 情绪切换立绘
2. ⬜ 拖到屏幕边缘 → 缩进 → 鼠标靠近滑出
3. ⬜ 透明区域点击穿透到底层窗口
4. ⬜ 关闭重开后窗口出现在上次位置

## 相关设计文档

- [UI 层](../../desgin/06-UI层.md)
- [3D 模型支持](../../desgin/09-3d-model-support.md)
