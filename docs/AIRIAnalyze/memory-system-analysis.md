# AIRI 记忆系统实现分析

本文基于当前仓库代码分析 AIRI 的“记忆系统”实际落地情况。结论先行：仓库里同时存在多套与 memory 相关的代码，但它们的成熟度和职责不同。

- `services/telegram-bot` 是目前最接近“长期/短期记忆系统”的实现：用 PostgreSQL + pgvector 保存聊天消息、贴纸、图片描述，以及一组尚未被业务代码使用的结构化记忆表。
- `services/computer-use-mcp` 实现了完整的“任务记忆”，但它只记录当前自动化任务状态，不是 AIRI 人格或聊天长期记忆。
- `packages/memory-pgvector` 目前只是一个 server-sdk 模块壳，没有实际 CRUD、向量检索或记忆管理逻辑。
- Stage Web / Desktop 设置页已经露出“Memory / Short-Term Memory / Long-Term Memory”入口，但页面仍是 `WIP`，没有连到后端或本地存储。
- 文档和 DevLog 中描述的遗忘曲线、强化、情绪影响、随机召回等设计，大部分仍停留在规划/实验说明层面，主代码路径没有完整实现。

## 代码位置总览

| 区域 | 路径 | 当前作用 | 成熟度 |
| --- | --- | --- | --- |
| Telegram 记忆数据库 | `services/telegram-bot/src/db/schema.ts` | 定义聊天消息、贴纸、图片、结构化记忆、目标、想法等表 | 表结构已落地 |
| Telegram 消息记录 | `services/telegram-bot/src/models/chat-message.ts` | 记录 Telegram 消息并生成 embedding | 已接入运行路径 |
| Telegram 相关消息召回 | `services/telegram-bot/src/models/chat-message.ts` | 用 cosine similarity + 时间相关性召回历史消息片段 | 已接入读取消息动作 |
| Telegram Prompt 注入 | `services/telegram-bot/src/bots/telegram/agent/actions/read-message.ts` | 将最近消息、未读消息、相关历史消息拼到 Prompt | 已接入运行路径 |
| Telegram 工作记忆 | `services/telegram-bot/src/types.ts`、`services/telegram-bot/src/bots/telegram/index.ts` | 每个 chat 维护 `messages` 和 `actions` 数组 | 已接入运行路径 |
| 任务记忆 | `services/computer-use-mcp/src/task-memory/*` | MCP 会话中的任务状态合并、读取、清空 | 完整独立实现 |
| 任务记忆 MCP 工具 | `services/computer-use-mcp/src/server/register-task-memory.ts` | 注册 `task_memory_update/get/clear` | 已接入 MCP server |
| pgvector 模块包 | `packages/memory-pgvector/src/index.ts` | 创建名为 `memory-pgvector` 的 server-sdk client | 仅壳代码 |
| Stage 设置页 | `packages/stage-pages/src/pages/settings/memory/index.vue` 等 | 显示 `WIP` | 未实现 |
| 模块列表入口 | `packages/stage-ui/src/composables/use-modules-list.ts` | 展示短期/长期记忆模块入口，`configured: false` | 入口已注册 |
| Minecraft 临时记忆 | `services/minecraft/src/libs/mineflayer/memory.ts` | 只保存 chatHistory/actions 数组 | 简单运行时状态 |

## Telegram Bot 的记忆实现

### 数据库基础

`services/telegram-bot/src/db/index.ts` 通过 `drizzle-orm/node-postgres` 连接 `env.DATABASE_URL`，并载入 `schema.ts` 里的表定义。迁移文件位于 `services/telegram-bot/drizzle`。

最底层依赖 PostgreSQL 的向量扩展：

- 初始迁移 `0000_harsh_king_cobra.sql` 执行 `CREATE EXTENSION vectors`。
- 聊天消息、贴纸、图片描述和结构化记忆均使用 `vector(dimensions)` 字段。
- 向量索引采用 HNSW，operator class 是 `vector_cosine_ops`。

当前支持三种 embedding 维度：

- `1536`
- `1024`
- `768`

代码通过 `env.EMBEDDING_DIMENSION` 决定写入或查询哪一个向量列。

## 向量数据库设计

