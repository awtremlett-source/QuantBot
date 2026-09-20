# Planted wall violations — kept so the wall can be seen going red

These files are NOT code. Each one is a deliberate violation of one wall rule,
stored with a `.txt` extension so nothing imports, lints or type-checks it.

Every test in `tests/wall/` points its own scanner at the matching fixture and
asserts it goes RED. That is the birth certificate (SCARS #9): a check nobody
has watched fail is not a check. If a fixture ever stops tripping its test,
the scanner has rotted — fix the scanner, never the fixture.

| fixture | trips |
|---|---|
| `engine_imports_manual.py.txt` | `test_engine_never_imports_manual.py` |
| `manual_writes_bot.py.txt` | `test_manual_cannot_write_bot.py` |
| `requirements_with_ui.txt` | `test_engine_install_is_headless.py` |
| `installer_with_ui.ps1.txt` | `test_engine_install_is_headless.py` |
| `forbidden_token.py.txt` | `test_forbidden_paths.py` |

The violations are real ones, written the way they would actually arrive: a
convenience import, a "quick fix" straight into the bot's database, a pip
dependency added to the wrong file.
