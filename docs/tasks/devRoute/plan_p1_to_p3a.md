---
tags:
  - Kokoro
  - execution-plan
status: active
created: 2026-04-21
executor: copilot
---

# 执行计划：P1 轻记忆 → P2 轻感知 → P3A 后端 sidecar

> 本文档供 Copilot 自主执行。按章节顺序推进，每个 Task 完成后运行对应测试再进入下一个。
> 不允许跨阶段合并提交，每个 Task 独立可回滚。

---

## 0. 前置约束（所有阶段通用）

### 0.1 代码哲学

- **单一职责**：每个类/函数只做一件事。`MemoryService` 不生成 prompt，`PerceptionCollector` 不决定触发，`ConversationService` 不做 IO 以外的判断。
- **依赖方向**：`application → personality / memory / perception / capability`，下层绝不 import 上层。
- **接口稳定优先**：改内部实现无需通知上层，改公开方法签名必须同步修改所有调用方。
- **失败静默原则**：记忆写入失败、感知采集失败、摘要生成失败，均不能崩溃主对话链路。用 `try/except` 兜住，最多打印 `[警告]`，继续运行。
- **不过度设计**：不为"将来可能需要"而抽象。当前阶段只有一个 provider、一个 character active，不做多实例池。

### 0.2 边界规则

| 层 | 可以做 | 不能做 |
|----|--------|--------|
| `memory/` | 读写文件、估算 token、裁剪记忆 | import personality、import perception、调用 LLM（MemoryService 接受 llm_chat_fn 注入）|
| `perception/` | 采集 OS 信息、计算触发条件、管理冷却 | import memory、import personality、直接修改情绪状态 |
| `personality/` | 构建 prompt、情绪状态机 | 读写文件、调用 LLM、感知 OS |
| `capability/` | 封装 LLM / TTS 调用 | 业务逻辑 |
| `application/` | 编排所有层 | 直接操作文件、直接拼 prompt |
| `api/` | HTTP / WebSocket 路由、序列化 | 业务逻辑（全部委托给 ConversationService）|

### 0.3 执行前必读文件

在执行任何 Task 前，先完整阅读：

```
src/memory/memory_service.py
src/memory/summary_memory.py
src/memory/long_term_memory.py
src/memory/working_memory.py
src/memory/context.py
src/personality/prompt_builder.py  （estimate_tokens 已在此定义）
src/application/conversation_service.py
src/perception/context.py
```

### 0.4 测试运行方式

```bash
python -m unittest discover -s tests -v
```

全部 PASS 才能进入下一个 Task。

---

## P1 — 轻记忆

### 概述

当前状态：`MemoryService` 门面已存在，`SummaryMemory` / `LongTermMemory` 已实现文件 IO，但：
- `get_context()` 无 token budget 裁剪，可能撑爆 context window
- `on_session_end()` 只生成摘要，未提取长期事实
- 被裁剪的记忆无记录，无法复盘
- `ConversationService` 调用 `get_context()` 时未传 token budget

目标：记忆注入受控（不超 budget）、会话结束后自动提取事实、已使用记忆可追溯。

---

### Task 1.1 — `get_context()` 加入 token budget

**文件**：`src/memory/memory_service.py`

**修改**：`get_context()` 签名变更如下：

```python
def get_context(
    self,
    character_id: str,
    token_budget: int = 500,
) -> MemoryContext:
```

**token 分配策略**（在方法内实现）：

```
长期事实预算  = min(token_budget // 2, 200)   # 长期事实优先，最多占一半
摘要预算      = token_budget - 已用长期事实 token 数
```

**长期事实裁剪逻辑**：
1. 调用 `self._long_term_memory.read_facts(character_id)` 取全部 `FactRecord`（含 pending）
2. 过滤 `pending_confirm=False`，按 `updated_at` **降序**排列（最新事实优先保留）
3. 逐条追加到 `selected_facts`，直到估算 token 超出长期事实预算
4. 被丢弃的 key 写入截断日志（见 Task 1.3）
5. 最终返回 `{k: v.value for k, v in selected_facts.items()}`

**摘要裁剪逻辑**：
1. 调用 `self._summary_memory.load_recent_summaries(character_id, n=5)`
2. 从最新摘要向前取，逐条追加，直到估算 token 超出摘要预算
3. 被丢弃的条目写入截断日志

**token 估算**：使用 `src/personality/prompt_builder.py` 中已有的 `estimate_tokens(text)` 函数。
- 不要在 memory 层 import personality 层。
- 将 `estimate_tokens` 逻辑复制为 `memory/_token.py` 中的私有函数 `_estimate_tokens(text: str) -> int`，保持实现一致（`max(1, int(len(text) / 1.5))`）。
- 两处独立存在是合理的：memory 层不应依赖 personality 层。

**新建文件** `src/memory/_token.py`：

```python
"""记忆层内部用 token 估算工具，不对外暴露。"""

def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1.5 字/token）。"""
    return max(1, int(len(text) / 1.5))
```

**返回值**：`MemoryContext`，与现有契约兼容，无需改动 `MemoryContext` dataclass。

**测试要求**（在 Task 1.5 中写）：
- budget 充足时返回全部事实和摘要
- budget 不足时只返回能装下的部分
- budget=0 时返回空 MemoryContext（不崩溃）

---

### Task 1.2 — 长期事实自动提取

