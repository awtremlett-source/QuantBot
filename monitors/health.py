"""Monthly health report -- MEASURE, NEVER REFIT.

THE LAW (this module's whole contract): read-only over the journal, CLEAN
prices, and the trial log -- the store is opened in SQLite read-only mode, so a
write is impossible by construction. It writes ONLY its report file under
``data/health/`` and changes no parameter, no threshold, no state. A health
report that could touch what it measures would be an optimizer wearing a
stethoscope (SCARS #21: observe outcome, never chase it).

Sections: live performance (LOW-CONFIDENCE labeled until the track is long
enough to mean anything), drawdown envelope vs the validated lines, regime mix
via the live strategy's own replay, cost tally from recorded fills, the SHADOW
RECONCILIATION (below), and trials/DSR progress.

SHADOW RECONCILIATION -- the ongoing birth certificate. The validated
backtester replays the frozen config's strategy over the same CLEAN history
(``log_path=None``: a verification rerun, not a selection trial), and every
paper bar is compared against it ANCHORED one step: shadow(t) = paper(t-1) *
(1 + backtester return(t)). Anchoring isolates each bar's physics (fill price,
slippage, marking) from history: paper's mid-history inception (it started
flat on 2026-07-14 inside a series where the strategy was already long) and
any superseded bar shows up ONCE, on its own date, instead of contaminating
every later level. Mismatches beyond 0.01 GBP are listed with dates; a date
whose RAW bar was superseded (quarantine ``price_raw``/``superseded_by_refetch``)
is explained -- the engines saw different bars, honestly recorded. Final
shares/cash are audited EXACTLY against the sum of recorded fills.

BASIS NOISE (measured live 2026-08-07): because paper joined mid-history, the
shadow holds the same WEIGHT with a different cash/shares composition, so even
perfectly-agreeing bars differ by pennies (observed <= 0.03 GBP on 10k, sign
alternating with the day's move). Listed mismatches at or under the 0.10 GBP
ceiling are labeled basis-noise and do NOT trip the verdict; a real physics
error (one mispriced fill ~= 5 GBP) sits 50x above the ceiling. Anything
unexplained beyond it is RED: book physics drifted from the validated
backtester.
"""

from __future__ import annotations

import argparse
import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from data_store import store
from data_store.timeutils import now_utc_iso
from execution.config import CONFIG, VALIDATED_WORST_DRAWDOWN
from monitors import notify
from research import trial_log
from research.backtester import run_backtest
from research.deflation import count_selection_trials
from strategies.regime_switcher import regime_series

PAPER_INCEPTION = "2026-07-14"  # go-live date (STATE/MANIFEST: "Live since")
# Below this many daily marks, performance stats are tracking-only noise.
_MIN_CONFIDENT_BARS = 40
# Validated OOS regime mix for the live switcher (rubric-4 experiment record);
# CITED as reference, deliberately never recomputed here.
_REFERENCE_PCT_STRESSED = 25.8
# The rubric-2 run's estimate: at the switcher's observed moments, DSR >= 0.95
# needs roughly +20% more track length than the validated T=2,142 bars.
_TARGET_EXTRA_BARS = round(0.20 * 2142)
_TRADING_DAYS = 252
_EQUITY_TOLERANCE_GBP = 0.01  # list diffs beyond this
_BASIS_NOISE_CEILING_GBP = 0.10  # verdict-RED only beyond this (docstring)


@dataclass(frozen=True, slots=True)
class PerfBlock:
    label: str
    bars: int
    equity_start: float
    equity_end: float
    total_return: float
    annualized_sharpe: float
    max_drawdown: float
    low_confidence: bool


@dataclass(frozen=True, slots=True)
class EnvelopeBlock:
    current_dd: float
    worst_dd_period: float
    red_line: float
    warn_line: float


@dataclass(frozen=True, slots=True)
class RegimeBlock:
    threshold: float
    pct_stressed: float
    switches: int
    reference_pct_stressed: float


@dataclass(frozen=True, slots=True)
class CostsBlock:
    fills: int
    round_trips: int
    slippage_gbp: float
    slippage_pct_of_equity: float


@dataclass(frozen=True, slots=True)
class ShadowMismatch:
    event_time: str
    paper_equity: float
    shadow_equity: float
    diff_gbp: float
    superseded: bool


@dataclass(frozen=True, slots=True)
class ShadowBlock:
    verdict: str  # 'OK' | 'RED'
    shares_exact: bool
    cash_exact: bool
    mismatches: list[ShadowMismatch]
    note: str


@dataclass(frozen=True, slots=True)
class TrialsBlock:
    log_records: int
    selection_n: int
    live_bars_banked: int
    target_extra_bars: int