当前仓库里没有独立运行的“向量数据库服务”。向量检索能力嵌在 `services/telegram-bot` 的 PostgreSQL 数据库里，通过 Drizzle schema、SQL migration 和向量索引实现。

需要注意命名差异：

- 包名是 `packages/memory-pgvector`，但它目前只是 server-sdk client 壳。
- Telegram bot 迁移中执行的是 `CREATE EXTENSION vectors`，不是常见 pgvector 扩展的 `CREATE EXTENSION vector`。
- Drizzle schema 使用 `drizzle-orm/pg-core` 的 `vector({ dimensions })` 类型，并用 `vector_cosine_ops` 建 HNSW 索引。

所以当前实际设计可以理解为“PostgreSQL + vectors/pgvector 风格向量列 + HNSW 索引”，而不是已经抽象完成的 memory-pgvector 模块。

### 向量列设计

同一份文本内容会按 embedding 模型维度写入不同列。仓库没有用单一 `vector` 列配合维度元数据，而是为每种支持维度建立独立列：

| 表 | 文本字段 | 1536 维 | 1024 维 | 768 维 | 当前是否业务使用 |
| --- | --- | --- | --- | --- | --- |
| `chat_messages` | `content` | `content_vector_1536` | `content_vector_1024` | `content_vector_768` | 是 |
| `stickers` | `description` | `description_vector_1536` | `description_vector_1024` | `description_vector_768` | 部分使用，主要查描述 |
| `photos` | `description` | `description_vector_1536` | `description_vector_1024` | `description_vector_768` | 部分使用，主要查描述 |
| `memory_fragments` | `content` | `content_vector_1536` | `content_vector_1024` | `content_vector_768` | 表已建，业务未接入 |
| `memory_short_term_ideas` | `content` | `content_vector_1536` | `content_vector_1024` | `content_vector_768` | 表已建，业务未接入 |

这种设计的好处：

- 查询时可以直接选择固定维度列，不需要在一列里混存不同维度。
- 不同 embedding provider/model 可以通过 `EMBEDDING_DIMENSION` 切换。
- 每个维度都能建立独立 HNSW 索引。

代价：

- 每新增一种 embedding 维度都要改 schema 和 migration。
- 同一条数据如果切换 embedding 维度，需要补算新列。
- 查询代码里会出现多处 `switch (env.EMBEDDING_DIMENSION)`。
- 旧维度列可能长期为空或过期，没有统一的版本/模型标识。

### 向量索引设计

每个向量列都建立 HNSW cosine 索引。例如初始迁移中：

```sql
CREATE INDEX "chat_messages_content_vector_1536_index"
ON "chat_messages"
USING hnsw ("content_vector_1536" vector_cosine_ops);
```

1024 维是在后续迁移 `0001_next_talkback.sql` 追加的：

```sql
ALTER TABLE "chat_messages" ADD COLUMN "content_vector_1024" vector(1024);

CREATE INDEX "chat_messages_content_vector_1024_index"
ON "chat_messages"
USING hnsw ("content_vector_1024" vector_cosine_ops);
```

结构化记忆迁移 `0003_black_warbird.sql` 也给 `memory_fragments` 和 `memory_short_term_ideas` 的三种维度列建立了 HNSW 索引。

索引选择说明：

- `hnsw` 适合近似最近邻搜索，面向较大规模向量召回。
- `vector_cosine_ops` 表示按 cosine distance 建索引。
- 代码里的 similarity 计算使用 `1 - cosineDistance(...)`，与 cosine 距离索引匹配。

当前代码没有看到对 HNSW 参数的显式配置，例如 `m`、`ef_construction`、`ef_search`。索引使用扩展/数据库默认参数。

### 写入路径

目前真正写入向量并被业务使用的是聊天消息。

```txt
Telegram Message
  -> recordMessage()
    -> convert message/sticker/photo into text
    -> embed({ model, input })
    -> switch EMBEDDING_DIMENSION
    -> write one vector column
    -> insert chat_messages
```

`recordMessage` 只会写入当前环境变量指定的那一个向量列：

- `EMBEDDING_DIMENSION=1536` 写 `content_vector_1536`
- `EMBEDDING_DIMENSION=1024` 写 `content_vector_1024`
- `EMBEDDING_DIMENSION=768` 写 `content_vector_768`

