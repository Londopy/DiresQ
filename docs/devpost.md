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

And if you stay quiet fifteen minutes past that, the server stops waiting to be
noticed and files a report *about you*, at your last known position. It joins
the feed like any other job, so somebody can go and find you.

### The machine learning, and why it isn't a language model

Somebody filing a report at 2am from a flooded house is being asked to pick a
severity from a dropdown. They don't know. They aren't trained, they're
frightened, and the honest answer to "how bad is this on a three-point scale"
is *you tell me*.

So we trained a **naive Bayes classifier on 65 hand-labelled reports** to
suggest severity and required equipment from free text. It returns the words
that drove each decision, measures its own duplicate-detection threshold
against real data — 0.157 worst false positive, 0.409 true match, threshold
0.30 — and ships a model card listing what it gets wrong. It runs locally in
**0.1 ms with no network**, because the app is for a disaster, which is when
the network fails.

Type *"water rising fast, grandmother upstairs and cannot walk down"* and it
answers `HIGH · 95% sure · boat`, and tells you it decided that from
*rising, upstairs, cannot*. Touch the dropdown yourself and it stops adjusting
it, permanently — somebody who has made a decision about their own emergency
should not have software arguing with them.

The same maths does something else that matters more: it spots when your
description matches a report **somebody has already filed**. Duplicate reports
are exactly how six people end up at one address while a street nearby has
nobody.

We deliberately did not use an LLM. Three reasons, in the order they mattered:

1. **It has to explain itself.** The words shown *are* the decision — the
   ranked log-odds — not a separately generated rationalisation that can
   disagree with it. "Trust me" isn't available when somebody is deciding
   where to send a boat.
2. **It has to be honest about being wrong.** Below 45% confidence it says
   nothing at all. A confident paragraph from a language model is much harder
   to disbelieve, and this is a domain where confidently wrong sends people to
   the wrong street.
3. **It has to run.** No download, no API key, no network, no GPU. Our
   check-ins already queue offline; a classifier that needed somebody else's
   datacentre would be the one part of the system that fails exactly when it
   is needed.

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

**Tests found bugs that looked like working features.** Five of them. The
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

**Test on a database that already has something in it.** A table added late to
our schema got its `CREATE` and not its `DROP`, so rebuilding an *existing*
database stopped halfway and left it in pieces. Every test passed, because
tests build from empty and empty is the one case that works. The fix was one
line; the test we wrote afterwards reads the schema file itself and fails if
anything is ever created without being dropped, including tables nobody has
written yet.

**Agree your field names in writing before either person starts.** We didn't.
The frontend said `HIGH`/`MEDIUM`/`LOW` and `latitude`; the schema said
integers 1–4 and `lat`. Fifteen minutes of writing up front would have saved
all of it.

### The challenges

The plan didn't survive contact. We'd agreed the backend would push stub JSON
endpoints in the first hour so the frontend could build against them, and then
we put the one hard dependency in the whole plan on a single task and didn't
treat it as one. It sat in the doc looking like a step rather than a blocker.

The stubs never got written, and the frontend — rightly — kept moving instead
of waiting, building five complete pages as server-rendered templates. Those
ignore JSON entirely, so the stubs would have been thrown away regardless.

We kept what was already working rather than rewriting it, and the plan failing
produced a better app: the whole thing works with JavaScript switched off, and
only the parts that need to be live are live.

What it cost was the contract. With no stubs and no conversation instead of
them, both sides assumed one, and three field names came out different. The
lesson we actually took isn't "somebody should have waited" — it's that a plan
with a dependency in it needs that dependency named as one, out loud, with a
time on it.

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

The classifier counts words, so it cannot read "no longer trapped" correctly,
and its duplicate detection misses two descriptions of the same house that
happen to share no vocabulary. Sixty-five training examples is a demonstration,
not a dataset. It suggests; the person filing the report always decides.

And it has never been used in a real disaster. Everything here is reasoned from
accounts of Harvey, Kathmandu and Mexico City, and from published triage
protocol. We think the reasoning is sound. That's not the same as knowing it
works.

---

## Built with

```
python, flask, sqlite, jinja, javascript, html, css, leaflet,
openstreetmap, naive-bayes, tf-idf, machine-learning, astro,
timefuzz, vitalscore, patchnotes, pygeospy, hmac, lora,
werkzeug, python-dotenv, pytest, ruff, github-actions, bandit,
pip-audit, gitleaks, keep-a-changelog, start-triage, ics-214,
wcag, git, sublime-text
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
