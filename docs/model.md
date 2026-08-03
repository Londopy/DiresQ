# The classifier

DiresQ reads what somebody types into a report and suggests how bad it is,
what equipment is needed, and whether the same incident has already been
reported.

It is a **multinomial naive Bayes classifier over a bag of words**, written by
hand in about 250 lines of Python with no dependencies, trained at import from
a corpus of 55 labelled reports, paired with a phrase lexicon for the
categories a triage protocol treats as immediate. No model file, no network,
no GPU, no API key. It runs in about **0.1 milliseconds**.

It is not a language model. This page explains why that was the right call —
and then shows you the accuracy numbers, including the bad one.

---

## The numbers first

Every classifier demo you have ever seen quotes the accuracy on its own
training data. Here is ours:

| | |
| --- | --- |
| Trained on 55 reports, tested on those same 55 | **100%** |

That number is worthless and we nearly shipped it. The model had memorised
its corpus.

Here is the same model measured properly — hold one report out, retrain on the
other 54, predict the one it has never seen, repeat 55 times:

| | Held out |
| --- | --- |
| Always guess the commonest label (`HIGH`) | 36% |
| **Naive Bayes alone** | **45%** |
| **Naive Bayes + severity lexicon** | **75%** |

Naive Bayes on its own was nine points better than guessing. Worse, it failed
in the direction that matters:

| Report | Predicted | Should be |
| --- | --- | --- |
| *"child not breathing properly after being pulled from…"* | MEDIUM | HIGH |
| *"gas smell very strong, whole street evacuating now"* | LOW | HIGH |
| *"man having chest pains, ambulance cannot reach us"* | MEDIUM | HIGH |
| *"live wire in standing water in the front yard, children…"* | MEDIUM | HIGH |

A bag of words does not know that *breathing* is a different kind of word from
*fence*. It counts them the same.

