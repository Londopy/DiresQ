"""Reads a report's description and suggests how bad it is.

Somebody filing a report at 2am in a flooded house is being asked to pick a
priority from a dropdown and tick which equipment is needed. They don't know.
They're not trained, they're frightened, and the honest answer to "how severe
is this" is "you tell me".

So this reads what they wrote and suggests. Two models, both trained at import
from the corpus at the bottom of this file:

  * a multinomial naive Bayes classifier over HIGH / MEDIUM / LOW
  * one binary scorer per capability — boat, chainsaw, medical, truck,
    generator

And a TF-IDF cosine similarity, used for something different: spotting that a
new report describes an incident somebody has already filed. Duplicate reports
are how six people end up at one address while a street nearby has nobody,
which is the failure this whole project exists to make visible.

WHY NOT A LANGUAGE MODEL
------------------------
Three reasons, in order of how much they matter.

It has to be explainable. Every suggestion here comes back with the words that
caused it, so a coordinator can see *why* and disagree. "Trust me" is not a
thing you get to say to somebody deciding where to send a boat.

It has to be honest about being wrong. This is a bag-of-words model trained on
sixty-odd examples, and it says so. It suggests, the human decides, and the
dropdown is never overwritten — the same rule as the triage helper.

It has to run. No download, no GPU, no API key, no network. Pure Python, a few
milliseconds, deterministic, and it works in the disaster this app is for,
where nothing else does.

The maths is Bayes' theorem and inverse document frequency, both older than
the people who wrote this file. That's a feature: you can read all of it.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

PRIORITIES = ("HIGH", "MEDIUM", "LOW")

CAPABILITIES = ("boat", "chainsaw", "medical", "truck", "generator")

# Words carrying no signal about severity. Deliberately short — aggressive
# stopword lists throw away "no", "not" and "can't", which are exactly the
# words that make a report urgent.
STOPWORDS = frozenset("""
    a an the and or but if of to in on at is are was were be been being it its
    this that these those there here for from with we our us they them their
    he she his her i my me you your as so than then when while about
