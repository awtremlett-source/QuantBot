# Getting your practice API key into the system

Ten minutes, once. Nothing in this guide can place a trade: the only code that
talks to Trading 212 right now can read, and there is no function in it that
could buy or sell anything.

You need the **practice** (demo) account key, not the real one. Trading 212's own
help centre notes that "API Key versions may differ between real and demo
accounts", so generate it while you are in the practice account.

## 1 — Make the key, in the phone app

The key is generated in the mobile app, not on the website.

1. Open the Trading 212 app and switch to your **practice** account.
2. Tap the **☰** menu.
3. **Settings**.
4. **API (Beta)**.
5. **Generate API key**.
6. Look at the permissions it offers (account data, history, orders, portfolio).
7. For where it can be used from, choose **"Restrict access to trusted IPs
   (recommended)"** if you can. "Unrestricted" works but is less safe.

You will be shown two values: an **API Key** and an **API Secret Key**.

> **The secret is shown once.** Trading 212's words: it "works like a password
> and will be shown only once after generation." If you lose it you cannot look
> it up — you have to generate a new pair. So do step 2 before you close the app.

## 2 — Put them in `.env`

In the folder `C:\Users\mtrem\TRADING` there is a file called `.env`. Open it in
Notepad. You will find these two lines already there, empty:

```
T212_API_KEY=
T212_API_SECRET=
```

Paste each value after its `=`, with no quotes and no spaces:

```
T212_API_KEY=the-key-it-showed-you
T212_API_SECRET=the-secret-it-showed-you
```

Save and close.

`.env` is deliberately kept out of version control, so these never leave your
machine. Nothing in this project prints them, logs them, or puts them in an error
message — there is a test that checks the repo for them and fails if any value
from `.env` ever appears in a file we wrote.

## 3 — Check it worked

From the repo folder, run:

```
.venv-qb2\Scripts\python.exe -m pytest tests/qb2 -q -rs
```

- **Before** you add the keys, one test is skipped and tells you why:
  `no T212 practice credentials in .env`. That is not a failure.
- **After** you add them, that test runs, reads your practice account, and prints
  a line like `connected: yes, 12000 instruments, 3 positions`.

If it says something else, the message will tell you what — it will never guess.

## What this does and does not do

**It reads:** your account cash and value, your open positions, any pending
orders, the list of tradable instruments, and exchange trading hours.

**It cannot trade.** There is no method to place, change or cancel an order, and
the single function that touches the network refuses every request type except a
read. That is checked by tests in `tests/wall/`, so it stays true.

**It only ever talks to the practice environment.** The real-money address does
not appear anywhere in the new code — not even commented out — and a test fails if
it ever does. Real money is deliberately the last thing that happens, after the
system has been moved to the always-on PC (see `docs/plan/PLAN_V3.md`, stages S13
and S14).

## Two things worth knowing about the API itself

Both came out of reading Trading 212's documentation, and both changed the plan.
The full list with sources and dates is in [FACTS.md](FACTS.md).

1. **Trading 212 has no "trailing stop" order.** So the moving stop you asked for
   cannot be parked at the broker — our own code has to run it. That is why the
   move to an always-on PC comes *before* real money: a stop run by our code can
   only watch prices while the machine is awake.
2. **The API will not tell us the price of a share you do not already own.** It
   only reports a price for something in your portfolio. So checking a price
   before buying something new has to lean on our own data, which is the next
   stage's problem to solve honestly.

---

## What the key is allowed to do (2026-10-01)

You replaced the key on 2026-10-01 and deleted the old one. You described its
permissions, in your own words:

> **"Orders – Execute OFF, Pies – Write OFF"**

Tested against the practice account with GET requests only, **all ten documented
read endpoints are granted**: account summary, cash and info; positions; orders;
instruments; exchanges; and the three history endpoints. That is wider than the
previous key, which was 403 on five of them.

**No order can be placed, for two independent reasons.** Execute is OFF at Trading
212's end, and the client in this repository physically cannot send anything but a
GET — a test takes networking away entirely and proves the refusal happens *before
a socket is even opened*. Either reason alone would be enough; we keep both.

**Two gaps from 2026-09-30 are now closed:**

- Trading 212's instrument list has been downloaded and saved
  (`data/raw/t212/instruments-2026-10-01.json`, 18,483 rows). Every name we record
  is now checked against it — see `docs/universe/README.md`, which is worth reading:
  the check found that four of our old names were wrong, one of them a company that
  had become a different company.
- Order history is readable, which settled the question below without you having to
  do anything.

### If the key ever stops working

Keys can be revoked or expire. The symptom is `401` on every endpoint. Generate a
new practice key with the same permissions (**Execute OFF**), paste it into `.env`
in place of the old one, and delete the old key at Trading 212's end. Nothing else
changes, and nothing in this project ever prints the key.

## "One position per share" — SETTLED (FACTS row g)

**You do not need to do anything. The answer is one position.**

This was an open question on 2026-09-30: if buying the same share twice created
*two* positions, then one part of the system selling could close the other part's
holding. The two-minute manual check that used to be written here is no longer
needed — the new key can read order history, and the practice account already
contained the decisive case:

`MU_US_EQ` has **two separate filled BUY orders** (12.5711224 and 10.0) and one
filled SELL (10.0). The positions endpoint returns it as **exactly one row, with a
quantity of 12.5711224** — the net of all three.

So Trading 212 aggregates. A second buy of something you already hold adds to the
existing position; there is no second row and no position id to track. "How much do
I hold?" is always one number, found by the ticker alone.

## A second key, for the P20 anchors — only when you are ready to say "GO QT-12 LIVE"

**Nothing in this section is needed yet.** The anchor buyer (QT-12) has been built
and dry-run with the read-only key. It buys nothing until you make this second key
and say the words.

Why a *second* key: the key you already have is read-only (Execute OFF), and it
should stay that way, because the recorder and every other part of the program use
it. The anchor buyer is the only part allowed to place an order, so it gets its own
key, which no other file in the project is allowed to read (a test enforces that).

1. In the phone app, switch to your **practice** account (not real money).
2. **☰ → Settings → API (Beta) → Generate API key** — a NEW key; do not edit or
   delete the existing one.
3. Tick exactly these two permissions and leave every other one off:
   - **Orders – Execute** — this is the permission that allows placing an order
     (Trading 212's API calls it `orders:execute`);
   - **Account data** — so the program can check, before buying anything, that the
     key belongs to a practice account in pounds.
4. Choose "Restrict access to trusted IPs (recommended)" if you can.
5. Add **two new lines** to `.env` (keep your existing `T212_API_KEY` and
   `T212_API_SECRET` lines exactly as they are):

```
T212_ORDER_KEY=the-new-key
T212_ORDER_SECRET=the-new-secret
```

Never paste either value into a chat. The program refuses to run if the order key
is the same as the read-only key.

**What it will do with it:** buy about £1 of each bot name the practice account
does not already hold — never more than £3 per order, £100 in total for its whole
life, 50 orders a day — only while that name's own market is open, and never sell.
It talks only to the practice server and refuses the real-money server outright.
