# Devpost submission

Draft copy. Paste into the form, edit freely.

---

## Elevator pitch

> Every disaster app tells you where the disaster is. DiresQ tracks the people
> going into it.

Alternates if that one doesn't fit:

- Volunteers self-deploy into disasters and nobody logs that they went. DiresQ
  is the sign-out sheet.
- A live board of who went in, where they are, and when to start worrying.

---

## About the project

### The thing that started it

During Hurricane Harvey, civilians took their own fishing boats out to pull
neighbours off roofs. They rescued thousands of people. Some of them drowned
doing it.

We kept coming back to one detail: when a volunteer self-deploys, **nobody
writes down that they went.** No dispatcher, no roster, no log. If they don't
come back, there is no moment where a system notices. Someone eventually
realises they haven't heard from a person in a while.

Every disaster app we looked at maps the incident. We couldn't find one that
keeps a list of the people walking into it.

### The mistake we made first

Our first design was the dispatch model: one responder claims one report, it's
locked, nobody else can take it. It felt obviously right.

Then we read about Kathmandu in 2015 and Mexico City in 1985 — hundreds of
neighbours converging on single collapse sites — and about Harvey, where
whoever owned a boat went to whatever address they saw online. A claim lock
would have fought the exact thing that saves people.

**The real failure mode isn't two people colliding on one job. It's fifty
people on one street while the next one over has nobody.**

So we rebuilt it. Any number of responders can join a report. Once you're
physically on scene you can signal how staffed it is, and that reorders the
feed — so the next person who opens the app goes where the help isn't. Nobody
coordinates that. The feed does.

### How it works

You file a report: what's happening, how bad, and where — pinned on a map or
pulled from your phone's GPS. If you can't judge how bad it is, four questions
run START, the triage protocol used at real multiple-casualty scenes, and pick
for you.

Responders join and give a rough ETA in plain English — "30 min", "back in a
couple hours". That becomes a check-in deadline.

Then the part the whole thing exists for: **if nobody hears from you by your
deadline, the board turns red.** Your name, your last known position, how long
since anyone heard from you. Nobody has to notice. Nobody has to remember you
went out.

### What we built it with

Flask and SQLite, server-rendered pages with a JSON API layered on top, Leaflet
for maps.

Four of the libraries are ours — written, published to PyPI, then used here:

- **timefuzz** turns "back in a couple hours" into a real deadline, with a
  confidence score
- **vitalscore** runs the START triage
- **patchnotes** validates our changelog on every push
- **pygeospy** for the geo maths

### What we learned

**Tests found bugs that looked like working features.** Three of them. The
backend was calling `flash()` in five places to report errors — no template
rendered them, so every rejected form just sat there looking frozen. Nobody
would have found that by clicking around, because the page looks *fine*. A
test asserting the login page said *why* it rejected you caught it in seconds.

The report form marked its hidden latitude and longitude fields `required`.
Hidden inputs are exempt from browser validation — so an untouched map
submitted anyway and the report saved with no coordinates, invisible on the
map, forever.

**A safety check that fails silently is worse than no check.** Our CI greps for
hardcoded secrets. The pattern needed both quote characters, and escaping that
inside a YAML block scalar produced an unterminated string. The job went red
having searched nothing. We rewrote it in Python and tested it against a
deliberately broken file, to prove it still catches a real one.

**Agree your field names in writing before either person starts.** We didn't.
The frontend said `HIGH`/`MEDIUM`/`LOW` and `latitude`; the schema said
integers 1–4 and `lat`. Fifteen minutes of writing up front would have saved
all of it.

### The challenges

The plan didn't survive contact. We'd agreed the backend would push stub JSON
endpoints in the first hour so the frontend could build against them. Instead
the frontend built five complete pages as server-rendered templates — which
ignore JSON entirely. The stubs would have gone unused.

We kept what she'd built rather than rewriting it, and it turned out better
than the plan: the board works with JavaScript switched off, and only the parts
that need to be live are live.

Deciding what *not* to build was harder than building. LoRa mesh is in our
notes as roadmap-only. We don't have radios, which means we couldn't test it,
and untested code isn't a feature — it's a file that looks like one. It's a
sentence in the video instead.

### What it doesn't do

There's a `/limits` page and a `docs/limits.md`, and we'd rather you read them
than not. No identity verification — anyone can register as a responder.
Location is self-reported; we detect inconsistency, not intent. Spam control is
community flagging, not verification. The overdue timer measures contact, not
safety: a dead battery flags identically to a flooded basement.

And it has never been used in a real disaster. Everything here is reasoned from
accounts of Harvey, Kathmandu and Mexico City, and from published triage
protocol. We think the reasoning is sound. That's not the same as knowing it
works.

---

## Built with

```
python, flask, sqlite, jinja, javascript, html, css, leaflet,
openstreetmap, timefuzz, vitalscore, patchnotes, pygeospy,
werkzeug, python-dotenv, pytest, ruff, github-actions, bandit,
pip-audit, gitleaks, keep-a-changelog, start-triage, git, sublime-text
```

## Try it out

- Code — https://github.com/Skythe7/DiresQ
- Decisions — https://github.com/Skythe7/DiresQ/blob/main/docs/decisions.md
- Build log — https://github.com/Skythe7/DiresQ/blob/main/docs/process.md
- Known limits — https://github.com/Skythe7/DiresQ/blob/main/docs/limits.md

## Development tools

Sublime Text 4, Git and GitHub, GitHub Actions for CI, pytest, ruff, bandit,
pip-audit, gitleaks, Discord for coordination, Leaflet and OpenStreetMap,
PyPI for the four libraries we published and consumed.