@dataclass(frozen=True, slots=True)
class HealthReport:
    asof: str
    ticker: str
    inception: str
    perf: PerfBlock
    last30: PerfBlock
    envelope: EnvelopeBlock
    regime: RegimeBlock
    costs: CostsBlock
    shadow: ShadowBlock
    trials: TrialsBlock


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    """Read-only connection: the measure-never-refit law, enforced by SQLite."""
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _perf(label: str, marks: list[tuple[str, float]]) -> PerfBlock:
    """Performance stats from (event_time, equity) marks; empty-safe."""
    equities = [equity for _, equity in marks]
    bars = len(equities)
    if bars == 0:
        return PerfBlock(label, 0, 0.0, 0.0, 0.0, 0.0, 0.0, True)
    start, end = equities[0], equities[-1]
    total_return = end / start - 1.0 if start > 0 else 0.0

    sharpe = 0.0
    if bars >= 3:
        series = pd.Series(equities)
        returns = series.pct_change().iloc[1:]
        std = float(returns.std(ddof=1))
        if std > 0.0 and math.isfinite(std):
            sharpe = float(returns.mean()) / std * math.sqrt(_TRADING_DAYS)

    peak = -math.inf
    worst = 0.0
    for equity in equities:
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)

    return PerfBlock(
        label=label,
        bars=bars,
        equity_start=start,
        equity_end=end,
        total_return=total_return,
        annualized_sharpe=sharpe,
        max_drawdown=worst,
        low_confidence=bars < _MIN_CONFIDENT_BARS,
    )


def _shadow(
    conn: sqlite3.Connection,
    prices: pd.DataFrame,
    marks: list[tuple[str, float]],
) -> ShadowBlock:
    """The anchored shadow reconciliation (see module docstring)."""
    if not marks:
        return ShadowBlock("OK", True, True, [], "no paper bars yet")

    # Verification rerun of the validated engine -- log_path=None on purpose.
    result = run_backtest(
        CONFIG.build_strategy(),
        prices,
        slippage_pct=CONFIG.slippage_pct,
        starting_equity=CONFIG.starting_equity,
        log_path=None,
    )
    shadow_returns: dict[str, float] = {
        str(ts): float(r) for ts, r in result.returns.items()
    }

    mismatches: list[ShadowMismatch] = []

    def superseded(event_time: str) -> bool:
        row = conn.execute(
            "SELECT COUNT(*) FROM quarantine WHERE ticker = ? AND event_time = ? "
            "AND domain = 'price_raw' AND reason = 'superseded_by_refetch'",
            (CONFIG.ticker, event_time),
        ).fetchone()
        return bool(row[0])

    # First mark must be the starting stake; later marks anchored one step.
    first_time, first_equity = marks[0]
    if abs(first_equity - CONFIG.starting_equity) > _EQUITY_TOLERANCE_GBP:
        mismatches.append(
            ShadowMismatch(
                first_time, first_equity, CONFIG.starting_equity,
                first_equity - CONFIG.starting_equity, superseded(first_time),
            )
        )
    for (_, prev_equity), (event_time, paper_equity) in zip(marks, marks[1:]):
        r = shadow_returns.get(event_time)
        if r is None:
            mismatches.append(
                ShadowMismatch(event_time, paper_equity, math.nan, math.nan, False)
            )
            continue
        shadow_equity = prev_equity * (1.0 + r)
        diff = paper_equity - shadow_equity
        if abs(diff) > _EQUITY_TOLERANCE_GBP:
            mismatches.append(
                ShadowMismatch(
                    event_time, paper_equity, shadow_equity, diff,
                    superseded(event_time),
                )
            )

    # Journal audit: state must equal the exact sum of its recorded fills.
    state = store.read_paper_state(conn, CONFIG.ticker)
    fills = store.read_paper_fills(conn, CONFIG.ticker)
    shares_from_fills = sum(f.shares_delta for f in fills)
    cash_from_fills = CONFIG.starting_equity + sum(f.cash_delta for f in fills)
    shares_exact = state is not None and abs(state.shares - shares_from_fills) < 1e-9
    cash_exact = state is not None and abs(state.cash - cash_from_fills) < 1e-9

    unexplained = [
        m
        for m in mismatches
        if not m.superseded
        and (math.isnan(m.diff_gbp) or abs(m.diff_gbp) > _BASIS_NOISE_CEILING_GBP)
    ]
    if shares_exact and cash_exact and not unexplained:
        superseded_n = sum(1 for m in mismatches if m.superseded)
        noise_n = len(mismatches) - superseded_n
        note = (
            "all bars match the validated backtester"
            if not mismatches
            else (
                f"{len(mismatches)} bar(s) differ: {superseded_n} superseded, "
                f"{noise_n} within inception basis-noise "
                f"(<= {_BASIS_NOISE_CEILING_GBP:.2f} GBP)"
            )
        )
        return ShadowBlock("OK", shares_exact, cash_exact, mismatches, note)
    return ShadowBlock(
        "RED", shares_exact, cash_exact, mismatches,
        "book physics drifted from validated backtester — investigate before "
        "trusting further paper evidence",
    )