The fix is described under [Priority](#priority) below, and the measurement
runs in CI — `TestTheClassifierIsMeasuredNotAssumed` fails the build if the
held-out number drops below 68%.

---

## The problem it solves

Somebody filing a report at 2am from a flooded house is being asked to pick a
severity from a dropdown and tick which equipment is needed.

They don't know. They aren't trained, they're frightened, and the honest
answer to "how severe is this on a three-point scale" is *you tell me* — the
person asking is the one with the map and the volunteers, not the person
standing in the water.

So the app reads what they wrote:

> *"Water rising fast, grandmother upstairs, she cannot walk down"*

```
HIGH · 95% sure · boat
Suggested from: rising, fast, upstairs. You decide — change it if it's wrong.
```

That block is not an illustration. It is what the code returns for that
sentence, and a test in the suite runs it to make sure this page cannot drift
away from the software it describes — which it had, quietly, until somebody
typed the example into the real thing.

The order of those three words changed once, and the reason is worth knowing.
`fast` and `upstairs` are exactly as telling as each other here — identical
arithmetic — and which one came second was decided by the last bit of a
logarithm. That surfaced when the same model was ported to the browser: two
implementations of `log` rounded the same expression differently and the two
explanations diverged. Ties are now rounded flat and broken alphabetically, so
the answer is the same on every machine. See `NaiveBayes.why`.

The dropdown moves to HIGH. **The moment you touch it yourself, the model
stops touching it** for the rest of the form. Somebody who has made a decision
about their own emergency should not have software arguing with them.

## Why not an LLM

Three reasons, in the order they mattered.

### It has to explain itself

Every suggestion returns the words that caused it. A coordinator deciding
where to send a boat can see *why* the model said HIGH and disagree with it on
the spot.

"Trust me" is not a thing you get to say to somebody making that decision. It
is the same rule the triage helper follows — START returns a category *and*
the plain-English reason — and it is the same rule the whole project follows:
show your working or don't show up.

An LLM can be asked to explain, but the explanation is generated separately
from the decision and can disagree with it. Here the explanation *is* the
decision — it's the ranked log-odds, which is the arithmetic the classifier
actually did.

### It has to be honest about being wrong

Below 45% confidence it says nothing. Under three words it says nothing. It is
a bag-of-words model trained on 55 examples and it will be wrong regularly,
which is fine, because it is a suggestion sitting next to a dropdown the human
controls.

A confident-sounding paragraph from a language model is much harder to
disbelieve, and this is a domain where being confidently wrong sends people to
the wrong street.

There is also the disclaimer problem. DiresQ says, in the app and in writing,
that it does not give advice. Bolting on something that produces advice-shaped
sentences would make that a lie.

### It has to run

No download, no API key, no network, no GPU, and it survives being deployed on
whatever a volunteer group can afford.

The app is for a disaster — the situation in which the network is the first
thing to fail. Check-ins already queue offline. A classifier that needs a
round trip to somebody else's datacentre would be the one part of the system
that stops working exactly when it's needed, and shipping that would
contradict the rest of the design.

The maths is Bayes' theorem and inverse document frequency, both older than
everyone who worked on this. That's the point — you can read all of it in one
file and check it.

## How it works

### Priority

Multinomial naive Bayes. Count how often each word appears in reports of each
class, apply Bayes' theorem, pick the highest.

Add one to every count before dividing — Laplace smoothing — so a word never
seen in a class doesn't drive its probability to zero. On a corpus this small
that single line is the difference between working and not.

Confidence is a softmax over the log scores. The max is subtracted before
exponentiating, or long descriptions underflow and every answer comes back
100% sure.

**And then a lexicon gets the first vote.** Before any of that arithmetic
runs, the description is checked against a list of phrases that a triage
protocol treats as immediate — airway and breathing, circulation, entrapment,
hazardous material, structural collapse, dependence on powered medical
equipment, moving water on a person. If one matches, the priority is HIGH and
the matched phrase is the explanation. A short list of the opposite kind
(*"reporting in case it gets worse"*, *"not blocking the road"*) does the same
for LOW.

That is what takes the held-out number from 45% to 75%.

Two things about it are deliberate:

**The phrases come from the protocol, not from our own mistakes.** It would
have been easy to read the misses in the table above and write phrases that
fixed exactly those reports. That produces a lexicon that scores brilliantly
on the corpus you measured and has learned nothing. These are the standard
immediate categories from START — the same protocol the app's triage helper
already implements — written down before checking what they'd score.

**It is checked against the labels.** A test asserts that no phrase ever fires
on a report labelled something else. `"cannot get out"` was in the first draft
and this test removed it: the corpus contains *"tree across the driveway,
cannot get the car out"*, which is a blocked car, not a trapped person.

### Explanation

For the chosen class, each word is scored by how much *more* likely it is
under that class than under the best alternative. A word common everywhere
explains nothing, and this ranking drops it automatically. Top three are
shown.

### Equipment — where we went backwards on purpose

This started as five binary naive Bayes classifiers, one per capability, and
**we deleted them.** The story is the most useful thing on this page.

Running them over the seeded reports:

| Report | Predicted | Right? |
| --- | --- | --- |
| *"Power line down across both lanes, still arcing"* | chainsaw, **100% confident** | No |
| *"Roof peeled back, family of four inside"* | boat, chainsaw, medical, truck, generator | Meaningless |

The chainsaw one had a cause: a single training line reads *"large branch
leaning on the power line to the house"*, so `power` and `line` became
chainsaw evidence. With 55 examples split five ways, each capability's
positive class is a handful of sentences, and a long description drowns the
signal in ordinary words.

Raising the threshold didn't fix it — the *wrong* answer was the confident one
and a true positive (`chainsaw` on a tree report, 67%) fell below the cut
first.

So equipment is now a **lexicon**: a curated set of words per capability,
stemmed the same way the text is, capped at two matches.

```python
"boat": ("water", "flood", "rising", "upstair", "attic", "swept", ...)
"chainsaw": ("tree", "branch", "limb", "trunk", "fallen", ...)
```

| Report | Now |
| --- | --- |
| Power line down, arcing | `generator`, from *"power"* |
| Water rising, upstairs | `boat`, from *"water"* |
| Tree across driveway | `chainsaw`, from *"tree"* |
| *"Please do not send anyone"* | **nothing** |

Capped at two, because a report that appears to need all five is a report the
model has not understood — and saying so at length is the same as saying
nothing while looking confident. There's a phrase check first, so *"please do
not send anyone"* and *"for the record"* return nothing at all.

**Less sophisticated, and better.** It names the word that matched, it is
wrong in ways you can see, and a wrong answer is a one-line fix instead of a
retraining problem.

The general lesson, which cost us an hour to learn: **measure the clever
version before keeping it.** We would have shipped the confident, wrong one.

And then we learned it a second time. We had assumed priority was fine because
it *looked* fine — the same mistake, one layer up, hidden behind a 100%
accuracy figure that was measured on the training data. Naive Bayes still does
the work on every report the lexicon doesn't recognise, which is most of them,
and that is where the maths earns its place. It just no longer decides alone
whether somebody who cannot breathe is a MEDIUM.

### Duplicates

TF-IDF cosine similarity against every open report. This is not about
severity: **duplicate reports are how six people end up at one address while a
street nearby has nobody**, which is the failure the whole project exists to
make visible.

The threshold was measured, not guessed. Against the eight seeded reports:

| | Cosine |
| --- | --- |
| Two genuinely different reports, worst case | **0.157** |
| A restatement of the same incident | **0.409** |
| A restatement using different words | 0.241 |

0.30 sits between the first two with nearly double the margin over the worst
false positive.

## What it's bad at

Written down rather than discovered by a judge.

**Negation, and the lexicon made it worse.** It counts words, so *"no longer
trapped"* and *"trapped"* look similar to it — the fundamental limit of
bag-of-words, with no patching around it. The severity lexicon takes that from
a tendency to a certainty: *"no longer trapped"* contains `trapped`, so it
comes back HIGH, full confidence. We accepted that knowingly. A false HIGH
sends somebody to a house that is already fine; a false MEDIUM leaves somebody
who cannot breathe below the fold. Those are not symmetrical errors and we
would rather make the first one.

**Synonyms.** *"Flooding, couple on the second floor"* and *"water rising, two
adults upstairs"* describe the same house and share almost no vocabulary, so
the duplicate check misses it — that's the 0.241 row above, below the
threshold. Catching it needs embeddings, and embeddings need a model file.

**Fifty-five examples is a demonstration, not a dataset.** Real deployment
would need thousands of real reports, and real reports contain names and
addresses, which is its own problem. It is also why the held-out number moves
around: leaving one report out of 55 changes the model noticeably, which is
not true of a real corpus.

**75% is not good.** It is roughly twice the baseline and it is measured
honestly, which is more than the version we nearly shipped could say, but one
report in four still gets the wrong priority suggested. The reason we are
willing to ship it is that it lands in a dropdown the person filing the report
controls, next to the words that caused it, and it stops adjusting the moment
they touch it. It would not be acceptable as a decision.

**The equipment lexicon is hand-written, so it only knows the words we
thought of.** "Pirogue" and "jon boat" are what people in south Louisiana
actually say and neither is in it. A word list is honest about being a word
list, but it does not generalise, and every gap is invisible until somebody
hits it.

**English only.** Katy is not an English-only town, and that is a real gap
rather than a technicality.

**Flood-shaped.** The corpus is weighted towards flooding and storms because
that is what the Gulf Coast gets. It will be weaker on fire, chemical, or
structural collapse.

**It cannot be wrong safely in every direction.** Under-calling an emergency
is worse than over-calling one, and nothing in the maths knows that. A version
worth deploying would weight the classes asymmetrically.

## It also runs on the phone

The person this suggestion exists for — filing at 2am from a flooded house —
is the person most likely to have no signal. A classifier that needs a round
trip is missing at exactly the moment it was built for.

So the trained model ships to the device. `flask --app app export-model`
writes the word counts to `static/model/priority.json`, about 8 KB, and the
service worker caches it alongside the stylesheet. `static/scripts/classify.js`
reads those numbers.

**That is one model in two runtimes, not two classifiers.** The corpus stays
in `classify.py` and is the only place a training example is ever written. The
JSON is generated, never edited, and the JavaScript evaluates it — it does not
learn anything of its own.

### The condition that makes it survivable

Two implementations of the same maths drift. When they do, somebody offline
gets a confidently different answer from the one they would get online, and
nothing on screen says so — which is worse than having no offline suggestion
at all.

So there is a parity harness. `tools/parity.mjs` runs descriptions through the
browser evaluator and prints what it decided; a test feeds it every line of
the corpus plus a dozen deliberately awkward ones and fails on any
disagreement in priority, confidence, equipment or the words shown. CI
installs node specifically so this cannot skip, because a skip here reads as a
pass.

It found a real bug the first time it ran. The words behind a suggestion are
ranked by how much more likely each is under the chosen class, and where two
words tied, the order fell out of floating-point noise — CPython and V8 round
`log` differently in the last bit. The explanation was unstable, and it was
unstable *in the Python*, on every machine, before any of this. One
implementation could never have shown it. Ties are now rounded flat and broken
alphabetically.

### What still does not work offline

Duplicate detection. It needs every other open report, and that is precisely
the thing the app refuses to keep on a device — see
[docs/offline.md](offline.md). So offline the panel says it has not checked
and why, rather than returning an empty list, which would read as *checked,
found none*. The server runs it the moment the report arrives.

## Trying it

```bash
curl -X POST localhost:5000/api/suggest \
  -H "Content-Type: application/json" \
  -d '{"text":"water rising fast, two people trapped upstairs"}'
```

```bash
curl localhost:5000/api/model     # what it is, and what it is not
```

`/api/model` is public and unauthenticated on purpose: anybody should be able
to find out what the software is doing to their report without making an
account.

## Tests

Exact rather than approximate, because the model is
deterministic — there is no "usually" in a test suite. They cover each
priority band, equipment detection, the confidence floor, refusing to guess at
two words, junk and unicode input, duplicate detection in both directions, and
one that fails if the corpus becomes lopsided enough to under-predict a class.

Plus the two that hold this page to the code: one runs the worked example
above and fails if the page and the software disagree, and one measures
held-out accuracy and fails the build below 68%. Both exist because this file
was wrong once — it quoted a confidence and a set of reasons belonging to a
different sentence than the one printed above them, and that error had already
been copied into a demo video before anybody typed it into the real thing.
