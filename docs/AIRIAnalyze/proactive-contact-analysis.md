# AIRI 主动联系机制分析

本文专门回答一个容易混淆的问题：airi 主仓里是否已经有“角色主动联系用户”的完整产品机制。

## 结论

- 目前没有看到类似“空闲检测 -> 主动发话 -> 节流策略 -> 提醒计划”的独立调度器实现。
- airi 当前最接近“主动联系”的主路径，不是用户行为驱动的 scheduler，而是事件驱动的 spark:notify 反应机制。
- 移动端确实有本地通知权限与测试页面，但更多是能力准备和 devtools，不是完整的主动关怀系统。
- 因此这一块应判定为“部分实现”：有主动反应入口，但没有完整的生活化主动联系系统。

## 当前最核心的主动反应机制：spark:notify

关键文件：

- packages/core-agent/src/agents/spark-notify/handler.ts
- packages/core-agent/src/agents/spark-notify/tools.ts
- packages/plugin-protocol/src/types/events.ts
- packages/server-shared/README.md

### 1. 机制定义

plugin-protocol 中定义了 spark:notify 事件，说明系统层面认可“外部模块主动推送上下文给角色”这一模型。

server-shared README 也明确给出了使用场景，例如：

- Minecraft 低血量、低食物、被袭击等事件触发 spark:notify。

### 2. 处理方式

handler.ts 里的 setupAgentSparkNotifyHandler 会：

1. 接收 websocket spark:notify 事件。
2. 组装 system prompt，告知角色“另一个模块触发了事件”。
3. 调用 LLM 流式生成反应文本。
4. 可通过 builtIn_sparkCommand 产生命令草案，交给其他子代理处理。
5. 把非 tool-call 文本作为角色对该事件的实际 reaction，并可能进一步进入 TTS 播放。

这已经具备“系统主动触发角色发声/表态”的能力，但它的触发源主要是外部模块事件，不是用户空闲或情境感知。

### 3. 处理策略

该 handler 还包含：

- pending 队列
- processing 锁
- immediate urgency 优先级处理
- no-response 分支

这说明它不是简单日志广播，而是真正的“被动接收事件后主动生成反应”的执行器。

## 与 TTS 和角色表现的关系

handler.ts 内部注释已经明确写出：

- spark:notify 的文本输出会流到用户界面。
- 这些输出“可能会被文本转语音系统处理并播放出来”。

因此从系统设计上讲，spark:notify 不只是内部状态事件，而是有机会成为角色向用户主动说话的入口。

## 另一条相关能力：移动端本地通知

关键文件：

- apps/stage-pocket/src/components/onboarding/step-permissions.vue
- apps/stage-pocket/src/pages/devtools/notifications.vue

当前已落地内容：

- onboarding 会请求 LocalNotifications 权限。
- devtools/notifications.vue 可以手动调度一条本地通知。

但这条线目前的状态更像：

- 通知能力接入已完成。
- 产品级“谁来发通知、何时发、发什么”的策略层尚未落地。

## 当前没有看到的东西

在 airi 主仓当前代码里，没有看到下列成熟实现：

- 像 Kokoro 那样的 idle / late night / reminder / long work 触发器。
- 基于最近对话、时间段和打扰策略的主动发话 policy。
- 统一的 reminder repository / scheduler。
- 主动联系频率控制、冷却时间、勿扰窗口等完整规则系统。

所以如果从“陪伴产品”的角度理解主动联系，airi 现在还没有完整实现。

## 当前状态判断

建议这样分类：

- 已实现：
  - 事件驱动的主动反应入口 spark:notify。
  - 移动端本地通知权限和测试发送能力。
- 未形成完整产品机制：
  - 面向用户生活节律的主动联系调度器。
  - 用户空闲/情境感知后的主动开场。
  - 提醒计划、节流和打扰控制。

## 最值得关注的文件

- packages/core-agent/src/agents/spark-notify/handler.ts
- packages/core-agent/src/agents/spark-notify/tools.ts
- packages/plugin-protocol/src/types/events.ts
- packages/server-shared/README.md
- apps/stage-pocket/src/components/onboarding/step-permissions.vue
- apps/stage-pocket/src/pages/devtools/notifications.vue
