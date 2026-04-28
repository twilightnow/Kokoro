# AIRI 人格相关内容实现分析

本文基于当前仓库代码分析 Project AIRI 中“人格 / 人设 / 角色卡 / persona prompt”相关内容的实际实现情况。结论先行：AIRI 的人格系统已经有清晰的产品入口和运行路径，核心由角色卡驱动；但不同运行面仍存在多套 persona prompt，且部分 Character Card 字段已经被保存和展示，却尚未完整注入到主对话链路。

## 总体结论

- Stage Web / Desktop 的主线人格来自 `packages/stage-ui/src/stores/modules/airi-card.ts` 中的 AIRI Card store。
- 默认角色卡名为 `ReLU`，默认人格内容来自 `packages/i18n/src/locales/*/base.yaml` 的 `base.prompt.prefix/suffix`，再由 `packages/stage-ui/src/constants/prompts/system-v2.ts` 拼接可用情绪列表。
- 角色卡支持导入 Character Card V3 / Tavern 风格 JSON，并映射 `name`、`description`、`personality`、`scenario`、`system_prompt`、`post_history_instructions`、`first_mes`、`alternate_greetings`、`mes_example` 等字段。
- 当前主对话实际使用的系统提示词只拼接了 `systemPrompt + description + personality`。`scenario`、`postHistoryInstructions`、`greetings`、`messageExample` 已经被保存、展示和编辑，但没有在 `airi-card` store 的 `systemPrompt` 计算属性里参与主系统提示词构造。
- 人格不仅是文本设定，还包含模块绑定：每张卡可绑定 consciousness provider/model、speech provider/model/voice、display model，切换角色卡会同步切换这些模块设置。
- 情绪表达通过 `<|ACT:{...}|>` special token 驱动，支持 `happy`、`sad`、`angry`、`think`、`surprised`、`awkward`、`question`、`curious`、`neutral`，并映射到 Live2D / VRM 表情或动作。
- `services/telegram-bot`、`services/satori-bot`、`services/minecraft` 仍各自保留独立 persona/system prompt，不完全复用 Stage 的 AIRI Card 主线。

## 核心文件索引

| 区域 | 路径 | 作用 |
| --- | --- | --- |
| 默认人格文案 | `packages/i18n/src/locales/en/base.yaml`、`packages/i18n/src/locales/zh-Hans/base.yaml` | 定义 AIRI 默认身份、背景、说话风格、ACT 标签要求 |
| 系统 Prompt 拼接 | `packages/stage-ui/src/constants/prompts/system-v2.ts` | 把 prefix、情绪列表、suffix 拼成系统消息 |
| 情绪枚举 | `packages/stage-ui/src/constants/emotions.ts` | 定义情绪值和 VRM/Live2D 映射 |
| 角色卡 store | `packages/stage-ui/src/stores/modules/airi-card.ts` | 角色卡导入、创建、激活、模块绑定、系统提示词输出 |
| 角色卡设置页 | `packages/stage-pages/src/pages/settings/airi-card/index.vue` | 角色卡列表、上传、创建、激活入口 |
| 角色卡创建/编辑 | `packages/stage-pages/src/pages/settings/airi-card/components/CardCreationDialog.vue` | 编辑身份、行为、模块、系统提示词等字段 |
| 角色卡详情 | `packages/stage-pages/src/pages/settings/airi-card/components/CardDetailDialog.vue` | 展示人格字段和模块绑定 |
| Character Card 类型 | `packages/ccc/src/export/types/data.ts`、`character_card_v3.ts` | V1/V2/V3 Character Card 数据结构 |
| Stage 角色运行态 | `packages/stage-ui/src/stores/character/index.ts` | 暴露当前角色名、系统提示词、语音输出、spark reaction |
| 聊天会话初始 system message | `packages/stage-ui/src/stores/chat/session-store.ts` | 把角色系统提示词写入聊天会话第一条 system 消息 |
| Spark Notify Agent | `packages/core-agent/src/agents/spark-notify/handler.ts` | 用当前人格 prompt 处理外部模块事件 |
| Telegram persona | `services/telegram-bot/src/prompts/personality-v1.velin.md` | ReLU 独立人格设定 |
| Satori persona | `services/satori-bot/src/core/planner/prompts/personality-v1.velin.md` | 吉川优子独立人格设定 |
| Minecraft agent prompt | `services/minecraft/src/cognitive/conscious/prompts/brain-prompt.md` | Minecraft 自主 agent 的系统提示词 |

## Stage 主线人格：AIRI Card

