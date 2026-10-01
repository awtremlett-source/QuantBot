"""Read index membership out of a saved public page. Never off the network.

Two rules shape this file.

**The fetch and the parse are separate.** Something else downloads the page and
writes it to ``data/raw/reference/`` with its URL, date and sha256 in a manifest;
this module only ever reads that saved copy. So the universe can be rebuilt years
from now from the bytes we actually read, and a disagreement can be traced to the
source rather than argued about.

**No summarising model stands between us and the table.** An earlier attempt asked
a model to read the S&P 500 table and it invented several hundred ticker symbols
that do not exist (TOZZ, TOYZ, ...). Membership is a list of facts, so it is parsed
mechanically, and every name is then checked against Trading 212's own instrument
list before it can enter a universe.

A caveat that belongs in every result built from these pages: they give **today's**
membership. A back-test over past years that uses today's index members has
survivorship bias built in -- the companies that failed have been quietly removed
from history. See ``SURVIVORSHIP_CAVEAT``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_RAW = REPO_ROOT / "data" / "raw" / "reference"

SURVIVORSHIP_CAVEAT = (
    "Membership is TODAY's membership. Any back-test run over past years using "
    "this list is biased upward, because companies that fell out of the index "
    "(or failed) are absent from it. Treat every result built on it as an "
    "OPTIMISTIC bound, and mark it down (S4 carries the survivorship mark-down)."
)


@dataclass(frozen=True, slots=True)
class Source:
    """Where a membership list came from, so a result can cite it."""

    what: str
    url: str
    retrieved: str
    sha256: str
    rows: int


class _TableGrabber(HTMLParser):
    """Collect every row of every <table> as lists of cell text. No cleverness."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table":
            if self._depth == 1 and self._table is not None:
                self.tables.append(self._table)
                self._table = None
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def tables_in(html: str) -> list[list[list[str]]]:
    parser = _TableGrabber()
    parser.feed(html)
    return parser.tables


def _table_with_column(tables: list[list[list[str]]],
                       wanted: tuple[str, ...]) -> tuple[list[list[str]], int]:
    """The first table whose header row holds one of ``wanted``, and that column."""
    for table in tables:
        if not table:
            continue
        header = [cell.strip().lower() for cell in table[0]]
        for name in wanted:
            if name in header:
                return table, header.index(name)
    raise LookupError(f"no table with a column in {wanted}")


# A ticker is upper-case letters, with the odd dot or dash (BRK.B, BT.A).
TICKER = re.compile(r"^[A-Z][A-Z0-9]{0,5}(?:[.\-][A-Z0-9]{1,2})?$")


def symbols_from(path: Path, column: tuple[str, ...]) -> list[str]:
    """Every ticker-shaped value in the named column of the first matching table."""
    table, index = _table_with_column(
        tables_in(path.read_text(encoding="utf-8", errors="replace")), column)
    out: list[str] = []
    for row in table[1:]:
        if len(row) <= index:
            continue
        value = row[index].strip()
        if TICKER.match(value) and value not in out:
            out.append(value)
    return out


def newest(what: str, folder: Path | None = None) -> Path:
    base = folder or REFERENCE_RAW
    found = sorted(base.glob(f"{what}-*.html"))
    if not found:
        raise FileNotFoundError(f"no saved {what} page in {base}")
    return found[-1]


def sp500(folder: Path | None = None) -> list[str]:
    """S&P 500 members, as yfinance spells them (BRK.B -> BRK-B)."""
    raw = symbols_from(newest("sp500", folder), ("symbol", "ticker"))
    return [s.replace(".", "-") for s in raw]


def ftse100(folder: Path | None = None) -> list[str]:
    """FTSE 100 members as yfinance spells them: EPIC + ".L"."""
    raw = symbols_from(newest("ftse100", folder), ("ticker", "epic", "symbol"))
    # "BT.A" is "BT-A.L" to yfinance: the share class takes a dash, not a dot,
    # because the dot already means "London".
    return [f"{s.replace('.', '-')}.L" for s in raw]
