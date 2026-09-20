# Typing debt — the manual app

Recorded 2026-09-20 (merge stage 3a). `mypy --strict .` is GREEN repo-wide, and
this page is the price of that: 52 real type errors in five inherited modules
are silenced by an explicit `ignore_errors` list in `pyproject.toml`.

Silenced, not fixed, and **not hidden** — the list is short, named module by
module, and uses no wildcard, so it is obvious what is uncovered.

## Where the 52 sit

| file | errors | what they are |
|---|---:|---|
| `manual/scout/scoring.py` | 34 | 31 `operator`, 2 `assignment`, 1 `arg-type` |
| `manual/scout/config.py` | 15 | 12 `assignment`, 3 `arg-type` |
| `manual/scout/store.py` | 1 | `arg-type` |
| `manual/scout/journal.py` | 1 | `return-value` |
| `manual/scout/data.py` | 1 | `type-var` |
| **total** | **52** | |

## What each class actually is

* **`scoring.py`, 31 × `operator`** — comparisons like `close <= sma200` where
  both sides are `float | None`. The code IS guarded, by its own `_ok()`
  helper, but `_ok()` returns a plain `bool`, so mypy cannot narrow the type
  through it. FIX: make `_ok` a `TypeGuard`. Then most of these vanish at once
  and the remainder are worth reading individually.
* **`config.py`, 12 × `assignment` + 3 × `arg-type`** — the `DEFAULTS` dict
  holds mixed value types, so it infers as `dict[str, object]`, and every
  dataclass field default taken from it looks like `object` assigned to
  `float`. FIX: a `TypedDict` for `DEFAULTS`, or literal field defaults.
* **the three singletons** — `store.py` calls `int()` on a `COUNT(*)` that mypy
  types as `int | None`; `journal.py` returns `get_trade()`'s `dict | None`
  from a function declared `-> dict`; `data.py` calls `min()` over
  `str | None`. Each is an invariant the code guarantees and the types do not
  express. None is known to misbehave — but this class of error is exactly
  where a real `None` bug hides, so they are worth doing properly.

## The cost of the deferral

`ignore_errors` silences FUTURE errors in those five files too. Anyone editing
`scoring.py`, `config.py`, `store.py`, `journal.py` or `data.py` gets no type
checking at all until this is burned down. Everything else under `manual/` IS
checked, at mypy's default level.

Two modules are deliberately held to full `--strict` regardless, because they
are the safety-critical ones: `manual/bot_readonly.py` (the only way to read
the engine's books) and `manual/bot_governance.py` (the only way to launch an
engine command). Both pass.

## Burn-down plan

1. `_ok()` as a `TypeGuard` in `scoring.py` — biggest win for the least risk.
2. `TypedDict` for `config.py`'s `DEFAULTS`.
3. The three singletons, each with a test that pins the invariant.
4. Delete this file and the `ignore_errors` block together.

Not scheduled into a stage yet. It is quality debt, not a blocker: the engine
stays at `--strict`, and nothing here touches the trading engine.
