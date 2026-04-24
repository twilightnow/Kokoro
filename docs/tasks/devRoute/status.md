---
tags:
  - Kokoro
  - roadmap
  - status
status: active
created: 2026-04-21
updated: 2026-04-24
---

# 当前版本可运行功能汇总

> 更新于 2026-04-24 · 110 个单元测试通过

| 功能 | 状态 |
|------|------|
| 多 provider LLM（anthropic / openai / gemini / deepseek / openrouter / copilot / 三个 CLI） | ✅ |
| 情绪状态机（触发词匹配 + 衰减） | ✅ |
| 工作记忆（10 轮截断） | ✅ |
| 会话日志（JSONL）+ 调试模式 + 日志回放 | ✅ |
| 人格稳定性复盘脚本 / 成本统计脚本 | ✅ |
| 会话摘要记忆 + 长期事实记忆（token budget 裁剪 + 截断日志） | ✅ |
| 感知层（窗口监控 + 活跃检测 + 五类触发器 + 冷却机制） | ✅ `enable_perception=True` 启用 |
| FastAPI sidecar（/chat、/state、/health、/switch-character、WebSocket /stream） | ✅ 接口完成，支持 Tauri 自动启动与 PyInstaller 打包脚本 |
| 角色资源 API（/character-assets）：模型文件、纹理、VMD 静态服务 | ✅ |
| 管理后台 API（情绪统计、日志、记忆、Debug） | ✅ |
| 桌面 UI — Tauri 骨架（透明窗口、托盘、始终置顶） | ✅ |
| 桌面 UI — 气泡 + 输入框（含动画） | ✅ |
| 桌面 UI — WebSocket 接入 + 断线重连 + 健康检查 | ✅ |
| 桌面 UI — 点击穿透 / 边缘吸附 / 位置持久化 | ✅ |
| 桌面 UI — 管理控制台（独立窗口） | ✅ |
| Live2D 立绘（情绪驱动动作/表情） | ✅ |
| 3D 模型（PMX + MMDLoader）：皮肤切换、摄像机/灯光配置、程序化待机动画 | ✅ |
| VMD 动画（在 scene.json 指定文件名即可启用） | 🔧 代码就绪，待配置 VMD 文件 |
| TTS 语音输出 | ✅ edge-tts 接入，支持开关、声线、语速、音量配置 |
| 角色包分发 | ❌ 未开始 |