**文件**：`src/memory/memory_service.py`，修改 `on_session_end()`

**新增内部方法**：

```python
def _extract_facts(
    self,
    character_id: str,
    history: List[Dict[str, str]],
    llm_chat_fn: Callable,
) -> None:
    """调用 LLM 从对话历史提取用户显式陈述的事实，写入 LongTermMemory。

    失败时静默，不抛出异常，不影响主链路。
    """
```

**事实提取 system prompt**（作为模块级常量 `_FACT_EXTRACT_PROMPT`）：

```
你是信息提取助手。从以下对话中提取用户（User）明确陈述的个人信息，
例如名字、职业、爱好、习惯等。只提取用户主动说出的内容，不要推断。

输出格式为 JSON 对象，key 为信息类别（英文小写下划线），value 为用户原话中的值。
例如：{"user_name": "小明", "user_job": "程序员"}

如果没有可提取的信息，输出空对象 {}。只输出 JSON，不要其他内容。
```

**解析逻辑**：
1. 调用 `llm_chat_fn(_FACT_EXTRACT_PROMPT, history)`，取 `.text`
2. 用 `json.loads()` 解析，外层 `try/except json.JSONDecodeError` 静默失败
3. 过滤非字符串 value（类型守卫）
4. 对每个 key/value 调用 `self._long_term_memory.write_fact(character_id, key, value, source="llm_extract")`

**`on_session_end()` 修改**：在现有摘要生成之后，串行调用 `_extract_facts()`。两步独立 try/except，互不影响。

**约束**：
- 仅对历史轮数 ≥ 2 的会话提取（轮数过少提取无意义）
- 不修改 `on_session_end()` 签名（保持与 `ConversationService` 调用兼容）

---

### Task 1.3 — 截断日志

**新建文件** `src/memory/truncation_log.py`：

```python
class TruncationLog:
    """记录因 token budget 超限被丢弃的记忆条目，用于后期分析和优化。"""

    def __init__(self, data_dir: Path) -> None: ...

    def record(
        self,
        character_id: str,
        kind: str,           # "fact" | "summary"
        dropped_keys: list,  # 被丢弃的 key 或摘要前几字
        budget: int,
        used: int,
    ) -> None:
        """追加一条截断记录到 memories/<character_id>/truncation.log（纯文本，按行）。"""
```

**格式**（纯文本，每次截断一行）：

```
2026-04-21T22:00:00 | kind=fact | budget=200 | used=210 | dropped=["user_age"]
```

**集成**：在 `MemoryService.get_context()` 中，当有条目被丢弃时调用 `TruncationLog.record()`。

**`MemoryService.__init__()` 中初始化**：

```python
self._truncation_log = TruncationLog(data_dir)
```

---

### Task 1.4 — 接入 ConversationService

**文件**：`src/application/conversation_service.py`

**修改**：`handle_turn()` 中已有 `memory_ctx = self._memory.get_context(character_id)` 这一行，改为：

```python
memory_ctx = self._memory.get_context(character_id, token_budget=500)
```

**常量化**：在 `ConversationService` 顶部或类属性中定义：

```python
_MEMORY_TOKEN_BUDGET: int = 500
```

后续可通过环境变量 `MEMORY_TOKEN_BUDGET` 覆盖（在 `__init__` 中读取 `int(os.environ.get("MEMORY_TOKEN_BUDGET", 500))`）。

**不需要修改其他调用**，`on_session_end()` 签名未变。

---

### Task 1.5 — P1 测试

**新建文件** `tests/test_memory.py`

覆盖以下场景：

```python
class TestTokenEstimate(unittest.TestCase):
    # _estimate_tokens 基础行为

class TestGetContextWithBudget(unittest.TestCase):
    # budget 充足：返回全部事实 + 摘要
    # budget 不足事实：只取能装下的事实，摘要取剩余预算
    # budget=0：返回空 MemoryContext，不崩溃
    # 无数据时返回空 MemoryContext

class TestFactExtraction(unittest.TestCase):
    # LLM 返回合法 JSON：正确写入 facts
    # LLM 返回空 {}：facts 无变化
    # LLM 返回非法 JSON：静默失败，不抛异常
    # LLM 抛异常：静默失败，不影响摘要生成
    # history 轮数 < 2：跳过提取

class TestTruncationLog(unittest.TestCase):
    # record() 写入文件，格式正确
    # 多次调用追加，不覆盖
```

使用 `tempfile.TemporaryDirectory` 隔离文件 IO，用 `unittest.mock.Mock` 模拟 `llm_chat_fn`。

**验收**：`python -m unittest discover -s tests -v` 全部 PASS。

---

## P2 — 轻感知

### 概述

目标：Level 0 感知（窗口标题 + 活跃/空闲 + 时间段） + 4 类主动介入触发器 + 冷却机制。

感知层在 CLI 模式下采用**轮间轮询**策略：每次对话循环开始时检查感知状态，不引入后台线程（后台线程留给 P3A sidecar 模式）。

---

### Task 2.0 — 安装依赖

```bash
pip install pygetwindow pynput
```

同时更新 `requirements.txt`，追加：

```
pygetwindow>=0.0.9
pynput>=1.7.6
```

