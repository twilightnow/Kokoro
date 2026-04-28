"""
POST /notify — 外部主动事件入口。

允许插件、外部服务或前端主动向 Kokoro 推送触发事件。
事件会进入 CompanionRuntime 的调度队列，在下一个周期统一处理。
"""
from fastapi import APIRouter, HTTPException

from ..schemas import NotifyEventRequest
from ..service_registry import get_runtime
from ...proactive.notify import NotifyEvent, validate_external_notify_params

router = APIRouter(tags=["notify"])


@router.post("/notify", status_code=202)
async def push_notify_event(body: NotifyEventRequest) -> dict[str, str]:
    """推送外部 NotifyEvent 到调度队列。

    返回 202 Accepted，事件不保证立即触发（受策略和 DND 控制）。
    """
    try:
        scene, urgency, privacy_level = validate_external_notify_params(
            body.scene, body.urgency, body.privacy_level
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    event = NotifyEvent(
        source="external",
        scene=scene,
        urgency=urgency,
        payload=dict(body.payload),
        privacy_level=privacy_level,
    )

    runtime = get_runtime()
    runtime.push_notify_event(event)

    return {"status": "accepted", "event_id": event.id}
