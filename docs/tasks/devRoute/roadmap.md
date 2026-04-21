---
tags:
  - Kokoro
  - roadmap
status: active
created: 2026-04-21
---

# Kokoro 开发路线图

---

## 优先级

> 原则：先稳人格，再加记忆，再加感知，最后上 UI。每个阶段有独立验收标准，不跨阶段堆功能。

| 优先级 | 阶段 | 目标 | 状态 |
|--------|------|------|------|
| **P0** | 1.5 — CLI 收尾 | 补全 Phase 1 遗留缺口，让 CLI 版本真正"可用于验收" | ✅ 已完成 |
| **P1** | 2A — 轻记忆 | 会话摘要 + 少量长期记忆注入，让她"记得你说过什么" | ✅ 已完成 |
| **P2** | 2B — 轻感知 | Level 0 感知（窗口标题、活跃状态、时间段）+ 主动介入触发器 | ✅ 已完成 |
| **P3** | 3A — 后端 sidecar | FastAPI sidecar + IPC 协议，为 UI 提供接口 | 🔧 进行中（接口已实现，打包待完成） |
| **P4** | 3B — 桌面 UI | Tauri 壳 + Vue 气泡 UI + 基础表情切换 | ❌ 未开始 |
| **P5** | 3C — 表现增强 | 静态立绘差分 → Live2D → TTS | ❌ 未开始 |
| **P6** | 4 — 扩展与分发 | 角色包格式、install/export/import、创意工坊雏形 | ❌ 未开始 |

---

## Phase 1.5 — CLI 收尾 ✅

**目标**：让 CLI 版本达到可信的人格验收标准，不留"技术债进 Phase 2"。

**现状**：全部完成。103 个单元测试通过，工具脚本可用。

### 任务清单

- [x] **固化角色配置 schema**：`character.py` dataclass 字段补全校验，`loader.py` 对缺字段给出明确错误提示，而不是 KeyError
- [x] **prompt 长度估算与告警**：`prompt_builder.py` 在 debug 模式下打印 system prompt token 估算值，超 600/1200 分级告警
- [x] **人格层单元测试补全**：40 个用例，覆盖 emotion / loader / prompt_builder 边界情况
- [x] **人格稳定性复盘脚本**：`python tools/analyze_session.py logs/<file>.jsonl`
- [x] **成本统计脚本**：`python tools/cost_summary.py logs/`

**验收标准**：
1. ✅ 连续 10 轮对话，禁用词零命中
2. ✅ 情绪触发和衰减的单元测试全部通过
3. ✅ 复盘脚本能从现有日志文件正常输出报告

---

## Phase 2A — 轻记忆 ✅

**目标**：让她在对话结束后"记得住"，下次开聊时有上下文，不像每次重置。

**设计原则**：
- 记得准，不乱记。只写入用户明确说出的事实，不写模型推断
- 首版不依赖 ChromaDB / mem0，用 JSON 文件，够用为止
- 记忆注入受 token budget 约束，不把 context 撑爆

### 任务清单

- [x] **`MemoryService.get_context(character_id, token_budget)`**：统一记忆注入入口，按优先级（长期 > 摘要）填充，超出则截断并写入 `TruncationLog`
- [x] **会话摘要自动生成**：`on_session_end()` 调用 LLM 生成摘要，写入 `memories/<character_id>/summaries.jsonl`
- [x] **长期记忆结构化写入**：LLM 提取用户显式陈述的事实，写入 `memories/<character_id>/facts.json`，冲突时标记 `pending_confirm`
- [x] **记忆注入 system prompt**：`prompt_builder.py` 接受 `MemoryContext`，在人格段之后注入"关于用户的记忆"段落
- [x] **被截断记忆日志**：`TruncationLog` 记录每次因 token 超限被丢弃的条目
- [x] **`MemoryService` 核心接口**：`get_context()`、`on_session_end()`、`working_memory` 落地并有测试

**验收标准**：
1. ✅ 用户在第一次会话说"我叫 X"，第二次对话开口时她能在合适时机提到这个名字
2. ✅ 记忆注入不超过 token budget（`_token.py` 估算 + 截断逻辑验证）
3. ✅ 会话结束时摘要文件正常写入

