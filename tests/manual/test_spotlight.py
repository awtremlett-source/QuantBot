from manual.scout.scoring import ScoreResult
from manual.scout.spotlight import spotlight_rows


def row(ticker, index="FTSE100", steady=0.95, year=20.0, turnover=10e6,
        close=500.0, sma200=430.0):
    return {"ticker": ticker, "name": ticker, "sector": "Test",
            "index": index, "stamp_duty": "Y",
            "snap": {"close": close, "sma200": sma200,
                     "above200_frac": steady, "roc252": year,
                     "roc126": year / 2, "turnover_gbp": turnover,
                     "close_gbp": close / 100, "currency": "GBp"},
            "buy": ScoreResult(), "sell": ScoreResult()}


def test_durable_climber_qualifies_and_ranks_first():
    rows = [row("STAR.L", steady=0.98, year=30.0),
            row("OK.L", steady=0.85, year=10.0)]
    out = spotlight_rows(rows)
    assert [r["ticker"] for r in out] == ["STAR.L", "OK.L"]
    assert out[0]["steady_pct"] == 98.0


def test_wobblers_and_fallers_excluded():
    rows = [row("WOBBLY.L", steady=0.60),
            row("FALLEN.L", close=400.0, sma200=430.0),
            row("DOWNYEAR.L", year=-5.0)]
    assert spotlight_rows(rows) == []


def test_small_names_need_liquidity():
    rows = [row("SMALL.L", index="FTSE250", turnover=1e6),
            row("BIGVOL.L", index="FTSE250", turnover=8e6)]
    out = spotlight_rows(rows)
    assert [r["ticker"] for r in out] == ["BIGVOL.L"]


def test_uses_half_year_when_no_full_year():
    rows = [row("YOUNG.L")]
    rows[0]["snap"]["roc252"] = None
    out = spotlight_rows(rows)
    assert out and out[0]["year_pct"] is None
