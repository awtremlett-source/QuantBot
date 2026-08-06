"""Monitors -- meters that OBSERVE the system and report; they never act.

LAW: a monitor's only output is a status line. It places no orders, cancels
nothing, deletes nothing, and never mutates the store -- the killswitch stays
the HUMAN's lever. And per SCARS #9, no meter is trusted until it has proven it
turns RED on a broken fixture (its birth certificate lives in the tests).
"""