def build_report(
    db_path: str | Path,
    trials_path: str = trial_log.DEFAULT_TRIAL_LOG,
    asof: str | None = None,
) -> HealthReport:
    """Assemble the report (read-only; see the module law)."""
    the_asof = asof if asof is not None else datetime.now(timezone.utc).date().isoformat()
    conn = _connect_readonly(Path(db_path))
    try:
        prices = store.read_price_asof(conn, CONFIG.ticker, now_utc_iso())
        prices = prices[prices["event_time"].str[:10] <= the_asof].reset_index(
            drop=True
        )

        all_marks = [
            (m.event_time, m.equity)
            for m in store.read_paper_equity(conn, CONFIG.ticker)
            if m.event_time[:10] <= the_asof
        ]
        cutoff30 = (date.fromisoformat(the_asof) - timedelta(days=30)).isoformat()
        last30_marks = [m for m in all_marks if m[0][:10] > cutoff30]

        perf = _perf("inception -> asof", all_marks)
        last30 = _perf("last 30 days", last30_marks)

        envelope = EnvelopeBlock(
            current_dd=(
                0.0
                if not all_marks
                else all_marks[-1][1] / max(e for _, e in all_marks) - 1.0
            ),
            worst_dd_period=perf.max_drawdown,
            red_line=VALIDATED_WORST_DRAWDOWN,
            warn_line=round(0.8 * VALIDATED_WORST_DRAWDOWN, 4),
        )

        labels = regime_series(prices, CONFIG.threshold)
        window_times = {t for t, _ in all_marks}
        window_labels = [
            label
            for ts, label in zip(prices["event_time"], labels)
            if str(ts) in window_times
        ]
        switches = sum(
            1 for a, b in zip(window_labels, window_labels[1:]) if a != b
        )
        regime = RegimeBlock(
            threshold=CONFIG.threshold,
            pct_stressed=(
                100.0 * sum(1 for x in window_labels if x == "stressed")
                / len(window_labels)
                if window_labels
                else 0.0
            ),
            switches=switches,
            reference_pct_stressed=_REFERENCE_PCT_STRESSED,
        )

        fills = store.read_paper_fills(conn, CONFIG.ticker)
        slip = CONFIG.slippage_pct
        slippage_gbp = 0.0
        for fill in fills:
            open_px = fill.fill_price / (
                (1.0 + slip) if fill.shares_delta > 0 else (1.0 - slip)
            )
            slippage_gbp += abs(fill.shares_delta) * open_px * slip
        equity_now = all_marks[-1][1] if all_marks else CONFIG.starting_equity
        costs = CostsBlock(
            fills=len(fills),
            round_trips=sum(1 for f in fills if f.shares_delta < 0),
            slippage_gbp=slippage_gbp,
            slippage_pct_of_equity=(
                100.0 * slippage_gbp / equity_now if equity_now > 0 else 0.0
            ),
        )

        shadow = _shadow(conn, prices, all_marks)

        trials = TrialsBlock(
            log_records=trial_log.count_trials(trials_path),
            selection_n=count_selection_trials(trials_path)[0],
            live_bars_banked=len(all_marks),
            target_extra_bars=_TARGET_EXTRA_BARS,
        )
    finally:
        conn.close()

    return HealthReport(
        asof=the_asof,
        ticker=CONFIG.ticker,
        inception=PAPER_INCEPTION,
        perf=perf,
        last30=last30,
        envelope=envelope,
        regime=regime,
        costs=costs,
        shadow=shadow,
        trials=trials,
    )


def _perf_lines(block: PerfBlock) -> list[str]:
    flag = (
        f"  [LOW-CONFIDENCE: ~{block.bars} bars cannot distinguish skill from "
        "noise; tracking only]"
        if block.low_confidence
        else ""
    )
    return [
        f"  {block.label}: {block.bars} bars{flag}",
        f"    equity {block.equity_start:,.2f} -> {block.equity_end:,.2f} "
        f"({block.total_return:+.2%})",
        f"    annualized sharpe {block.annualized_sharpe:+.2f} | "
        f"max dd {block.max_drawdown:+.2%}",
    ]