**注意**：`pygetwindow` 仅支持 Windows/macOS，`pynput` 在 Linux 需要额外权限。在代码中用 `try/except ImportError` 做可选导入守卫，导入失败时感知层降级（返回空 `PerceptionContext`），不崩溃。

---

### Task 2.1 — `InputTracker`

**新建文件** `src/perception/input_tracker.py`

```python
"""
键鼠活跃状态追踪。使用 pynput 监听事件，记录最后活跃时间。
监听器在后台线程运行，但只更新时间戳，不做任何业务判断。
"""
import threading
import time
from typing import Optional


class InputTracker:
    """追踪用户最后一次键鼠操作的时间戳。

    职责边界：
      - 只记录时间，不判断"是否空闲"（空闲判断由触发器负责）
      - 不 import 任何业务层模块
    """

    def __init__(self) -> None:
        self._last_activity: float = time.monotonic()
        self._lock = threading.Lock()
        self._listener: Optional[object] = None

    def start(self) -> None:
        """启动 pynput 后台监听。导入失败时静默降级。"""

    def stop(self) -> None:
        """停止监听器。"""

    def idle_seconds(self) -> float:
        """返回距离最后一次活动的秒数。"""
        with self._lock:
            return time.monotonic() - self._last_activity

    def mark_active(self) -> None:
        """手动标记活跃（用于测试或无 pynput 时的降级）。"""
        with self._lock:
            self._last_activity = time.monotonic()
```

**实现细节**：
- `start()` 内部 `try: from pynput import keyboard, mouse`，`ImportError` 时 `return`（降级）
- 创建 `keyboard.Listener` 和 `mouse.Listener`，回调均调用 `self.mark_active()`
- `daemon=True`，主进程退出时自动销毁
- `stop()` 调用 `listener.stop()` 并捕获所有异常

---

### Task 2.2 — `WindowMonitor`

**新建文件** `src/perception/window_monitor.py`

```python
"""
活动窗口标题监控。使用 pygetwindow 获取当前前台窗口标题。
"""
import time
from collections import deque
from typing import Deque, Optional, Tuple


class WindowMonitor:
    """监控活动窗口标题，统计切换频率。

    职责边界：
      - 只采集窗口标题和切换事件，不判断场景含义
      - 场景判断（游戏/代码/浏览器）由触发器负责
    """

    # 游戏窗口标题关键词（粗判，不依赖截图）
    GAME_KEYWORDS: tuple = (
        "Steam", "Origin", "Epic", "Battle.net",
        "League of Legends", "Genshin", "原神",
        "英雄联盟", "Minecraft", "Overwatch", "守望先锋",
    )

    def __init__(self, history_window_seconds: int = 60) -> None:
        self._history_window = history_window_seconds
        # (timestamp, window_title) 的时间窗口队列
        self._switch_history: Deque[Tuple[float, str]] = deque()
        self._last_title: str = ""

    def current_title(self) -> str:
        """获取当前活动窗口标题。失败时返回空字符串。"""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""

    def record_switch(self) -> None:
        """记录一次窗口切换（在 collect() 内部调用）。"""

    def switches_per_minute(self) -> float:
        """返回最近 history_window_seconds 内的窗口切换次数/分钟。"""

    def collect(self) -> str:
        """采集当前窗口标题，内部更新切换历史，返回标题字符串。"""

    def is_gaming(self, title: str) -> bool:
        """粗判是否在玩游戏（基于窗口标题关键词）。"""
        return any(kw.lower() in title.lower() for kw in self.GAME_KEYWORDS)
```

**实现细节**：
- `collect()` 调用 `current_title()`，与 `_last_title` 对比，变化则调用 `record_switch()` 并更新 `_last_title`
- `record_switch()` 向 `_switch_history` 追加 `(time.monotonic(), title)`
- `switches_per_minute()` 过滤 `_switch_history` 中超出时间窗口的旧记录，再计算频率

---

### Task 2.3 — `PerceptionCollector`

**修改文件** `src/perception/collector.py`（此文件可能不存在，新建）

```python
"""
感知数据采集器：整合 InputTracker 和 WindowMonitor，生成 PerceptionContext。

职责边界：
  - 负责采集，不判断触发条件
  - 输出 PerceptionContext，人格层以此构建 prompt
"""
from datetime import datetime
from .context import PerceptionContext
from .input_tracker import InputTracker
from .window_monitor import WindowMonitor


class PerceptionCollector:
    def __init__(
        self,
        input_tracker: InputTracker,
        window_monitor: WindowMonitor,
    ) -> None:
        self._input = input_tracker
        self._window = window_monitor

    def collect(self) -> PerceptionContext:
        """采集当前一次感知快照，返回 PerceptionContext。"""
        now = datetime.now()
        title = self._window.collect()
        idle_sec = self._input.idle_seconds()
        switches_pm = self._window.switches_per_minute()

        return PerceptionContext(
            timestamp=now,
            active_window_title=title,
            is_user_active=idle_sec < 300,  # 5 分钟无操作视为不活跃
            hour=now.hour,
            idle_seconds=idle_sec,          # 新增字段，见下方
            switches_per_minute=switches_pm, # 新增字段，见下方
            is_gaming=self._window.is_gaming(title),  # 新增字段，见下方
        )
```

**同步修改** `src/perception/context.py`，在 `PerceptionContext` 中补充字段：

