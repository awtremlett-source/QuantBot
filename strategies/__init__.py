"""Strategy library -- one file per strategy family.

Every strategy here implements the research/ contracts
(:class:`research.strategy.Strategy` and :class:`research.strategy.TunableStrategy`)
and must pass the FULL §7 validation firewall (backtest + walk-forward + Monte
Carlo) before it is anything more than a spare part. Being in this package does
NOT mean a strategy trades: the paper loop runs ONLY the frozen champion in
``execution/config.py``.
"""
