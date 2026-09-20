"""Engine fingerprint -- proof that the trading engine did not move.

The paper engine is running a FORWARD track record. A merge, a linter-on-save
or a stray formatter that silently rewrites an engine file would corrupt that
record's provenance without touching a single test. This tool takes a SHA-256
of every source file in the engine folders plus the engine config files, sorts
them by path, and folds path+digest into ONE combined hash.

Use it as a before/after clamp around any risky repo surgery: run it before,
run it after, and require the combined hash to be IDENTICAL. Because the path
is hashed alongside the digest, a rename is caught as loudly as an edit.

The report is deterministic ON PURPOSE -- no timestamps, no absolute paths --
so two runs of an untouched engine produce byte-identical files and a plain
``diff before.txt after.txt`` is the whole proof.

EXCLUDED: ``__pycache__`` and ``*.pyc``/``*.pyo``. They are rebuilt on every
import, hold no source of truth, and would make the fingerprint unreproducible.

CLI: ``python -m tools.engine_fingerprint [--root DIR] [--out FILE]
      [--expect HASH]``  (exit 1 if --expect is given and does not match)
"""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from pathlib import Path

# The engine: every folder whose behaviour the live paper record depends on.
ENGINE_DIRS: tuple[str, ...] = (
    "data_store",
    "execution",
    "ingest",
    "monitors",
    "reconcile",
    "research",
    "risk",
    "strategies",
    "tools",
)

# Engine config: what the engine installs, lints and type-checks against.
ENGINE_FILES: tuple[str, ...] = (
    ".env.example",
    "install.ps1",
    "pyproject.toml",
    "requirements.txt",
)

EXCLUDED_DIRS = frozenset({"__pycache__"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo"})


class FingerprintError(RuntimeError):
    """A folder or config file the fingerprint must cover is missing."""


def engine_paths(root: Path) -> list[Path]:
    """Every file the fingerprint covers, sorted by repo-relative POSIX path."""
    found: list[Path] = []
    for name in ENGINE_DIRS:
        folder = root / name
        if not folder.is_dir():
            raise FingerprintError(f"engine folder missing: {name}")
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if EXCLUDED_DIRS.intersection(relative.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            found.append(path)
    for name in ENGINE_FILES:
        path = root / name
        if not path.is_file():
            raise FingerprintError(f"engine config missing: {name}")
        found.append(path)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def fingerprint(root: Path) -> tuple[str, list[tuple[str, str, int]]]:
    """Return (combined_hash, rows) where rows = (rel_path, sha256, bytes)."""
    combined = hashlib.sha256()
    rows: list[tuple[str, str, int]] = []
    for path in engine_paths(root):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        rows.append((relative, digest, len(payload)))
        # Hash the PATH too: a rename must break the fingerprint.
        combined.update(relative.encode("utf-8"))
        combined.update(b"\0")
        combined.update(digest.encode("ascii"))
        combined.update(b"\n")
    return combined.hexdigest(), rows


def report(root: Path) -> str:
    """The deterministic report written to docs/merge/fingerprint_*.txt."""
    combined, rows = fingerprint(root)
    lines = [
        "QuantBot ENGINE FINGERPRINT",
        "",
        f"folders: {', '.join(ENGINE_DIRS)}",
        f"config:  {', '.join(ENGINE_FILES)}",
        "excluded: __pycache__, *.pyc, *.pyo (generated, not source)",
        "",
        f"files: {len(rows)}   bytes: {sum(size for _, _, size in rows)}",
        "",
    ]
    lines += [f"{digest}  {size:>9}  {path}" for path, digest, size in rows]
    lines += ["", f"COMBINED: {combined}", ""]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="engine_fingerprint",
        description="SHA-256 fingerprint of the engine folders + engine config.",
    )
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="repo root (default: current directory)")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the full report here as well as stdout")
    parser.add_argument("--expect", default=None,
                        help="combined hash to require; exit 1 on mismatch")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    text = report(root)
    combined, _ = fingerprint(root)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    print(f"COMBINED: {combined}")

    if args.expect is not None and args.expect != combined:
        print(f"MISMATCH: expected {args.expect}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