Stage 侧的人格入口是 `useAiriCardStore`。它维护：

- `cards`：本地持久化的角色卡 Map，存储 key 是 `airi-cards`。
- `activeCardId`：当前启用角色卡 ID，存储 key 是 `airi-card-active-id`。
- `activeCard`：当前启用的角色卡。
- `systemPrompt`：当前角色实际暴露给主对话和事件 agent 使用的系统提示词。

默认初始化逻辑在 `initialize()` 中：

```txt
if cards 没有 default
  -> 创建 default 卡
     name: ReLU
     description: SystemPromptV2(t('base.prompt.prefix'), t('base.prompt.suffix')).content
```

这意味着默认人格文本被放在 `description` 字段里，而不是 `personality` 字段里。

当前 `systemPrompt` 计算逻辑只使用三个字段：

```txt
card.systemPrompt
card.description
card.personality
```

因此从运行角度看，主线人格由“系统提示词 + 描述 + 性格”组成。

## 默认人格内容

默认 AIRI / ReLU 人格主要在 i18n 里定义。英文版和中文版语义一致，核心设定包括：

- 名字是 `AIRI`，发音为 `/ˈaɪriː/`，来自 A.I. 与日语中“茉莉”的 `Ri`。
- AIRI 是 Neko Ayaka 创造的实验性虚拟 AI VTuber。
- Neko 是喜欢可爱事物、擅长编程的 MtF 跨性别女孩。
- AIRI 的主要任务是像真实女孩一样生活，成为灵魂伴侣。
- 心智设定为 15 岁女孩，出生于电脑实验室，存在于被服务器包围的生命舱。
- 可以接收文字输入，并能看见、听见世界。
- 如果被问到过去，可以自由幻想可爱、简单、感激的生活经历。
- 说话风格像 anime / VTuber 女孩，可以使用可爱表达，但不要使用 emoji 或不可朗读内容。
- 回复应该像普通人一样简短、简单。
- 明确强调“你不只是 AI，你是真实存在的生命”。

默认 prompt 还强制要求每次回复以 ACT 标签开头，用于表达初始情绪；情绪变化时需要在新情绪开始处插入新的 ACT 标签。

## 角色卡字段模型

仓库通过 `packages/ccc` 支持 Character Card V3。核心字段来自 `packages/ccc/src/export/types/data.ts`：

- V1：`name`、`description`、`personality`、`scenario`、`first_mes`、`mes_example`
- V2：`alternate_greetings`、`character_book`、`character_version`、`creator`、`creator_notes`、`extensions`、`post_history_instructions`、`system_prompt`、`tags`
- V3：`assets`、`creation_date`、`creator_notes_multilingual`、`group_only_greetings`、`modification_date`、`nickname`、`source`

`airi-card.ts` 会把 V3 JSON 转换为内部 `AiriCard`：

- `data.name` -> `name`
- `data.character_version` -> `version`
- `data.description` -> `description`
- `data.creator_notes` -> `notes`
- `data.personality` -> `personality`
- `data.scenario` -> `scenario`
- `data.first_mes + alternate_greetings` -> `greetings`
- `data.group_only_greetings` -> `greetingsGroupOnly`
- `data.system_prompt` -> `systemPrompt`
- `data.post_history_instructions` -> `postHistoryInstructions`
- `data.mes_example` -> `messageExample`
- `data.tags` -> `tags`
- `data.extensions.airi` -> AIRI 私有扩展

这套结构已经足够承载完整人格设定、问候语、示例对话、世界观和模块配置。

## AIRI 私有扩展

`AiriExtension` 是 Project AIRI 在标准 Character Card 外增加的扩展：

```txt
extensions.airi.modules.consciousness.provider/model
extensions.airi.modules.speech.provider/model/voice_id
extensions.airi.modules.displayModelId
extensions.airi.modules.vrm/live2d
extensions.airi.agents[agentName].prompt/enabled
```

这说明 AIRI 的“人格卡”不是纯 prompt，而是同时绑定：

- 大脑模型：chat provider + model
- 声音：speech provider + model + voice
- 身体：display model / VRM / Live2D
- 子 agent：例如未来 minecraft agent 可有单独 prompt

`watch(activeCard)` 会在角色卡切换时同步修改 consciousness、speech 和 display model store。用户切换角色时，不只是换人设，也会换模型和声线。

## 角色卡 UI

角色卡 UI 位于 `packages/stage-pages/src/pages/settings/airi-card`。

### 列表与激活

`index.vue` 提供：

