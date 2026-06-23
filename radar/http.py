"""A shared requests session with a polite User-Agent, timeouts, and light retry.

Every network call goes through this so we get consistent behavior: a descriptive
User-Agent that includes a contact email (polite-pool for OpenAlex and Crossref),
a timeout on every request, and a try/except so a dead source is logged and
skipped rather than fatal.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from . import config

log = logging.getLogger("radar.http")

DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
BACKOFF_BASE = 1.5    # seconds, multiplied by attempt number


def user_agent() -> str:
    email = config.contact_email()
    return f"ResearchRadar/0.1 (https://github.com/kitzcode/research-radar; mailto:{email})"


class Http:
    """Thin wrapper over a requests.Session.

    get() never raises on network failure. It logs and returns None so callers
    can skip a dead source. Callers that need the body check for None first.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent()})

    def get(self, url: str, params: Optional[dict] = None,
            headers: Optional[dict] = None) -> Optional[requests.Response]:
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url, params=params, headers=headers,
                    timeout=self.timeout, allow_redirects=True,
                )
                # Retry on transient server and rate-limit codes.
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = f"status {resp.status_code}"
                    self._sleep(attempt)
                    continue
                return resp
            except requests.RequestException as exc:
                last_err = str(exc)
                self._sleep(attempt)
        log.warning("GET failed after %d attempts: %s (%s)", MAX_RETRIES, url, last_err)
        return None

    def _sleep(self, attempt: int) -> None:
        time.sleep(BACKOFF_BASE * attempt)

    def get_json(self, url: str, params: Optional[dict] = None,
                 headers: Optional[dict] = None) -> Optional[dict]:
        resp = self.get(url, params=params, headers=headers)
        if resp is None or resp.status_code != 200:
            if resp is not None:
                log.warning("non-200 (%s) from %s", resp.status_code, url)
            return None
        try:
            return resp.json()
        except ValueError as exc:
            log.warning("bad JSON from %s: %s", url, exc)
            return None