""".split())

# Below this the suggestion is withheld rather than shown quietly wrong.
MIN_CONFIDENCE = 0.45

# Cosine similarity above which two reports are probably the same incident.
#
# Measured, not guessed. Against the eight seeded reports:
#
#   two genuinely different reports    at most  0.157
#   a restatement of the same incident          0.409
#   a reworded restatement using synonyms       0.241
#
# 0.30 sits between the first two with nearly double the margin over the worst
# false positive. It does miss the synonym case, and that is the honest limit
# of counting words — "flooding, couple on the second floor" and "water
# rising, two adults upstairs" share almost no vocabulary and describe the
# same house. Catching that needs embeddings, and embeddings need a model
# file, a download, and a machine to run it on.
DUPLICATE_THRESHOLD = 0.30


def tokenise(text: str) -> list[str]:
    """Words, lowercased, lightly stemmed.

    The stemming is crude on purpose — "flooding", "flooded" and "floods" all
    have to land on the same token or a sixty-example corpus never sees the
    same word twice.
    """
    words = re.findall(r"[a-z']+", (text or "").lower())
    out = []
    for word in words:
        word = word.replace("'", "")
        if len(word) < 2 or word in STOPWORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.append(word)
    return out


@dataclass
class Suggestion:
    priority: str
    confidence: float
    capabilities: list[str]
    reasons: list[str] = field(default_factory=list)
    confident: bool = True

    def as_dict(self) -> dict:
        return {
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "capabilities": self.capabilities,
            "reasons": self.reasons,
            "confident": self.confident,
        }


class NaiveBayes:
    """Multinomial naive Bayes, in about thirty lines.

    Counts how often each word appears in each class, applies Bayes' theorem,
    and adds one to every count so a word never seen in a class doesn't drive
    its probability to zero (Laplace smoothing). That last part is the whole
    reason it works on a small corpus.
    """

    def __init__(self, labels):
        self.labels = tuple(labels)
        self.counts = {label: Counter() for label in self.labels}
        self.totals = dict.fromkeys(self.labels, 0)
        self.docs = dict.fromkeys(self.labels, 0)
        self.vocabulary: set[str] = set()

    def learn(self, text: str, label: str) -> None:
        tokens = tokenise(text)
        self.counts[label].update(tokens)
        self.totals[label] += len(tokens)
        self.docs[label] += 1
        self.vocabulary.update(tokens)

    def weight(self, token: str, label: str) -> float:
        """log P(token | label), smoothed."""
        return math.log(
            (self.counts[label][token] + 1)
            / (self.totals[label] + len(self.vocabulary) + 1))

    def scores(self, text: str) -> dict[str, float]:
        total_docs = sum(self.docs.values()) or 1
        out = {}
        tokens = tokenise(text)
        for label in self.labels:
            score = math.log((self.docs[label] or 1) / total_docs)
            for token in tokens:
                score += self.weight(token, label)
            out[label] = score
        return out

    def predict(self, text: str) -> tuple[str, float]:
        """Best label, and how sure — softmax over the log scores."""
        scores = self.scores(text)
        best = max(scores, key=scores.get)
        top = scores[best]
        # Subtract the max before exponentiating or long descriptions
        # underflow to zero and every confidence comes out as 1.0.
        weights = {k: math.exp(v - top) for k, v in scores.items()}
        return best, weights[best] / sum(weights.values())

    def why(self, text: str, label: str, limit: int = 3) -> list[str]:
        """The words that pushed hardest towards this label.

        Ranked by how much more likely each word is under this label than
        under the others — a word common everywhere explains nothing.
        """
        others = [x for x in self.labels if x != label]
        ranked = []
        for token in set(tokenise(text)):
            if token not in self.vocabulary:
                continue
            edge = self.weight(token, label) - max(
                self.weight(token, other) for other in others)
            if edge > 0:
                ranked.append((edge, token))
        ranked.sort(reverse=True)
        return [token for _, token in ranked[:limit]]


class Similarity:
    """TF-IDF cosine, for finding a report somebody already filed."""

    def __init__(self):
        self.document_count = 0
        self.seen_in = Counter()

    def learn(self, text: str) -> None:
        self.document_count += 1
        self.seen_in.update(set(tokenise(text)))

    def vector(self, text: str) -> dict[str, float]:
        counts = Counter(tokenise(text))
        if not counts:
            return {}
        vector = {}
        for token, count in counts.items():
            # +1 top and bottom so a word we've never seen still has a weight
            # rather than dividing by zero.
            idf = math.log((self.document_count + 1) / (self.seen_in[token] + 1)) + 1
            vector[token] = (count / len(counts)) * idf
        length = math.sqrt(sum(v * v for v in vector.values())) or 1.0
        return {k: v / length for k, v in vector.items()}

    def between(self, first: str, second: str) -> float:
        a, b = self.vector(first), self.vector(second)
        if not a or not b:
            return 0.0
        shared = a.keys() & b.keys()
        return sum(a[t] * b[t] for t in shared)


# The corpus. Every line is the kind of thing somebody types into the report
# box, labelled with what it turned out to be. Written by hand, weighted
# towards flooding because that's what Katy gets.
#
# It is small, and small is the honest size for a weekend. It is also why the
# confidence floor exists: below MIN_CONFIDENCE the app says nothing rather
# than guessing at somebody.
CORPUS: list[tuple[str, str, tuple[str, ...]]] = [
    # ---- HIGH: life at immediate risk
    ("water rising fast two adults trapped upstairs cannot get out",
     "HIGH", ("boat",)),
    ("family on the roof water is at the second floor windows",
     "HIGH", ("boat",)),
    ("elderly man on oxygen concentrator power out for three hours tank running low",
     "HIGH", ("medical", "generator")),
    ("child not breathing properly after being pulled from the water",
     "HIGH", ("medical",)),
    ("power line down across the road still sparking cars driving over it",
     "HIGH", ()),
    ("house fire spreading to the next building people still inside",
     "HIGH", ("medical",)),
    ("car swept off the road driver still inside water rising around it",
     "HIGH", ("boat", "medical")),
    ("gas smell very strong whole street evacuating now",
     "HIGH", ()),
    ("tree fell through the bedroom someone is pinned underneath",
     "HIGH", ("chainsaw", "medical")),
    ("wheelchair user alone downstairs water coming in under the door",
     "HIGH", ("boat",)),
    ("elderly woman collapsed and unresponsive we cannot wake her",
     "HIGH", ("medical",)),
    ("dialysis patient missed treatment two days roads flooded",
     "HIGH", ("medical", "boat")),
    ("water over the porch and rising they have gone to the attic no ladder",
     "HIGH", ("boat",)),
    ("bleeding badly from the arm cannot stop it",
     "HIGH", ("medical",)),
    ("infant in the house no formula no clean water three days",
     "HIGH", ("medical", "truck")),
    ("roof collapsed on the back half of the house people unaccounted for",
     "HIGH", ("chainsaw", "medical")),
    ("man having chest pains ambulance cannot reach us",
     "HIGH", ("medical",)),
    ("water in the house neck deep two people standing on furniture",
     "HIGH", ("boat",)),
    ("live wire in standing water in the front yard children nearby",
     "HIGH", ()),
    ("trapped in the car water up to the windows on the crossing",
     "HIGH", ("boat", "medical")),

    # ---- MEDIUM: needs help, can wait a little
    ("tree across the driveway cannot get the car out not hurt",
     "MEDIUM", ("chainsaw",)),
    ("roof peeled back tarp needed before the next band of rain",
     "MEDIUM", ("truck",)),
    ("car in the water at the crossing driver got out and is on the bank",
     "MEDIUM", ("truck",)),
    ("storm drain blocked water backing up ankle deep and climbing",
     "MEDIUM", ()),
    ("fence down large branch leaning on the power line to the house",
     "MEDIUM", ("chainsaw",)),
    ("no power since last night freezer thawing elderly couple coping",
     "MEDIUM", ("generator",)),
    ("water in the garage not in the house yet but coming up",
     "MEDIUM", ()),
    ("large branch blocking one lane traffic getting around it",
     "MEDIUM", ("chainsaw",)),
    ("need drinking water and food for four people been two days",
     "MEDIUM", ("truck",)),
    ("shed roof came off sheet metal in the road",
     "MEDIUM", ("truck",)),
    ("ceiling sagging in the kitchen water coming through",
     "MEDIUM", ()),
    ("elderly neighbour has not answered the door since yesterday",
     "MEDIUM", ("medical",)),
    ("septic backed up into the yard smells bad kids playing outside",
     "MEDIUM", ()),
    ("cannot reach my mother phone is dead she lives on the flooded street",
     "MEDIUM", ("boat",)),
    ("half the fence down two large trees leaning over the neighbours roof",
     "MEDIUM", ("chainsaw",)),
    ("generator running out of fuel medical equipment plugged into it",
     "MEDIUM", ("generator", "truck")),
    ("water reached the crawl space furnace may be flooded",
     "MEDIUM", ()),
    ("road washed out at the bend nobody hurt but nobody can pass",
     "MEDIUM", ("truck",)),
    ("stuck at work cannot get home to check on my father",
     "MEDIUM", ()),
    ("mud and debris blocking the back door can get out the front",
     "MEDIUM", ("truck",)),

    # ---- LOW: reporting for the record
    ("fence down two dogs loose please do not send anyone",
     "LOW", ()),
    ("small branches all over the lawn nothing blocking anything",
     "LOW", ()),
    ("power flickering but still on reporting in case it goes",
     "LOW", ()),
    ("water pooling at the end of the street not near any houses",
     "LOW", ()),
    ("mailbox knocked over by the wind no other damage",
     "LOW", ()),
    ("lost a few roof shingles no leak reporting for the record",
     "LOW", ()),
    ("garden furniture blew into the pool everyone fine",
     "LOW", ()),
    ("cat missing since the storm please keep an eye out",
     "LOW", ()),
    ("gutter came loose hanging off the front of the house",
     "LOW", ()),
    ("street sign bent over not blocking the road",
     "LOW", ()),
    ("small leak in the garage roof nothing urgent",
     "LOW", ()),
    ("trash cans washed down the street looking for them tomorrow",
     "LOW", ()),
    ("neighbours tree lost a big limb it is on their own lawn",
     "LOW", ()),
    ("internet down phone works fine just letting people know",
     "LOW", ()),
    ("puddle in the yard deeper than usual watching it",
     "LOW", ()),
]


def _train():
    priority = NaiveBayes(PRIORITIES)
    capability = {name: NaiveBayes(("yes", "no")) for name in CAPABILITIES}
    similarity = Similarity()

    for text, label, needed in CORPUS:
        priority.learn(text, label)
        similarity.learn(text)
        for name, model in capability.items():
            model.learn(text, "yes" if name in needed else "no")

    return priority, capability, similarity


# Trained once, at import. The whole corpus is sixty short strings, so this
# costs about a millisecond and there is no model file to ship, version, or
# forget to commit.
_PRIORITY, _CAPABILITY, _SIMILARITY = _train()


def suggest(text: str) -> Suggestion:
    """Read a description and suggest a priority and what's needed.

    Always a suggestion. Nothing here writes to a report — the person filing
    it picks, and this only changes what the dropdown starts on.
    """
    if len(tokenise(text)) < 3:
        # Two words is not enough to be confident about anything, and being
        # confidently wrong is worse than saying nothing.
        return Suggestion("MEDIUM", 0.0, [], [], confident=False)

    label, confidence = _PRIORITY.predict(text)
    reasons = _PRIORITY.why(text, label)

    needed = []
    for name, model in _CAPABILITY.items():
        guess, sure = model.predict(text)
        if guess == "yes" and sure > 0.6:
            needed.append(name)

    return Suggestion(
        priority=label,
        confidence=confidence,
        capabilities=needed,
        reasons=reasons,
        confident=confidence >= MIN_CONFIDENCE,
    )


def duplicates(text: str, existing: list[dict], limit: int = 3) -> list[dict]:
    """Reports that look like they describe the same incident.

    `existing` is dicts with at least `id` and `subject`; `description` is
    used too when present. Returns the closest matches above the threshold,
    each with the score, so the interface can say how sure it is.
    """
    scored = []
    for report in existing:
        other = f"{report.get('subject', '')} {report.get('description', '')}"
        score = _SIMILARITY.between(text, other)
        if score >= DUPLICATE_THRESHOLD:
            scored.append({
                "id": report.get("id"),
                "subject": report.get("subject"),
                "score": round(score, 3),
            })
    scored.sort(key=lambda r: -r["score"])
    return scored[:limit]


def model_card() -> dict:
    """What this is, for anyone who asks. Including the bad news."""
    per_class = defaultdict(int)
    for _, label, _ in CORPUS:
        per_class[label] += 1

    return {
        "kind": "multinomial naive Bayes, bag of words",
        "trained_on": f"{len(CORPUS)} hand-labelled reports",
        "per_class": dict(per_class),
        "vocabulary": len(_PRIORITY.vocabulary),
        "capabilities": list(CAPABILITIES),
        "runs": "locally, no network, no model file, deterministic",
        "limits": [
            "English only",
            "trained on flood and storm reports, weaker on anything else",
            "bag of words, so it cannot read 'no longer trapped' correctly",
            "sixty examples is a demonstration, not a dataset",
            "duplicate detection misses rewordings that share no vocabulary",
            "suggests only — the person filing the report always decides",
        ],
        "duplicate_threshold": DUPLICATE_THRESHOLD,
    }
