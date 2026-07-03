from __future__ import annotations

import os

from fastapi import Header, HTTPException


def verify_internal_secret(x_internal_secret: str = Header(default="")) -> None:
    """Reject internal-API calls that don't carry the correct shared secret.

    Mirrors ``agent/bootstrap.py``'s ``InternalSecretMiddleware`` and
    ``app/api/chat.py``'s env read — the secret is never in config.yaml.
    """
    expected = os.environ.get("AGENT_INTERNAL_SECRET", "")
    if not expected or x_internal_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
