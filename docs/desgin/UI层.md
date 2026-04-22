---
tags:
  - 设计
  - 当前实现
---

# UI层

当前 UI 层由两部分组成：

- `src-tauri`：桌面壳、托盘、窗口命令
- `frontend/src`：Vue 3 + Pinia 界面

当前实现目标：先把桌面挂件形态跑通，再升级角色表现；主线是 `Live2D`，但架构不能绑死在 `Live2D`。

## 当前技术栈

| 模块 | 当前方案 |
|------|----------|
| 桌面壳 | Tauri 2 |
| 前端 | Vue 3 |
| 状态管理 | Pinia |
| 通信 | WebSocket + 少量 HTTP |
| 角色展示 | 纯前端占位立绘面板 |

当前没有 Live2D，也没有 3D 模型。`SpritePanel.vue` 只是根据情绪切换占位表情和文案。

## 当前组件结构

前端页面比较薄：

- `App.vue`：页面装配、窗口事件、角色切换监听
- `components/SpritePanel.vue`：角色面板与情绪展示
- `components/BubbleBox.vue`：气泡与快捷回应按钮
- `components/InputBar.vue`：输入框
- `stores/chat.ts`：聊天显示状态
- `stores/ui.ts`：窗口吸附状态
- `composables/useChat.ts`：sidecar 通信
- `composables/useEdgeSnap.ts`：边缘吸附
- `composables/useWindowPosition.ts`：窗口位置持久化

这个拆法已经够用，后续新增 UI 能力优先落到 composable 或 store，不把逻辑塞回 `App.vue`。

## 当前交互形态

- 主窗口固定为 `320 x 520`
- 透明、无边框、置顶、隐藏任务栏
- 鼠标进入窗口时取消点击穿透
- 鼠标离开窗口且未吸附时恢复点击穿透
- 点击角色面板显示输入框
- 回复中显示思考状态
- 托盘可切换显示/隐藏和角色切换

当前没有“完整聊天记录区”，气泡是单轮展示，不是 IM 聊天面板。

## 当前窗口行为

已落地：

- 边缘吸附：左、右、下三边
- 吸附后只保留少量可见区域
- 鼠标进入时解除吸附
- 位置保存到 `localStorage`
- 关闭窗口前保存位置

对应实现：

- `frontend/src/composables/useEdgeSnap.ts`
- `frontend/src/composables/useWindowPosition.ts`
- `src-tauri/src/commands.rs`

## 当前角色切换流程

角色切换不是前端直接改状态，而是走一条简单链路：

1. Tauri 托盘发出 `character-switch-requested`
2. 前端监听事件
3. 前端调用 sidecar `POST /switch-character?name=...`
4. sidecar 重建 `ConversationService`
5. 前端重置本地聊天状态

这样做的好处是角色切换的真实状态仍由后端掌控，前端只是表现层。

## 保持简单的约束

- UI 不持有记忆、人格、感知规则
- UI 不自己拼 prompt
- UI 不直接管理角色目录
- Tauri 命令只处理桌面壳能力，不处理业务
- WebSocket 帧协议尽量简单，当前只依赖 `thinking` / `done` / `error`

## 表现层目标

- 当前主线：`Live2D`
- 当前备选：`静态差分 / 少量帧动画`
- 后续扩展：`VRM 3D`

判断标准：

- `3D` 自由度更高，但制作、渲染、调试成本都更重
- `Live2D` 更适合当前桌面挂件形态，表现力和成本更均衡
- 首版重点不是大动作，而是 `待机`、`说话态`、`情绪切换`、`主动开口前摇`

## 表现层抽象

UI 只消费角色状态，不直接依赖某种渲染技术。

推荐保持这层抽象：

- `角色状态层`：角色名、情绪、是否思考、是否说话、是否待机、一次性反应事件
- `表现驱动层`：把状态转换成统一指令，如切表情、播待机、播说话态、触发 reaction、显示气泡
- `渲染实现层`：具体由 `Sprite`、`Live2D`、`VRM` renderer 落地

约束：

- 上层逻辑不直接操作 `Live2D` 参数
- 上层逻辑不直接依赖 `VRM` 动画名
- `renderer` 可替换，但 `chat`、`memory`、`perception` 不需要跟着改

## UI 侧建议保留的统一状态

当前 `mood + characterName + turn` 够占位阶段使用，但不够支撑后续表现升级。后续建议统一到以下状态：

- `characterName`
- `mood`
- `thinking`
- `speaking`
- `idle`
- `attention`
- `reaction`
- `visibilityMode`

说明：

- `mood`：持续情绪，如开心、生气、冷淡
- `speaking`：当前是否处于说话态
- `idle`：当前待机状态，如 normal / blink / breathe
- `attention`：是否在“准备开口”或“被唤起注意”
- `reaction`：一次性事件，如 poke / greet / surprise
- `visibilityMode`：常驻、吸附、展开对话

## Renderer 设计约束

后续如果升级 UI，建议保留统一 renderer 接口，而不是让 `SpritePanel` 直接长成某种具体实现。

建议形态：

- `StaticSpriteRenderer`
- `Live2DRenderer`
- `VRMRenderer`

三者都只接收统一的表现状态，不暴露底层实现细节给页面层。

## 升级顺序

1. 占位角色面板替换为正式静态差分素材
2. 补齐待机微动作、说话态、气泡前摇
3. 接入 `Live2DRenderer`
4. 再考虑 `VRMRenderer`

结论：

- `Live2D` 是当前最合适的主方案
- `3D` 不作为当前主线，但接口要预留
- UI 层要围绕“角色状态”和“表现指令”设计，不围绕某个具体引擎设计
