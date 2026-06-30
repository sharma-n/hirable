from __future__ import annotations

import json
import os

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import agent_base_url

router = APIRouter()

_M0_USER_ID = "m0-placeholder"  # replaced by session user_id in M1


@router.websocket("/api/chat/ws/{conversation_id}")
async def chat_proxy(websocket: WebSocket, conversation_id: str) -> None:
    """Proxy browser WS ↔ agent_kit sidecar WS, injecting user_id + shared secret."""
    await websocket.accept()

    secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
    upstream_url = f"ws://{agent_base_url().removeprefix('http://')}/ws/{conversation_id}"
    headers = {"X-Internal-Secret": secret}

    try:
        async with websockets.connect(upstream_url, additional_headers=headers) as upstream:
            async def browser_to_agent() -> None:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = {"message": raw}
                    # Inject the trusted user_id (never trust client-supplied value)
                    payload["user_id"] = _M0_USER_ID
                    await upstream.send(json.dumps(payload))

            async def agent_to_browser() -> None:
                async for frame in upstream:
                    await websocket.send_text(frame)

            import asyncio
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(browser_to_agent()),
                    asyncio.create_task(agent_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(exc)}))
        except Exception:
            pass
        finally:
            await websocket.close()
