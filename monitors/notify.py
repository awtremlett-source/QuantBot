"""Telegram digest push -- the daily digest, delivered to the operator's phone.

Observe-never-act (package law): this module REPORTS text it is given; it never
places, cancels, or mutates anything. The operating rhythm it enables: read the
Telegram message each morning; act only on RED.

SECRETS LAW (SCARS #1): ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` live in
``.env`` only (names in ``.env.example``, values gitignored). The token appears
INSIDE every Telegram API URL, so a raw ``requests`` exception string -- which
embeds the URL -- IS the secret. Every error/log/detail string this module
emits therefore passes through :func:`sanitize`, which replaces the token with
``'***'``. A leaked exception string is a leaked secret; the leak test in
``tests/monitors/test_notify.py`` fails if the sanitizer is removed.

ENV LOADING: existing code reads plain ``os.environ`` (tools/backup.py), but
nothing in the stack loads ``.env`` into the environment -- and the scheduled
task runs headless. ``load_config`` therefore ALSO parses the repo-root
``.env`` file directly (simple KEY=VALUE lines); real environment variables
win over file values. Unconfigured is a STATE (returns None), not an error.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from data_store.timeutils import now_utc_iso

_API_URL = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT_S = 10.0
_RETRY_DELAY_S = 3.0
# Telegram's hard cap is 4,096 chars; truncate at 4,000 for headroom.
_MAX_CHARS = 4000

ENV_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_CHAT_ID = "TELEGRAM_CHAT_ID"


@dataclass(frozen=True, slots=True)
class NotifyConfig:
    """The two secrets a send needs (values never logged -- see module law)."""

    token: str
    chat_id: str


@dataclass(frozen=True, slots=True)
class NotifyResult:
    """Outcome of one send: ``detail`` is ALWAYS sanitized, safe to print."""

    sent: bool
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines from a .env file; comments/blank lines skipped."""
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_config(
    env: Mapping[str, str] | None = None, root: Path | None = None
) -> NotifyConfig | None:
    """Read the token + chat id; ``None`` if either is missing (unconfigured).

    Environment variables win; the repo-root ``.env`` file fills the gaps (the
    scheduled task runs with no shell profile, so the file is the normal
    source). Tests pass ``env`` and ``root`` explicitly for determinism.
    """
    the_env: Mapping[str, str] = env if env is not None else _os_environ()
    file_values = _parse_env_file((root if root is not None else _repo_root()) / ".env")
    token = the_env.get(ENV_TOKEN, "").strip() or file_values.get(ENV_TOKEN, "")
    chat_id = the_env.get(ENV_CHAT_ID, "").strip() or file_values.get(ENV_CHAT_ID, "")
    if not token or not chat_id:
        return None
    return NotifyConfig(token=token, chat_id=chat_id)


def _os_environ() -> Mapping[str, str]:
    import os

    return os.environ


def sanitize(text: str, token: str | None = None) -> str:
    """Replace the bot token with ``'***'`` wherever it appears in ``text``.

    With no explicit ``token``, the configured one is looked up; if nothing is
    configured there is nothing to leak and ``text`` passes through.
    """
    the_token = token
    if the_token is None:
        config = load_config()
        the_token = config.token if config is not None else None
    if not the_token:
        return text
    return text.replace(the_token, "***")


def send_digest(
    text: str,
    config: NotifyConfig | None = None,
    *,
    post: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> NotifyResult:
    """POST ``text`` to the configured chat; one retry on connection/timeout.

    Plain text (no markdown -- digest lines contain characters Telegram's
    parsers mangle), truncated at 4,000 chars, 10s timeout, one retry after 3s
    on connection/timeout errors only (an HTTP error status is answered by the
    API and retrying it changes nothing). The returned ``detail`` is sanitized.
    """
    the_config = config if config is not None else load_config()
    if the_config is None:
        return NotifyResult(False, "unconfigured")
    the_post = post if post is not None else requests.post
    body = text[:_MAX_CHARS]
    truncated = " (truncated)" if len(text) > _MAX_CHARS else ""
    url = _API_URL.format(token=the_config.token, method="sendMessage")

    for attempt in (1, 2):
        try:
            response = the_post(
                url,
                json={"chat_id": the_config.chat_id, "text": body},
                timeout=_TIMEOUT_S,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 1:
                sleep(_RETRY_DELAY_S)
                continue
            return NotifyResult(
                False,
                "send failed after retry: "
                + sanitize(str(exc), the_config.token),
            )
        status = int(response.status_code)
        if status == 200:
            return NotifyResult(True, f"sent{truncated}")
        return NotifyResult(
            False,
            sanitize(f"HTTP {status}: {str(response.text)[:200]}", the_config.token),
        )
    raise AssertionError("unreachable")  # pragma: no cover


def get_chat_ids(
    config: NotifyConfig, *, post: Callable[..., Any] | None = None
) -> list[tuple[int, str]]:
    """Chat ids + display names seen by getUpdates (deduped, in order)."""
    the_post = post if post is not None else requests.post
    url = _API_URL.format(token=config.token, method="getUpdates")
    response = the_post(url, json={}, timeout=_TIMEOUT_S)
    payload: dict[str, Any] = response.json()
    seen: dict[int, str] = {}
    for update in payload.get("result", []):
        chat = (update.get("message") or {}).get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        name = str(
            chat.get("title")
            or chat.get("username")
            or chat.get("first_name")
            or chat.get("type", "?")
        )
        seen[int(chat_id)] = name
    return list(seen.items())


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``--test`` sends a probe message; ``--get-chat-id`` lists chats."""
    parser = argparse.ArgumentParser(
        prog="notify", description="Telegram digest utilities (secrets in .env)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", action="store_true", help="send a test message")
    group.add_argument(
        "--get-chat-id", action="store_true", help="list chat ids seen by the bot"
    )
    args = parser.parse_args(argv)

    config = load_config()
    if config is None:
        print(
            f"unconfigured: set {ENV_TOKEN} and {ENV_CHAT_ID} in .env "
            "(create the bot via @BotFather first)"
        )
        return 1

    if args.test:
        result = send_digest(f"QuantBot test — {now_utc_iso()}", config)
        print(f"sent={result.sent} detail={result.detail}")
        return 0 if result.sent else 1

    try:
        chats = get_chat_ids(config)
    except requests.RequestException as exc:
        print(f"getUpdates failed: {sanitize(str(exc), config.token)}")
        return 1
    if not chats:
        print("no chats seen yet — message your bot first, then rerun")
        return 1
    for chat_id, name in chats:
        print(f"chat_id={chat_id}  name={name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
