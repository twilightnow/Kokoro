---
tags:
  - 设计
  - UI
  - 表现层
---

# UI 层

UI 层负责 Kokoro 的桌面存在感：角色展示、气泡、输入、窗口行为、语音播放、管理入口和状态反馈。UI 不负责人格判断、记忆治理、主动调度或 provider 鉴权。

## 组成

- `src-tauri`：桌面壳、托盘、窗口命令、窗口权限和系统集成
- `frontend/src`：主窗口 Vue 应用
- `frontend/src/admin`：管理界面 Vue 应用
- `frontend/src/components`：角色展示、气泡、输入等组件
- `frontend/src/composables`：通信、窗口、语音、吸附等可复用逻辑

## 设计职责

UI 负责：

- 展示当前角色
- 展示当前回复和思考状态
- 提供用户输入
- 播放语音和基础口型同步
- 展示 Live2D / 3D / placeholder
- 管理窗口置顶、透明、吸附和点击穿透
- 提供设置和管理入口
- 呈现主动行为和提醒

UI 不负责：

- 拼接 prompt
- 判断情绪迁移
- 修改关系数值
- 直接读写记忆文件
- 决定是否主动打扰用户
- 直接持有 API key

## 主窗口形态

主窗口是桌面伴侣的常驻表面，不是完整 IM 客户端。

核心形态：

- 透明悬浮窗
- 角色模型或立绘
- 单轮气泡
- 轻量输入框
- 快捷工具按钮
- 边缘吸附
- 点击穿透

主窗口应优先保持低打扰。完整配置、日志、记忆编辑和调试能力放到管理界面。

## 表现状态模型

UI 不应直接消费零散字段，而应围绕统一 `DisplayState` 设计。

建议字段：

- `character_id`
- `character_name`
- `display_mode`
- `mood`
- `emotion_intensity`
- `thinking`
- `speaking`
- `idle_state`
- `attention`
- `reaction`
- `visibility_mode`
- `lip_sync_level`
- `active_skin`

说明：

- `mood`：持续情绪
- `emotion_intensity`：表现强度，影响动作和语音
- `thinking`：是否等待模型回复
- `speaking`：是否处于语音播放或文字输出阶段
- `idle_state`：待机状态，如 normal、sleepy、focused
- `attention`：是否被唤起注意或准备主动开口
- `reaction`：一次性动作，如 poke、surprise、greet
- `visibility_mode`：常驻、吸附、展开、隐藏

## Renderer 抽象

角色展示应通过统一 Avatar Surface 分发到不同 renderer。

```text
AvatarSurface
  |-- PlaceholderRenderer
  |-- Live2DRenderer
  |-- Model3DRenderer
```

Renderer 只接收展示状态和角色资源配置，不接触人格、记忆、关系和 provider。

设计约束：

- 页面层不直接操作 Live2D 参数
- 页面层不直接依赖 3D 动画文件名
- renderer 失败时能回退
- 新 renderer 不应影响对话链路

## 角色资源加载

前端通过 sidecar 提供的 display 配置加载资源。

设计原则：

- 角色资源路径由后端解析
- 前端只使用 URL，不拼本地路径
- manifest 决定 display mode 和资源结构
- 资源加载失败时回退到 placeholder
- 手动皮肤选择优先于自动情绪切换

## 气泡与输入

气泡负责展示当前轮输出或主动短句。

输入框负责接收用户输入，不应承担复杂聊天历史管理。若后续需要完整聊天记录，应作为独立面板或管理视图，不应把主窗口变成大型聊天页。

主动行为气泡应支持：

- 普通文本
- 快捷回应
- 稍后提醒
- 不再提醒
- 进入设置

## 语音与口型

语音播放由前端控制播放队列，TTS 能力由 sidecar 提供。

设计原则：

- 文本生成和语音合成解耦
- 语音失败不影响文字回复
- 用户可一键静音
- 口型同步先做基础幅度，不要求精细音素级同步
- TTS 参数来自设置或角色 voice 配置

## 主动行为呈现

主动行为不一定表现为气泡。

UI 应支持四种呈现等级：

- `silent`：无 UI 变化
- `expression`：表情或动作变化
- `short_message`：短气泡
- `conversation`：进入可回复对话

介入等级由 `ProactiveScheduler` 决定，UI 只负责呈现。

## 管理入口

主窗口只保留轻量入口：

- 管理界面
- 置顶
- 同步状态
- 静音
- 勿扰

复杂能力进入管理界面：

- 记忆编辑
- 关系状态
- 提醒管理
- 安全边界
- provider 配置
- 日志和诊断

## 设计约束

- UI 层是表现层，不是业务层
- 主窗口保持轻量和低打扰
- 所有长期状态修改都应走后端 API
- 所有敏感配置都应避免在前端长期明文保存
- 表现层可以丰富，但不能反向污染人格和记忆系统
