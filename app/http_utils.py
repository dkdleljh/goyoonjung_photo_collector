from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 3,
    polite_delay: bool = False,
    backoff_base_seconds: float = 1.0,
    backoff_jitter_seconds: float = 0.3,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        if polite_delay:
            await asyncio.sleep(random.uniform(0.8, 1.6))
        try:
            response = await client.request(method, url, **kwargs)

            # Retry on server errors and common throttling responses.
            if response.status_code >= 500 or response.status_code in {429, 408}:
                raise httpx.HTTPStatusError(
                    f"retryable http error: {response.status_code}", request=response.request, response=response
                )

            # For 403, do NOT attempt to bypass; but transient blocks can happen.
            # Retry a little, then give up.
            if response.status_code == 403 and attempt < retries:
                raise httpx.HTTPStatusError(
                    f"transient forbidden: {response.status_code}", request=response.request, response=response
                )

            return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < retries:
                sleep_for = backoff_base_seconds * (2 ** (attempt - 1)) + random.uniform(0.0, backoff_jitter_seconds)
                await asyncio.sleep(sleep_for)

    if last_exc is None:
        raise RuntimeError("unknown request failure")
    raise last_exc
