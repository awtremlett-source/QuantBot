"""The manual paper-trading app (TradeScout), walled off from the engine.

It is a DECISION AID the operator drives by hand: it places no orders, holds
no broker credentials, and cannot write to the bot's books. The one doorway
to engine data is manual/bot_readonly.py, and it only ever reads.
"""
