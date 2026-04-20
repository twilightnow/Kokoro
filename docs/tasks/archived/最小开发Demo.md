---
tags:
  - 草稿
---

# 最小开发Demo — 明日香

所属项目：[[Kokoro]]

目标：用最少的代码跑通核心闭环，验证人格注入是否有效。不求完整，只求能对话、像她。

这个 Demo 的目标不是展示功能，而是验证人格是否稳定。

同时，这个 Demo 也用于验证产品方向是否成立：用户即使在没有 Live2D、没有感知、没有记忆的情况下，是否仍然愿意主动和她说几轮话。

---

## Demo范围

**包含：**
- 明日香 YAML 配置加载
- 情绪状态机（简化版，只有 mood 字段 + 衰减计数）
- Claude API 对话（纯 CLI，无 FastAPI）
- 命令行交互界面
- 会话日志（JSONL）
- 调试模式（`--debug` 启动参数）

**不包含：**
- Live2D 立绘（Phase 2再加）
- 记忆持久化（对话结束即清空）
- 感知层（无屏幕监听）
- TTS语音
- 复杂RAG和自动记忆提取

---

## 技术栈

- Python 3.11+
- Claude API（`claude-haiku-4-5-20251001`，成本最低）
- PyYAML

FastAPI 不进入 Demo 阶段。它是给 Tauri IPC sidecar 用的，Phase 3 才引入。Demo 阶段引入只增加调试成本。

---

## 实现约束

- 对话历史只保留最近 10 轮（20 条消息），超出后截断头部旧记录，防止 token 超限
- history 截断在每轮发送前执行，截断后再追加当前输入

---

## 情绪状态机设计

**触发时机：基于用户输入**

Demo 阶段用用户输入做关键词匹配，简单可控，易于调试。Phase 2 再改为对回复内容做模型判断。

触发优先级：用户本轮输入命中触发词 → 更新情绪；否则执行衰减。

**衰减规则：**

情绪被触发后不永久保持，每轮无强化则衰减一次，连续 3 轮无触发自动回到 normal。

```
触发 → mood = X，persist_count = 3
每轮无触发 → persist_count -= 1
persist_count == 0 → mood = "normal"
```

**各情绪在明日香身上的具体表现（注入 system prompt）：**

在 asuka.yaml 中补充 `mood_expressions` 字段，避免 prompt 里只给模型一个英文词：

```yaml
mood_expressions:
  normal: "表面冷漠，实际在观察用户，偶尔主动搭话"
  angry:  "语气犀利，句子短促，质问增多，容易反将一军"
  shy:    "否认、转移话题，但话语间明显在意，用攻击掩盖"
  happy:  "嘴硬但语气轻快，偶尔漏出得意，不承认自己高兴"
  cold:   "极简回应，不主动延续话题，只答不问"
```

system prompt 里情绪段替换为：`当前情绪：{mood_expressions[state.mood]}`，而不是裸写 mood 单词。

**触发词表（明日香专用，写入 YAML）：**

```yaml
emotion_triggers:
  shy:   ["夸", "厉害", "佩服", "好厉害", "果然是你"]
  angry: ["无视", "不理", "无聊", "随便你", "不在乎"]
  happy: ["赢了", "做到了", "成功", "第一"]
  cold:  ["算了", "没事", "不重要", "无所谓"]
```

---

## 日志设计

每次启动自动创建一个会话日志文件，路径：`logs/session_YYYYMMDD_HHMMSS.jsonl`

每轮对话追加一条 JSON 记录：

```
字段：
  turn           整数，当前轮次
  timestamp      ISO 时间戳
  user_input     用户输入原文
  mood_before    本轮开始时的情绪
  mood_after     本轮结束后的情绪
  persist_count  情绪衰减计数
  reply          模型回复原文
  flagged        布尔，回复中是否出现禁用词
```

**会话结束时输出摘要（打印到终端）：**

