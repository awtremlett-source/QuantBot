# WI-0001: independent review of the first version (commit c31bbac, since replaced)

A fresh agent that did not write the work, 2026-11-08. Its report, as delivered. The corrections are
in docs/reports/WI-0001.md.

# Adversarial review of WI-0001 (commit c31bbac)

**Result: of the 19 ENFORCED bullets, 2 are UPHELD, 14 PARTLY and 3 REFUTED.** All five gates exist, but each is weaker than ordered, and the commit-door path itself has no test.

**Verdict rule.** UPHELD: the rule as written is held by the named code. PARTLY: a real part is held, but the rule is broader than the check, or a bypass was demonstrated. REFUTED: ordinary use, or the real commit, breaks the rule's core while the named tests stay green.

**Unmodified tree.** All 34 named test nodes: 44 passed, 1 skipped. The two new test files: 1 failed, 77 passed. `test_the_commit_hook_is_wired` was red because `core.hooksPath` had become the absolute path, while the test required `qb2/tools/hooks`.

## One row per ENFORCED bullet

LL = `docs/LESSONS_LEARNED.md`, DS = `docs/DESK_STANDARDS.md`.

| File:line | Rule | Verdict | Evidence |
|---|---|---|---|
| LL:9 | CLAUDE under 120 lines, import live | PARTLY | `is_imported` returned True for an indented block, a `~~~` fence and an HTML comment (B13) |
| LL:10 | At most 200 lines and 14,000 chars | UPHELD | Both tests read the real file and went red on mutants |
| LL:14 | Every rule tagged, names exist, gates listed | PARTLY | Only `- ` lines seen; prose after a tag passes; a second name outside backticks ignored; a name only in a comment counts (B14, B15, B21) |
| LL:16 | Owed count may only fall | PARTLY | Renaming the test file resets the history (B20); deleting or relabelling a rule stays green |
| LL:23 | Diagnose: assumption and evidence | PARTLY | "Measured" means one digit; `evidence="1"`, `evidence_source="."` accepted (B1) |
| LL:26 | Premortem | PARTLY | Five junk words pass; an item about anything can carry a commit to any file (B1, B25) |
| LL:27 | Every change names requirement and check | PARTLY | Read test accepts a closed item the write door refuses (B12); `_commit_msg` and the hook body have no test (B22) |
| LL:31 | Third failed attempt | **REFUTED** | "Failed" recorded nowhere; slug is free text (B4); the ledger itself satisfied "design note" (B5); one open item allows unlimited commits (B6) |
| LL:52 | Seam change deletes old path | PARTLY | Seam key omittable (B10); never-existing path passes at read (B7); rename closes it (B8); change lands first (B9); unstaged delete passes (B23) |
| LL:55 | Size caps count production code | PARTLY | Tests correctly not counted; `manual/` is production with no cap |
| LL:62 | Nothing arms sender or reaches orders | PARTLY | `setattr`, tuple-assign, `from .anchors import`, `requests.post` on a joined URL: wall tests still pass (B18) |
| LL:72 | Queue short, WIP limits | PARTLY | Cap real; tests read the constant so `MAX_OPEN` 50 stays green (B22); GRAND_TODO's 26 rows outside any cap |
| LL:76 | Brief names exact files, failing test, check | **REFUTED** | WI-0001's real row omitted 4 changed files and named one unchanged; an item closes with `assert False` (B2) |
| LL:99 | Requirement open in phase; exceptions shown | PARTLY | "Shown" is one count in `list`, never the name; done rows skip the check (B3, B22) |
| DS:11 | One writer into clean store | PARTLY | The test looks only for `.to_parquet` (B19) |
| DS:16 | One basis, never splice | **REFUTED** | Named tests are about double-counted dividends and column names; production `refetch.py:53,57` produced a real splice nothing refuses (B24) |
| DS:23 | Strategy may not read the future | PARTLY | Only 3 cut points compared; a peeker passes 133 of 1000 random series, an exit-before-a-fall peek 886 of 1000 (B16) |
| DS:33 | Missing brake or pot figure refused | PARTLY | Named cases hold; `View` defaults holdings to `()` and production builds exactly that (`engine.py:46`); unknown owner uncounted; a brake row with null figures passes (B17) |
| DS:34 | Brakes survive restarts | UPHELD | `state()` re-reads the file on every call; forget-on-restart mutant went red |

