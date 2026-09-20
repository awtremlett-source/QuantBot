"""Configuration loading for TradeScout.

All values are user-editable in config.json at the project root. Tax-related
values (stamp_duty_pct, ptm_levy_gbp, ptm_threshold_gbp) are CONFIG, not
claims about current law -- verify current HMRC / PTM rates yourself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

# The manual app lives INSIDE the QuantBot repo but keeps its own books.
# PACKAGE_ROOT = manual/ (shipped files); STATE_DIR = the only place it
# writes state -- data/manual/, gitignored, never the engine's data/.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_ROOT.parent
STATE_DIR = REPO_ROOT / "data" / "manual"
CONFIG_PATH = PACKAGE_ROOT / "config.json"

DEFAULTS = {
    "bankroll_gbp": 10000,
    "risk_pct": 1.0,
    "atr_stop_mult": 2.0,
    "history_period": "2y",
    "chunk_size": 40,
    "chunk_pause_s": 2.0,
    "min_turnover_gbp": 1_000_000,
    "stamp_duty_pct": 0.5,
    "ptm_levy_gbp": 1.0,
    "ptm_threshold_gbp": 10000,
    "top_n": 25,
    "live_interval_min": 2,
}


@dataclass
class Config:
    bankroll_gbp: float = DEFAULTS["bankroll_gbp"]
    risk_pct: float = DEFAULTS["risk_pct"]
    atr_stop_mult: float = DEFAULTS["atr_stop_mult"]
    history_period: str = DEFAULTS["history_period"]
    chunk_size: int = DEFAULTS["chunk_size"]
    chunk_pause_s: float = DEFAULTS["chunk_pause_s"]
    min_turnover_gbp: float = DEFAULTS["min_turnover_gbp"]
    stamp_duty_pct: float = DEFAULTS["stamp_duty_pct"]
    ptm_levy_gbp: float = DEFAULTS["ptm_levy_gbp"]
    ptm_threshold_gbp: float = DEFAULTS["ptm_threshold_gbp"]
    top_n: int = DEFAULTS["top_n"]
    live_interval_min: int = DEFAULTS["live_interval_min"]

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Path | None = None) -> Config:
    """Load config.json, tolerating a missing or partial file."""
    path = path or CONFIG_PATH
    values = dict(DEFAULTS)
    if path.exists():
        try:
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            for key in values:
                if key in on_disk:
                    values[key] = on_disk[key]
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults; never crash the app on bad config
    else:
        try:
            path.write_text(json.dumps(values, indent=2), encoding="utf-8")
        except OSError:
            pass
    return Config(**values)
