"""Polite JSON over HTTP: an on-disk cache, a minimum interval between calls and retries with back-off.

Errors are raised, never turned into placeholder rows.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

Transport = Callable[[str, dict[str, str], float], tuple[int, bytes]]


def urllib_transport(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https API hosts
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""


class HTTPError(RuntimeError):
    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status


class JsonClient:
    def __init__(self, cache_dir: str | Path | None = None, min_interval_s: float = 0.2, retries: int = 3,
                 timeout_s: float = 20.0, user_agent: str = "citecheck/0.1",
                 transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval_s = min_interval_s
        self.retries = retries
        self.timeout_s = timeout_s
        self.headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self.transport = transport or urllib_transport
        self.sleep = sleep
        self._last = 0.0
        self.network_calls = 0

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")

    def get(self, url: str) -> dict | None:
        """Return the JSON body, ``None`` for HTTP 404, or raise ``HTTPError``."""
        path = self._cache_path(url)
        if path is not None and path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            return cached["body"]
        delay = 1.0
        for attempt in range(self.retries + 1):
            wait = self.min_interval_s - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            self.network_calls += 1
            status, raw = self.transport(url, self.headers, self.timeout_s)
            if status == 200:
                body = json.loads(raw.decode("utf-8"))
                break
            if status == 404:
                body = None
                break
            if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                self.sleep(delay)
                delay *= 2
                continue
            raise HTTPError(url, status)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"url": url, "body": body}), encoding="utf-8")
        return body
