<div align="center">

<img src="static/images/DiresQ.png" alt="DiresQ" width="120">

# DiresQ

**Every disaster app tells you where the disaster is.
DiresQ tracks the people going into it.**

[![CI](https://github.com/Skythe7/DiresQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/ci.yml)
[![Security](https://github.com/Skythe7/DiresQ/actions/workflows/security.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/security.yml)
[![Changelog](https://github.com/Skythe7/DiresQ/actions/workflows/changelog.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/changelog.yml)
[![Pages](https://github.com/Skythe7/DiresQ/actions/workflows/pages.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/pages.yml)

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Flask](https://img.shields.io/badge/flask-3.1-black)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/sqlite-3-003B57)](https://sqlite.org)
[![Tests](https://img.shields.io/badge/tests-344%20passing-brightgreen)](tests/test_app.py)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![Accessibility](https://img.shields.io/badge/accessibility-WCAG_2.1_AA_audited-a6e3a1)](docs/accessibility.md)
[![Works offline](https://img.shields.io/badge/check--ins-work_offline-fab387)](docs/offline.md)
[![No JS required](https://img.shields.io/badge/works_without-JavaScript-89b4fa)](docs/architecture.md)
[![Limitations](https://img.shields.io/badge/limitations-written_down-f38ba8)](docs/limits.md)

[![Changelog](https://img.shields.io/badge/changelog-keep--a--changelog-orange)](CHANGELOG.md)
[![Docs](https://img.shields.io/badge/docs-14_pages-cba6f7)](https://skythe7.github.io/DiresQ)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

**[Read the docs →](https://skythe7.github.io/DiresQ)**
&nbsp;&nbsp;·&nbsp;&nbsp;
**[Watch the demo →](https://youtu.be/T0Udg9WgRYA)**

Built at **Katy Youth Hacks 2026** (Tech for Humanity)
· also submitted to **STEMist Hacks IV**

<br>

<img src="docs/demo.gif"
     alt="The accountability board turning red when a responder stops checking
          in, and the report DiresQ files automatically at their last known
          position"
     width="720">

<sub>Five responders on scene, then s.reyes goes quiet. At fifteen minutes the
board turns red; the report on the right filed itself.</sub>

</div>

---

## The problem

During Hurricane Harvey, civilians in fishing boats rescued thousands of
people. Some of them drowned doing it.

When a volunteer self-deploys, nobody logs that they went. Nobody knows where
they are. Nobody knows when to start worrying. And because everyone converges
on whatever address is loudest online, six people end up on one street while
the next one over has nobody.

DiresQ tracks the responders, not just the incidents. You join a report, you
check in on a timer, you check out. Miss a check-in and the board turns red.
Every report shows how many people are already on it, so help spreads out
instead of piling up.

## What it actually looks like

A storm comes through Katy. Here is one hour on the app.

**A neighbour files a report.** Her street is flooding. She opens DiresQ, taps
the spot on the map, and writes *"Water rising, 2 trapped."* Marks it HIGH. It
lands at the top of the feed, and the card reads **0 responding**.

**You have a boat.** You see that card sitting above one with six people
already on it. You tap join, and type *"30 min"* — that's how long before
anyone should start worrying about you. The card now reads **1 en route**. On
the board, your row turns blue.

**You get there.** You mark yourself on scene, and your row goes green. It's
worse than she described, so you tag the report **NEEDS MORE** — it climbs the
feed. Two streets over, someone on a job with plenty of hands tags theirs
**OVERSTAFFED**, and that card sinks. The next person who opens the app comes
to you instead of there. Nobody coordinated that. The feed did it.

**Then you stop checking in.** You're inside a flooded house and your phone is
in your pocket. Thirty minutes pass. Your row on the board turns red:

```
londo    OVERDUE    Water rising, 2 trapped    last contact 47 min ago
                    last position 29.7858, -95.8244
```

Nobody had to notice. Nobody had to remember you went out. The board went red
on its own, and now somebody knows where to start looking.

**That last part is the product.** Everything else is how you get there.

## What it does

- **File a report** — what, how bad, and where, with the location pinned on a
  map or pulled from your phone's GPS.
- **See the feed** — worst first, with responder counts on every card. A report
  nobody has gone to reads `0 responding`, and you can see it sitting under one
  with six people on it.
- **Join** — any number of responders per report. No claim lock: in a real
  disaster the failure mode is convergence, not collision.
- **Signal staffing** — once you're on scene you can tell everyone else whether
  the site needs more help or has too many people. Where responders disagree,
  the most cautious signal wins.
- **It reads what you wrote** — a classifier suggests the priority and what
  equipment is needed from the description, and shows you the words that
  caused it. Naive Bayes, trained at import, 0.1 ms, no network. It also
  spots when somebody has already reported the same incident, which is how
  six people end up at one address. You always decide; touch the dropdown
  and it stops touching it. [How it works, and why it isn't an
  LLM](docs/model.md).
- **Triage it properly** — if you can't judge how bad something is, four
  questions run START, the protocol used at real multiple-casualty scenes,
  and pick the severity for you.
- **Check in** — resets your timer and updates your last known position. Works
  with no signal: it's kept on your phone, sent when there's a connection, and
  judged on when you pressed the button rather than when it arrived.
- **The accountability board** — everyone who is out, what they're doing, and
  how long since anyone heard from them. Overdue sorts to the top.
- **The dead man's switch** — stay silent fifteen minutes past your deadline
  and the server files a report about you, at your last known position. A red
  row only helps if somebody is looking at the board.
- **Coverage gaps, counted out loud** — a banner saying how many reports have
  nobody going to them at all. Not the same as understaffed.
- **ICS-214 export** — the activity log agencies already keep, built from
  records rather than from memory.
- **Check-ins over a radio** — a check-in packs into 22 signed bytes, small
  enough for LoRa, and `tools/gateway.py` forwards them from a pipe or a
  serial port to `/api/uplink`. Every packet is verified against that
  responder's key before anything is written.
  **The radio itself is not built** — we have no hardware, so there is no
  firmware. [docs/offline.md](docs/offline.md) is the full accounting of which
  parts exist.

## Quickstart

```bash
git clone https://github.com/Skythe7/DiresQ.git
cd DiresQ

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

flask --app app init-db         # build the tables (destructive)
flask --app app seed            # load Katy-area demo data
flask --app app run --debug
```

Then open <http://127.0.0.1:5000>.

Seeded accounts, all with the password `diresq`:

| Username | Role | Capabilities |
| --- | --- | --- |
| `londo` | responder | boat, medical |
| `skythe` | responder | truck, chainsaw |
| `kiyan` | reporter | — |

## Configuration

Copy `.env.example` to `.env` and fill it in. Real environment variables
override the file, so your shell and CI always win.

| Variable | Purpose |
| --- | --- |
| `DIRESQ_SECRET_KEY` | Signs session cookies. Generate your own with `python -c "import secrets; print(secrets.token_hex(32))"`. Without it a new key is made every boot, which logs you out on every reload. Do not share it between machines. |
| `DIRESQ_DEV_USER` | Stay signed in as this user without logging in. **Development only — it is a full auth bypass.** Leave unset for the real login flow. |
| `DIRESQ_DB` | Path to the SQLite file. Defaults to `diresq.db`. |
| `DIRESQ_HTTPS_ONLY` | Set to `1` when the site is served over HTTPS, so session cookies are marked Secure. Leave unset on localhost or you will not stay signed in. |
| `DIRESQ_DEMO` | Set to `1` on a public instance. Puts a banner on every page saying it is a demo, the data resets, and not to type a real address into it. |

## API

Pages are server-rendered; everything under `/api` returns JSON.

| Method | Route | |
| --- | --- | --- |
| `GET` | `/` | Report feed |
| `GET` | `/board` | Accountability board. Refreshes itself every 3s |
| `GET` | `/triage` | START triage helper |
| `GET` | `/disclaimer` | What this is and isn't. No login required |
| `GET` | `/map` | Map of located reports |
| `GET` `POST` | `/login` · `/signup` | Auth |
| `POST` | `/logout` | |
| `GET` `POST` | `/report/new` | File a report |
| `GET` | `/report/<id>` | Report detail |
| `POST` | `/report/<id>/rescue` | Join. Optional `eta_text` free-text ETA |
| `POST` | `/report/<id>/resolve` | Close it. Reporter or on-scene only |
| `GET` | `/api/reports` | Feed as JSON |
| `GET` | `/api/responders` | The accountability board |
| `POST` | `/api/reports/<id>/staffing` | `need_more` · `adequate` · `overstaffed` · `stood_down`. On-scene only |
| `POST` | `/api/assignments/<id>/status` | `on_scene` then `cleared`. Forward only, your own only |
| `POST` | `/api/checkin` | `{lat, lng}` — resets your timer |
| `POST` | `/api/uplink` | A check-in as a base64 22-byte signed packet. No session — see limits |
| `POST` | `/api/suggest` | Description in, suggested priority, equipment and duplicates out |
| `GET` | `/api/model` | What the classifier is and what it's bad at. No login |
| `POST` | `/api/triage` | Four observations in, START category out |
| `GET` | `/export/ics214` | Activity log as CSV |

Status codes: `200` ok · `201` created · `302` redirect · `400` bad input ·
`401` not signed in · `403` not yours · `404` not found.

## Design notes

**Overdue is computed when the board is read**, never stored. There is no
background job to forget to start, and no timer process that can silently die.

**Staffing is derived from votes, not stored on the report.** Where two people
on scene disagree, the most conservative signal wins — `need_more` always beats
`adequate`. An optimistic report must never be able to suppress a call for
help.

**Staffing reorders the feed inside a severity band, never across one.** A
minor report asking for help cannot bury a critical one nobody has reached.

**Free-text ETAs are refused rather than guessed.** `eta.py` wraps
[timefuzz](https://github.com/Londopy/timefuzz) with a confidence floor, a
four-hour cap and a five-minute minimum. If the parser isn't sure what you
meant you get the default interval and a message — a safety timer set from a
bad guess is worse than no timer at all.

**Severity can come from a protocol instead of a guess.** `triage.py` runs
START via [vitalscore](https://pypi.org/project/vitalscore/) — can they walk,
are they breathing, how fast, is there a pulse, do they respond — and maps the
category onto a severity band. It orders who gets reached first. It is not
medical advice.

## The classifier, and the number we nearly published

DiresQ reads what you typed and suggests a priority. It is a hand-written
multinomial naive Bayes classifier — 250 lines, no dependencies, no model
file, no network, 0.1 ms — paired with a phrase lexicon.

We checked it the obvious way first: run it over the corpus it was trained on.
It scored **100%**, and that number is worthless. It had memorised its 55
examples.

Measured properly — hold one report out, retrain on the other 54, predict the
one it has never seen, repeat 55 times:

| | Held out |
| --- | --- |
| Always guess the commonest label | 36% |
| Naive Bayes alone | **45%** |
| Naive Bayes + severity lexicon | **75%** |

Nine points above guessing, and wrong in the worst direction — *"child not
breathing properly"* came back MEDIUM, *"gas smell, whole street evacuating"*
came back LOW.

The fix was the same one that had already rescued equipment detection: a
lexicon of the categories a triage protocol calls immediate, written from the
START protocol rather than from our own failures, checked by a test that it
never contradicts a label. The measurement now runs in CI and fails the build
if it regresses.

It still gets one report in four wrong. That is survivable because it lands in
a dropdown you control, next to the words that caused it, and stops adjusting
the moment you touch it — and unacceptable if it were deciding anything.

**[The full write-up, including why it isn't an LLM →](docs/model.md)**

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

344 test functions covering every route, the permission rules, feed ordering,
staffing resolution, ETA parsing, overdue calculation, packet signing, the
offline queue, the auth guardrails and an adversarial pass. CI runs them on
every push, along with a boot check against a real server.

That number is itself checked by a test, because a README that lies about its
own test count is worse than one that doesn't mention it.

## Layout

```
app.py              routes, queries, CLI
classify.py         priority suggestion and duplicate detection
eta.py              free-text ETA parsing with a confidence gate
triage.py           START triage, mapped onto report severity
transport.py        the check-in packet, small enough for a radio
tools/gateway.py    forwards packets from a pipe or a serial port
tools/demo_state.py winds the clock so the board goes red on camera
tools/make_og.py    draws the social preview card
schema.sql          accounts · reports · assignments · checkins
templates/          Jinja pages
static/             CSS, JS, images
tests/              pytest suite
docs/               twelve pages: why, install, architecture, decisions,
                    process, offline, security, accessibility, limits,
                    disclaimer, api, errata — plus the video script and
                    Devpost draft, which are working notes rather than
                    published pages
site/               Astro docs site, built from docs/
static/scripts/sw.js  caches map tiles you have already seen
SECURITY.md         what's in scope, what we know is wrong
render.yaml         one-file deployment, plus start.sh
.github/workflows/  ci · security · changelog · pages · release
```

## Commands

```bash
flask --app app init-db          # drop everything and rebuild
flask --app app seed             # load an incident already in progress
flask --app app sweep            # file reports for anyone gone quiet
flask --app app node-key londo   # show or --rotate a radio key
```

`sweep` is the dead man's switch without a browser. It also runs when a page
is loaded, but put it on cron or Task Scheduler and the alarm stops depending
on somebody having a tab open:

```
*/5 * * * *  cd /srv/diresq && flask --app app sweep
```

## Docs site

```bash
cd site
npm install
npm run dev
```

`npm run sync` copies `../docs/*.md` into `src/pages` before every build, so
the site can't drift from the docs in the repo. The generated pages are
gitignored — edit `docs/`, never `site/src/pages/*.md`.

## Releasing

```bash
patchnotes CHANGELOG.md bump 1.0.0
git tag v1.0.0
git push --tags
```

## Read more

**All of this is a website: [skythe7.github.io/DiresQ](https://skythe7.github.io/DiresQ)**
— same words, easier to read, and it's built from the files below on every
push so the two can't disagree.

The links here are to the source, which is the version that still works in a
fork, offline, or if Pages is down.

- [Why](docs/why.md) — the gap this exists to fill, and what we refused to
  build
- [Running it](docs/install.md) — setup, the commands, and how to see each
  feature working
- [Architecture](docs/architecture.md) — the data model, what runs on a
  request, and the point at which each design stops working
- [Decisions](docs/decisions.md) — what we argued about and what we picked
- [Process](docs/process.md) — the build log, including what broke
- [Offline and LoRa](docs/offline.md) — the radio packet, the gateway, and an
  honest table of what is and isn't built
- [Hosting it](docs/deploy.md) — one file, one click, free, and what the cold
  start means for anyone you send the link to
- [The classifier](docs/model.md) — naive Bayes over 55 labelled reports, measured held-out at 75%,, the
  measured duplicate threshold, and why it isn't a language model
- [SECURITY.md](SECURITY.md) — disclosure policy, scope, and what we already know is wrong
- [Security](docs/security.md) — the threat model, packet signing, and the
  open redirect we shipped by accident
- [Accessibility](docs/accessibility.md) — the WCAG 2.1 AA audit: nine issues
  found, three critical, all fixed and held in place by tests
- [Limits](docs/limits.md) — what this doesn't do
- [Disclaimer](docs/disclaimer.md) — it does not call for help, and the triage
  helper is not medical advice
- [API](docs/api.md) — full reference
- [Project doc errata](docs/project-doc-errata.md) — where the planning doc
  and the code disagree, and which one won

## Known limitations

- **No identity verification.** Anyone can register as a responder. Solving it
  properly needs real ID checks or organisational affiliation, and there is no
  honest weekend version.
- **Location is self-reported** and can be falsified.
- **Staffing is resolved by taking the most cautious signal**, which means one
  pessimistic responder can hold a report at "needs more". We chose that over
  the alternative deliberately.
- **`/api/uplink` is unauthenticated.** A radio gateway has no session, so the
  responder is named inside the packet. It proves the shape is right; it is
  not something to expose.
- **The dead man's switch runs on page loads, not a timer.** If nobody has
  DiresQ open, nothing is swept. One tab on the board is enough, but that's a
  dependency, not a guarantee.

## Team

Skythe — frontend · Londo — backend

## License

[Apache-2.0](LICENSE)
