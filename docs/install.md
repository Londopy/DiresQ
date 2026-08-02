# Running it

Ten minutes from a clean machine to a working board with a responder already
overdue on it.

---

## What you need

Python **3.10 or newer**. That's it — no database server, no Node, no Docker.
The database is a file.

Node 22 is only needed if you want to build this documentation site, which is
a separate thing under `site/` and not required to run the app.

```bash
python --version
```

If that says 3.9 or lower, install a newer Python before going further.

## Get it running

```bash
git clone https://github.com/Skythe7/DiresQ.git
cd DiresQ

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

flask --app app init-db
flask --app app seed
flask --app app run --debug
```

Open <http://127.0.0.1:5000> and sign in as **`londo`** with the password
**`diresq`**.

**Use the virtual environment.** Skipping it works right up until
`pip install -r requirements.txt` silently downgrades the Flask your other
projects rely on. We know because we did it.

## What the commands do

| Command | What it does |
| --- | --- |
| `init-db` | Drops every table and rebuilds from `schema.sql`. **Destructive.** |
| `seed` | Loads an incident already two hours old |
| `sweep` | Files reports for anyone gone quiet. Also runs on page loads |
| `node-key <user>` | Shows or `--rotate`s a responder's radio key |

`init-db` really does drop everything. There are no migrations — a schema
change means rebuilding, which is fine at this size and would not be fine in
production.

## What you should see

The seed loads a disaster **already in progress**, not an empty to-do list.
That's deliberate: an empty board makes this look like a task tracker.

Straight after seeding:

- **The feed** has eight Katy-area reports. Notice the car-in-a-creek with
  four people on it sitting *below* three reports nobody has touched.
- **The banner** at the top counts reports nobody is going to at all.
- **The board** has `s.reyes` in red, 47 minutes out of contact.
- **The nav badge** shows `1`, on every page.
- **Within a page load or two**, a new HIGH report appears that nobody filed:
  *"No contact from s.reyes for 47 minutes."* That's the dead man's switch.

If the board is empty or the feed has five reports instead of eight, you're
running an old database — run `init-db` and `seed` again.

## Accounts

Every seeded account uses the password `diresq`.

| Username | Role | Capabilities |
| --- | --- | --- |
| `londo` | responder | boat, medical |
| `skythe` | responder | truck, chainsaw |
| `m.torres` | responder | boat, swiftwater |
| `j.okafor` | responder | truck, chainsaw, generator |
| `d.nguyen` | responder | medical |
| `s.reyes` | responder | boat, medical — *the overdue one* |
| `kiyan` | reporter | — |
| `a.whitlock` | reporter | — |

## Configuration

Copy `.env.example` to `.env`. Real environment variables beat the file, so
your shell and CI always win.

| Variable | Purpose |
| --- | --- |
| `DIRESQ_SECRET_KEY` | Signs session cookies. Without it a fresh key is generated every boot, which signs you out on every reload |
| `DIRESQ_DEV_USER` | Stay signed in as this user with no login. **Full auth bypass — development only** |
| `DIRESQ_DB` | Path to the SQLite file. Defaults to `diresq.db` |
| `DIRESQ_HTTPS_ONLY` | Set to `1` behind HTTPS so cookies are marked Secure. Leave unset on localhost or you won't stay signed in |

Generate a key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Seeing the interesting bits

**The offline queue.** Open a report page, DevTools → Network → tick
**Offline**, press *Check in*. The button says "Saved — will send" and a pill
appears bottom-left. Untick Offline and it sends within fifteen seconds. The
board shows the time you *pressed the button*, not the time it synced.

**The dead man's switch, on demand.** Join a report, then age the assignment
past its deadline:

```bash
python -c "import sqlite3,datetime; d=sqlite3.connect('diresq.db'); \
d.execute(\"UPDATE assignments SET joined_at=?\", \
((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=60)).isoformat(),)); \
d.commit()"
flask --app app sweep
```

It prints what it filed. Run it twice — the second time files nothing, because
one open report per person is the whole idempotency rule.

**A check-in over the radio path.** No hardware needed:

```bash
flask --app app node-key londo      # note the id and key
python tools/gateway.py send --responder 1 --key <hex> \
    --lat 29.7858 --lng -95.8244 --age 3
```

Eighteen signed bytes, through the same code path a real LoRa gateway would
use. Change one character of the key and it's rejected.

**The ICS-214 export.** `/board` → the ICS-214 button. Opens in any
spreadsheet, built from real timestamps.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Every test gets a throwaway database, so order never matters. Add `-k queue`
or `-k break` to run one area.

Lint is errors-only, not style:

```bash
ruff check --select=E9,F .
```

## The documentation site

Separate project. Needs Node 22.

```bash
cd site
npm install
npm run dev
```

`npm run sync` copies `../docs/*.md` into `src/pages` before every build, so
the site can't drift from the repo. **Edit `docs/`, never
`site/src/pages/*.md`** — those are generated and gitignored.

## When it goes wrong

**`table report_flags already exists`** — a half-finished `init-db` on an old
database. Run `init-db` again; it's safe to repeat.

**`no such column: node_key`** — your database predates a schema change. There
are no migrations. `init-db` then `seed`.

**`coverage_gap_count is undefined`** — you're running a server started before
a code change. Restart it, and use `--debug` so it reloads on save.

**Signed out on every reload** — no `DIRESQ_SECRET_KEY`, so a new signing key
is made each boot.

**The map opens over the ocean** — old seed data with no located reports. Run
`seed` again.
