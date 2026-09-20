"""The wall: tests that keep the manual app and the trading engine apart.

Two books, one wall, one direction. The engine never learns that the manual
app exists; the manual app may read the engine's books and may never write
them. Every test here ships with a red-on-broken proof against a planted
violation kept in tests/museum/wall_violations/ (SCARS #9: a monitor nobody
has seen go red is not a monitor).
"""
