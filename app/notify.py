from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def notify(text: str, *, extra: dict[str, Any] | None = None) -> None:
    """Best-effort notification.

    Supported methods:
    - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
    - NOTIFY_WEBHOOK_URL (generic POST)

    If no env is configured, this is a no-op.
    """

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
            _post_json(url, payload)
            return
        except Exception:
            pass

    webhook = os.getenv("NOTIFY_WEBHOOK_URL")
    if webhook:
        try:
            payload = {"text": text}
            if extra:
                payload["extra"] = extra
            _post_json(webhook, payload)
        except Exception:
            pass


def _post_json(url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as _:
        return
