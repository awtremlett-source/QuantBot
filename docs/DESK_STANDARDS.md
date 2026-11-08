# DESK STANDARDS (read on demand, never imported)

From the operator's directive of 2026-11-08, verbatim in docs/sessions/SESSION_2026-11-08_RULES.md.
Each bullet is one rule, tagged as in docs/LESSONS_LEARNED.md, where the owed gates are listed.

Homes elsewhere, not repeated here: costs, taxes and FX in research, the trial count, deflation, the
held-out period, the one-bar shift (fill at next-bar open), and the Sharpe red flag (0.7 to 1.2 net is
real, higher is a red flag, stricter than a limit of 2) all live in CLAUDE.md's laws.

## Data
- One writer cleans data on entry. OWED: data-check
- Nothing in qb2 outside the front door and recorder calls to_parquet directly. Other write routes are not caught yet. ENFORCED: `tests/qb2/test_s3d_dividends_and_return.py::test_only_the_front_door_writes_to_the_clean_store`
- A watcher that only reports is not a control; if the mandate says keep it clean, something must repair it. OWED: data-check
- A quality score reads the store decisions read, per ticker, never as an average or median. Check its worst name. OWED: data-check
- A blank bar must never reach a rule silently: recursive indicators can be poisoned permanently, so one bad day weeks ago can switch a strategy off with no warning. Serve priced bars only and name the missing dates. Never invent a price. OWED: data-check
- A voided row must be able to heal: an empty row is absent evidence, so a clean new print fills it. Two real prints that disagree stay void. Wrong-unit and filler rows are not empty rows: they stay in sticky quarantine until the operator's words lift them (qb2/data/cross_bar.py). OWED: data-check
- One price basis per series. Never splice adjusted and unadjusted history. OWED: data-check
- An adjusted close is never stored, and adding dividends to one is refused. ENFORCED: `tests/qb2/test_s3d_dividends_and_return.py::test_adding_dividends_to_an_adjusted_close_is_refused`, `tests/qb2/test_s3d_dividends_and_return.py::test_the_clean_daily_store_never_holds_an_adjusted_close`
- Handle splits, dividends, spin-offs, currency and pence units explicitly. OWED: data-check
- Calendars and holidays are a checked input. OWED: data-check
- Use point-in-time, survivorship-free universes for research. Until a list exists, PLAN_V3 S4's survivorship mark-down stands. OWED: research
- Measure a vendor or broker limit; never assume it. Do not park a ticker without a proven cause, and parked names must have a route back. OWED: data-check

## Signals
- A strategy may not read the future. qb2/research/strategy.py compares three cut points, so a peeker can still pass. OWED: research
- Live and backtest run the same decision code. OWED: req-checks
- Each strategy keeps its own exit. Combining strategies on one ticker must not silently become an all-must-agree exit. OWED: req-checks
- Compute each rule's decisions in one pass; the live desk reads the last row. OWED: req-checks

## Execution and risk
- The position book comes from the broker, never from intended orders. OWED: broker-s10
- Stops rest at the broker and are read back from it. PLAN_V3 P10 stands until stage S10 settles this (operator's GO, 2026-11-08): today the stop is run by our code, because Trading 212 has no trailing stop and no amend. Know what your stop order type does through a gap, and make the simulator match it. OWED: broker-s10
- A fill gets a stop immediately, including a late fill. Test delayed and partial fills, restarts with open orders, gateway loss and duplicate orders. OWED: broker-s10
- One capital number, read by both the sizer and the send path. OWED: broker-s10
- Safeties fail closed. OWED: broker-s10
- No saved brake state, no pot view, no account total, or a pot holding with no value is a refusal. ENFORCED: `tests/qb2/test_qt16b_checks.py::test_a_missing_brake_state_means_no_buys_and_tight_stops`, `tests/qb2/test_qt16b_checks.py::test_a_missing_pot_figure_is_a_refusal`
- Drawdown brakes need memory that survives restarts. ENFORCED: `qb2/guard/brakes.py`, `tests/qb2/test_qt16b_checks.py::test_brake_levels_follow_the_pots_own_peak`

## Research
- Judge on the worst fold. OWED: research
- Use walk-forward or purged cross-validation. OWED: research
- Promote the centre of a plateau, never the peak. OWED: research
- Publish results at measured cost as well as floor cost. OWED: research
- Reproduce a known published result before trusting the harness. OWED: research
- One broken strategy must not contaminate another's verdict or a shared hurdle. OWED: research
- Decide the kill condition before deploying, and size for the path. OWED: research

## Operations
- Prove every scheduled job by reading back its registered command and a dated receipt. "Registered" and "Ready" do not mean it will launch. OWED: job-receipts
- Failures are loud. No silent background processes. Every wait has a named timeout. OWED: job-receipts
- Unattended work must never depend on a dialog someone has to click. OWED: job-receipts
- Plan for reboots, power loss, broker resets, full disks and off-machine backups. OWED: job-receipts
- Keep scheduled jobs few. OWED: job-receipts