贴纸和图片表也预留了 description vector，但当前 `recordSticker` / `recordPhoto` 只保存 description、base64、path 等字段，没有在 model 层写 description vector。仓库里 `services/telegram-bot/src/llm/photo.ts` 和 `sticker.ts` 有调用 `embed()` 的代码，但变量名是 `_embedRes`，需要结合具体调用链继续确认是否已完整落库。就当前 model 层而言，贴纸/图片召回主要依赖 file_id 查 description，不是向量召回。

历史消息补 embedding 脚本是 `services/telegram-bot/scripts/embed-all-chat-messages.ts`：

- 查找当前维度列为 null 的消息。
- 批量调用 embedding API。
- 按当前 `EMBEDDING_DIMENSION` 回填对应向量列。
- 用 `WORKER_POOL_SIZE` 和 `BATCH_SIZE` 控制并发和批次。

这说明设计上允许先存消息、后补向量。

### 查询路径

当前可运行的向量查询在 `findRelevantMessages(...)`。

查询时先根据 `EMBEDDING_DIMENSION` 选择列：

```ts
switch (env.EMBEDDING_DIMENSION) {
  case '1536':
    similarity = sql<number>`(1 - (${cosineDistance(chatMessagesTable.content_vector_1536, embedding.embedding)}))`
    break
  case '1024':
    similarity = sql<number>`(1 - (${cosineDistance(chatMessagesTable.content_vector_1024, embedding.embedding)}))`
    break
  case '768':
    similarity = sql<number>`(1 - (${cosineDistance(chatMessagesTable.content_vector_768, embedding.embedding)}))`
    break
}
```

然后把语义相似度和时间相关性合成排序分：

```sql
combined_score = (1.2 * similarity) + (0.2 * time_relevance)
```

过滤和排序：

- 只查 Telegram 平台。
- 只查同一个 chat。
- 排除当前已知消息，避免把刚读到的消息当作历史记忆。
- `similarity > 0.5`。
- 按 `combined_score` 降序。
- 每个 unread embedding 取 top 3。

命中历史消息后，再围绕每条命中取前后各 5 条，形成上下文窗口。这一点很关键：向量库真正召回的是“锚点消息”，最终注入 Prompt 的是“锚点消息附近的一段对话”。

### 多模态内容如何向量化

聊天消息表的 `content` 不只保存纯文本，也保存贴纸/图片的文本化描述。

当前规则：

- 文本消息：直接使用消息文本或 caption。
- 贴纸消息：查贴纸描述，拼成“用户发送了某贴纸，贴纸集是...”。
- 图片消息：查图片描述，拼成“图片描述是...”。

这是一种轻量的多模态转文本方案：

```txt
image/sticker
  -> caption/vision/sticker description
  -> text
  -> embedding
  -> chat_messages.content_vector_*
```

也就是说，向量数据库不直接存图片 embedding 或视觉 embedding，而是存“图片/贴纸语义描述文本”的 embedding。

### 结构化记忆的向量预留

`memory_fragments` 和 `memory_short_term_ideas` 已经按同样模式设计了向量列和 HNSW 索引。

设计意图比较清楚：

- `memory_fragments.content` 是事实/事件/关系等抽象记忆文本。
- `memory_short_term_ideas.content` 是梦境、对话、反思产生的想法文本。
- 两者都可以走同一套 embedding 维度切换和 cosine 检索。

但当前缺少对应代码：

- 没有 `recordMemoryFragment`。
- 没有 `embed memory fragment`。
- 没有 `findRelevantMemoryFragments`。
- 没有访问后更新 `last_accessed` / `access_count`。
- 没有从 `chat_messages` 抽取结构化记忆并写入这些表的后台任务。

因此这部分属于“向量数据库 schema 已预留，业务层未闭环”。

### 与传统 RAG 的差异

当前实现不是标准文档 RAG 分块库，而是“消息事件 RAG”：

- 基本单位是 Telegram message。
- 向量命中后扩展为前后对话窗口。
- 排序不只看 cosine similarity，还额外加入时间相关性。
- 召回结果用自然语言 one-line 格式注入 Prompt。

