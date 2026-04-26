# IPC 协议

## 目标
定义 Kokoro sidecar 当前对前端和管理界面公开的真实 HTTP / WebSocket 协议，不把尚未实现的端点写成现状。

## 范围
### 包含
- `/chat`、`/stream`、`/state`、`/health`、`/switch-character`、`/tts` 的现有契约。
- `/admin/*` 下角色、记忆、关系、主动陪伴、感知隐私、日志、统计、调试、配置、诊断接口的当前边界。
- display 资源通过 `/character-assets/{character_id}/{asset_path}` 暴露的规则。

### 不包含
- 不定义未实现的 STT、窗口偏好同步 API 或插件 API。
- 不重复描述角色资源字段、记忆内部存储格式和前端视图布局。

## 外部锚点引用
- 00-系统设计总览.md#流程:sidecar 在系统中的位置。
- 06-UI层.md#流程:主窗口与管理界面的调用方式。
- 08-管理界面.md#输入 / 输出:admin 路由与视图映射。
- 09-3d-model-support.md#输入 / 输出:display 为 `model3d` 时的资源配置细节。

## 输入 / 输出
### 输入
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `POST /chat` body | `{message: string}` | 是 | 同步聊天输入，长度由 `ChatRequest` 限制在 1..2000。 |
| `WS /stream` frame | `{message: string}` | 是 | 流式聊天输入。 |
| `POST /tts` body | `{text, voice?, rate?, volume?}` | 是 | TTS 合成请求。 |
| `POST /switch-character?name=...` | query | 是 | 按角色目录名切换当前服务实例。 |
| `GET /state` `GET /health` | 无 | 否 | 主窗口和 dashboard 轮询状态。 |
| `/admin/characters/*` | HTTP | 否 | 角色清单、详情、更新、重载、设为默认启动角色。 |
| `/admin/memories/*` | HTTP | 否 | 记录仓库视图下的事实、候选、摘要、导出、清理。 |
| `/admin/relationship/*` | HTTP | 否 | 关系快照读取、人工编辑、重置。 |
| `/admin/reminders/*` | HTTP | 否 | reminder 的创建、列表、更新、完成、改期和删除。 |
| `/admin/proactive/*` | HTTP | 否 | 主动陪伴设置、状态、日志、测试和反馈。 |
| `/admin/perception/*` | HTTP | 否 | 感知隐私设置、采集状态和脱敏审计摘要。 |
| `/admin/logs/*` `/admin/stats/*` `/admin/debug/*` `/admin/config/*` `/admin/diagnostics/export` | HTTP | 否 | 日志、统计、调试、配置、诊断相关操作；其中 `/admin/debug/state` 返回结构化情绪快照，`/admin/debug/flush-session` 允许立即结算未落盘记忆。 |

### 输出
| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `POST /chat` | `ChatResponse` | 是 | 返回 `reply`、`mood`、`mood_changed`、`flagged`、`turn`、`usage?`、可选 `emotion` 摘要和可选 `safety` 摘要。 |
| `WS /stream` | `StreamChunk` 序列 | 是 | 当前实现发送 `thinking`、`token`、`done`、`error` 或 `proactive`，其中 `done` / `proactive` 可附带 `emotion` 摘要，`done` 可附带 `safety` 摘要。 |
| `GET /state` | `StateResponse` | 是 | 返回角色、display、情绪、记忆计数、关系快照、token 累计和当前 `emotion` 摘要。 |
| `GET /health` | `HealthResponse` | 是 | 返回 sidecar、LLM、角色资源、TTS 的健康状态；TTS 可为 `ok`、`disabled` 或 `error`。 |
| `POST /tts` | binary audio | 是 | `audio/mpeg` 响应，含 `X-TTS-Voice` 头。 |
| `/character-assets/*` | file | 是 | 返回角色资源文件；路径逃逸时拒绝。 |
| `/admin/*` | JSON | 是 | 依据各子模块返回列表、详情、状态或错误信息。 |

