---
tags:
  - Kokoro
  - roadmap
status: active
created: 2026-04-21
updated: 2026-04-23
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
| **P3** | 3A — 后端 sidecar | FastAPI sidecar + IPC 协议，为 UI 提供接口 | 🔧 接口完成，打包待做 |
| **P4** | 3B — 桌面 UI | Tauri 壳 + Vue 气泡 UI + 立绘切换 | ✅ 已完成 |
| **P5** | 3C — 表现增强 | Live2D ✅ · 3D 模型 ✅ · VMD 动画 🔧 · TTS ❌ | 🔧 进行中 |
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
- [x] **`GET /state`**：返回当前情绪、活跃角色、记忆摘要条数、角色显示配置（display mode / 皮肤 URL）
- [x] **`WebSocket /stream`**：长连接推送，同步 LLM + `asyncio.to_thread`；协议预留逐 token 扩展接口
- [x] **`GET /health`**：健康检查端点，返回角色名和版本
- [x] **`POST /switch-character`**：运行时热切换角色，返回新角色的完整 display 配置
- [x] **`GET /character-assets/{id}/{path}`**：PMX 模型、纹理、VMD、Live2D 模型等静态资源服务（path traversal 防护）
- [x] **角色资源构建**（`character_assets.py`）：从 `manifest.yaml` + `scene.json` 动态生成前端所需的皮肤 URL、摄像机、灯光参数
- [x] **管理后台路由**（`admin` router）：情绪统计、日志查看、记忆管理、Debug 面板
- [ ] **sidecar 打包脚本**：PyInstaller 打包，验证无外部依赖（待完成）

**验收标准**：
1. ⬜ `curl` 能正常调用 `/chat` 并收到角色回复
2. ⬜ WebSocket 流式接口能推送完整回复
3. ⬜ PyInstaller 打包后在无 Python 环境的机器上正常运行

---

## Phase 3B — 桌面 UI ✅

**目标**：搭出最小可用的桌面悬浮窗，能对话、有表情、低打扰常驻。

**技术栈**：Tauri 2.x + Vue 3 + TypeScript + Vite + Pinia

### 任务清单

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

**验收标准**：
1. ⬜ 启动 sidecar 后发消息 → 流式回复出现在气泡 → 情绪切换立绘
2. ⬜ 拖到屏幕边缘 → 缩进 → 鼠标靠近滑出
3. ⬜ 透明区域点击穿透到底层窗口
4. ⬜ 关闭重开后窗口出现在上次位置

---

## Phase 3C — 表现增强 🔧

**目标**：在 UI 已稳定的前提下，逐步提升表现力。

**顺序**：Live2D ✅ → 3D 模型 ✅ → VMD 动画 → TTS → 口型同步（每步可独立交付，不互相阻塞）

### 任务清单

- [x] **Live2D 接入**：`pixi-live2d-display`，情绪驱动动作参数（眉眼、呼吸、动作组）
- [x] **3D 模型接入**：PMX 格式 + Three.js MMDLoader；`manifest.yaml` 定义皮肤列表和 `scene.json` 路径；scene.json 配置摄像机、灯光、缩放、旋转
- [x] **3D 待机程序化动画**：无 VMD 时，自动叠加轻微旋转摆动 + 上下浮动呼吸感
- [ ] **VMD 动画**：在 `scene.json` 中指定 `"vmd"` 字段即可加载循环播放；支持情绪 → VMD 切换（如 happy 时播放活跃动作）
- [ ] **3D 表情控制**：通过 PMX Morph Target 驱动口型、眼型等表情变化，与情绪状态联动
- [ ] **TTS 抽象层**：`src/capability/tts.py`，定义 `TTSClient.speak(text)` 接口
- [ ] **TTS 后端接入**：首选本地方案（edge-tts），不强依赖云端 API；流式 token → 流式合成 → 实时播放，目标延迟 < 1s
- [ ] **说话时口型同步**：TTS 播放时驱动 Live2D / 3D 口型参数（基础幅度，不做精细音素对齐）
- [ ] **响应节奏优化**：回复前显示"思考指示"（省略号动画），避免机械感

**验收标准**：
1. ⬜ 放入 VMD 文件并配置后，模型按指定动作循环播放
2. ⬜ TTS 能在本地无网络环境下正常合成
3. ⬜ 整体交互延迟（用户输入 → 气泡出现 + 语音开始）< 3 秒