```python
idle_seconds: float = 0.0          # 距最后键鼠操作的秒数
switches_per_minute: float = 0.0   # 最近1分钟窗口切换频率
is_gaming: bool = False            # 是否在游戏（基于窗口标题粗判）
```

同步修改 `src/personality/prompt_builder.py` 中感知上下文注入段，补充新字段的展示：

```python
if ctx.perception:
    parts.append("")
    parts.append("【当前场景】")
    p = ctx.perception
    parts.append(f"时间段：{p.time_of_day}")
    if p.is_late_night:
        parts.append("（深夜）")
    if p.active_window_title:
        parts.append(f"当前窗口：{p.active_window_title[:40]}")  # 截断避免过长
    if p.is_gaming:
        parts.append("（用户正在游戏）")
    if not p.is_user_active:
        parts.append("（用户当前不活跃）")
```

---

### Task 2.4 — `CooldownManager`

**新建文件** `src/perception/cooldown.py`

```python
"""
冷却管理器：防止触发器频繁打扰用户。

全局冷却：任意触发器触发后，所有触发器进入冷却期。
独立冷却：每类触发器有独立冷却，同类不重复触发。
"""
import time
from typing import Dict


class CooldownManager:
    """双层冷却：全局 + 每类触发器独立。

    职责边界：只管理时间，不做任何感知或触发判断。
    """

    GLOBAL_COOLDOWN_SEC: int = 1800   # 30 分钟全局冷却
    PER_TRIGGER_COOLDOWN_SEC: int = 3600  # 同类触发器 1 小时独立冷却

    def __init__(self) -> None:
        self._global_last: float = 0.0
        self._trigger_last: Dict[str, float] = {}

    def can_trigger(self, trigger_name: str) -> bool:
        """检查指定触发器是否已过冷却期。"""
        now = time.monotonic()
        if now - self._global_last < self.GLOBAL_COOLDOWN_SEC:
            return False
        last = self._trigger_last.get(trigger_name, 0.0)
        return now - last >= self.PER_TRIGGER_COOLDOWN_SEC

    def mark_triggered(self, trigger_name: str) -> None:
        """记录触发时间（同时刷新全局冷却和独立冷却）。"""
        now = time.monotonic()
        self._global_last = now
        self._trigger_last[trigger_name] = now

    def reset(self) -> None:
        """清空所有冷却（测试用）。"""
        self._global_last = 0.0
        self._trigger_last.clear()
```

---

### Task 2.5 — 触发器

**新建文件** `src/perception/triggers.py`

```python
"""
主动介入触发器。

设计原则：
  - BaseTrigger 是纯函数式的检查器，不持有状态
  - 状态（上次触发时间）由 CooldownManager 管理
  - 触发条件只看 PerceptionContext，不依赖历史序列
"""
from abc import ABC, abstractmethod
from typing import Optional
from .context import PerceptionContext


class BaseTrigger(ABC):
    """触发器基类。

    子类只需实现 check()，返回触发原因字符串或 None。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """触发器唯一标识（用于冷却 key）。"""

    @abstractmethod
    def check(self, ctx: PerceptionContext) -> Optional[str]:
        """检查是否触发。返回触发原因（角色说话的场景描述），或 None。"""


class IdleTrigger(BaseTrigger):
    """用户空闲超过阈值触发。"""
    name = "idle"

    def __init__(self, threshold_sec: int = 7200) -> None:  # 默认 2 小时
        self._threshold = threshold_sec

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.idle_seconds >= self._threshold:
            return "用户已长时间没有操作电脑"
        return None


class LateNightTrigger(BaseTrigger):
    """深夜仍在活跃时触发。"""
    name = "late_night"

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.is_late_night and ctx.is_user_active:
            return "深夜用户仍在使用电脑"
        return None


class LongWorkTrigger(BaseTrigger):
    """持续工作超过阈值触发（idle_seconds 小代表持续活跃）。"""
    name = "long_work"

    def __init__(self, active_threshold_sec: int = 3600) -> None:  # 持续活跃 1 小时
        self._threshold = active_threshold_sec
        self._session_start: float = 0.0  # 会话开始时间（由 ProactiveEngine 注入）

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        # 通过 PerceptionContext 无法直接知道"持续工作多久"
        # 实现：ProactiveEngine 在首次收到 ctx 时记录开始时间，传递给此触发器
        # 此处接受外部注入的 elapsed_sec 参数来判断
        return None  # 见 ProactiveEngine 的 elapsed 注入逻辑


class WindowSwitchTrigger(BaseTrigger):
    """频繁切换窗口触发（可能处于纠结/分心状态）。"""
    name = "window_switch"

    def __init__(self, freq_threshold: float = 10.0) -> None:  # 10 次/分钟
        self._threshold = freq_threshold

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.switches_per_minute >= self._threshold:
            return "用户频繁切换窗口，可能处于纠结状态"
        return None


class GamingTrigger(BaseTrigger):
    """检测到用户在游戏时触发。"""
    name = "gaming"

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.is_gaming:
            return "用户正在打游戏"
        return None
```

**关于 `LongWorkTrigger` 的实现补充**（在 `ProactiveEngine` 中处理）：
- `ProactiveEngine` 记录 `_session_active_since: float`（首次检测到用户活跃时的时间戳）
- 每次 `collect()` 后，若用户活跃则维持此时间戳；若空闲则重置
- 将 `elapsed = now - _session_active_since` 注入判断，达到阈值则触发 `LongWorkTrigger`
- 因此 `LongWorkTrigger.check()` 重构为接受 `elapsed_sec: float` 额外参数，或在 `ProactiveEngine` 内直接内联判断