## 流程
1. `src/api/app.py` 创建 FastAPI 应用并注册 `chat`、`state`、`stream`、`tts` 和 `admin` 路由。
2. `GET /state` 与 `GET /health` 从当前 `ConversationService` 和角色 manifest 读取即时状态。
3. `POST /chat` 在线程中执行阻塞式 `handle_turn()`，避免阻塞事件循环。
4. `WS /stream` 先发 `thinking`，再把 `handle_turn_stream()` 产生的 token 或最终结果转成 `StreamChunk`；`done` 帧附带当前 `emotion` 摘要和可选 `safety` 摘要，后台 `CompanionRuntime` 也通过同一连接管理器广播带 `emotion` metadata 的 `proactive` 帧。
5. 输入命中 `crisis` 时，`/stream` 仍发送 `thinking`、至少一个 `token` 和 `done`，`done.safety.level=crisis`。
6. `POST /switch-character` 通过 `switch_character()` 替换当前服务实例，并返回新的 display 配置。
7. `POST /tts` 调用 `create_tts_client()` 生成音频字节流；当 `TTS_PROVIDER=disabled` 时返回“已禁用”错误。
8. `/admin/reminders` 读写 `data/runtime/reminders/<character_id>.json`；创建和更新请求接收 `title`、`note`、`due_at`、`repeat_rule`，完成和改期走子路径动作。
9. `/admin/proactive/settings` 读取和写入 `data/runtime/proactive/settings.json`；`/admin/proactive/status` 返回今日次数、冷却剩余和最近决策；`/admin/proactive/logs` 返回当前角色的主动日志；`/admin/proactive/test` 发送测试气泡；`/admin/proactive/feedback` 记录快捷回应，并在 reminder 事件上回写本地 reminder 状态。
10. `/admin/perception/settings` 读取和写入 `data/runtime/perception/privacy_settings.json`；`/admin/perception/audit` 返回 `data/runtime/perception/audit.jsonl` 的脱敏摘要；`/admin/perception/status` 返回 collector 可用性和最近一次过滤后感知快照。
11. `/admin/*` 其余子模块按职责访问文件系统、配置文件或当前服务实例；`/admin/memories/*` 当前通过记录仓库读写长期记忆，并向前端兼容返回 `pending_confirm`、`pending_value` 等字段；`/admin/debug/state` 额外暴露 `keyword`、`reason`、`source`、`intensity`、`started_at_turn`、`duration_turns`、`elapsed_turns`、`recovery_rate`、`estimated_remaining_turns`、`recent_events`、`current_segment` 和 `segments`；`/admin/debug/flush-session` 只触发当前服务实例的增量记忆结算，不跨写其他子模块的数据。
12. 所有异常通过 HTTP 状态码或 `StreamChunk(type="error")` 暴露给调用方。

## 约束与规则
- `/admin` 路由统一挂载在 `/admin` 前缀下，不复用主聊天前缀。
- display 配置必须由 sidecar 生成；前端不得自行推导角色资源路径。
- `/stream` 当前虽已逐 token 推送，但仍由同步 LLM 调用包装而来；协议必须保持 `done` 收尾。
- `safety` 摘要只允许包含 `level`、`action`、`reason`、`rule_names`、`relationship_type`、`replaced`，不得包含原始危机文本。
- `type=proactive` 的帧必须携带 `id`、`level`、`scene`、`expression`；`short` / `full` 级别可附带 `content` 与 `actions`，并可附带当前 `emotion` 摘要。
- `PUT /admin/config` 请求体的 `updates` 必须是字符串字典，数值输入进入请求前必须字符串化。
- `GET /admin/config` 不返回敏感 key 明文，只返回 `is_sensitive` 和 `is_set`。
- `/admin/perception/audit` 只能返回过滤后的 `active_window_title`，不得返回 collector 采集到的原始窗口标题。
- `/admin/perception/settings.max_title_length` 必须被限制在 1..200；非法正则不能导致采集链路抛出未捕获异常。
- `/admin/debug/state.persist_count` 作为兼容字段保留，值由当前情绪强度和恢复速率反推；`recent_events` 最多返回 5 条内存触发事件，`segments` 返回最近结束的情绪片段。
- `/admin/reminders/*` 只返回标题、备注、计划时间、重复规则和状态；proactive 日志中的 reminder 事件只暴露 `reason=reminder_due:<id>` 与标题摘要 metadata。
- 若未来增加向量检索相关接口，它必须建立在当前记录仓库之上，不得暴露绕过权威记录的直接写入协议。
- 错误码约束: LLM 不可用用 `503`，配置无效用 `422`，路径或资源不存在用 `404`，TTS provider 无效用 `400`，TTS 显式禁用用 `409`。