## The five gates

| Gate | At write | At read | Judgement |
|---|---|---|---|
| 1. Item fields | Yes | Yes, but done rows skip the phase and evidence-source checks, and a first row may already say done (B3) | "Measured" is one digit; "premortem" is 5 words; "verifying check" is a name present in a file, never run |
| 2. Third attempt | Yes, exact slug only | Yes, exact slug only | Counts items, not failures. The ledger counted as the note |
| 3. Seam deletes | `add` needs a real path; `close` refused | Done rows re-checked; open rows not | The change lands before anything refuses it |
| 4. Limits, import, names | Test | Test | Can fail. Weak on import forms, bullet shape and comment-only names |
| 5. Owed ratchet | Test | Test | Catches a plain raise. Beaten by a rename; "falls" on deletion or relabelling |

Cross-cutting: the hook read the ledger from the index but the world from the working tree (B23). Reverts waited for paperwork (B11), including a revert that restores a seam's old path.

## Bypasses demonstrated

- **B1** `add` accepted `evidence="1"` with junk words; `evidence_source="."`; `files=("",)`; a nonexistent file.
- **B2** `close` accepted a check that is `assert False`, and one whose name exists only in a comment.
- **B3** A hand-written first row with status done, requirement S999 and a missing source: `load` accepted it.
- **B4** Third attempt with a varied slug and no note: accepted.
- **B5** Third attempt with `design_note="work/items.jsonl"`: accepted.
- **B6** 20 commits naming one open item: all accepted.
- **B7** Seam row deleting `never/existed.py`: `load` accepted it as open and as done.
- **B8** `old.py` renamed, then `close`: accepted.
- **B9** Seam commit while `old.py` survives: no refusal.
- **B10** Row with no `seam` key: read as `none`.
- **B11** Refused: a revert once the path is back; a revert of a pre-gate commit; a revert after S6 leaves the phase.
- **B12** Commit naming a closed item: write door refuses, the read test passes it.
- **B13** `is_imported` True for indented, `~~~` and HTML-comment forms.
- **B14** `tag_faults` empty for a `*` bullet, an indented bullet, and prose after the tag.
- **B15** `enforced_faults` empty for a comment-only name, a second name outside backticks, an ENFORCED line naming only a `.md`.
- **B16** Look-ahead pass rates 133 of 1000 and 886 of 1000, through production `checked_weights`.
- **B17** `pots.check(BOT, 10.0, pots.View(10_000.0))` accepted; an owner `""` line worth 5x the limit accepted; a brake row with level OK and null figures passed `check_buy`.
- **B18** A planted file with `setattr`, tuple-assign, relative import and joined-URL `requests.post`: wall tests pass.
- **B19** A planted `pq.write_table` writer: the one-writer test passes.
- **B20** Test file renamed, ceiling raised, one owed rule added: passes. Relabel or delete with a lowered ceiling: passes.
- **B21** Enforced test renamed, old name left in a comment: passes.
- **B22** `_commit_msg` returning `[]`, hook `|| true`, `list` print removed, `MAX_OPEN` 50, `MIN_WORDS` 2: no new failure.
- **B23** Seam item, unstaged working-tree delete, only the ledger staged: the door passed with the path still in the index.
- **B24** Stored 200 a share, re-fetched after a split at 100, one day sent broken: production `refetch.merge` gave closes 100, 100, 200, 100, 100. `impossible_rows` and `cross_bar.found` found nothing.
- **B25** Real hook: message naming nothing refused; `WI-0001: rewrite anything at all, unrelated to the item` accepted.

Not demonstrated: an actual `--no-verify` commit, because of the no-commit fence.

## Counts

UPHELD 2 · PARTLY 14 · REFUTED 3 (of 19).