**选择内联判断**（更简单，避免 `check()` 接口不统一）：在 `ProactiveEngine._check_long_work()` 单独处理。

---

### Task 2.6 — `ProactiveEngine`

**新建文件** `src/perception/engine.py`

```python
"""
主动介入引擎：整合感知采集、触发检查、冷却管理。

在 CLI 模式下，由 ConversationService 在每轮对话开始前调用 check()。
不引入后台线程（线程模式留给 P3A sidecar）。

职责边界：
  - 输出结构化事件（触发原因字符串），不输出台词
  - 不修改情绪状态，不构建 prompt
  - 台词由人格层根据 proactive_style 字段生成
"""
import time
from typing import Optional
from .collector import PerceptionCollector
from .cooldown import CooldownManager
from .event import ProactiveEvent          # 复用已有 dataclass，字段: tag, trigger_name
from .triggers import (
    BaseTrigger, IdleTrigger, LateNightTrigger,
    WindowSwitchTrigger, GamingTrigger,
)


class ProactiveEngine:
    """主动介入引擎，在对话轮间检查是否有触发条件满足。"""

    _LONG_WORK_THRESHOLD_SEC = 3600  # 持续活跃 1 小时

    def __init__(
        self,
        collector: PerceptionCollector,
        cooldown: Optional[CooldownManager] = None,
    ) -> None:
        self._collector = collector
        self._cooldown = cooldown or CooldownManager()
        self._triggers: list[BaseTrigger] = [
            IdleTrigger(threshold_sec=7200),
            LateNightTrigger(),
            WindowSwitchTrigger(freq_threshold=10.0),
            GamingTrigger(),
        ]
        self._session_active_since: float = time.monotonic()
        self._last_was_active: bool = True

    def check(self) -> Optional[ProactiveEvent]:
        """采集感知快照，检查所有触发器，返回第一个满足条件且未在冷却期的事件。

        返回 None 表示无主动介入。
        """
        ctx = self._collector.collect()

        # 维护持续活跃计时
        if ctx.is_user_active:
            if not self._last_was_active:
                self._session_active_since = time.monotonic()
            self._last_was_active = True
        else:
            self._last_was_active = False

        # 检查 LongWork（内联，ProactiveEvent.tag = "long_work"）
        elapsed = time.monotonic() - self._session_active_since
        if elapsed >= self._LONG_WORK_THRESHOLD_SEC:
            if self._cooldown.can_trigger("long_work"):
                self._cooldown.mark_triggered("long_work")
                return ProactiveEvent(tag="long_work", trigger_name="LongWorkTrigger")

        # 检查其余触发器
        for trigger in self._triggers:
            reason = trigger.check(ctx)
            if reason and self._cooldown.can_trigger(trigger.name):
                self._cooldown.mark_triggered(trigger.name)
                return ProactiveEvent(tag=trigger.name, trigger_name=type(trigger).__name__)

        return None

    def last_perception(self) -> Optional[object]:
        """返回最近一次采集的 PerceptionContext（供 ConversationService 注入 prompt）。"""
        return self._collector.last_perception()  # PerceptionCollector 需暴露此方法
```

**同步修改 `PerceptionCollector`**：
- `collect()` 将结果缓存到 `self._last_ctx`（私有）
- 新增 `last_perception() -> Optional[PerceptionContext]` 方法（公开），供 `ProactiveEngine` 调用，避免跨类访问私有属性
- `PerceptionContext.capture()` 静态工厂方法保留但标注为 deprecated，后续由 `PerceptionCollector.collect()` 统一负责采集

---

### Task 2.7 — 感知日志

**新建文件** `src/perception/perception_log.py`

```python
"""
感知事件日志：记录每次主动介入触发，供事后分析频率和效果。
"""
import json
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class PerceptionLog:
    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / "perception_events.jsonl"

    def record(
        self,
        trigger_name: str,
        reason: str,
        character_id: str,
        proactive_reply: Optional[str] = None,
    ) -> None:
        """追加一条触发事件记录。失败时静默。"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger_name,
            "reason": reason,
            "character_id": character_id,
            "reply": proactive_reply,
        }
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
```

---

### Task 2.8 — 接入 ConversationService

**文件**：`src/application/conversation_service.py`

**修改 `__init__()`**：新增可选参数：

```python
def __init__(
    self,
    character_path: Path,
    debug: bool = False,
    data_dir: Optional[Path] = None,
    enable_perception: bool = False,  # 新增，默认关闭（保持向后兼容）
) -> None:
```

**初始化感知引擎（仅当 `enable_perception=True`）**：

```python
self._proactive_engine: Optional[ProactiveEngine] = None
self._perception_log: Optional[PerceptionLog] = None
if enable_perception:
    from ..perception.input_tracker import InputTracker
    from ..perception.window_monitor import WindowMonitor
    from ..perception.collector import PerceptionCollector
    from ..perception.engine import ProactiveEngine
    from ..perception.perception_log import PerceptionLog
    tracker = InputTracker()
    tracker.start()
    monitor = WindowMonitor()
    collector = PerceptionCollector(tracker, monitor)
    self._proactive_engine = ProactiveEngine(collector)
    self._perception_log = PerceptionLog(self._logger._log_dir.parent / "perception")
    self._input_tracker = tracker  # 持有引用用于 stop()
```

