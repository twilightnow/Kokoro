# Kokoro Sidecar IPC 协议

IPC 层负责连接 Tauri/Vue 前端和 Python sidecar。它只定义协议和数据形状，不承载人格、记忆、关系或主动调度的业务逻辑。

## 基本信息

- sidecar：FastAPI
- 默认地址：`127.0.0.1`
- 默认端口：`18765`
- 通信方式：HTTP + WebSocket

## 设计原则

- 路由层只做协议转换
- 核心业务下沉到 application service
- 前端不直接读取本地角色文件或记忆文件
- API key 不通过 IPC 明文返回
- 长连接只推送前端需要的状态变化
- 所有 destructive 操作需要明确 API 语义

## HTTP 接口类别

### Chat

用于单轮对话。

核心接口：

- `POST /chat`

请求包含用户消息。响应包含角色回复、当前情绪、轮次、flagged 状态和 usage。

设计约束：

- 路由不拼 prompt
- 路由不直接写记忆
- LLM 失败返回可解释错误

### State

用于主窗口同步当前状态。

核心接口：

- `GET /state`
- `GET /health`

状态应保持轻量，适合频繁轮询或窗口聚焦时同步。

可包含：

- 当前角色
- display 配置
- 当前情绪
- 会话轮次
- 记忆注入数量摘要
- token 用量
- TTS / provider / sidecar 健康状态

不应包含：

- 完整记忆
- 完整关系历史
- API key
- 未脱敏感知原文

### Character

用于角色切换和资源访问。

核心接口：

- `POST /switch-character`
- `GET /character-assets/{character_id}/{asset_path}`

设计约束：

- 角色切换由后端完成会话收尾
- 资源路径必须防止 path traversal
- 前端只使用 URL，不拼本地绝对路径

### TTS

用于语音合成。

核心接口：

- `POST /tts`

设计约束：

- TTS 失败不影响文字回复
- 请求文本长度受限
- voice / rate / volume 可由设置或角色默认值决定

### Admin

用于管理界面。

接口前缀：

- `/admin/*`

设计约束：

- 只面向本地管理
- 敏感值不回显
- destructive 操作需要明确确认
- 导出默认脱敏

## WebSocket 协议

核心接口：

- `GET /stream`

当前主要用于流式对话。

客户端发送：

```json
{ "message": "你好" }
```

服务端帧类型：

- `thinking`：开始处理
- `token`：增量文本
- `done`：本轮完成
- `error`：本轮失败

后续可扩展帧类型：

- `state`：轻量状态变化
- `display`：表现层事件
- `proactive`：主动行为消息
- `reminder`：提醒事件
- `safety`：安全降级提示

设计要求：

- 新帧必须向后兼容
- 未识别帧前端应忽略或记录
- 帧内容不应包含敏感原文
- 主动类帧必须来自运行时调度，不由感知触发器直接推送

## Display 配置

`display` 是前端选择 renderer 的依据。

可支持：

- `placeholder`
- `live2d`
- `model3d`

设计原则：

- display 配置由后端根据角色 manifest 构建
- 前端只消费解析后的 URL 和参数
- display 失败可回退

## 未来状态接口

长期伴侣运行时会引入更多状态，但不应把所有状态塞进 `/state`。

建议拆分：

- `/relationship`：关系状态摘要和配置
- `/memories`：记忆治理
- `/reminders`：提醒和承诺
- `/privacy`：感知和隐私设置
- `/safety`：安全边界设置和审计摘要
- `/runtime`：主动调度和生活循环状态

`/state` 保持主窗口轻量同步接口。

## 错误模型

建议错误响应包含：

- `code`
- `message`
- `recoverable`
- `detail`（可选，脱敏）

常见错误：

- `llm_unavailable`
- `tts_unavailable`
- `character_not_found`
- `asset_not_found`
- `invalid_config`
- `permission_denied`
- `unsafe_request`

## 模块边界

- API 层不写人格逻辑
- API 层不操作底层记忆文件
- API 层不直接修改关系数值
- API 层不绕过安全策略
- 所有真实业务处理下沉到 service

这条边界比具体 URL 更重要。后续加接口时优先保持服务边界清晰。