这种设计适合聊天场景，因为单条消息通常语义太碎，前后上下文比单个 chunk 更重要。

### 当前向量数据库设计缺口

1. 没有 embedding 模型版本字段。

同一维度可能来自不同模型。当前只按维度分列，无法判断 `content_vector_1024` 来自哪个 embedding model。如果模型切换但维度相同，旧向量和新向量会混在同一列。

2. 没有统一向量 repository。

向量写入和查询逻辑散落在 Telegram bot model/script 里，`packages/memory-pgvector` 没有承接这些能力。

3. 软删除和向量查询没有统一策略。

结构化记忆表有 `deleted_at`，但还没有查询封装，因此未来实现向量召回时必须明确默认过滤软删除记录。

4. 贴纸/图片 description vector 没有完整召回路径。

表和索引存在，但 Telegram bot 的贴纸/图片主要是 file_id 查描述，尚未看到“根据当前语义召回相关贴纸/图片”的完整路径。

5. 时间相关性公式可能需要修正。

当前 `time_relevance` 用毫秒差除以 `86400 / 30` 量级的表达式，单位疑似不正确。向量检索排序会被这个分数影响，因此这是向量召回质量的关键风险。

6. 没有召回质量评估。

当前没有针对 similarity threshold、topK、上下文窗口、时间权重的测试或评估集。`similarity > 0.5`、`top 3`、前后 5 条都属于硬编码经验值。

### 消息记忆表

`chat_messages` 是实际被运行路径使用的核心记忆表。字段包括：

- 平台信息：`platform`
- 平台消息 ID：`platform_message_id`
- 发送者：`from_id`、`from_name`
- 群聊：`in_chat_id`
- 内容：`content`
- 回复关系：`is_reply`、`reply_to_name`、`reply_to_id`
- 时间戳：`created_at`、`updated_at`
- 向量列：`content_vector_1536`、`content_vector_1024`、`content_vector_768`

这张表更像“历史聊天记忆库”，而不是已经抽象成事实、偏好、关系的长期记忆库。每条 Telegram 消息会作为一个可召回片段保存。

### 消息写入流程

入口在 `recordMessage(botInfo, message)`。

写入步骤：

1. 根据 Telegram 消息类型构造待 embedding 的文本。
2. 如果是贴纸，会查 `findStickerDescription(file_id)`，生成类似“某用户发送了某贴纸，贴纸描述是...”的文本。
3. 如果是图片，会查每张图片的 `findPhotoDescription(file_id)`，把描述拼成文本。
4. 如果是普通文本，使用 `message.text || message.caption || ''`。
5. 空文本直接跳过。
6. 调用 `@xsai/embed` 的 `embed()`，使用环境变量中的 embedding API。
7. 按 `EMBEDDING_DIMENSION` 写入对应向量列。
8. 插入 `chat_messages`。

这说明当前系统不是先做“记忆抽取”，而是先完整保存可 embedding 的消息，再在读取时做相关历史召回。

### 历史消息召回

核心函数是 `findRelevantMessages(botId, chatId, unreadHistoryMessagesEmbedding, excludeMessageIds)`。

召回逻辑：

1. 对每条未读消息 embedding 分别查询历史消息。
2. 根据 `EMBEDDING_DIMENSION` 选择对应向量列。
3. 使用 `cosineDistance` 计算相似度：

```sql
similarity = 1 - cosineDistance(vector_column, query_embedding)
```

4. 计算时间相关性：

```sql
time_relevance = 1 - (now_ms - created_at) / 86400 / 30
```

5. 组合分数：

```sql
combined_score = 1.2 * similarity + 0.2 * time_relevance
```

6. 过滤条件包括：

- `platform = 'telegram'`
- `in_chat_id = chatId`
- `similarity > 0.5`
- 排除当前未读消息和最近 30 条已知消息

7. 按 `combined_score` 倒序取前 3 条。
8. 对每条命中的历史消息，再取前后各 5 条上下文消息。
9. 如果上下文消息中存在回复关系，再额外查询被回复的消息。
10. 最后全部转成 one-line 文本，交给 Prompt。

这个实现已经包含了 DevLog 里提到的“语义相关性 + 时间相关性”的雏形，但还没有接入：

