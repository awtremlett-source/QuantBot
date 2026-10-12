# Flat on shutdown — the design (S5 designs, S10 builds)

Written 2026-10-12 (QT-16 B7). PLAN_V3 P4: the bot holds nothing overnight and is
flat before any shutdown, sleep or restart; waking after an unplanned stop, it
sells any bot holding **first**, then writes an incident. S5 designs it; **S10
builds it**, and S10 cannot be marked DONE until every test named below exists
(`tests/plan/test_flat_on_shutdown.py` enforces that).

## The machine, as it really is

- A **desktop**, not a laptop (operator, 2026-10-08). No battery: a power cut gives
  **no notice at all**. PLAN_V3 S5's laptop wording ("lid-close", "the laptop's own
  battery is its UPS") does not apply; the S13 UPS is the only notice a cut can give.
- Shut down overnight, the operator said. The Windows System log for 9–12 Oct shows
  **sleep**, not shutdown: "entering sleep" (Kernel-Power 42) at 02:08 Sat, 04:38 Sun
  and 22:18 Sun; "resumed from a low power state" at 18:04 Sat, 18:06 Sun and
  18:02 Mon. Sleep is the common case, so it is designed for first.
- Windows gives a sleeping program about **two seconds** of notice — far too short to
  send market orders and see them fill. So the design never relies on the notice to
  flatten: it **keeps the machine awake while the bot holds anything**, and goes
  flat at the session's end (P4's 15-minute cut-off) before allowing sleep.

## Triggers, actions, and the S10 test each needs

Every action below sells **bot-tagged quantity only** (flatten_bot): anchors (P20),
advisor and manual holdings are never touched. Every sell goes through the sender,
which never blocks a sell. Every step is written to the incident or flat log with
the time.

| trigger | what happens | S10 test |
|---|---|---|
| shutdown | The shutdown notice is taken (the program is the last to agree): pending bot orders cancelled, bot holdings sold at market (US extended hours: `extendedHours=true`, FACTS j1), the flat check run, time recorded; only then is shutdown allowed. If the sells cannot complete, the shutdown is still allowed and the next start treats it as an unplanned stop. | `tests/qb2/test_s10_flat_on_shutdown.py::test_a_shutdown_notice_flattens_the_bot_before_agreeing` |
| restart | As shutdown; then, at boot, reconcile against the broker **before anything else** (no buy is possible until the reconcile is clean). | `tests/qb2/test_s10_flat_on_shutdown.py::test_a_restart_flattens_then_reconciles_first_on_boot` |
| sleep | While the bot holds anything the machine is kept awake (SetThreadExecutionState). At the session's end the bot is flat (P4) and only then may the machine sleep. A sleep that still arrives (power button, forced) is taken as an unplanned stop at wake. | `tests/qb2/test_s10_flat_on_shutdown.py::test_sleep_is_held_off_while_the_bot_holds_and_allowed_once_flat` |
| power loss | No notice. A heartbeat file is written every minute while running; at the next start a gap while the bot could have held anything is a power loss: reconcile, **sell any bot holding first**, then write an incident, then arm STOP_NEW_TRADES until the operator reads it. | `tests/qb2/test_s10_flat_on_shutdown.py::test_a_heartbeat_gap_sells_bot_holdings_first_then_writes_an_incident` |
| unplanned stop | A crash, a kill or a hang (no clean exit line). On wake or restart: same as power loss — **sell bot holdings first**, then the incident, then the stop catch-up (stops.Ledger.catch_up) for the advisor and manual positions, alerting only. | `tests/qb2/test_s10_flat_on_shutdown.py::test_wake_after_an_unplanned_stop_sells_first_then_writes_the_incident` |

Also required at S10, from P4 and P20, so they sit beside the five:

| check | S10 test |
|---|---|
| flatten never sells an anchor, an advisor or a manual holding, on any trigger | `tests/qb2/test_s10_flat_on_shutdown.py::test_no_trigger_ever_sells_an_anchor_or_his_holdings` |
| a buy can never be queued into a closed market by a trigger's retry | `tests/qb2/test_s10_flat_on_shutdown.py::test_no_trigger_queues_a_buy_into_a_closed_market` |

## What already exists (S2b–S5) and is reused, not rebuilt

- `qb2/execution/safety.py`: `flatten_bot`, `bot_view` (anchors subtracted), `bot_is_flat`,
  the killswitch.
- `qb2/execution/sender.py`: sells skip every buy check; `sell_crossed` for stops.
- `qb2/guard/age.py`: `overnight` — a bot position past its session is an incident
  and arms STOP_NEW_TRADES.
- `qb2/guard/stops.py`: `Ledger.catch_up` on waking.

## Open questions for S10 (not decided here)

- Whether a pending order can be cancelled and confirmed inside a shutdown's grace
  period on this machine (measure it; do not assume).
- FACTS j2 (UNVERIFIED): what happens to an order placed while the market is shut.
  The design never relies on it.
