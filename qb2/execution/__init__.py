"""The broker doorway: batched demo orders, throttle, killswitch, fill recorder.

DEMO only until graduation. Every order records expected price against actual
price, and that gap feeds the cost model with a safety margin, because demo fills
are kinder than real ones. Empty until the execution stage.
"""