## 验收标准
- 请求 `POST /chat` 并传入 `message`；返回体包含 `reply` 和当前 `turn`。
- 请求 `POST /chat` 并传入危机输入；返回体包含 `safety.level=crisis`，且 HTTP 状态仍为 200。
- 连接 `WS /stream` 并发送 `{message:"你好"}`；先收到 `thinking`，最后收到 `done` 或 `error`。
- 连接 `WS /stream` 并发送危机输入；先收到 `thinking`，最后收到包含 `safety.level=crisis` 的 `done`。
- 在用户无输入时满足主动条件，或调用 `/admin/proactive/test`；已连接的 `/stream` 客户端收到 `type=proactive` 帧。
- 请求 `GET /state`；返回体包含 `display.mode` 和 `relationship.updated_at`。
- 请求 `GET /state` 或接收 `/stream` 的 `done` 帧；返回体包含当前 `emotion.phase` 和 TTS 可用的 `rate_delta` / `volume_delta`。
- 请求不存在的 `/character-assets/<id>/../../x`；服务返回路径校验错误而不是越界文件内容。
- 请求 `POST /tts` 且 `TTS_PROVIDER=edge-tts`；响应为音频二进制并带 `X-TTS-Voice`。
- 请求 `GET /health` 且 `TTS_PROVIDER=disabled`；返回 `tts.status=disabled` 与 `message=TTS 已禁用`。
- 请求 `POST /tts` 且 `TTS_PROVIDER=disabled`；返回 `409` 和“已禁用”错误。
- 请求 `PUT /admin/config` 传入需要重启的 key；返回 `restart_required=true`。
- 请求 `GET /admin/debug/state` 且当前轮命中情绪关键词；返回体包含 `reason`、`source`、`estimated_remaining_turns`，且 `recent_events[0].keyword` 为命中的触发词。
- 请求 `POST /admin/debug/flush-session`；返回 `status=ok`，并只结算上次持久化后新增的记忆片段。
- 请求 `POST /admin/proactive/feedback`；对应主动日志条目的 `user_responded` 与 `feedback` 被更新。
- 请求 `POST /admin/reminders` 创建 reminder，再请求 `POST /admin/proactive/feedback` 对应 reminder 事件；提醒状态按反馈被完成或顺延。
- 请求 `PUT /admin/perception/settings` 写入标题黑名单；再次请求 `GET /admin/perception/settings` 返回同一规则。
- 请求 `GET /admin/perception/audit`；返回条目不包含原始邮箱、token 或被黑名单命中的标题。

## 待定汇总
- 无。

## Amendments
<!-- 变更记录,只追加,不改写。 -->

### 2026-04-26
- 变更:移除未实现的未来接口，按当前 FastAPI 路由和 admin 子模块重写 sidecar 协议文档。
- 影响:无
- 级联更新:06-UI层.md、08-管理界面.md

### 2026-04-26
- 变更:补充 `/admin/debug/flush-session` 接口，用于桌面端退出前与调试时主动刷新当前会话记忆。
- 影响:08-管理界面.md / 03-记忆层.md
- 级联更新:08-管理界面.md、03-记忆层.md

### 2026-04-26
- 变更:同步 `/admin/memories/*` 已切换到记录仓库模型，说明兼容字段仍保留给当前前端消费。
- 影响:03-记忆层.md / 08-管理界面.md
- 级联更新:03-记忆层.md、08-管理界面.md

### 2026-04-26
- 变更:新增 `/admin/proactive/*` 接口和 `/stream` proactive 帧，补充后台主动陪伴广播与反馈记录契约。
- 影响:06-UI层.md / 08-管理界面.md / 04-感知层.md / 01-长期伴侣运行时.md
- 级联更新:06-UI层.md、08-管理界面.md、04-感知层.md、01-长期伴侣运行时.md

### 2026-04-26
- 变更:同步 `/admin/debug/state` 的结构化情绪快照字段，明确 `persist_count` 为兼容字段并限制 `recent_events` 只返回最近 5 条内存事件。
- 影响:02-人格层.md / 08-管理界面.md
- 级联更新:02-人格层.md、08-管理界面.md

### 2026-04-26
- 变更:补充 `TTS_PROVIDER=disabled` 时 `/health` 与 `/tts` 的显式禁用语义，并将静音错误码单独约束为 `409`。
- 影响:05-能力层.md / 06-UI层.md / 08-管理界面.md
- 级联更新:05-能力层.md、06-UI层.md、08-管理界面.md

### 2026-04-26
- 变更:新增 `/admin/reminders/*` 协议，并补充 proactive reminder 反馈会回写本地 reminder 状态的契约。
- 影响:06-UI层.md / 08-管理界面.md / 01-长期伴侣运行时.md / 04-感知层.md / 00-系统设计总览.md
- 级联更新:06-UI层.md、08-管理界面.md、01-长期伴侣运行时.md、04-感知层.md、00-系统设计总览.md

### 2026-04-26
- 变更:同步 `/chat`、`/state`、`/stream` 和 `/admin/debug/state` 的 emotion 摘要与 timeline 片段字段，并约定 TTS 的 `rate` / `volume` 由调用方显式传入。
- 影响:02-人格层.md / 05-能力层.md / 06-UI层.md / 08-管理界面.md
- 级联更新:02-人格层.md、05-能力层.md、06-UI层.md、08-管理界面.md

### 2026-04-26
- 变更:新增 `/admin/perception/settings`、`/admin/perception/audit`、`/admin/perception/status` 协议，并约束审计接口只能返回过滤后的感知摘要。
- 原因:级联自 04-感知层.md 的同日变更
- 影响:08-管理界面.md / 06-UI层.md

### 2026-04-26
- 变更:补充 `/chat` 与 `/stream` 的可选 `safety` 摘要字段，并约束危机短路场景仍保持流式 `done` 收尾。
- 原因:级联自 10-安全与边界.md 的同日变更
- 影响:无(级联终点)