- 遗忘曲线半衰期
- access count 强化
- 情绪分数 rerank
- 随机回想
- 短期/长期/肌肉记忆不同权重

### Prompt 注入流程

实际在 `readMessage(...)` 中发生：

1. 查询最近 30 条消息：`findLastNMessages(action.chatId, 30)`。
2. 对未读消息做 embedding。
3. 查询相关历史消息：`findRelevantMessages(...)`。
4. 把三类上下文传入 `actionReadMessages` Prompt：

- `lastMessages`：最近 30 条消息。
- `unreadHistoryMessages`：本次要求读取的未读消息。
- `relevantChatMessages`：向量召回出的相关历史消息及其上下文。

Prompt 文件 `action-read-messages.velin.md` 中明确有一段：

```md
Relevant chat messages may help you recall the memories:
{{ props.relevantChatMessages || 'No relevant messages' }}
```

所以 Telegram bot 的“回忆”不是一个独立 Agent 或工具调用，而是“检索历史消息后拼进 LLM 输入上下文”。

### 工作记忆

Telegram bot 还有一层非持久的工作记忆，定义在 `ChatContext`：

```ts
interface ChatContextMemoryShape {
  messages: LLMMessage[]
  actions: { action: Action, result: unknown }[]
}
```

它的生命周期在内存里，按 chatId 存在 `BotContext.chats` 里。

`services/telegram-bot/src/bots/telegram/index.ts` 中有几个重要行为：

- 每个 chat 维护独立 `messages` 和 `actions`。
- `messages.length > 20` 时，只保留最后 5 条，并向上下文里追加“系统上下文快满，正在减少 memory”的提示。
- `actions.length > 50` 时，只保留最后 20 条。
- `break` action 会清空 `chatCtx.messages` 和 `chatCtx.actions`。
- `sleep` 描述为清空 working memory，但当前代码路径主要是休眠后继续循环，实际清空行为不如 `break` 明确。

这层工作记忆与数据库里的 `chat_messages` 不同：

- 工作记忆：短生命周期，直接影响下一次 action 生成。
- 数据库消息记忆：持久化，供相关历史召回。

### 结构化记忆表

`schema.ts` 中已经定义了一组更像“记忆系统”的表，但当前没有找到业务代码对这些表进行插入、查询或 Prompt 注入。

#### `memory_fragments`

基础记忆片段表：

- `content`
- `memory_type`：注释说明包括 `working`、`short_term`、`long_term`、`muscle`
- `category`：如 `chat`、`relationships`、`people`、`life`
- `importance`：1-10
- `emotional_impact`：-10 到 10
- `created_at`
- `last_accessed`
- `access_count`
- `metadata`
- 三种 embedding 维度列
- `deleted_at` 软删除字段

它已经为“重要性、情绪影响、访问次数、最近访问时间、软删除、向量召回”留好了字段。

#### `memory_tags`

记忆标签表：

- `memory_id`
- `tag`
- `deleted_at`

用于给 `memory_fragments` 做多标签归类。

#### `memory_episodic`

情景/事件记忆表：

- `memory_id`
- `event_type`
- `participants`
- `location`
- `deleted_at`

这表示系统设计上准备区分“普通记忆片段”和“事件型记忆”。

#### `memory_long_term_goals`

长期目标表：

- `title`
- `description`
- `priority`
- `progress`
- `deadline`
- `status`
- `parent_goal_id`
- `category`
- 时间戳和软删除字段

Prompt 里的 `come_up_goals` action 也提到“生成长期目标并记录到长期记忆”，但当前 action union 和 dispatch 里没有落地对应 action。

#### `memory_short_term_ideas`

短期想法表：

- `content`
- `source_type`
- `source_id`
- `status`
- `excitement`
- 三种 embedding 维度列
- 时间戳和软删除字段

Prompt 里的 `come_up_ideas` action 与这张表概念匹配，但当前也没有实际 dispatch 分支。

### Telegram 记忆系统现状判断

Telegram bot 中已真正运行的是“聊天消息 RAG 记忆”：

```txt
Telegram message
  -> recordMessage()
    -> normalize text / sticker / photo description
    -> embed()
    -> insert chat_messages

read_unread_messages action
  -> findLastNMessages(30)
  -> embed unread messages
  -> findRelevantMessages()
    -> vector similarity
    -> time relevance
    -> top 3
    -> surrounding context window
  -> actionReadMessages prompt
  -> LLM decides response/action
```

