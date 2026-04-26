from __future__ import annotations

import asyncio

from fastapi import WebSocket


class StreamConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: str) -> None:
        async with self._lock:
            targets = list(self._connections)

        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_text(payload)
            except Exception:
                stale.append(websocket)

        if not stale:
            return

        async with self._lock:
            for websocket in stale:
                self._connections.discard(websocket)


_manager = StreamConnectionManager()


def get_stream_manager() -> StreamConnectionManager:
    return _manager