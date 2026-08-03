<div align="center">

<img src="static/images/DiresQ.png" alt="DiresQ" width="120">

# DiresQ

**Every disaster app tells you where the disaster is.
DiresQ tracks the people going into it.**

[![CI](https://github.com/Skythe7/DiresQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/ci.yml)
[![Security](https://github.com/Skythe7/DiresQ/actions/workflows/security.yml/badge.svg)](https://github.com/Skythe7/DiresQ/actions/workflows/security.yml)
[![Tests](https://img.shields.io/badge/tests-535%20passing-brightgreen)](tests/test_app.py)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[![Accessibility](https://img.shields.io/badge/accessibility-WCAG_2.1_AA_audited-a6e3a1)](docs/accessibility.md)
[![Works offline](https://img.shields.io/badge/reports_&_check--ins-work_offline-fab387)](docs/offline.md)
[![No JS required](https://img.shields.io/badge/works_without-JavaScript-89b4fa)](docs/architecture.md)
[![Limitations](https://img.shields.io/badge/limitations-written_down-f38ba8)](docs/limits.md)

[![parsed by timefuzz](https://img.shields.io/badge/parsed%20by-timefuzz-007ec6)](https://github.com/Londopy/timefuzz)
[![changelog checked by patchnotes](https://img.shields.io/badge/changelog%20checked%20by-patchnotes-007ec6)](https://github.com/Londopy/patchnotes)

[![Docs](https://img.shields.io/badge/docs-16_pages-cba6f7)](https://skythe7.github.io/DiresQ)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

**[Try it live →](https://diresq.onrender.com)**
&nbsp;&nbsp;·&nbsp;&nbsp;
**[Watch the demo →](https://youtu.be/T0Udg9WgRYA)**
&nbsp;&nbsp;·&nbsp;&nbsp;
**[Read the docs →](https://skythe7.github.io/DiresQ)**

<sub>Sign in as `londo` / `diresq`. Free tier — it sleeps after 15 idle
minutes, so the first load can take about a minute.</sub>

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

## Built in one night

14 hours: 6:00pm–8:00am for Londo, 8:00am–10:00pm for Skythe.

<!-- frozen: measured at the end of the 14-hour window and left alone from
     then on. The doc-freshness tests skip everything between these markers,
     because a snapshot that keeps updating itself is not a snapshot. -->
| | |
| --- | --- |
| **70 commits** | 65 of them inside the 14-hour window |
| **12,579 lines of code** | Python, JavaScript, CSS, HTML, SQL |
| **474 test functions** | 597 cases after parametrisation — every route, an adversarial pass |
| **16 documentation pages** | including the one listing what we didn't build |
| **No background jobs** | overdue is computed on read — nothing to forget to start, no timer that can silently die |
<!-- /frozen -->

That table is the night itself and does not move. It has kept growing since:
**18,125 lines of code** and **535 test functions**, 680 cases after
parametrisation. Those two are checked by a test, so unlike the snapshot they
cannot quietly go stale.

Everything in this README is running, tested and deployed. The parts that
aren't have their own page saying so.

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

## One hour on the app

A storm comes through Katy.

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

## What we can prove

Five claims, each with the measurement behind it.

**The classifier is 75% accurate, and we know because we tried to fool it.**
Run over its own training corpus it scored 100% — a worthless number, it had
memorised its 55 examples. Measured properly (hold one out, retrain on 54,
predict the unseen one, 55 times) naive Bayes alone got 45% against a 36%
always-guess-the-commonest baseline. Nine points. The severity lexicon took it
to 75%. That measurement runs in CI and fails the build if it regresses.
[Full write-up →](docs/model.md)

**The radio packet resists replay, not just corruption.** A check-in packs into
22 signed bytes. Every packet is verified against that responder's key, and a
strictly-increasing counter is persisted *before* the check-in is written — so
a crash between the two loses a check-in rather than reopening the window. The
packet carries an age rather than a timestamp, because a node running off a
battery in a flood is the last clock you want to trust.
[The threat model →](docs/security.md)

**The accessibility audit found thirteen issues and we fixed all thirteen.**
Three were critical. Nine came from the first pass; four more from a second
one over the offline report form, where contrast passed everywhere and the
announcing didn't — a status region written to while still hidden, two live
regions talking over each other. Every fix is held in place by a test, so they
can't quietly come back. [The audit →](docs/accessibility.md)

**The offline classifier is the same classifier, and a test proves it rather
than assuming it.** The browser gets the trained model, generated from
`classify.py`; a test fails if the committed copy has drifted, and a parity
harness runs every corpus line plus a dozen awkward cases through both
implementations and fails on any disagreement. It found a real bug on its
first run: the words shown behind a suggestion were being ordered by
floating-point noise, because CPython and V8 round `log` differently in the
last bit. That was wrong in the Python on every machine, and unfindable while
there was only one implementation. [How →](docs/offline.md)

**We wrote down what's broken before anyone asked.** `/api/uplink` is
unauthenticated. Location is self-reported. The radio firmware does not exist,
because we have no hardware. A system with no stated limitations isn't a system
without limitations — it's one nobody checked.
[All of them →](docs/limits.md)

## What it does

- **File a report** — what, how bad, and where, with the location pinned on a
  map or pulled from your phone's GPS. **It works with no signal:** the report
  is written to your phone before the network is touched, sends itself when
  there is a connection, and carries an id minted before the first attempt, so
  a phone that dies mid-send retries without filing a second incident.
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
  caused it. Naive Bayes, trained at import, 0.1 ms, no network. **It runs on
  the phone too**, from the same trained model, so the person filing at 2am
  with the towers down gets the suggestion that was built for them. You always
  decide; touch the dropdown and it stops touching it.
- **It notices when two reports are one incident** — which is how six people
  end up at one address while the next street has nobody. Checked when a
  report *arrives*, not while somebody types, so two neighbours who both filed
  offline and could not see each other's report are compared against each
  other the moment they sync.
- **And then the feed counts them as one.** This is the part that matters.
  Two reports of one flood with three responders each renders as two
  comfortably staffed rows — and the feed, whose whole job is to make
  convergence visible, would be hiding it in its own data. Grouped, it reads
  **6 responding to 1 incident**, counts each person once even if they joined
  both, takes the worst priority and the most cautious staffing signal, and
  counts once in the coverage-gap banner. Nothing is merged: both reports stay
  open, linkable and joinable. The map still shows both pins, because two
  people reporting from opposite ends of a street pinned two real places.
- **Stand down** — resolving a report clears everyone still attached, and used
  to tell none of them. Somebody who joined twenty minutes ago and is in a car
  found out by refreshing a page they weren't looking at. This project's whole
  argument is that people shouldn't be sent where they're not needed, and the
  app was doing it to its own responders. They now get a notice on the feed,
  the report page, and offline too — a resolved report stays resolved, so that
  claim survives being cached. It doesn't dismiss itself, because the person
  it's for is driving.
- **It says when it can't read your report** — typed in Spanish, *"mi madre no
  puede respirar"* (my mother cannot breathe) used to come back **LOW, 51%
  confident, and shown**. Naive Bayes can't abstain: every word unknown, every
  class falls back to its prior, and out comes a label that looks like
  knowledge. Katy is roughly a third Hispanic or Latino — not a hypothetical
  input. Wording the model has never seen now gets no suggestion and a
  sentence saying why, and files exactly as written. Not language detection:
  English full of unfamiliar street names is refused too, and correctly.
- **Triage it properly** — if you can't judge how bad something is, four
  questions run START, the protocol used at real multiple-casualty scenes, and
  pick the severity for you.
- **Check in** — resets your timer and updates your last known position. Works
  with no signal: it's kept on your phone, sent when there's a connection, and
  judged on when you pressed the button rather than when it arrived.
- **Install it** — add DiresQ to your home screen and it opens without browser
  chrome, with its own icon. With the radio off you still get the report you
  took, when you're due to check in, where you last were, and a working report
  form with the classifier behind it. What you don't get is the feed, the
  board, or a duplicate check: those are claims about other people that stop
  being true the moment they're saved, and a stale one sends somebody to an
  address that was cleared twenty minutes ago. Offline they're absent rather
  than wrong — and the form says so out loud rather than showing an empty
  duplicate list, which would read as *checked, found none*.
  [What's kept and what isn't →](docs/offline.md)
- **The accountability board** — everyone who is out, what they're doing, and
  how long since anyone heard from them. Overdue sorts to the top.
- **The dead man's switch** — stay silent fifteen minutes past your deadline
  and the server files a report about you, at your last known position. A red
  row only helps if somebody is looking at the board.
- **Coverage gaps, counted out loud** — a banner saying how many reports have
  nobody going to them at all. Not the same as understaffed. On the map the
  same judgement is a colour: pins are red where nobody has said they're
  coming, blue where somebody is en route, green where somebody has arrived,
  and only the red ones pulse. One button hides everything that already has
  help, so what's left on screen is the streets nobody is going to.
- **ICS-214 export** — the activity log agencies already keep, built from
  records rather than from memory.
- **Check-ins over a radio** — 22 signed bytes, small enough for LoRa, and
  `tools/gateway.py` forwards them from a pipe or a serial port to
  `/api/uplink`. **The radio itself is not built** — we have no hardware, so
  there is no firmware. [docs/offline.md](docs/offline.md) is the full
  accounting of which parts exist.

## Quickstart

The fastest route is the launcher attached to any
[release](https://github.com/Skythe7/DiresQ/releases): one file, run it, and
it fetches the source, sets up an isolated environment, seeds the demo and
opens the browser. `diresq-macos-linux.sh` or `diresq-windows.ps1`, with
`SHA256SUMS.txt` to check them against. They are scripts rather than binaries
because nothing here is compiled — see
[docs/install.md](docs/install.md).

By hand:

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

**Mismatch detection is generous on purpose.** Marking yourself on scene when
your last check-in was more than 500 metres away raises a flag. The radius is
wide because phone GPS is poor in bad weather, and a false accusation is worse
than a missed one.

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
| `GET` | `/offline` | Shown when a navigation fails. No login, so it can be cached ahead of time |
| `GET` | `/map` | Map of located reports |
| `GET` `POST` | `/login` · `/signup` | Auth |
| `POST` | `/logout` | |
| `GET` `POST` | `/report/new` | File a report |
| `GET` | `/report/<id>` | Report detail |
| `POST` | `/report/<id>/rescue` | Join. Optional `eta_text` free-text ETA |
| `POST` | `/report/<id>/resolve` | Close it. Reporter or on-scene only |
| `GET` | `/api/reports` | Feed as JSON |
| `GET` | `/api/responders` | The accountability board |
| `GET` | `/api/me` | Your own commitments and nothing else. The one response kept on the device |
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

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

535 test functions, which parametrisation expands into 680 cases, covering
every route, the permission rules, feed ordering, staffing resolution, ETA
parsing, overdue calculation, packet signing, the offline queues for both
check-ins and reports, arrival-time duplicate detection, the auth guardrails
and an adversarial pass. CI runs them on every push, along with a boot check
against a real server, the held-out accuracy measurement, and a parity run
that fails if the browser classifier and the Python one ever disagree.

## Layout

```
app.py              routes, queries, CLI
classify.py         priority suggestion and duplicate detection
eta.py              free-text ETA parsing with a confidence gate
triage.py           START triage, mapped onto report severity
transport.py        the check-in packet, small enough for a radio
tools/gateway.py    forwards packets from a pipe or a serial port
tools/parity.mjs    runs the browser classifier, so a test can compare the two
tools/queuecheck.mjs  runs the offline outbox against a fake browser
tools/demo_state.py winds the clock so the board goes red on camera
tools/make_og.py    draws the social preview card
schema.sql          accounts · reports · assignments · checkins
templates/          Jinja pages
static/             CSS, JS, images
static/scripts/sw.js  caches map tiles you have already seen
static/scripts/classify.js  the same trained model, evaluated on the phone
static/scripts/reportqueue.js  reports written to the device before they are sent
static/model/       the trained model, generated by `flask --app app export-model`
tests/              pytest suite
docs/               sixteen pages: why, install, architecture, decisions,
                    process, offline, security, accessibility, limits,
                    disclaimer, api, model, deploy, errata — plus the video
                    script and Devpost draft, which are working notes rather
                    than published pages
site/               Astro docs site, built from docs/
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
flask --app app export-model     # regenerate the browser's copy of the model
```

Run `export-model` after touching the corpus or the lexicons in `classify.py`.
A test fails if the committed artifact has gone stale, so forgetting is loud
rather than silent.

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
- [The classifier](docs/model.md) — naive Bayes over 55 labelled reports,
  measured held-out at 75%, the measured duplicate threshold, and why it isn't
  a language model
- [SECURITY.md](SECURITY.md) — disclosure policy, scope, and what we already
  know is wrong
- [Security](docs/security.md) — the threat model, packet signing, and the
  open redirect we shipped by accident
- [Accessibility](docs/accessibility.md) — the WCAG 2.1 AA audit: thirteen
  issues found across two passes, three critical, all fixed and held in place
  by tests
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
- **The classifier is wrong one time in four.** Survivable because it lands in
  a dropdown you control, next to the words that caused it, and stops adjusting
  the moment you touch it. Unacceptable if it were deciding anything.
- **Duplicate detection cannot run offline**, and that is a choice rather than
  a gap. It compares against everybody else's open reports, and keeping that
  list on a phone is the one thing this app refuses to do. The server checks
  on arrival instead, so the check is deferred rather than lost — but between
  filing and syncing, nothing has looked, and the form says so.
- **Duplicate detection misses rewordings.** "flooding, couple on the second
  floor" and "water rising, two adults upstairs" are one incident sharing
  almost no vocabulary. Catching that needs embeddings, which need a model
  file and a machine to run it on.
- **A report edited or resolved offline still needs a connection.** Only new
  reports queue. Reconciling an edit against whatever happened while you were
  away needs conflict rules we have not earned the right to guess at.

## Team

Skythe — frontend · Londo — backend

## License

[Apache-2.0](LICENSE)
