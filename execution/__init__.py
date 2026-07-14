"""execution: the paper-trading layer -- validated strategies on pretend money.

This package trades the SAME fill discipline the firewall validated (decide on a
completed bar, fill at the NEXT bar's open, slippage inside) against a local
paper book journaled in the data store. The T212 demo client is a LATER brick;
nothing here talks to a broker. research/ logic is consumed, never modified.
"""

from __future__ import annotations
