"""First light: the first pictures drawn from the clean store.

The point is not the pictures. The point is that a chart is the cheapest honest
test of a data pipeline -- a human eye catches a 100x step, a flat line, a weekend
that contains trading, or a price in the wrong currency faster than any assertion
we would have thought to write. PLAN_V3's S3 exit gate asks for exactly this: "a
chart renders from clean data".

Two rules this file keeps:

* **CLEAN only.** Nothing here opens anything under ``data/raw``. If a chart can
  only be drawn from raw bars, the front door has not done its job and that is the
  thing to fix. The guard is a test, not a promise.
* **The axis says the unit.** Every price axis is labelled with the currency the
  rows actually carry, read from the data rather than assumed, because the whole
  pence-versus-pounds problem (FACTS row r) is invisible on an unlabelled axis.

Drawing happens inside the functions, never at import. The wall (tests/wall)
forbids a module-level call anywhere in qb2, and it is right to: a module that does
work simply by being imported is a module that can surprise anything that imports
it. Choosing the headless backend is such a call, so it lives in ``_pyplot()``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from qb2.data.front_door import CLEAN

if TYPE_CHECKING:                            # pragma: no cover - typing only
    from qb2.data.census import Census

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS = REPO_ROOT / "reports" / "first_light"


def _pyplot() -> Any:
    """matplotlib, set to draw to a file rather than to a screen.

    Called inside the chart functions, not at import: this machine runs the
    recorder from a scheduler with no desktop session, where a backend that wants
    a display fails outright.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def load_clean(symbol: str, interval: str = "5m",
               clean_root: Path | None = None) -> pd.DataFrame:
    """Every clean bar for one name, in time order. Raises if there are none."""
    folder = (clean_root or CLEAN) / "bars" / interval / symbol
    files = sorted(folder.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(
            f"no clean {interval} bars for {symbol} in {folder} -- run the front "
            "door (python -m qb2.data.front_door) before drawing charts")
    frame = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
    return frame[~frame.index.duplicated(keep="first")]


def unit_of(frame: pd.DataFrame) -> str:
    """The currency the rows carry. Never guessed from the ticker."""
    if "currency" not in frame.columns:
        return "?"
    found = sorted({str(c) for c in frame["currency"].unique()})
    if len(found) > 1:
        # A single series in two currencies is exactly the silent 100x bug.
        raise ValueError(
            f"these bars carry more than one currency ({found}): refusing to draw "
            "a chart that would put two units on one axis")
    return found[0]


def price_chart(symbols: tuple[str, ...] = ("BP.L", "AAPL"),
                interval: str = "5m", clean_root: Path | None = None,
                out_dir: Path | None = None) -> Path:
    """One panel per name: the price, in its own currency, over everything we hold."""
    plt = _pyplot()
    target = (out_dir or REPORTS)
    target.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(len(symbols), 1, figsize=(11, 3.2 * len(symbols)),
                               sharex=False)
    if len(symbols) == 1:
        axes = [axes]

    for axis, symbol in zip(axes, symbols, strict=True):
        frame = load_clean(symbol, interval, clean_root)
        unit = unit_of(frame)
        axis.plot(frame.index, frame["close"], linewidth=0.7)
        axis.set_title(f"{symbol} -- {len(frame):,} clean {interval} bars, "
                       f"{frame.index.min().date()} to {frame.index.max().date()}",
                       fontsize=10)
        axis.set_ylabel(f"close ({unit})")
        axis.grid(alpha=0.25, linewidth=0.5)

    figure.suptitle(f"FIRST LIGHT -- drawn from the clean store only, "
                    f"{date.today().isoformat()}", fontsize=11)
    figure.tight_layout()
    path = target / f"price-{interval}-{date.today().isoformat()}.png"
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def coverage_chart(interval: str = "5m", clean_root: Path | None = None,
                   out_dir: Path | None = None,
                   taken: "Census | None" = None) -> Path:
    """How complete each name is, sorted worst-first -- where the holes are.

    Worst-first on purpose. A chart sorted best-first flatters the data: the eye
    reads the top and stops. The names that matter are the ones at the bottom.
    """
    from qb2.data import census as census_module

    plt = _pyplot()
    target = (out_dir or REPORTS)
    target.mkdir(parents=True, exist_ok=True)
    if taken is None:
        taken = census_module.take(interval, clean_root=clean_root)
    names = sorted(taken.names, key=lambda n: n.completeness)
    colours = ["tab:red" if not n.passes else "tab:green" for n in names]
    # A name with NO data has a bar of height zero, which draws as nothing at all
    # -- so the chart would show empty space exactly where the problem is. Failures
    # are given a visible stub instead, and the count is written on the chart so
    # the stub cannot be mistaken for a real measurement.
    stub = 0.015
    values = [max(n.completeness, stub) if not n.passes else n.completeness
              for n in names]
    empty = sum(1 for n in names if n.bars_present == 0)

    figure, axis = plt.subplots(figsize=(12, 4.2))
    axis.bar(range(len(names)), values, color=colours, width=1.0)
    if empty:
        axis.annotate(
            f"{empty} names have NO data at all -- the red stubs below",
            xy=(empty / 2, 0.06), xytext=(empty / 2, 0.42),
            ha="center", fontsize=9, color="tab:red",
            arrowprops={"arrowstyle": "->", "color": "tab:red", "linewidth": 1})
    axis.axhline(census_module.PASS_COMPLETENESS, color="black", linestyle="--",
                 linewidth=1,
                 label=f"pass mark {census_module.PASS_COMPLETENESS:.0%}")
    axis.set_ylabel(f"share of expected {interval} bars present")
    axis.set_xlabel(f"{len(names)} names, least complete first")
    axis.set_title(
        f"DATA CENSUS -- {len(taken.passing)} of {len(taken.names)} pass "
        f"({taken.fraction_passing:.1%}); plan asks "
        f"{census_module.UNIVERSE_PASS_FRACTION:.0%} -- {taken.verdict}",
        fontsize=11)
    axis.legend(fontsize=8)
    axis.grid(alpha=0.25, axis="y", linewidth=0.5)
    figure.tight_layout()
    path = target / f"census-{interval}-{date.today().isoformat()}.png"
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def main() -> None:
    for path in (price_chart(), coverage_chart()):
        print(f"wrote {path.relative_to(REPO_ROOT)} "
              f"({path.stat().st_size/1024:,.0f} KiB)")


if __name__ == "__main__":
    main()