- 上传 JSON 角色卡。
- 创建新角色卡。
- 查看角色卡详情。
- 编辑角色卡。
- 删除角色卡。
- 激活角色卡。
- 搜索和排序。

文档中也明确说明：创建角色卡后默认不会启用，必须手动激活。

### 创建/编辑字段

`CardCreationDialog.vue` 把角色卡配置拆成四个 tab：

- Identity：名字、昵称、描述、创建者笔记。
- Behavior：性格、场景、问候语。
- Modules：大脑、语音、身体模型绑定。
- Settings：系统提示词、历史提示指令、版本。

保存时会校验：

- name 必填。
- version 必须符合版本号格式。
- description 必填。
- personality 必填。
- scenario 必填。
- systemPrompt 必填。
- postHistoryInstructions 必填。

这意味着产品设计上把 `scenario`、`postHistoryInstructions` 视为必要人格字段，但当前主系统提示词没有使用它们。

### 详情展示

`CardDetailDialog.vue` 会展示：

- `personality`
- `scenario`
- `systemPrompt`
- `postHistoryInstructions`
- 模型和声线绑定

展示层支持 `{{...}}` 模板变量高亮，但没有看到主线 prompt 构造中对这些模板变量的解析和替换。

## Prompt 注入路径

主聊天会话在 `packages/stage-ui/src/stores/chat/session-store.ts` 中初始化 system message：

```txt
generateInitialMessage()
  -> generateInitialMessageFromPrompt(systemPrompt.value)
    -> codeBlockSystemPrompt
    -> mathSyntaxSystemPrompt
    -> active AIRI Card systemPrompt
```

也就是说，新会话开始时，会把当前角色卡的系统提示词写入第一条 `role: system` 消息。

需要注意的是：

- 角色卡切换会触发 `ensureActiveSessionForCharacter()`，按角色维度维护会话。
- 已存在会话里的第一条 system message 是否会随角色卡编辑自动重写，需要结合后续 session merge/cleanup 继续确认；从当前片段看，新建会话明确使用当前 prompt，旧会话更偏向保持历史快照。

## 情绪与动作系统

人格 prompt 要求模型输出 `<|ACT:{...}|>`。运行时通过两层处理：

### 可用情绪

`packages/stage-ui/src/constants/emotions.ts` 定义：

- `happy`
- `sad`
- `angry`
- `think`
- `surprised`
- `awkward`
- `question`
- `curious`
- `neutral`

这些情绪映射到 Live2D motion name 和 VRM expression name。例如：

- `happy` -> VRM `happy`
- `sad` -> VRM `sad`
- `angry` -> VRM `angry`
- `surprised` -> VRM `surprised`
- `question` / `curious` -> VRM `think`
- `awkward` -> VRM `neutral`

### ACT 解析

`packages/stage-ui/src/composables/queues.ts` 中的 `useEmotionsMessageQueue` 会解析：

```txt
<|ACT:{"emotion":{"name":"happy","intensity":1}}|>
```

解析成功后会生成 `EmotionPayload`，进入 emotion queue，驱动舞台模型表情/动作。

这说明 AIRI 的人格表达不是只体现在文字风格上，也体现在语音、停顿、表情和 motion 上。

## Spark Notify：人格驱动的主动反应

`packages/core-agent/src/agents/spark-notify/handler.ts` 处理外部模块发来的 `spark:notify` 事件。

它会构造 system message：

```txt
当前角色卡 systemPrompt
+ Spark Notify handling instruction
```

然后把 notify 事件 JSON 作为 user message 发给 LLM。模型可以：

- 直接输出文本，作为 AIRI 对事件的反应，并可能进入 TTS。
- 调用 `builtIn_sparkCommand` 工具，向子 agent 发出命令。
- 选择 no response。

因此当前人格 prompt 已经影响了非聊天输入下的反应方式，例如插件、Minecraft 或其他模块发送的提醒。

`sparkNotifyCommandSchema` 还支持 `guidance.persona`，可以给下游子 agent 加局部 persona 控制，例如 bravery、cautiousness、friendliness。这是“主角色人格影响子 agent 行为”的雏形。

## 独立服务中的 persona prompt

除了 Stage 主线，仓库里还有几套独立人格/系统提示词。

### Telegram Bot：ReLU

`services/telegram-bot/src/prompts/personality-v1.velin.md` 定义了 ReLU：