结构化长期记忆表已经准备好，但缺少：

- 写入函数，例如 `recordMemoryFragment`、`recordGoal`、`recordIdea`。
- 召回函数，例如 `findRelevantMemoryFragments`。
- 访问后更新 `last_accessed` / `access_count`。
- 将结构化记忆注入 Prompt。
- 从聊天消息中抽取事实/偏好/关系/目标的后台任务。
- 与 Stage 设置页的管理 UI。

## computer-use-mcp 的任务记忆

`services/computer-use-mcp/src/task-memory` 是一套完整但不同语义的记忆系统。文件顶部注释已经明确说明：它不是长期记忆，只跟踪“正在做什么、已确认什么、阻塞什么、下一步是什么”。

### 数据结构

`TaskMemory` 包含：

- `status`: `active` / `blocked` / `done`
- `goal`
- `currentStep`
- `confirmedFacts`
- `artifacts`
- `blockers`
- `nextStep`
- `updatedAt`
- `sourceTurnId`
- 可选的 `plan`
- 可选的 `workingAssumptions`
- 可选的 `recentFailureReason`
- 可选的 `completionCriteria`

列表字段有硬编码上限：

- confirmed facts: 10
- artifacts: 8
- blockers: 5
- plan: 6
- assumptions: 6
- completion criteria: 6

### 合并策略

`mergeTaskMemory` 的规则：

- 标量字段：新的非空值覆盖旧值。
- 列表字段：旧值 + 新值合并，去重，保留尾部，裁剪到上限。
- `newTask = true`：软重置后应用新 extraction。
- `status = done`：清空 blockers、nextStep、recentFailureReason。
- 空 extraction 不会创建可见记忆。

### 并发和陈旧写入

`TaskMemoryManager` 用 `sourceTurnIndex` 和 `sourceTurnId` 防止乱序写入：

- 如果更新的 `sourceTurnIndex` 小于已见最新 index，则忽略。
- 如果 index 相同但 turn id 冲突，也忽略。
- 即使较新的 turn 是空更新，也会推进 latest seen index，防止老 turn 之后覆盖当前状态。

这套设计适合工具调用/浏览器自动化任务，因为它解决的是“多次工具结果异步返回时，旧状态不能覆盖新状态”的问题。

### MCP 工具暴露

`register-task-memory.ts` 注册三个工具：

- `task_memory_update`
- `task_memory_get`
- `task_memory_clear`

`task_memory_update` 使用 zod schema 接收结构化参数，成功更新后同步到 `runtime.stateManager.updateTaskMemory(merged)`。

这套系统没有 embedding、向量库或长期存储；它是会话内状态管理。

## Stage UI 的记忆入口

Stage 页面和模块入口已经存在，但没有真实功能：

- `packages/stage-pages/src/pages/settings/memory/index.vue`
- `packages/stage-pages/src/pages/settings/modules/memory-short-term.vue`
- `packages/stage-pages/src/pages/settings/modules/memory-long-term.vue`

这三个页面都只渲染：

```vue
<WIP />
```

`packages/stage-ui/src/composables/use-modules-list.ts` 中注册了两个模块：

- `memory-short-term`
- `memory-long-term`

但它们的 `configured` 均为 `false`，没有对应 store，也没有 provider 配置和数据管理能力。

文档 `docs/content/zh-Hans/docs/manual/tamagotchi/setup-and-use/index.md` 也写明：

- “记忆体”功能暂未发布。
- “短期记忆”功能暂未发布。
- “长期记忆”功能暂未发布。

因此 Stage 产品侧的记忆功能目前是占位入口。

## packages/memory-pgvector

`packages/memory-pgvector/src/index.ts` 当前只有：

- 创建 `Client<{ connectionString: string }>`。
- 模块名是 `memory-pgvector`。
- 监听 `module:configure`，但回调为空。
- 等待进程信号并在 SIGINT/SIGTERM 时关闭 client。

它没有：

- 初始化 PostgreSQL 连接。
- 定义或导出 schema。
- 写入记忆。
- 查询记忆。
- embedding。
- 召回 API。
- 与 `services/telegram-bot` 的 schema 复用。

