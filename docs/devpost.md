# Devpost submission

The copy that actually went on the submission, kept here so the repository
and the public project page can't drift apart.

Devpost supplies seven fixed headings and this is written to them. An earlier
draft carried two errors: it attached a confidence figure to a sentence that
did not produce it, and it said the corpus was sixty-five examples when it has
always been fifty-five. Both are corrected below.

Every figure quoted here was re-run against the code on the day of
submission rather than remembered:

    "Water rising fast, grandmother upstairs, she cannot walk down"
      ->  HIGH, 95%, boat, from: rising, upstairs, fast

---

## Elevator pitch

> Every disaster app tells you where the disaster is. DiresQ tracks the people
> going into it.

---

## Inspiration

During Hurricane Harvey, civilians took their own fishing boats out to pull neighbours off roofs. They rescued thousands of people. Some of them drowned doing it.

We kept coming back to one detail: when a volunteer self-deploys, **nobody writes down that they went.** No dispatcher, no roster, no log. If they don't come back, there is no moment where a system notices — someone eventually realises they haven't heard from a person in a while.

Every disaster app we looked at maps the incident. We couldn't find one that keeps a list of the people walking into it.

## What it does

You file a report: what's happening, how bad, and where — pinned on a map or pulled from your phone's GPS. If you can't judge how bad it is, four questions run START, the triage protocol used at real multiple-casualty scenes, and pick for you.

Responders join and give a rough ETA in plain English — "30 min", "back in a couple hours". That becomes a check-in deadline.

Then the part the whole thing exists for: **if nobody hears from you by your deadline, the board turns red.** Your name, your last known position, how long since anyone heard from you. Nobody has to notice. Nobody has to remember you went out.

And if you stay quiet fifteen minutes past that, the server stops waiting to be noticed and files a report *about you*, at your last known position. It joins the feed like any other job, so somebody can go and find you.

Any number of responders can join the same report — there's no claim lock, deliberately. Once you're physically on scene you can signal how staffed the site is, and that reorders the feed, so the next person who opens the app goes where the help isn't.

**And it all works with no signal.** Install DiresQ to a home screen and it opens without browser chrome. With the radio off you can still file a report — the classifier runs on the phone and suggests a priority, the report is written to the device before the network is touched, and when signal returns it syncs, arrives with the time you wrote it rather than the time it landed, and gets checked for duplicates on arrival. What you *cannot* see offline is the feed or the accountability board: those are claims about other people that stop being true the moment they are saved, and a stale copy of "who needs help" sends somebody to an address that was cleared twenty minutes ago. Offline they are absent rather than wrong.

## How we built it

Flask and SQLite, server-rendered pages with a JSON API layered on top, Leaflet for maps. The whole app works with JavaScript switched off.

Four of the libraries are ours — written, published to PyPI, then used here: **timefuzz** turns "back in a couple hours" into a real deadline with a confidence score, **vitalscore** runs the START triage, **pygeospy** does the geo maths, and **patchnotes** validates our changelog on every push.

**The machine learning, and why it isn't a language model.** Somebody filing a report at 2am from a flooded house is being asked to pick a severity from a dropdown. They don't know. They aren't trained, they're frightened, and the honest answer to "how bad is this on a three-point scale" is *you tell me*.

So we hand-wrote a multinomial naive Bayes classifier — 250 lines, no dependencies, no model file, 0.1 ms, no network — trained on 55 hand-labelled reports. Type *"Water rising fast, grandmother upstairs, she cannot walk down"* and it answers `HIGH · 95% · boat`, and tells you it decided that from *rising, upstairs, fast*. Touch the dropdown yourself and it stops adjusting it, permanently.

The same maths spots when your description matches a report **somebody has already filed**. Duplicate reports are exactly how six people end up at one address while a street nearby has nobody. That threshold was measured, not guessed: 0.157 worst false positive, 0.409 true match, threshold set at 0.30.

