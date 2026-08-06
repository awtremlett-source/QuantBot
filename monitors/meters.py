"""Five observe-only meters over the store + backup report (rubric condition 6).

Each meter answers one question a human would otherwise have to remember to ask
every morning, and answers it with OK / WARN / RED plus a one-line detail. The
meters READ; they never write, place, cancel, or delete (see package docstring).
``run_all`` returns every verdict plus the overall = worst status, which the
paper loop prints as the digest's MONITORS block.

Birth-certificate law (SCARS #9): every meter here has a test that feeds it a
deliberately broken fixture and asserts RED -- a meter that cannot go red is
wallpaper, not a monitor.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Literal

from execution import paper_book
from execution.config import VALIDATED_WORST_DRAWDOWN
from tools.backup import BackupReport

Status = Literal["OK", "WARN", "RED"]

# Worst-first ordering for the overall verdict.
_SEVERITY: dict[str, int] = {"OK": 0, "WARN": 1, "RED": 2}

# --- data_freshness thresholds (calendar days since the latest CLEAN bar) ---
# Daily bars arrive next morning, so 1-2 days old is normal; a weekend makes the
# latest bar 3 days old by Monday's run, and a long/holiday weekend 4. Five or
# more calendar days therefore means the pipeline itself missed runs -- that is
# never explained by the calendar alone.
_FRESH_WARN_DAYS = 4
_FRESH_RED_DAYS = 5

# --- drawdown lines (from the validated OOS record; single source of truth) ---
_DD_RED = VALIDATED_WORST_DRAWDOWN  # -36.5%: outside anything validation promised
_DD_WARN = round(0.8 * VALIDATED_WORST_DRAWDOWN, 4)  # -29.2%: 80% of the line

# --- book_invariants cash floor ---
# The validated book legitimately runs a SMALL negative cash balance: fills pay
# slippage after sizing at the raw open (the known ~-5.00 GBP overdraft, see
# STATE.md FIRST FILL). -25 is far beyond anything that mechanism can produce
# while still catching a real sizing/settle anomaly early.
_CASH_FLOOR_GBP = -25.0

# --- quarantine_growth thresholds (new rows quarantined today) ---
_QUARANTINE_WARN_MAX = 20  # 1-20: a source hiccup; >20: mass rejection


@dataclass(frozen=True, slots=True)
class MeterResult:
    """One meter's verdict: a name, OK/WARN/RED, and a one-line detail."""

    name: str
    status: Status
    detail: str


def data_freshness(
    conn: sqlite3.Connection, today: str, ticker: str = "NVDA"
) -> MeterResult:
    """RED when the latest CLEAN bar is older than 5 calendar days.

    Calendar days, not trading days, deliberately: weekends explain 3 days and a
    holiday weekend 4 (WARN -- worth a glance), but 5+ means scheduled runs are
    not happening or ingest is failing -- the calendar never explains it (see the
    threshold rationale at the top of this module).
    """
    name = "data_freshness"
    row = conn.execute(
        "SELECT MAX(event_time) FROM price_clean WHERE ticker = ?", (ticker,)
    ).fetchone()
    latest = row[0] if row else None
    if latest is None:
        return MeterResult(name, "RED", f"no CLEAN bars at all for {ticker}")
    age = (date.fromisoformat(today) - date.fromisoformat(str(latest)[:10])).days
    detail = (
        f"latest CLEAN bar {str(latest)[:10]} is {age}d old "
        f"(WARN>={_FRESH_WARN_DAYS}d, RED>{_FRESH_RED_DAYS}d)"
    )
    if age > _FRESH_RED_DAYS:
        return MeterResult(name, "RED", detail)
    if age >= _FRESH_WARN_DAYS:
        return MeterResult(name, "WARN", detail)
    return MeterResult(name, "OK", detail)


def drawdown(conn: sqlite3.Connection, ticker: str = "NVDA") -> MeterResult:
    """RED at the validated worst drawdown; WARN at 80% of that line.

    Reuses :func:`execution.paper_book.drawdown_from_peak` (the digest's own
    number) so the meter and the digest can never disagree. RED means the book
    is outside anything validation promised.
    """
    name = "drawdown"
    dd = paper_book.drawdown_from_peak(conn, ticker)
    detail = f"dd={dd:+.2%} (WARN<={_DD_WARN:+.1%}, RED<={_DD_RED:+.1%})"
    if dd <= _DD_RED:
        return MeterResult(name, "RED", detail)
    if dd <= _DD_WARN:
        return MeterResult(name, "WARN", detail)
    return MeterResult(name, "OK", detail)