def render(report: HealthReport) -> str:
    """The full human-readable report."""
    lines: list[str] = [
        f"QUANTBOT MONTHLY HEALTH — {report.ticker} — asof {report.asof} "
        f"(paper inception {report.inception})",
        "law: measure, never refit — this report changes nothing",
        "",
        "LIVE PERFORMANCE",
        *_perf_lines(report.perf),
        *_perf_lines(report.last30),
        "",
        "ENVELOPE",
        f"  current dd {report.envelope.current_dd:+.2%} | worst this period "
        f"{report.envelope.worst_dd_period:+.2%}",
        f"  validated worst {report.envelope.red_line:+.1%} (RED) | warn line "
        f"{report.envelope.warn_line:+.1%}",
        "",
        "REGIME (live threshold "
        f"{report.regime.threshold}, via the strategy's own replay)",
        f"  {report.regime.pct_stressed:.1f}% of paper bars stressed | "
        f"{report.regime.switches} switch(es)",
        f"  validated OOS reference: {report.regime.reference_pct_stressed}% "
        "stressed (cited, not recomputed)",
        "",
        "COSTS",
        f"  {report.costs.fills} fill(s), {report.costs.round_trips} "
        f"round-trip(s) | slippage paid £{report.costs.slippage_gbp:.2f} "
        f"({report.costs.slippage_pct_of_equity:.3f}% of equity)",
        "",
        "SHADOW RECONCILIATION (ongoing birth certificate)",
        f"  final shares exact: {report.shadow.shares_exact} | final cash "
        f"exact: {report.shadow.cash_exact}",
    ]
    for m in report.shadow.mismatches:
        if m.superseded:
            tag = "explained: superseded bar"
        elif (
            not math.isnan(m.diff_gbp)
            and abs(m.diff_gbp) <= _BASIS_NOISE_CEILING_GBP
        ):
            tag = "within inception basis-noise"
        else:
            tag = "UNEXPLAINED"
        lines.append(
            f"  {m.event_time[:10]}: paper {m.paper_equity:,.2f} vs shadow "
            f"{m.shadow_equity:,.2f} (diff {m.diff_gbp:+.2f}) [{tag}]"
        )
    lines += [
        f"  VERDICT: {report.shadow.verdict} — {report.shadow.note}",
        "",
        "TRIALS & DSR PROGRESS",
        f"  trial log: {report.trials.log_records} records | selection-N "
        f"{report.trials.selection_n}",
        f"  live bars banked toward DSR>=0.95: "
        f"{report.trials.live_bars_banked}/{report.trials.target_extra_bars} "
        "(~+20% more T at the switcher's validated moments; see STATE rubric-2)",
    ]
    return "\n".join(lines)


def summary(report: HealthReport) -> str:
    """The <=15-line Telegram summary: headline numbers + both verdicts."""
    perf = report.perf
    flag = " [LOW-CONFIDENCE]" if perf.low_confidence else ""
    lines = [
        f"QuantBot HEALTH {report.asof[:7]} ({report.ticker})",
        f"equity {perf.equity_end:,.2f} | ret {perf.total_return:+.2%} over "
        f"{perf.bars} bars{flag}",
        f"sharpe {perf.annualized_sharpe:+.2f} | dd now "
        f"{report.envelope.current_dd:+.2%} vs RED "
        f"{report.envelope.red_line:+.1%}",
        f"regime: {report.regime.pct_stressed:.1f}% stressed "
        f"(ref {report.regime.reference_pct_stressed}%), "
        f"{report.regime.switches} switch(es)",
        f"costs: {report.costs.fills} fills, {report.costs.round_trips} "
        f"round-trip(s), £{report.costs.slippage_gbp:.2f} slippage",
        f"shadow: {report.shadow.verdict} — {report.shadow.note}",
        f"trials N={report.trials.selection_n}; bars banked "
        f"{report.trials.live_bars_banked}/{report.trials.target_extra_bars}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="health", description="Monthly health report (measure, never refit)."
    )
    parser.add_argument("--db", required=True, metavar="PATH")
    parser.add_argument("--asof", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args(argv)

    report = build_report(Path(args.db), asof=args.asof)
    text = render(report)
    print(text)

    out_dir = Path(args.db).parent / "health"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"health-{report.asof[:7].replace('-', '')}.txt"
    out_file.write_text(text + "\n", encoding="utf-8")
    print(f"report written: {out_file}")

    # Telegram push: same contract as the loop -- sanitized, never blocking.
    try:
        config = notify.load_config()
        if config is None:
            print("telegram: unconfigured")
        else:
            outcome = notify.send_digest(summary(report), config)
            print(
                "telegram: OK" if outcome.sent
                else f"telegram: WARN - {outcome.detail}"
            )
    except Exception as exc:  # noqa: BLE001 -- scoped: report must still land
        print(f"telegram: WARN - {notify.sanitize(str(exc))}")

    return 0 if report.shadow.verdict == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
