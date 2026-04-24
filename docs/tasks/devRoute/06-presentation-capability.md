---
tags:
  - Kokoro
  - roadmap
  - capability
  - presentation
status: in-progress
created: 2026-04-21
updated: 2026-04-24
---

# Phase 3C — 表现增强 🔧

**架构关注点**：能力层 / 表现层

**目标**：在 UI 已稳定的前提下，逐步提升表现力。

**顺序**：Live2D ✅ → 3D 模型 ✅ → VMD 动画 → TTS → 口型同步（每步可独立交付，不互相阻塞）

## 任务清单

- [x] **Live2D 接入**：`pixi-live2d-display`，情绪驱动动作参数（眉眼、呼吸、动作组）
- [x] **3D 模型接入**：PMX 格式 + Three.js MMDLoader；`manifest.yaml` 定义皮肤列表和 `scene.json` 路径；scene.json 配置摄像机、灯光、缩放、旋转
- [x] **3D 待机程序化动画**：无 VMD 时，自动叠加轻微旋转摆动 + 上下浮动呼吸感
- [ ] **VMD 动画**：在 `scene.json` 中指定 `"vmd"` 字段即可加载循环播放；支持情绪 → VMD 切换（如 happy 时播放活跃动作）
- [ ] **3D 表情控制**：通过 PMX Morph Target 驱动口型、眼型等表情变化，与情绪状态联动
- [ ] **TTS 抽象层**：`src/capability/tts.py`，定义 `TTSClient.speak(text)` 接口
- [ ] **TTS 后端接入**：首选本地方案（edge-tts），不强依赖云端 API；流式 token → 流式合成 → 实时播放，目标延迟 < 1s
- [ ] **说话时口型同步**：TTS 播放时驱动 Live2D / 3D 口型参数（基础幅度，不做精细音素对齐）
- [ ] **响应节奏优化**：回复前显示"思考指示"（省略号动画），避免机械感

## 验收标准

1. ⬜ 放入 VMD 文件并配置后，模型按指定动作循环播放
2. ⬜ TTS 能在本地无网络环境下正常合成
3. ⬜ 整体交互延迟（用户输入 → 气泡出现 + 语音开始）< 3 秒

## 相关设计文档

- [能力层](../../desgin/能力层.md)
- [3D 模型支持](../../desgin/3d-model-support.md)