def book_invariants(conn: sqlite3.Connection, ticker: str = "NVDA") -> MeterResult:
    """RED on any broken book invariant; the detail names every violation found.

    Checks: long-only (shares >= 0); the latest processed bar has its equity
    mark; no order still 'pending' while a NEWER CLEAN bar exists (the loop
    settles pending orders at the next bar's open, so after a run this means
    settle is broken); cash above the floor (the known slippage overdraft is
    ~-5.00 GBP -- see the floor rationale at the top of this module).
    """
    name = "book_invariants"
    state = conn.execute(
        "SELECT shares, cash, last_decided_event_time FROM paper_state "
        "WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    if state is None:
        return MeterResult(name, "RED", f"no paper_state row for {ticker}")
    shares, cash, last_decided = float(state[0]), float(state[1]), str(state[2])

    violations: list[str] = []
    if shares < 0.0:
        violations.append(f"shares={shares:.6f} < 0 (long-only violated)")
    marked = conn.execute(
        "SELECT 1 FROM paper_equity WHERE ticker = ? AND event_time = ?",
        (ticker, last_decided),
    ).fetchone()
    if marked is None:
        violations.append(f"no equity mark for latest processed bar {last_decided[:10]}")
    stale = conn.execute(
        "SELECT COUNT(*) FROM paper_orders o WHERE o.ticker = ? "
        "AND o.status = 'pending' AND EXISTS (SELECT 1 FROM price_clean p "
        "WHERE p.ticker = o.ticker AND p.event_time > o.decision_event_time)",
        (ticker,),
    ).fetchone()[0]
    if stale:
        violations.append(f"{stale} pending order(s) older than the newest CLEAN bar")
    if cash < _CASH_FLOOR_GBP:
        violations.append(f"cash={cash:.2f} below floor {_CASH_FLOOR_GBP:.2f}")

    if violations:
        return MeterResult(name, "RED", "; ".join(violations))
    pending = conn.execute(
        "SELECT COUNT(*) FROM paper_orders WHERE ticker = ? AND status = 'pending'",
        (ticker,),
    ).fetchone()[0]
    return MeterResult(
        name, "OK", f"shares={shares:.6f} cash={cash:.2f} pending={pending}"
    )


def quarantine_growth(conn: sqlite3.Connection, today: str) -> MeterResult:
    """New quarantine REJECTIONS today: 0 OK; 1-20 WARN (source hiccup); >20 RED.

    A handful of rejected rows is a source hiccup worth a glance; a mass
    rejection means the source itself broke and CLEAN is starving. Rows with
    reason 'superseded_by_rebuild' are EXCLUDED: they are the reconciler's
    quarantine-never-delete archive of a routine CLEAN rebuild, not rejections
    (proven live 2026-08-06 against the 2,899 rows one rebuild archived on
    2026-07-28 -- the unfiltered count cried RED on a healthy pipeline, the
    SCARS #8 wallpaper failure this meter must never repeat). The string mirrors
    ``reconcile.clean_prices.QuarantineReason.SUPERSEDED_BY_REBUILD`` (not
    imported: that module pulls the network stack).
    """
    name = "quarantine_growth"
    count = conn.execute(
        "SELECT COUNT(*) FROM quarantine WHERE substr(knowable_time, 1, 10) = ? "
        "AND reason != 'superseded_by_rebuild'",
        (today,),
    ).fetchone()[0]
    detail = f"{count} row(s) quarantined today (WARN 1-{_QUARANTINE_WARN_MAX}, RED >{_QUARANTINE_WARN_MAX})"
    if count > _QUARANTINE_WARN_MAX:
        return MeterResult(name, "RED", detail)
    if count > 0:
        return MeterResult(name, "WARN", detail)
    return MeterResult(name, "OK", detail)


def backup_status(report: BackupReport | None) -> MeterResult:
    """RED if the local verify failed (no trustworthy snapshot exists); WARN if
    the verified snapshot is local-only (honest until rubric 7's off-laptop
    destination is wired); OK otherwise."""
    name = "backup_status"
    if report is None or not report.verified:
        return MeterResult(name, "RED", "backup verify FAILED -- journal unprotected")
    if report.local_only:
        return MeterResult(
            name, "WARN", f"verified but LOCAL-ONLY -> {report.dest_dir}"
        )
    return MeterResult(name, "OK", f"verified off-laptop -> {report.dest_dir}")


def run_all(
    conn: sqlite3.Connection,
    backup_report: BackupReport | None,
    today: str,
    ticker: str = "NVDA",
) -> tuple[list[MeterResult], Status]:
    """Run every meter; return the verdicts plus overall = the WORST status."""
    results = [
        data_freshness(conn, today, ticker),
        drawdown(conn, ticker),
        book_invariants(conn, ticker),
        quarantine_growth(conn, today),
        backup_status(backup_report),
    ]
    overall: Status = max(
        (r.status for r in results), key=lambda s: _SEVERITY[s]
    )
    return results, overall