---

## Phase 2B — 轻感知 ✅

**目标**：让她知道用户在干什么、几点了、活不活跃，并在少数高价值场景主动开口。

**设计原则**：
- 首版只做 Level 0（进程级，零成本，无截图无 OCR）
- 默认不打扰，有冷却机制，宁可少触发也不能烦人
- 感知层只输出结构化上下文标签，不直接干预人格判断

### 任务清单

- [x] **`PerceptionCollector`**（`collector.py`）：整合 `WindowMonitor`（pygetwindow）+ `InputTracker`（pynput）采集窗口标题、活跃状态、时间段
- [x] **`BaseTrigger` 抽象与五类触发器**：`IdleTrigger`（空闲 2h）、`LateNightTrigger`（23:00-04:00）、`LongWorkTrigger`（连续工作 1h）、`WindowSwitchTrigger`（频繁切窗口 ≥10 次/分钟）、`GamingTrigger`（窗口标题关键词匹配）
- [x] **冷却机制**（`CooldownManager`）：全局冷却 30 分钟，同类触发器冷却期内不重复触发
- [x] **感知上下文注入 prompt**：`PromptContext.perception` 字段接入主流程，不为 None 时追加"当前场景"段
- [x] **感知日志**（`PerceptionLog`）：每次触发主动介入时写入日志
- [x] **游戏粗判**：`WindowMonitor.GAME_KEYWORDS` 关键词匹配，命中时场景标签为 `gaming`
- [x] **`ProactiveEngine`** 整合以上全部，通过 `ConversationService(enable_perception=True)` 接入主流程

**验收标准**：
1. ✅ 深夜（23:00 后）连续使用 30 分钟，触发一次主动介入
2. ✅ 空闲 2 小时后重新操作，触发一次主动介入
3. ✅ 30 分钟内不重复触发同一类型

---

## Phase 3A — 后端 sidecar 🔧

**目标**：将现有 CLI 逻辑封装为 FastAPI sidecar，为 Tauri UI 提供稳定的 IPC 接口。

**说明**：CLI 逻辑不重写，sidecar 是在已有 `ConversationService` 之上加一层 HTTP/WebSocket 壳。

### 任务清单

- [x] **FastAPI 应用骨架**：`src/api/app.py`，lifespan 管理、CORS 配置
- [ ] **IPC 协议文档**：定义 Tauri ↔ Python sidecar 的消息格式（见 `docs/desgin/IPC协议.md`，待完善）
- [x] **`POST /chat`**：接收用户输入，返回角色回复 + 当前情绪 + usage
- [x] **`GET /state`**：返回当前情绪状态、活跃角色、记忆摘要条数
- [x] **`WebSocket /stream`**：长连接推送，当前为同步 LLM + `asyncio.to_thread`；协议预留逐 token 扩展接口
- [ ] **sidecar 打包脚本**：PyInstaller 打包，验证无外部依赖（待完成）
- [x] **`GET /health`**：健康检查端点，返回角色名和版本

**验收标准**：
1. ⬜ `curl` 能正常调用 `/chat` 并收到角色回复（需先 `pip install fastapi uvicorn`）
2. ⬜ WebSocket 流式接口能推送完整回复
3. ⬜ PyInstaller 打包后在无 Python 环境的机器上正常运行

---

## Phase 3B — 桌面 UI

**目标**：搭出最小可用的桌面悬浮窗，能对话、有表情、低打扰常驻。

**设计基调**：漫画对白框式气泡，不是聊天记录；立绘悬浮右侧，可拖动；双击切换对话 / 锁定模式。

### 任务清单

- [ ] **Tauri 项目初始化**：`frontend/`，配置 sidecar 启动、系统托盘、透明窗口
- [ ] **点击穿透配置**：立绘区域可点击，透明区域穿透到底层窗口
- [ ] **气泡组件**：漫画对白框样式，说完后淡出，无历史堆叠；主动介入附带快捷回应按钮
- [ ] **输入框组件**：默认隐藏，进入对话模式后淡入；无操作 N 秒后淡出
- [ ] **静态立绘占位**：按情绪加载不同 PNG 差分图（normal / angry / shy / happy / cold），先用静态图占位
- [ ] **托盘菜单**：角色切换、退出、打开历史记录
- [ ] **边缘吸附**：拖至屏幕边缘时立绘半隐藏，气泡或点击时滑出
- [ ] **流式输出接入**：前端通过 WebSocket 接收逐字推送，模拟打字效果