---

## Phase 4 — 扩展与分发 ❌

**目标**：让角色成为 App 内可安装、可卸载、可升级、可管理的独立内容包。

**原则**：
- 角色是数据包，不是代码分支
- 运行时只依赖 schema，不依赖具体角色名
- 静态资源与用户数据分离
- 所有隔离、索引、升级都基于稳定 `character_id`

### 任务清单

- [ ] **角色包目录规范**：确定 `manifest.yaml`、`personality.yaml`、`assets/`、`prompts/`、`voices/` 的标准布局
- [ ] **稳定 `character_id` 规则**：明确目录名 / 包内 ID / 显示名三者职责，禁止用显示名做存储主键
- [ ] **`manifest.yaml` schema 定义**：覆盖 `id`、`display_name`、`version`、`schema_version`、作者、资源入口、能力声明
- [ ] **角色能力声明**：在 manifest 中声明 `live2d`、`model3d`、`portrait`、`voice`、`proactive` 等可选能力，支持降级
- [ ] **角色注册中心**：统一负责扫描、校验、注册、启用、禁用、默认角色选择，不再由各层自行扫目录
- [ ] **角色静态资源与运行时数据分离**：固定 `characters/<id>/` 放包内容，`data/characters/<id>/` 放记忆、缓存、日志、状态
- [ ] **角色安装格式**：定义 `.charpkg`，用于分发和导入，包内只含静态定义与资源
- [ ] **安装流程**：临时目录解包、schema 校验、资源校验、冲突检查、原子写入正式目录
- [ ] **卸载流程**：区分"卸载角色包"和"删除角色数据"两个动作，不混用
- [ ] **升级流程**：支持同 `character_id` 覆盖升级，保留用户数据；明确版本比较与失败回滚策略
- [ ] **角色管理接口**：列出、安装、卸载、启用、禁用、设为默认、查询详情等统一 API
- [ ] **角色管理 UI**：App 内提供角色列表、安装入口、启停状态、删除确认、数据清理入口
- [ ] **schema 迁移策略**：为角色包和运行时数据分别定义 `schema_version` 与迁移入口
- [ ] **文档收敛**：制作角色包 / 安装 / 升级 / 清理数据的简明文档

**验收标准**：
1. 新角色可通过 App 内安装流程导入，无需改代码、无需手动复制目录
2. 删除角色包不会误删其他角色的数据
3. 角色升级后，原有记忆和状态仍按 `character_id` 保留
4. 一个只带静态图的角色包和一个带 Live2D / 3D 的角色包都能被同一套运行时识别并正常加载

---

## 当前版本可运行功能汇总

> 更新于 2026-04-23 · 103 个单元测试通过（8 skipped）

| 功能 | 状态 |
|------|------|
| 多 provider LLM（anthropic / openai / gemini / deepseek / openrouter / copilot / 三个 CLI） | ✅ |
| 情绪状态机（触发词匹配 + 衰减） | ✅ |
| 工作记忆（10 轮截断） | ✅ |
| 会话日志（JSONL）+ 调试模式 + 日志回放 | ✅ |
| 人格稳定性复盘脚本 / 成本统计脚本 | ✅ |
| 会话摘要记忆 + 长期事实记忆（token budget 裁剪 + 截断日志） | ✅ |
| 感知层（窗口监控 + 活跃检测 + 五类触发器 + 冷却机制） | ✅ `enable_perception=True` 启用 |
| FastAPI sidecar（/chat、/state、/health、/switch-character、WebSocket /stream） | 🔧 接口完成，打包待做 |
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
| TTS 语音输出 | ❌ 未开始 |
| 角色包分发 | ❌ 未开始 |

---

## 下一步优先建议

> 基于当前状态，体验提升最大的路径：

1. **VMD 待机动画**（低成本，效果显著）：下载一个免费 idle VMD，放入角色目录并配置 `scene.json`，立刻有生命感
2. **TTS 语音输出**（体验质变）：接入 `edge-tts`（免费、无需 API Key），流式 token → 流式合成 → 实时播放
3. **情绪 → VMD 联动**：happy/angry 等情绪触发时切换到对应动作，比光换灯光颜色表现力强很多
4. **sidecar 打包**：PyInstaller 打包，消除用户需要手动装 Python 的门槛