**修改 `run()` 循环**，在 `input("你: ")` 之前插入主动介入检查：

```python
# 主动介入检查（仅在启用感知时）
if self._proactive_engine:
    event = self._proactive_engine.check()
    if event:
        proactive_reply = self._handle_proactive(event)
        if proactive_reply:
            print(f"{config.name}: {proactive_reply}")
            print()
```

**新增 `_handle_proactive()` 方法**：

```python
def _handle_proactive(self, event: "ProactiveEvent") -> Optional[str]:
    """根据主动介入事件生成角色台词。使用 proactive_style 字段构建 prompt。"""
    # 从 character.proactive_style 中取对应场景台词提示
    style = self._config.proactive_style
    style_hint = {
        "idle": style.idle_too_long,
        "late_night": style.user_working_late,
        "gaming": style.user_gaming,
        "long_work": style.user_working_late,  # 复用"深夜工作"提示
        "window_switch": style.idle_too_long,  # 复用"发呆"提示
    }.get(event.trigger_name, "")

    if not style_hint:
        return None  # 无对应台词提示，不主动介入

    system = build_system_prompt(PromptContext(
        character=self._config,
        emotion=self._state,
    ))
    # 合成一条 user 消息作为触发上下文（Anthropic API 要求 messages 非空）
    # 此消息不进入工作记忆，不写入 session log，不计入 turn 计数
    synthetic_message = [
        {"role": "user", "content": f"【场景】{style_hint}。请用一句简短的话自然开口，不要解释场景。"}
    ]
    try:
        result = self._llm.chat(system, synthetic_message)
        reply = result.text
        if self._perception_log:
            self._perception_log.record(event.trigger_name, event.tag, self._config.name, reply)
        # 注意：主动介入消息不写入 session log（无对应 user_input），不计入 turn 计数
        # 也不加入工作记忆（不影响后续对话历史）
        return reply
    except Exception:
        return None
```

**修改 `_on_session_end()`**：停止 InputTracker：

```python
def _on_session_end(self) -> None:
    if hasattr(self, "_input_tracker"):
        try:
            self._input_tracker.stop()
        except Exception:
            pass
    # 原有逻辑...
```

**修改 `main.py`**，新增 `--perception` 启动参数：

```python
parser.add_argument("--perception", action="store_true", help="启用感知层（窗口监听/空闲检测）")
# ...
service = ConversationService(character_path=_CHARACTER_PATH, debug=debug, enable_perception=args.perception)
```

---

### Task 2.9 — P2 测试

**新建文件** `tests/test_perception.py`

```python
class TestInputTracker(unittest.TestCase):
    # idle_seconds() 初始值合理（接近 0）
    # mark_active() 重置计时
    # start() 在 pynput 不可用时不抛异常

class TestWindowMonitor(unittest.TestCase):
    # collect() 失败时返回空字符串，不抛异常
    # is_gaming() 正确匹配关键词（大小写不敏感）
    # switches_per_minute() 历史为空时返回 0

class TestCooldownManager(unittest.TestCase):
    # can_trigger() 初始时返回 True
    # mark_triggered() 后 can_trigger() 返回 False
    # reset() 后 can_trigger() 重新返回 True

class TestTriggers(unittest.TestCase):
    # IdleTrigger: idle_seconds 超阈值时返回非 None
    # IdleTrigger: idle_seconds 未超阈值时返回 None
    # LateNightTrigger: 深夜 + 活跃 → 触发
    # LateNightTrigger: 深夜 + 不活跃 → 不触发
    # LateNightTrigger: 非深夜 + 活跃 → 不触发
    # WindowSwitchTrigger: 超频 → 触发
    # GamingTrigger: is_gaming=True → 触发

class TestProactiveEngine(unittest.TestCase):
    # 无触发时 check() 返回 None
    # 触发后立即 check() 因冷却返回 None（不重复触发）
    # 返回的 ProactiveEvent.tag 与触发器 name 一致

class TestHandleProactive(unittest.TestCase):
    # style_hint 为空时返回 None（不主动介入）
    # LLM 调用失败时返回 None（静默）
    # 正常触发时返回非空字符串
    # 调用后 turn 计数不变（主动介入不消耗轮次）
    # 调用后工作记忆长度不变（不污染对话历史）
```

使用 `unittest.mock.MagicMock` 替代 `PerceptionCollector`，注入构造好的 `PerceptionContext` 测试触发逻辑。

---

## P3A — 后端 sidecar

### 概述

将 `ConversationService` 封装为 FastAPI sidecar，供 Tauri 前端通过 HTTP/WebSocket 调用。

**核心约束**：
- API 层是薄壳，所有业务逻辑留在 `ConversationService`
- 路由函数不做任何人格/记忆/情绪判断
- `ConversationService` 实例由 FastAPI 的 lifespan 管理（启动时初始化，关闭时销毁）
- 一个 sidecar 进程管理一个 active character（与 CLI 模式一致）

---

### Task 3.0 — 安装依赖

```bash
pip install fastapi uvicorn[standard] websockets
```

