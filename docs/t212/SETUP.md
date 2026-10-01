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

## Two things the key cannot currently do (2026-09-30)

When the key was tested against the practice account, it could read the account
and the portfolio, but three endpoints came back "403 Forbidden": orders,
instruments and exchanges. That means the key was granted **account data** and
**portfolio** permissions only.

**The good news:** a key that cannot even *read* orders cannot *place* one. That
is the strongest read-only evidence available without ever trying to send an
order, which this project does not do.

**The cost:** we cannot download Trading 212's list of tradable instruments, so
the recording list in `docs/RECORDING_LIST.md` is not checked against what T212
actually offers. Names on it may not be tradable there.

### If you want to close that gap

Generate a new practice key with the **instruments / metadata** permission ticked
as well (and **history**, if you would like the check below done automatically),
then paste it into `.env` exactly as before. Nothing else changes.

## The manual check for "one position per share" (FACTS row g)

We still cannot prove whether buying the same share twice makes **one** position
or **two**. The account currently holds 10 shares in 10 separate rows, which
points strongly at one-row-per-share, but none of them is known to have been
bought twice, and the key cannot read order history to find out.

It matters because the bot and the advisor must never hold the same share: if
two buys became two separate positions, one part's sell could close the other
part's holding.

**Two minutes in the Practice app settles it:**

1. Pick the cheapest share you already hold, or any cheap one.
2. Buy **1 share**.
3. Buy **1 more share** of the same thing.
4. Tell Claude Code: **"check 2g"**.

It will read your positions and report whether that share appears as one row
with a quantity of 2, or as two rows of 1. Either answer is useful; the guessing
is what is not.