所以 README 图里的 `@proj-airi/memory-pgvector --> Memory` 目前更像架构目标，而不是已实现模块。

## DevLog 中的目标设计与当前代码差距

DevLog 描述了更完整的目标：

- 工作记忆：类似 messages array。
- 短期记忆：RAG 条目，新记忆更容易被召回，会逐渐衰减。
- 长期记忆：更稳定，半衰期更长，访问次数影响召回。
- 肌肉记忆：固定触发模式，类似精确匹配。
- 使用 stateless SQL 根据当前时间计算衰减分数。
- 召回后强化访问次数。
- 情绪分数影响召回和强化。
- 可能存在随机突然想起、PTSD/flashback 之类机制。
- 后台任务/潜意识任务负责重建索引和更新记忆分数。

当前主代码只落地了其中一小部分：

- `chat_messages` 实现了“历史消息作为 RAG 条目”。
- `findRelevantMessages` 实现了“语义相似度 + 时间相关性”的粗排序。
- `memory_fragments` 表预留了 `importance`、`emotional_impact`、`last_accessed`、`access_count`。

未落地部分：

- 记忆片段抽取。
- 短期到长期的转化。
- 肌肉记忆触发机制。
- 召回后强化。
- 遗忘曲线分数。
- 多情绪维度。
- 后台整理/梦境/潜意识任务。
- 用户可视化管理 UI。

## 主要风险和问题

### 1. 结构化记忆表未接入业务路径

`memory_fragments`、`memory_tags`、`memory_episodic`、`memory_long_term_goals`、`memory_short_term_ideas` 已经迁移落库，但没有模型层函数和调用链。这会造成“数据库看起来支持记忆，但产品实际只用聊天消息召回”的割裂。

### 2. `memory_type` 等枚举没有数据库约束

`memory_type`、`category`、`status`、`source_type` 等字段都是 `text()`，只靠注释说明取值。后续多模块写入时容易产生拼写分叉。

### 3. 软删除字段没有统一过滤

记忆表设计了 `deleted_at`，但缺少查询封装层。若后续直接查询表，很容易忘记过滤软删除记录。

### 4. 当前时间相关性公式单位疑似不严谨

当前代码：

```sql
1 - (now_ms - created_at) / 86400 / 30
```

`created_at` 是毫秒时间戳，`now_ms - created_at` 也是毫秒。若想表示 30 天衰减，应除以 `1000 * 86400 * 30`。当前公式相当于把毫秒差除以秒级天数，会让时间相关性下降非常快，并且可能变成很大的负数。

### 5. 召回按每条未读消息分别查，结果可能重复

`findRelevantMessages` 对每个 unread embedding 独立取 top 3 和上下文，最后拼接。多个未读消息语义相近时，可能重复召回同一段历史上下文。

### 6. 没有召回后更新 access count

`memory_fragments` 设计了 `access_count` 和 `last_accessed`，DevLog 也提到“simulate retrieval” 会加 retrieval count，但当前实际用的 `chat_messages` 召回没有类似强化更新。

### 7. Prompt 注入是纯文本拼接

召回结果最终被转换成 one-line 文本注入 Prompt。这简单有效，但缺少结构化边界，例如 `<memory>` block、score、source id、时间、召回原因等。模型可能难以区分“最近消息、未读消息、召回记忆”的可靠性和用途。

### 8. `recordMessage` 中 `text` 变量存在潜在未初始化风险

`recordMessage` 里 `let text: string`，但只有 sticker/photo/text 分支会赋值；随后判断 `if (text === '')`。在 TypeScript 严格设置下这类写法可能触发变量使用前未赋值问题，运行时也可能在非文本/非图片/非贴纸消息上出现 `undefined` 路径。

### 9. `come_up_ideas` / `come_up_goals` Prompt 动作未接入 dispatch

Prompt 中列出了这两个 action，但 `Action` union 和 `dispatchAction` 没有对应类型和处理分支。模型如果返回这些 action，会走“haven't implemented yet”。

## 建议的后续实现路线

### 第一阶段：统一“已存在的聊天消息记忆”

目标是把当前可运行的 RAG 消息记忆做稳。

