"""Tests for qb2. They run on .venv-qb2, not on v1's .venv.

The environment smoke test is deliberately strict: it asserts the versions
actually installed match requirements-qb2.txt, so "it works on my machine" can
never quietly mean a different set of libraries.
"""