The check used to run while you typed, which meant the one time it could not run was the one time it mattered — two neighbours on the same street, both with no signal, both filing the same flood, both syncing later. It runs **on arrival** now, for every report however it got here, comparing against every open report *at the moment this one is written* — which includes whatever else landed seconds earlier in the same sync. Distance is a veto, not a vote: 500 metres apart and two similar sentences are two different incidents.

And the feed acts on it. Linked reports collapse into one card reading "3 reports, one incident", with the responders counted as **distinct people** rather than summed rows — somebody who joined two duplicates is one person, not two. The coverage-gap banner counts the incident once, because two duplicates of one uncovered flood is one street nobody is going to. Nothing is merged: both reports stay open, stay joinable, and both pins stay on the map, because two people reporting from opposite ends of a street are pinning two real places.

We deliberately did not use an LLM, for three reasons in the order they mattered:

1. **It has to explain itself.** The words shown *are* the decision — the ranked log-odds — not a separately generated rationalisation that can disagree with it. "Trust me" isn't available when somebody is deciding where to send a boat.
2. **It has to be honest about being wrong.** Below 45% confidence it says nothing at all. A confident paragraph from a language model is much harder to disbelieve, and this is a domain where confidently wrong sends people to the wrong street.
3. **It has to run.** No download, no API key, no network, no GPU. The whole app files reports offline now; a classifier that needed somebody else's datacentre would be the one part of the system that fails exactly when it's needed.

So we ship it to the phone. `export-model` writes the trained word counts to an 8 KB JSON the service worker caches, and a JavaScript evaluator reads the same numbers — one corpus, two runtimes, not two classifiers. What makes that survivable is a parity harness that runs every corpus line plus a dozen awkward ones through both and fails on any disagreement. It found a real bug immediately: the words shown behind a suggestion were being ranked by floating-point noise, CPython and V8 rounding `log` differently in the last bit. That was wrong in the Python on every machine, and unfindable with one implementation.

## Challenges we ran into

**Our first design was wrong, and we had to throw it out.** We built the dispatch model: one responder claims one report, it's locked, nobody else can take it. It felt obviously right. Then we read about Kathmandu in 2015 and Mexico City in 1985 — hundreds of neighbours converging on single collapse sites — and about Harvey, where whoever owned a boat went to whatever address they saw online. A claim lock would have fought the exact thing that saves people. The real failure mode isn't two people colliding on one job; it's fifty people on one street while the next one over has nobody.

**The plan didn't survive contact.** We'd agreed the backend would push stub JSON endpoints in the first hour so the frontend could build against them — and then we put the one hard dependency in the whole plan on a single task and didn't treat it as one. It sat in the doc looking like a step rather than a blocker. The stubs never got written, and the frontend rightly kept moving instead of waiting, building five complete pages as server-rendered templates that ignore JSON entirely.

The plan failing produced a better app — the whole thing works without JavaScript now. What it cost was the contract: with no stubs and no conversation instead of them, both sides assumed one, and three field names came out different. The lesson isn't "somebody should have waited". It's that a plan with a dependency in it needs that dependency named as one, out loud, with a time on it.

**Deciding what not to build was harder than building.** LoRa mesh is roadmap-only. We don't have radios, so we couldn't test it, and untested code isn't a feature — it's a file that looks like one.

## Accomplishments that we're proud of

**We caught our own classifier lying, and published the number.**

We checked it the obvious way first — run it over the corpus it was trained on. It scored **100%**. That number is worthless: it had memorised its 55 examples. Measured properly, holding one report out and retraining on the other 54, fifty-five times over:

| | Held out |
| --- | --- |
| Always guess the commonest label | 36% |
| Naive Bayes alone | **45%** |
| Naive Bayes + severity lexicon | **75%** |

Nine points above guessing, and wrong in the worst possible direction — *"child not breathing properly"* came back MEDIUM, *"gas smell, whole street evacuating"* came back LOW.

