"""
API 数据契约：请求/响应的 Pydantic 模型。

职责边界：只做序列化/反序列化，不含业务逻辑。
"""
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入")


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""


class ChatResponse(BaseModel):
    reply: str
    mood: str
    """当前情绪（触发后）。"""
    mood_changed: bool
    """本轮是否发生情绪变化。"""
    flagged: bool
    """是否命中禁用词。"""
    turn: int
    usage: Optional[UsageInfo] = None


class StateResponse(BaseModel):
    character_name: str
    mood: str
    persist_count: int
    turn: int
    memory_summary_count: int
    """当前摘要条数。"""
    memory_fact_count: int
    """当前长期事实条数。"""


class HealthResponse(BaseModel):
    status: str = "ok"
    character: str
    version: str = ""


class StreamChunk(BaseModel):
    """WebSocket 流式消息块。"""
    type: str
    """消息类型："thinking" | "token" | "done" | "error"。"""
    content: str
    """token 文本 / done 时为完整回复 / error 时为错误描述。"""
    mood: Optional[str] = None
    """仅 done 时填充。"""
    flagged: Optional[bool] = None
    """仅 done 时填充。"""
