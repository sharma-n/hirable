from __future__ import annotations

import asyncio
import contextlib
import json
import os

import websockets
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.auth.dependencies import current_user
from app.auth.sessions import COOKIE_NAME, resolve_session
from app.config import agent_base_url, selectable_models
from app.db.engine import SessionLocal
from app.db.models import User

router = APIRouter()


@router.get("/api/chat/models")
def list_models(user: User = Depends(current_user)) -> dict:
    return {"models": selectable_models()}


@router.websocket("/api/chat/ws/{conversation_id}")
async def chat_proxy(websocket: WebSocket, conversation_id: str) -> None:
    """Proxy browser WS ↔ harness_kit sidecar WS, injecting trusted user_id + shared secret."""
    # Resolve session before accepting the connection
    db = SessionLocal()
    try:
        token = websocket.cookies.get(COOKIE_NAME)
        user = resolve_session(db, token) if token else None
    finally:
        db.close()

    if user is None:
        await websocket.close(code=4401)
        return

    user_id = user.id
    await websocket.accept()

    secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
    # Namespace by user_id: harness_kit conversations are globally keyed and
    # user-owned (SessionStore.load raises UnauthorizedError on cross-user access),
    # so a fixed client-chosen id like "profile" would collide across users.
    # The internal /internal/context endpoint strips this prefix back off.
    upstream_conversation_id = f"{user_id}:{conversation_id}"
    upstream_url = f"ws://{agent_base_url().removeprefix('http://')}/ws/{upstream_conversation_id}"
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
                    # Always overwrite with the server-derived user_id — never trust the client
                    payload["user_id"] = user_id
                    await upstream.send(json.dumps(payload))

            async def agent_to_browser() -> None:
                async for frame in upstream:
                    await websocket.send_text(frame)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(browser_to_agent()),
                    asyncio.create_task(agent_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            # Retrieve results so exceptions aren't logged as "never retrieved";
            # a client disconnect (e.g. navigating away from the chat page) is
            # a normal close, not an error, and is handled below.
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, WebSocketDisconnect):
                    raise exc

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(exc)}))
        except Exception:
            pass
        finally:
            await websocket.close()
