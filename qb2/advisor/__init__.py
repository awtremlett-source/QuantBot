"""qb2.advisor -- S9's advisor (QT-23): it only ever SUGGESTS; the operator trades by hand (P1).

ADV-0, the default (registered 8fb2c49): hold the index fund -- VWRL, the whole advisor pot --
with the big-fall stop and the 10% re-buy. S-01..S-06, the six batch-2 rules, scored in the
background from the arm date, counted 0. Operator, 2026-10-19 (verbatim): "GO on QT-23: build the
advisor with "hold the index fund" as its default, the 15% big-fall stop (10% when markets are
jumpy) as its live stop, and the rules scored in the background on live prices only."

live.py the one door to live bars · engine.py the weekly review; issue() checks and writes every
suggestion · daily.py the daily job and the review's timing · scorecard.py P9, as if followed ·
shadow.py the six shadows · page.py logs/advisor/advisor.md · state.py the record.
Walls (tests/qb2/test_qt23_advisor.py): no order path; every suggestion through
guard.suggestion.check_suggestion; bars only through live.py; no shadow score before the arm date.
"""