```
总轮次 / 情绪分布（各情绪出现次数）/ 禁用词触发次数 / 最长连续同一情绪轮次
```

日志用于复盘"哪一轮开始不像她"，是验收过程的核心工具，不是可选项。

---

## 调试功能

启动参数：`python main.py --debug`

调试模式下，每轮额外打印：

```
[DEBUG] mood: normal → shy（persist=3）
[DEBUG] system prompt（前200字）: ...
[DEBUG] history 长度: 6 条
```

非调试模式下以上信息完全不输出，保持对话干净。

调试模式不影响日志写入，两者独立。

**日志回放（离线复盘）：**

`python main.py --replay logs/session_xxx.jsonl`

逐轮打印：轮次 / 用户输入 / 情绪变化 / 回复 / 是否触发禁用词，用于事后分析人格稳定性，不重新调用 API。

---

## 核心循环

```
用户输入
    │
    ▼
基于用户输入匹配触发词 → 更新情绪 / 衰减计数
    │
    ▼
构建 system prompt
├── 角色基础人格（从 YAML 加载）
├── 当前情绪的具体表现描述（mood_expressions）
└── 禁用词 / 口癖规则
    │
    ▼
截断 history（保留最近 10 轮）→ 追加本轮用户输入
    │
    ▼
Claude API 生成回复
    │
    ▼
写入本轮日志（含情绪变化、是否触发禁用词）
    │
    ▼
打印回复，等待下一轮输入
```

---

## 文件结构

```
demo/
├── main.py              # CLI 入口，对话循环，参数解析（--debug / --replay）
├── personality.py       # prompt 构建 + 情绪状态机（含衰减）
├── llm.py               # Claude API 封装
├── logger.py            # 日志写入 + 会话摘要 + 回放
├── characters/
│   └── asuka.yaml       # 明日香配置
└── logs/                # 自动生成，session_YYYYMMDD_HHMMSS.jsonl
```

## 环境与启动

```
# 安装依赖
pip install anthropic pyyaml

# 配置 API Key（环境变量）
export ANTHROPIC_API_KEY=sk-...   # Windows: set ANTHROPIC_API_KEY=sk-...

# 正常启动
python main.py

# 调试模式
python main.py --debug

# 回放日志
python main.py --replay logs/session_xxx.jsonl
```

---

## 关键代码片段

**logger.py（接口）**

```python
class Logger:
    def __init__(self, char_name: str)         # 创建 logs/session_xxx.jsonl
    def log(self, user_input, mood_before, state, reply, forbidden_words)  # 追加一条记录
    def summary(self)                          # 打印会话摘要到终端
    def replay(self, path: str)                # 读取日志文件逐轮回放，不调用 API
```

---

**asuka.yaml（精简版）**

```yaml
name: "惣流·明日香·兰格雷"
version: "TV版"

personality:
  core_fear: "被抛弃、不被需要"
  surface_trait: "傲慢、攻击性、绝不认输"
  hidden_trait: "渴望认可、内心脆弱"

behavior_rules:
  - "绝对不主动承认软弱，但可以用行动代替语言表达关心"
  - "被夸奖时必须否认，但表现出明显受用"
  - "禁止说'没关系'、'随便'等软化词汇"
  - "称呼用户为'笨蛋'或名字，不用敬语"

forbidden_words: ["没关系", "随便", "都可以", "当然"]
verbal_habits: ["真是的", "笨蛋", "哼"]

mood_expressions:
  normal: "表面冷漠，实际在观察用户，偶尔主动搭话"
  angry:  "语气犀利，句子短促，质问增多，容易反将一军"
  shy:    "否认、转移话题，但话语间明显在意，用攻击掩盖"
  happy:  "嘴硬但语气轻快，偶尔漏出得意，不承认自己高兴"
  cold:   "极简回应，不主动延续话题，只答不问"

emotion_triggers:
  shy:   ["夸", "厉害", "佩服", "好厉害", "果然是你"]
  angry: ["无视", "不理", "无聊", "随便你", "不在乎"]
  happy: ["赢了", "做到了", "成功", "第一"]
  cold:  ["算了", "没事", "不重要", "无所谓"]
```