**验收标准**：
1. 悬浮窗常驻桌面，不遮挡主窗口操作
2. 用户打字 → 收到流式回复 → 气泡显示完整
3. 情绪变化时立绘表情同步切换

---

## Phase 3C — 表现增强

**目标**：在 UI 已稳定的前提下，逐步提升表现力。

**顺序**：静态差分 → 轻量帧动画 → Live2D → TTS（每步可独立交付，不互相阻塞）

### 任务清单

- [ ] **帧动画**：眨眼、说话口型等少量关键帧动画，比纯静态更有生命感
- [ ] **Live2D 接入**：`pixi-live2d-display`，情绪驱动动作参数（眉眼、呼吸、动作组）
- [ ] **TTS 抽象层**：`src/capability/tts.py`，定义 `TTSClient.speak(text)` 接口
- [ ] **TTS 后端接入**：首选本地方案（edge-tts 或 VITS），不强依赖云端 API
- [ ] **说话时口型同步**：TTS 播放时驱动 Live2D 口型参数（基础幅度即可，不做精细音素对齐）
- [ ] **响应节奏优化**：回复前显示"思考指示"（省略号动画），避免机械感

**验收标准**：
1. Live2D 模型随情绪切换动作
2. TTS 能在本地无网络环境下正常合成
3. 整体交互延迟（用户输入 → 气泡出现 + 语音开始）< 3 秒

---

## Phase 4 — 扩展与分发

**目标**：让角色可以像"安装包"一样分发，用户数据可一键迁移备份。

**说明**：这是长期目标，不阻塞前面任何阶段，条件成熟时再推进。

### 任务清单

- [ ] **`manifest.yaml` schema 定义**：角色包元数据格式（name、version、author、dependencies）
- [ ] **`.charpkg` 格式**：ZIP 打包，包含 personality.yaml、立绘资源、manifest.yaml
- [ ] **`kokoro install <path>`**：从本地或 URL 安装角色包
- [ ] **`kokoro export <character_id>`**：导出角色包（不含用户记忆数据）
- [ ] **`kokoro import <path>`**：导入用户数据备份（含记忆、关系状态）
- [ ] **用户数据单目录设计**：`KOKORO_DATA_DIR` 下所有数据集中，备份即迁移
- [ ] **插件接口草案**：定义第三方扩展的接入点（感知插件、TTS 后端等）

**验收标准**：
1. 新角色包可通过 `install` 命令一步导入，无需手动复制文件
2. 用户数据在两台机器间迁移后，记忆和关系状态完整保留

---

## 当前版本可运行功能汇总

> 更新于 2026-04-21 · 103 个单元测试通过（8 skipped）

| 功能 | 状态 |
|------|------|
| 多 provider LLM（anthropic / openai / gemini / deepseek / openrouter / copilot / 三个 CLI） | ✅ |
| 情绪状态机（触发词匹配 + 衰减） | ✅ |
| 工作记忆（10 轮截断） | ✅ |
| 会话日志（JSONL） + 调试模式 + 日志回放 | ✅ |
| 人格稳定性复盘脚本 / 成本统计脚本 | ✅ |
| 会话摘要记忆 + 长期事实记忆（token budget 裁剪 + 截断日志） | ✅ 已完整接入主流程 |
| 感知层（窗口监控 + 活跃检测 + 五类触发器 + 冷却机制） | ✅ `enable_perception=True` 启用 |
| FastAPI sidecar（/chat、/state、/health、WebSocket /stream） | 🔧 接口完成，打包待做 |
| 桌面 UI（Tauri + Vue） | ❌ 未开始 |
| Live2D / TTS | ❌ 未开始 |
| 角色包分发 | ❌ 未开始 |