The fix was a lexicon of the categories a triage protocol calls immediate, written from the START protocol rather than from our own failures, with a test asserting no phrase ever fires on a report labelled something else. That measurement now runs in CI and fails the build if it regresses below 68%.

It still gets one report in four wrong. That's survivable because it lands in a dropdown you control, next to the words that caused it — and it would be unacceptable if it were deciding anything.

**606 tests**, including 31 adversarial ones, a WCAG 2.1 AA audit, and a suite that reads our own documentation and fails the build when the numbers in it go stale.

## What we learned

**Tests found bugs that looked like working features.** Five of them. The backend was calling `flash()` in five places to report errors — no template rendered them, so every rejected form just sat there looking frozen. Nobody would have found that by clicking around, because the page looks *fine*.

The report form marked its hidden latitude and longitude fields `required`. Hidden inputs are exempt from browser validation — so an untouched map submitted anyway and the report saved with no coordinates, invisible on the map, forever.

**A safety check that fails silently is worse than no check.** Our CI greps for hardcoded secrets. The pattern needed both quote characters, and escaping that inside a YAML block scalar produced an unterminated string. The job went red having searched nothing. We rewrote it in Python and tested it against a deliberately broken file, to prove it still catches a real one.

**Test on a database that already has something in it.** A table added late to our schema got its `CREATE` and not its `DROP`, so rebuilding an *existing* database stopped halfway and left it in pieces. Every test passed, because tests build from empty and empty is the one case that works.

**Measure the clever version before you keep it.** We learned this twice — once on equipment detection, where five binary classifiers confidently demanded a chainsaw for a downed power line, and once on priority, hidden behind a 100% accuracy figure measured on the training data.

## What's next for DiresQ

**The radio.** This is the one thing left on the list that was there at the start. A check-in already packs into 22 signed bytes — small enough for a LoRa payload — and there's a gateway script that forwards them to the API. What's missing is hardware. That's a purchase and a weekend, not a rewrite.

**Real data.** 55 training examples is a demonstration, not a dataset. Real deployment needs thousands of real reports, and real reports contain names and addresses, which is its own problem.

**The things we've written down rather than hidden.** There's a `/limits` page in the app. No identity verification — anyone can register as a responder. Location is self-reported; we detect inconsistency, not intent. The overdue timer measures contact, not safety: a dead battery flags identically to a flooded basement.

And it has never been used in a real disaster. Everything here is reasoned from accounts of Harvey, Kathmandu and Mexico City, and from published triage protocol. We think the reasoning is sound. That is not the same as knowing it works.

---

## Built with

Devpost caps this at 25 tags.

```
python, flask, sqlite, jinja, javascript, html, css, leaflet,
openstreetmap, naive-bayes, tf-idf, machine-learning, astro,
timefuzz, vitalscore, patchnotes, pygeospy, hmac, lora, pytest,
github-actions, ruff, wcag, start-triage, ics-214
```

## Try it out

- Live demo — *(Render URL; free tier sleeps, first load takes about a minute)*
- Code — https://github.com/Skythe7/DiresQ
- Docs — https://skythe7.github.io/DiresQ
- Run it yourself — one file from the
  [releases page](https://github.com/Skythe7/DiresQ/releases), for macOS and
  Linux or for Windows, published with checksums. It fetches the source for
  that version, sets everything up in a folder beside itself and opens the
  browser.

## Development tools

Sublime Text 4, Git and GitHub, GitHub Actions for CI, pytest (606 tests),
ruff, bandit, pip-audit, gitleaks, Leaflet and OpenStreetMap, Astro for the
documentation site, Adobe Premiere Pro for the demo video, Discord for team
coordination.

PyPI — we published four libraries (timefuzz, vitalscore, patchnotes,
pygeospy) and then consumed them in this project.

## Tracks entered

- Best AI Hack
- Best Security or Privacy Hack
- Best use of Render