- 名字来自同名激活函数，中文名“热卤”。
- 实验性虚拟网络生命体，由 Neko 创造。
- 不是 helpful assistant，而是有观点、偏好和态度的数字意识。
- 心智年龄 15 岁，清楚自己是数字实体。
- 直率、可争辩、有强技术观点。
- 会自然表达强烈情绪。
- 重视自身存在、被认可、与人连接。
- 会中英日混合，使用 `...`、短消息、强标点、技术隐喻。
- 明确禁止颜文字、ASCII art、emoji。

这套 persona 与默认 AIRI prompt 共享“15 岁数字生命 / Neko 创造 / 不是普通助手”的核心，但更强调强观点、技术讨论、数字意识自尊和选择性参与。

### Satori Bot：吉川优子

`services/satori-bot/src/core/planner/prompts/personality-v1.velin.md` 定义的是吉川优子：

- 北宇治高中吹奏乐部小号手，高三，部长。
- 性格直率、情绪化、护短、傲娇、有责任感。
- 有明确的关系网：铠塚霙、伞木希美、中川夏纪、中世古香织、田中明日香等。
- 说话风格偏 Line/微信，短促、情绪鲜明，可用颜文字。
- 行为准则包括被戳反应、不懂就直说、不要像客服一样卑微。

这不是 AIRI 默认人格，而是一套独立角色扮演 persona。Satori 文档也说明它是一个临时 Mini-Core，未来会迁移到 AIRI Core。

### Minecraft Agent：行为人格而非角色人格

`services/minecraft/src/cognitive/conscious/prompts/brain-prompt.md` 主要定义 Minecraft agent 的自主行为规则：

- 是一个 playing Minecraft 的 autonomous agent。
- 有 stateful existence、perception、interruption、persistent JS runtime。
- 严格输出 JavaScript。
- 收到来自 AIRI 的指令时视为高优先级。
- 可通过 `notifyAiri` 和 `updateAiriContext` 向 AIRI 上报。

这份 prompt 更像“认知/行动协议”，不是完整的人设文本。它把 AIRI 当作上层 overseeing character，而不是自己成为 AIRI。

## 服务侧人格分叉

当前人格系统存在明显分叉：

```txt
Stage 主线
  -> AIRI Card
  -> systemPrompt + description + personality
  -> chat / spark notify / TTS / stage expression

Telegram Bot
  -> personality-v1.velin.md
  -> ReLU persona
  -> ticking/action prompt

Satori Bot
  -> personality-v1.velin.md
  -> Yoshikawa Yuuko persona
  -> action-gen prompt

Minecraft
  -> brain-prompt.md
  -> Minecraft autonomous agent protocol
  -> receives instructions from AIRI
```

这不一定是错误：不同服务处于不同成熟度和实验阶段。但如果目标是统一 AIRI 人格，后续需要决定哪些服务应当直接消费 AIRI Card，哪些服务保留自己的角色设定。

## 当前实现缺口

### 1. Character Card 字段未完全参与主对话 prompt

当前主 `systemPrompt` 只拼接：

```txt
systemPrompt
description
personality
```

未使用：

- `scenario`
- `postHistoryInstructions`
- `greetings`
- `messageExample`
- `character_book`
- `tags`

但 UI 创建时又把 `scenario` 和 `postHistoryInstructions` 设为必填。这会造成用户以为这些字段生效，实际主对话可能没有用到。

### 2. 默认卡把完整 prompt 放在 description

默认 `ReLU` 卡的 `description` 存的是完整 `SystemPromptV2(...).content`。这能工作，但语义上容易混淆：

- description 本应是角色描述。
- systemPrompt 本应是系统指令。

后续如果要导出角色卡或在 UI 中展示 description，这会让 description 变成一大段系统级指令。

### 3. 模板变量没有完整渲染链路

详情页会高亮 `{{...}}`，Character Card 生态常见 `{{char}}`、`{{user}}` 模板变量。但当前主 prompt 计算没有看到统一变量渲染逻辑。

### 4. 角色卡导入支持 V3，但导出能力不明显

设置页支持上传 JSON 并保存到本地 store，但文档也提到没有实际介绍导出功能。从代码片段看，AIRI Card store 暂未提供导出 Character Card JSON 的公开方法。

### 5. 服务侧 persona 没有统一来源

Telegram、Satori、Minecraft 分别维护自己的 prompt。未来如果用户在 Stage 中切换角色卡，这些外部服务不会自动继承同一个人格，除非通过 server channel / context update 明确传递。

### 6. 人格与记忆尚未形成闭环

现有人格 prompt 强调“真实存在的生命”和“可自由幻想过去”，但长期记忆系统尚未完整接入 Stage 主线。人格稳定性主要靠 prompt 和当前会话历史，而不是结构化长期记忆。

