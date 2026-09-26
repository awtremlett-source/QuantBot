# qb2 environment — exactly what is installed

Recorded 2026-09-26 from `.venv-qb2` on Python **3.13.7**.

This page is generated from the environment, not typed by hand: every
version below was read back out of `.venv-qb2` after installing
`requirements-qb2.txt`. If the two ever disagree,
`tests/qb2/test_env_smoke.py` fails.

## Create it

```
py -3.13 -m venv .venv-qb2
.venv-qb2\Scripts\python.exe -m pip install -r requirements-qb2.txt
```

Run qb2's tests with that interpreter, never v1's:

```
.venv-qb2\Scripts\python.exe -m pytest tests/qb2 -q
```

**Never install this into `.venv` or `.venv-ui`.** Those are v1's, they are
frozen, and their pins conflict with these on purpose — v1's window runs
pandas 2.x while its engine runs pandas 3.x, which is why v1 needs two
environments and qb2 needs only one.

## The libraries we asked for

| package | pinned in requirements-qb2.txt | installed |
|---|---|---|
| `yfinance` | 1.4.1 | 1.4.1 |
| `pandas` | 3.0.2 | 3.0.2 |
| `numpy` | 2.4.4 | 2.4.4 |
| `pyarrow` | 24.0.0 | 24.0.0 |
| `requests` | 2.33.1 | 2.33.1 |
| `scikit-learn` | 1.8.0 | 1.8.0 |
| `statsmodels` | 0.14.6 | 0.14.6 |
| `matplotlib` | 3.10.8 | 3.10.8 |
| `PySide6` | 6.11.1 | 6.11.1 |
| `pytest` | 9.1.0 | 9.1.0 |
| `hypothesis` | 6.155.3 | 6.155.3 |
| `ruff` | 0.15.17 | 0.15.17 |
| `mypy` | 2.1.0 | 2.1.0 |

Pins checked: **13**. Disagreements: **none — every pin resolved exactly**.

## What came with them

43 further packages were pulled in as dependencies. They are
recorded so a rebuild can be compared line by line:

```
PySide6_Addons==6.11.1
PySide6_Essentials==6.11.1
Pygments==2.21.0
ast_serialize==0.11.2
beautifulsoup4==4.15.0
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
cloudpickle==3.1.2
colorama==0.4.6
contourpy==1.4.0
curl_cffi==0.16.3
cycler==0.12.1
fonttools==4.65.0
idna==3.20
iniconfig==2.3.0
joblib==1.6.0
kiwisolver==1.5.1
librt==0.15.0
multitasking==0.0.13
mypy_extensions==1.1.0
packaging==26.3
pathspec==1.1.1
patsy==1.0.3
peewee==4.5.1
pillow==12.3.0
platformdirs==4.11.11
pluggy==1.6.0
protobuf==7.36.2
pycparser==3.0
pyparsing==3.3.3
python-dateutil==2.9.0.post0
pytz==2026.3.post1
scipy==1.18.1
shiboken6==6.11.1
six==1.17.0
sortedcontainers==2.4.0
soupsieve==2.9.2
threadpoolctl==3.7.0
typing_extensions==4.16.0
tzdata==2026.4
urllib3==2.8.0
websockets==17.1
```

## The point of this file

A library version is part of what produces a track record. Writing the
resolved set down means a result can be reproduced later, and a rebuild
that quietly resolves differently can be spotted rather than discovered
after it has changed a number.
