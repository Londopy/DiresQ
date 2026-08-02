# The classifier

DiresQ reads what somebody types into a report and suggests how bad it is,
what equipment is needed, and whether the same incident has already been
reported.

It is a **multinomial naive Bayes classifier over a bag of words**, written by
hand in about 250 lines of Python, trained at import from a corpus of 65
labelled reports. No dependencies, no model file, no network, no GPU. It runs
in about **0.1 milliseconds**.

It is not a language model, and this page explains why that was the right
call rather than a compromise.

---

## The problem it solves

Somebody filing a report at 2am from a flooded house is being asked to pick a
severity from a dropdown and tick which equipment is needed.

They don't know. They aren't trained, they're frightened, and the honest
answer to "how severe is this on a three-point scale" is *you tell me* — the
person asking is the one with the map and the volunteers, not the person
standing in the water.

So the app reads what they wrote:

> *"Water is coming up the stairs, my grandmother is upstairs and she can't
> walk down"*

```
HIGH · 95% sure · boat
Suggested from: rising, upstairs, cannot. You decide — change it if it's wrong.
```

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
a bag-of-words model trained on 65 examples and it will be wrong regularly,
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

### Explanation

For the chosen class, each word is scored by how much *more* likely it is
under that class than under the best alternative. A word common everywhere
explains nothing, and this ranking drops it automatically. Top three are
shown.

### Equipment

One binary classifier per capability — boat, chainsaw, medical, truck,
generator — each trained on the same corpus with the capability labels. Shown
only above 60% confidence.

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

**Negation.** It counts words, so *"no longer trapped"* and *"trapped"* look
similar to it. This is the fundamental limit of bag-of-words and there is no
patching around it.

**Synonyms.** *"Flooding, couple on the second floor"* and *"water rising, two
adults upstairs"* describe the same house and share almost no vocabulary, so
the duplicate check misses it — that's the 0.241 row above, below the
threshold. Catching it needs embeddings, and embeddings need a model file.

**Sixty-five examples is a demonstration, not a dataset.** Real deployment
would need thousands of real reports, and real reports contain names and
addresses, which is its own problem.

**English only.** Katy is not an English-only town, and that is a real gap
rather than a technicality.

**Flood-shaped.** The corpus is weighted towards flooding and storms because
that is what the Gulf Coast gets. It will be weaker on fire, chemical, or
structural collapse.

**It cannot be wrong safely in every direction.** Under-calling an emergency
is worse than over-calling one, and nothing in the maths knows that. A version
worth deploying would weight the classes asymmetrically.

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

Twenty-three, and they're exact rather than approximate, because the model is
deterministic — there is no "usually" in a test suite. They cover each
priority band, equipment detection, the confidence floor, refusing to guess at
two words, junk and unicode input, duplicate detection in both directions, and
one that fails if the corpus becomes lopsided enough to under-predict a class.