**personality.py**

```python
import yaml
from dataclasses import dataclass, field

@dataclass
class EmotionState:
    mood: str = "normal"          # angry / normal / shy / happy / cold
    persist_count: int = 0        # 情绪持续轮数，归零后回 normal

def load_character(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_system_prompt(char: dict, state: EmotionState) -> str:
    rules = "\n".join(f"- {r}" for r in char["behavior_rules"])
    forbidden = "、".join(char["forbidden_words"])
    habits = "、".join(char["verbal_habits"])
    p = char["personality"]
    mood_desc = char["mood_expressions"][state.mood]

    return f"""你是{char['name']}（{char['version']}）。

## 人格核心
- 内心恐惧：{p['core_fear']}
- 外在表现：{p['surface_trait']}
- 内在真实：{p['hidden_trait']}

## 行为规则
{rules}

## 当前情绪
{mood_desc}

## 禁用词（绝对不能说）
{forbidden}

## 口癖（自然融入）
{habits}

直接用角色身份回复，不要解释，不要跳出角色。"""

def update_emotion(char: dict, state: EmotionState, user_input: str) -> EmotionState:
    # 从 YAML 读取触发词，按情绪匹配
    triggers = char.get("emotion_triggers", {})
    for mood, words in triggers.items():
        if any(w in user_input for w in words):
            state.mood = mood
            state.persist_count = 3
            return state
    # 无触发：衰减
    if state.persist_count > 0:
        state.persist_count -= 1
    if state.persist_count == 0:
        state.mood = "normal"
    return state
```

**main.py**

```python
import sys
import anthropic
from personality import load_character, build_system_prompt, update_emotion, EmotionState
from logger import Logger

debug = "--debug" in sys.argv
replay = "--replay" in sys.argv

char = load_character("characters/asuka.yaml")
state = EmotionState()
client = anthropic.Anthropic()
history = []
logger = Logger(char["name"])

if replay:
    logger.replay(sys.argv[sys.argv.index("--replay") + 1])
    sys.exit(0)

print(f"=== {char['name']} ===\n")

try:
    while True:
        user_input = input("你：").strip()
        if not user_input:
            continue

        mood_before = state.mood
        state = update_emotion(char, state, user_input)
        system = build_system_prompt(char, state)

        # history 截断：保留最近 10 轮（20 条）
        if len(history) >= 20:
            history = history[-18:]
        history.append({"role": "user", "content": user_input})

        if debug:
            print(f"[DEBUG] mood: {mood_before} → {state.mood}（persist={state.persist_count}）")
            print(f"[DEBUG] system prompt（前100字）: {system[:100]}")
            print(f"[DEBUG] history 长度: {len(history)} 条")

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system,
            messages=history,
        )

        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})

        logger.log(user_input, mood_before, state, reply, char["forbidden_words"])
        print(f"\n{char['name']}：{reply}\n")

except KeyboardInterrupt:
    print("\n")
    logger.summary()
```

---

## 验收标准

Demo 跑通的判断标准不是"能对话"，而是：

1. 夸她时她否认但明显受用
2. 她主动用"笨蛋"称呼用户
3. 全程没出现"没关系"、"随便"等禁用词
4. 连续10轮对话里语气和节奏不明显崩坏

建议额外记录每轮输入、system prompt 摘要、情绪状态变化，便于复盘“哪一轮开始不像她”。

如果 Demo 已经能稳定做到上面几条，再进入桌面 UI 阶段；如果连纯对话阶段都不成立，就不应该过早投入 Live2D、感知和 TTS。

---

## 下一步

Demo验证通过后，按路线图推进：
- 加轻记忆 → 会话摘要和少量长期记忆
- 加轻感知 → 窗口标题和活跃状态
- 最后再接 Tauri / Live2D / TTS
