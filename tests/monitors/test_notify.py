"""Offline tests for the Telegram digest push.

NETWORK TRIPWIRE: an autouse fixture replaces ``requests.post`` with a function
that fails the test outright -- no test in this module can ever reach Telegram.
Every legitimate path injects its own fake ``post``.

THE LEAK TEST: the bot token appears inside API URLs, so exception strings
embed it. ``test_failure_detail_never_leaks_the_token`` feeds an error whose
message CONTAINS the fake token and asserts it appears NOWHERE in the result --
removing sanitize() from notify.py MUST fail that test (SCARS #1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from monitors import notify
from monitors.notify import (
    NotifyConfig,
    get_chat_ids,
    load_config,
    sanitize,
    send_digest,
)

FAKE_TOKEN = "1234567890:TEST-FAKE-TOKEN-abcDEF"
CONFIG = NotifyConfig(token=FAKE_TOKEN, chat_id="42")


@pytest.fixture(autouse=True)
def network_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    def trip(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network tripwire: a test tried to reach Telegram")

    # notify calls requests.post via the module attribute, so patching the
    # requests module itself covers every default-path call.
    monkeypatch.setattr(requests, "post", trip)


class _Response:
    def __init__(
        self, status: int = 200, text: str = "ok",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status
        self.text = text
        self._payload = payload if payload is not None else {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _RecordingPost:
    """A fake requests.post: records calls, replays scripted outcomes."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._outcomes = list(outcomes)

    def __call__(self, url: str, **kwargs: Any) -> Any:
        self.calls.append({"url": url, **kwargs})
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# ------------------------------------------------------------ load_config


def test_load_config_unconfigured_is_none(tmp_path: Path) -> None:
    assert load_config(env={}, root=tmp_path) is None
    assert load_config(env={notify.ENV_TOKEN: "x"}, root=tmp_path) is None  # half


def test_load_config_reads_env_file_and_env_wins(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# comment\nTELEGRAM_BOT_TOKEN=file-token\nTELEGRAM_CHAT_ID=7\n"
    )
    from_file = load_config(env={}, root=tmp_path)
    assert from_file == NotifyConfig(token="file-token", chat_id="7")
    overridden = load_config(env={notify.ENV_TOKEN: "env-token"}, root=tmp_path)
    assert overridden == NotifyConfig(token="env-token", chat_id="7")


# ------------------------------------------------------------ send_digest


def test_happy_path_posts_once_and_reports_sent() -> None:
    post = _RecordingPost([_Response(200)])
    result = send_digest("digest text", CONFIG, post=post, sleep=lambda s: None)
    assert result.sent is True
    assert result.detail == "sent"
    assert len(post.calls) == 1
    call = post.calls[0]
    assert call["url"] == f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"
    assert call["json"] == {"chat_id": "42", "text": "digest text"}
    assert call["timeout"] == 10.0


def test_unconfigured_send_makes_no_http_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify, "load_config", lambda: None)
    result = send_digest("digest text")  # tripwire proves no HTTP happens
    assert result.sent is False
    assert result.detail == "unconfigured"


def test_failure_detail_never_leaks_the_token() -> None:
    # The exception message CONTAINS the token (as real requests errors do --
    # they embed the URL). Removing sanitize() from notify.py MUST fail this.
    error = requests.ConnectionError(
        f"connection refused for url "
        f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"
    )
    post = _RecordingPost([error, error])
    result = send_digest("digest", CONFIG, post=post, sleep=lambda s: None)
    assert result.sent is False
    assert FAKE_TOKEN not in result.detail
    assert "***" in result.detail


def test_retry_once_on_timeout_then_success() -> None:
    slept: list[float] = []
    post = _RecordingPost([requests.Timeout("timed out"), _Response(200)])
    result = send_digest("digest", CONFIG, post=post, sleep=slept.append)
    assert result.sent is True
    assert len(post.calls) == 2  # exactly two attempts, no more
    assert slept == [3.0]


def test_http_error_status_fails_without_retry() -> None:
    post = _RecordingPost([_Response(403, "forbidden: bot was blocked")])
    result = send_digest("digest", CONFIG, post=post, sleep=lambda s: None)
    assert result.sent is False
    assert len(post.calls) == 1  # an answered error is not retried
    assert "HTTP 403" in result.detail


def test_truncation_at_4000_chars() -> None:
    post = _RecordingPost([_Response(200)])
    result = send_digest("x" * 5000, CONFIG, post=post, sleep=lambda s: None)
    assert result.sent is True
    assert result.detail == "sent (truncated)"
    assert len(post.calls[0]["json"]["text"]) == 4000


# ------------------------------------------------------------ sanitize


def test_sanitize_replaces_token_everywhere() -> None:
    text = f"a {FAKE_TOKEN} b {FAKE_TOKEN} c"
    assert sanitize(text, FAKE_TOKEN) == "a *** b *** c"


def test_sanitize_passthrough_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(notify, "load_config", lambda: None)
    assert sanitize("nothing to hide") == "nothing to hide"


# ------------------------------------------------------------ get_chat_ids


def test_get_chat_id_parses_getupdates_payload() -> None:
    payload = {
        "ok": True,
        "result": [
            {"message": {"chat": {"id": 123, "first_name": "Mark",
                                  "type": "private"}}},
            {"message": {"chat": {"id": 123, "first_name": "Mark",
                                  "type": "private"}}},  # duplicate update
            {"message": {"chat": {"id": -99, "title": "Family group",
                                  "type": "group"}}},
            {"edited_message": {"nothing": "here"}},  # no chat -> skipped
        ],
    }
    post = _RecordingPost([_Response(200, payload=payload)])
    chats = get_chat_ids(CONFIG, post=post)
    assert chats == [(123, "Mark"), (-99, "Family group")]
    assert post.calls[0]["url"] == (
        f"https://api.telegram.org/bot{FAKE_TOKEN}/getUpdates"
    )