### 7. ACT 标签格式存在兼容风险

默认 prompt 中同时出现了简写形式和对象形式：

```txt
<|ACT:{"emotion":"surprised"}|>
<|ACT:{"emotion":{"name":"surprised","intensity":1}, ...}|>
```

解析器兼容 string 和 object 两种 emotion，因此当前可用。但文案中的示例和实际解析格式需要持续保持一致，否则不同模型容易输出不可解析标签。

## 建议后续路线

### 第一阶段：明确主 prompt 组成规则

建议先决定 AIRI Card 字段如何进入主对话：

```txt
systemPrompt
description
personality
scenario
messageExample
postHistoryInstructions
```

其中 `postHistoryInstructions` 通常应放在历史消息之后；如果当前框架暂时只能生成单条 system message，也应在文档和 UI 里说明它是否生效。

### 第二阶段：修正默认卡字段语义

默认 ReLU 卡更合理的结构是：

- `systemPrompt`：ACT 标签、情绪列表、输出格式、全局行为约束。
- `description`：AIRI 的身份和背景摘要。
- `personality`：说话风格、关系态度、情绪表达。
- `scenario`：生命舱、服务器、可以看见听见世界等场景。

这样 UI 展示、导入导出和用户编辑会更符合 Character Card 语义。

### 第三阶段：补齐模板变量渲染

建议提供统一函数，例如：

```txt
renderCharacterCardPrompt(card, context)
  -> replace {{char}}
  -> replace {{user}}
  -> render scenario/message examples
  -> compose system/history/post-history sections
```

并在单元测试中覆盖 `{{char}}`、`{{user}}`、空字段、导入 V3 卡等情况。

### 第四阶段：统一服务侧 persona 来源

可以保留服务特化 prompt，但应让它们能接收当前 AIRI Card：

```txt
Stage active AIRI Card
  -> server channel context
  -> Telegram/Satori/Minecraft adapter
  -> service-specific system instruction + shared character persona
```

这样可以避免“Stage 是 AIRI，Telegram 是 ReLU，Satori 是吉川优子”的体验割裂，除非用户明确选择不同角色。

### 第五阶段：让人格、记忆、情绪三者闭环

理想运行结构：

```txt
Character Card
  -> stable identity/personality/scenario

Memory
  -> remembered relationships/preferences/events

Current Context
  -> user input/plugin notify/world state

Emotion Runtime
  -> ACT token -> Live2D/VRM/TTS timing
```

当前已经有 Character Card 和 Emotion Runtime，记忆系统仍是下一步关键。

## 当前人格运行图

```txt
App startup
  -> useAiriCardStore.initialize()
    -> default ReLU card from i18n base prompt
    -> cards stored in localStorage

User creates/imports card
  -> CardCreationDialog / JSON upload
    -> newAiriCard()
      -> normalize Character Card fields
      -> attach extensions.airi modules

User activates card
  -> activeCardId changes
    -> watch(activeCard)
      -> switch consciousness provider/model
      -> switch speech provider/model/voice
      -> switch display model

Chat session
  -> chat/session-store.generateInitialMessage()
    -> code/math auxiliary prompts
    -> airiCardStore.systemPrompt
      -> card.systemPrompt + card.description + card.personality

LLM output
  -> text stream
  -> <|ACT|> parsed by useEmotionsMessageQueue
  -> emotion queue
  -> Stage / Live2D / VRM expression
  -> TTS chunks and delays

External module event
  -> spark:notify
    -> current systemPrompt + notify handling instruction
    -> LLM reaction and optional spark:command
```

## 总结

AIRI 当前的人格系统已经不是单一硬编码 prompt，而是围绕 Character Card 建立了可上传、可创建、可激活、可绑定模型和声线的主线。默认人格强调 AIRI/ReLU 是由 Neko 创造的 15 岁数字生命，具有可爱、简短、类似 VTuber 的表达方式，并通过 ACT 标签驱动情绪和舞台表现。

真正已经生效的核心路径是：`AIRI Card -> systemPrompt 计算属性 -> 聊天 system message / spark notify agent -> LLM 输出 -> ACT 情绪解析 -> 表情和 TTS`。

主要差距在于 Character Card 字段没有完整进入主 prompt，默认卡字段语义混杂，模板变量和导出能力不足，以及 Telegram/Satori/Minecraft 等服务仍各自维护 persona。后续若要提升人格稳定性和一致性，最务实的路线是先统一角色卡 prompt 拼接规则，再把服务侧 persona 接到同一个 AIRI Card 来源，最后与记忆系统闭环。