更新 `requirements.txt`，追加：

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
websockets>=12.0
```

---

### Task 3.1 — Pydantic schemas

**新建文件** `src/api/schemas.py`

```python
"""
API 数据契约：请求/响应的 Pydantic 模型。

职责边界：只做序列化/反序列化，不含业务逻辑。
"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


class ChatResponse(BaseModel):
    reply: str
    mood: str                         # 当前情绪（触发后）
    mood_changed: bool                # 本轮是否发生情绪变化
    flagged: bool                     # 是否命中禁用词
    turn: int
    usage: Optional[UsageInfo] = None


class StateResponse(BaseModel):
    character_name: str
    mood: str
    persist_count: int
    turn: int
    memory_summary_count: int         # 当前摘要条数
    memory_fact_count: int            # 当前长期事实条数


class HealthResponse(BaseModel):
    status: str = "ok"
    character: str
    version: str = ""


class StreamChunk(BaseModel):
    """WebSocket 流式消息块。"""
    type: str       # "token" | "done" | "error"
    content: str    # token 文本 / done 时为空 / error 时为错误描述
    mood: Optional[str] = None        # 仅 done 时填充
    flagged: Optional[bool] = None    # 仅 done 时填充
```

---

### Task 3.2 — 应用状态与 lifespan

**新建文件** `src/api/app.py`

```python
"""
FastAPI 应用入口。

职责：
  - 定义 lifespan（启动/关闭 ConversationService）
  - 注册路由
  - CORS 配置（Tauri 前端本地访问）
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..application.conversation_service import ConversationService

_CHARACTER_PATH = Path("characters/asuka/personality.yaml")

# 全局服务实例（单例，lifespan 管理）
_service: ConversationService | None = None


def get_service() -> ConversationService:
    """依赖注入函数，路由通过此函数获取 ConversationService 实例。"""
    if _service is None:
        raise RuntimeError("ConversationService 未初始化")
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    global _service
    _service = ConversationService(
        character_path=_CHARACTER_PATH,
        enable_perception=False,  # sidecar 模式下感知由前端事件驱动，暂不启用
    )
    yield
    _service = None  # 清理


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kokoro API",
        description="Kokoro AI 人格伴侣平台 sidecar API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import chat, state, stream
    app.include_router(chat.router)
    app.include_router(state.router)
    app.include_router(stream.router)

    return app


app = create_app()
```

---

### Task 3.3 — `POST /chat` 路由

**新建文件** `src/api/routes/chat.py`

```python
"""
POST /chat — 同步对话接口。

返回完整回复，适合前端轮询或一次性请求。
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException

from ..app import get_service
from ..schemas import ChatRequest, ChatResponse, UsageInfo
from ...application.conversation_service import ConversationService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ConversationService = Depends(get_service),
) -> ChatResponse:
    mood_before = service.character_state.mood  # 需在 ConversationService 暴露此属性
    # handle_turn() 是同步阻塞调用，用 asyncio.to_thread 避免阻塞事件循环
    reply = await asyncio.to_thread(service.handle_turn, request.message)

    if reply is None:
        raise HTTPException(status_code=503, detail="LLM 调用失败，请稍后重试")

    # handle_turn 返回后，情绪已更新
    mood_after = service.character_state.mood
    last_log = service.last_log_entry  # 需在 ConversationService 暴露此属性

    return ChatResponse(
        reply=reply,
        mood=mood_after,
        mood_changed=mood_before != mood_after,
        flagged=last_log.get("flagged", False) if last_log else False,
        turn=service.turn,
        usage=UsageInfo(**last_log["usage"]) if last_log and last_log.get("usage") else None,
    )
```

**同步修改 `ConversationService`**，暴露以下属性（不改变现有 `run()` 行为）：

```python
@property
def character_state(self) -> EmotionState:
    return self._state

@property
def turn(self) -> int:
    return self._turn

@property
def last_log_entry(self) -> Optional[dict]:
    """返回最近一条日志记录（用于 API 层取 flagged/usage 等信息）。"""
    return self._last_log_entry  # 需在 log() 调用后缓存
```

**在 `handle_turn()` 中**，在日志写入后缓存：

```python
self._last_log_entry = {
    "flagged": flagged,
    "usage": usage,
}
```

**`__init__()` 中初始化**：`self._last_log_entry: Optional[dict] = None`

---

### Task 3.4 — `GET /state` 和 `GET /health`

**新建文件** `src/api/routes/state.py`

```python
from fastapi import APIRouter, Depends
from ..app import get_service
from ..schemas import StateResponse, HealthResponse
from ...application.conversation_service import ConversationService

router = APIRouter(tags=["state"])


@router.get("/state", response_model=StateResponse)
async def get_state(service: ConversationService = Depends(get_service)) -> StateResponse:
    state = service.character_state
    memory_ctx = service.memory_context  # 需暴露，见下方
    return StateResponse(
        character_name=service.character.name,
        mood=state.mood,
        persist_count=state.persist_count,
        turn=service.turn,
        memory_summary_count=len(memory_ctx.summary_items),
        memory_fact_count=len(memory_ctx.long_term_items),
    )


@router.get("/health", response_model=HealthResponse)
async def health(service: ConversationService = Depends(get_service)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        character=service.character.name,
        version=service.character.version,
    )
```

**同步修改 `ConversationService`**，暴露：

```python
@property
def memory_context(self) -> MemoryContext:
    """返回最近一次 get_context() 的结果（缓存）。"""
    return self._last_memory_ctx  # 在 handle_turn() 中缓存

@property
def character(self) -> CharacterConfig:
    return self._config  # 已存在
```

**在 `handle_turn()` 中**，在 `get_context()` 调用后缓存：

```python
memory_ctx = self._memory.get_context(character_id, token_budget=self._MEMORY_TOKEN_BUDGET)
self._last_memory_ctx = memory_ctx  # 新增缓存
```

`__init__()` 中初始化：`self._last_memory_ctx: MemoryContext = MemoryContext()`

---

### Task 3.5 — `WebSocket /stream`

**新建文件** `src/api/routes/stream.py`

```python
"""
WebSocket /stream — 流式对话接口。