建议：

- 修正时间相关性单位。
- 对召回结果按 message id 去重。
- 给召回结果保留 score、source message id 和时间。
- 将 Prompt 注入格式改为明确块结构。
- 添加 `findRelevantMessages` 的单元测试，覆盖维度选择、去重、时间分数和 exclude ids。

### 第二阶段：接入结构化记忆表

目标是让 `memory_fragments` 真正可写可读。

建议新增模型层：

- `recordMemoryFragment`
- `findRelevantMemoryFragments`
- `touchMemoryFragment`
- `softDeleteMemoryFragment`
- `recordMemoryTags`
- `recordEpisodicMemory`

查询默认必须过滤 `deleted_at is null`。

可以先只实现 `memory_type = short_term | long_term`，暂缓 muscle memory。

### 第三阶段：从聊天消息抽取记忆

目标是将“原始聊天历史”转化为“可复用事实/偏好/关系”。

可选策略：

- 在读取消息后异步分析未读消息，抽取候选记忆。
- 只在高置信度时写入 `memory_fragments`。
- 将原始 message ids 放入 `metadata`，保留溯源能力。
- 对用户偏好、人物关系、长期目标分别设置 category。

### 第四阶段：实现短期/长期差异

目标是让表字段承载真正的记忆生命周期。

建议：

- 短期记忆使用更短半衰期。
- 长期记忆使用更高基础分和更慢衰减。
- 每次召回后更新 `last_accessed` 和 `access_count`。
- 根据 `importance`、`emotional_impact`、`access_count`、时间衰减组合 rerank。

### 第五阶段：接入 Stage 设置 UI

目标是让用户能看到和管理记忆。

建议：

- Stage 设置页不直接读 Telegram bot 表，而是走统一 memory service API。
- 短期记忆页显示最近抽取和即将过期的记忆。
- 长期记忆页显示高重要性、人物、关系、目标。
- 支持删除、编辑、导出、重新 embedding。

### 第六阶段：抽离 `packages/memory-pgvector`

目标是让 memory-pgvector 从壳变成真正共享模块。

建议：

- 将 schema 或 repository 层从 `services/telegram-bot` 抽出。
- 提供 provider-compliant JSON schema 的 server-sdk API。
- 暴露 write/search/touch/delete/export 等操作。
- 让 Telegram bot、Stage、未来 Discord/Minecraft 都调用同一个记忆服务。

## 当前实现关系图

```txt
Telegram Bot
  Message arrival
    -> recordMessage()
      -> normalize text/sticker/photo
      -> @xsai/embed
      -> chat_messages + vector column

  Agent action loop
    -> imagineAnAction()
      -> ChatContext.messages/actions as working memory
      -> choose read_unread_messages

  read_unread_messages
    -> findLastNMessages()
    -> embed unread messages
    -> findRelevantMessages()
      -> cosine similarity
      -> time relevance
      -> combined score
      -> context window
    -> actionReadMessages prompt
    -> LLM response/action

Structured memory tables
  memory_fragments
  memory_tags
  memory_episodic
  memory_long_term_goals
  memory_short_term_ideas
    -> currently no business read/write path found

Stage UI
  memory pages
    -> WIP

packages/memory-pgvector
  server-sdk client shell
    -> no implemented memory API yet
```

## 总结

当前 AIRI 仓库中的记忆系统处于“底层设施和原型路径已经出现，但完整产品功能尚未闭环”的阶段。

真正工作的部分是 Telegram bot 的聊天历史向量召回：它会保存消息 embedding，在读取未读消息时召回语义相关的历史上下文，再注入 Prompt 让模型“回忆”。这已经是一个 RAG 型聊天记忆原型。

结构化记忆方向已经在数据库中设计了比较完整的字段，包括记忆类型、重要性、情绪影响、访问次数、标签、事件、长期目标、短期想法等，但缺少实际写入、检索、强化、衰减和 UI 管理。`packages/memory-pgvector` 和 Stage 设置页目前都是架构占位。

如果要继续推进，最务实的路径是先修稳 Telegram bot 的消息召回，再把 `memory_fragments` 接入为统一抽象，最后将其抽离到 `packages/memory-pgvector` 并接上 Stage UI。
