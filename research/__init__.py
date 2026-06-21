"""research: the honest track-record engine, and (next) the validation firewall.

This package currently houses the backtester (:mod:`research.backtester`) and the
Strategy contract + reference strategies (:mod:`research.strategy`). It reads the
CLEAN price series the rest of the system trusts and never writes to the store.

The §7 validation firewall + known-null birth-certificate layer is the NEXT brick
and will sit ON TOP of this engine -- it is deliberately NOT built here. The
backtester is the foundation that firewall will exercise and trust.
"""

from __future__ import annotations