当前阶段：LLM 调用仍为同步，WebSocket 用于保持长连接和推送完整回复。
真正的 token 级流式在 LLM provider 支持后扩展（不改变此接口协议）。
"""
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..app import get_service
from ..schemas import StreamChunk
from ...application.conversation_service import ConversationService

router = APIRouter(tags=["stream"])


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    # WebSocket 路由不使用 Depends()，直接调用 get_service() 保证跨版本兼容
    service: ConversationService = get_service()
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                message = payload.get("message", "").strip()
            except (json.JSONDecodeError, AttributeError):
                await websocket.send_text(
                    StreamChunk(type="error", content="消息格式错误，需要 JSON {message: ...}").model_dump_json()
                )
                continue

            if not message:
                continue

            # 发送"思考中"指示
            await websocket.send_text(
                StreamChunk(type="thinking", content="").model_dump_json()
            )

            # handle_turn() 是同步阻塞调用，用 asyncio.to_thread 避免阻塞事件循环
            mood_before = service.character_state.mood
            reply = await asyncio.to_thread(service.handle_turn, message)

            if reply is None:
                await websocket.send_text(
                    StreamChunk(type="error", content="LLM 调用失败").model_dump_json()
                )
                continue

            last_log = service.last_log_entry or {}
            await websocket.send_text(
                StreamChunk(
                    type="done",
                    content=reply,
                    mood=service.character_state.mood,
                    flagged=last_log.get("flagged", False),
                ).model_dump_json()
            )

    except WebSocketDisconnect:
        pass
```

**关于真正流式的升级路径**（写在注释中即可）：
- `AnthropicClient` 未来可添加 `stream_chat()` 返回 `AsyncGenerator[str, None]`
- 届时 `/stream` 路由改为逐 token 发送 `StreamChunk(type="token", content=token)`
- 当前协议兼容此扩展，`done` 帧始终作为结束标志

---

### Task 3.6 — sidecar 入口

**新建文件** `src/api/server.py`

```python
"""
sidecar 启动入口。

用法：
    python -m src.api.server          # 开发模式（热重载）
    python -m src.api.server --prod   # 生产模式（无热重载）
"""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro sidecar API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--prod", action="store_true", help="生产模式（禁用热重载）")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

**新建文件** `src/api/__init__.py`（空文件）

**新建文件** `src/api/routes/__init__.py`（空文件）

---

### Task 3.7 — IPC 协议文档

**新建文件** `docs/desgin/IPC协议.md`

内容包含：
- 端口约定（默认 18765）
- `POST /chat` 请求/响应格式（含字段说明）
- `GET /state` 响应格式
- `GET /health` 响应格式
- `WebSocket /stream` 消息协议（`StreamChunk` 格式，type 枚举）
- Tauri 侧调用示例（伪代码）
- sidecar 启动/关闭时序（Tauri 生命周期钩子触发 sidecar 进程）

---

### Task 3.8 — P3A 测试

**新建文件** `tests/test_api.py`

使用 `fastapi.testclient.TestClient`：

```python
class TestHealthEndpoint(unittest.TestCase):
    # GET /health 返回 200，status="ok"

class TestChatEndpoint(unittest.TestCase):
    # POST /chat 合法消息 → 200，reply 非空
    # POST /chat 空消息 → 422（Pydantic 校验）
    # POST /chat 消息超长 → 422
    # LLM 失败时 → 503

class TestStateEndpoint(unittest.TestCase):
    # GET /state 返回正确字段，mood 为合法值

class TestStreamWebSocket(unittest.TestCase):
    # 连接后发送消息，收到 thinking + done 帧
    # 发送非法 JSON，收到 error 帧
```

**mock LLM**：在 `TestClient` fixture 中用 `unittest.mock.patch` 替换 `create_llm_client` 返回 mock，`chat()` 返回 `LLMResult(text="测试回复", model="mock", provider="mock")`。

---

## 收尾

### 全量测试

```bash
python -m unittest discover -s tests -v
```

预期：所有已有 49 个用例 + P1/P2/P3A 新增用例全部 PASS。

### 更新清单文件

执行完成后，更新 `docs/tasks/devRoute/模块完成情况清单.md` 对应条目。

### 不需要做的事

- 不修改 `logs/` 下任何文件
- 不引入 ChromaDB / SQLite（留给 P2B 以后）
- 不实现真正的 token 级流式（留给 Live2D 阶段配合）
- 不修改 `characters/asuka/personality.yaml`（配置已完整）
- 不为 PyInstaller 打包（留给 P3A 完成后单独处理）
