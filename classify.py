"""Reads a report's description and suggests how bad it is.

Somebody filing a report at 2am in a flooded house is being asked to pick a
priority from a dropdown and tick which equipment is needed. They don't know.
They're not trained, they're frightened, and the honest answer to "how severe
is this" is "you tell me".

So this reads what they wrote and suggests. Three pieces, deliberately of
different sophistication:

  * **priority** — a phrase lexicon for the things a triage protocol calls
    immediate, backed by a multinomial naive Bayes classifier over HIGH /
    MEDIUM / LOW for everything else, trained at import from the corpus at
    the bottom of this file. Held out one report at a time, that pairing
    gets 75% of the corpus right; naive Bayes on its own got 45%, against
    36% for always guessing HIGH. The measurement lives in the tests
  * **equipment** — a lexicon, not a model. We built it as five binary
    classifiers first and they were worse; the reasoning is above
    EQUIPMENT_WORDS and it is the most useful thing in this file
  * **duplicates** — TF-IDF cosine similarity against open reports, for
    spotting that a new report describes an incident somebody has already
    filed. Duplicate reports are how six people end up at one address while a
    street nearby has nobody, which is the failure this whole project exists
    to make visible.

WHY NOT A LANGUAGE MODEL
------------------------
Three reasons, in order of how much they matter.

It has to be explainable. Every suggestion here comes back with the words that
caused it, so a coordinator can see *why* and disagree. "Trust me" is not a
thing you get to say to somebody deciding where to send a boat.

It has to be honest about being wrong. This is a bag-of-words model trained on
fifty-five examples, we have measured how often it is wrong, and the number is
written down. It suggests, the human decides, and the dropdown is never
overwritten — the same rule as the triage helper.

It has to run. No download, no GPU, no API key, no network. Pure Python, a few
milliseconds, deterministic, and it works in the disaster this app is for,
where nothing else does.

WHERE IT RUNS
-------------
On the server, and — for priority and equipment only — in the browser with the
radio off. `export_model()` writes the trained counts and the lexicons to
`static/model/priority.json`, and `static/scripts/classify.js` evaluates them.
There is one corpus and it is in this file; the browser gets the model, never a
second copy of the training data. A parity test runs both and fails if they
disagree.

Duplicate detection stays here and only here. It compares against the reports
other people have open right now, and that list is exactly what DiresQ refuses
to store on a device. See `export_model` for the argument.

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

# Equipment is matched by vocabulary, not by the classifier, and that is a
# deliberate step *down* in sophistication.
#
# We built it as five binary naive Bayes models first. With 55 examples split
# five ways the positive class for each capability is a handful of sentences,
# and a long description swamps the signal: "power line down across both lanes,
# still arcing" came back needing a chainsaw at 100% confidence, because one
# training line happened to mention a branch on a power line.
#
# A lexicon cannot do that. It is transparent, it names the word that matched,
# and when it is wrong it is wrong in a way you can see and fix in one line.
#
# We later measured priority the same way and found the same problem, which is
# why LIFE_THREAT_PHRASES exists below. Naive Bayes still does the work on
# everything the lexicon doesn't recognise.
#
# Tokens are stemmed the same way the text is, so "flooding" and "flooded"
# both reach "flood".
EQUIPMENT_WORDS = {
    "boat": ("water", "flood", "rising", "ris", "upstair", "attic", "roof",
             "swept", "submerg", "wade", "current", "swiftwater", "creek",
             "bayou", "drown", "neck", "waist", "deep"),
    "chainsaw": ("tree", "branch", "limb", "trunk", "fallen", "fell", "cut",
                 "blocking", "block", "driveway", "timber"),
    "medical": ("hurt", "injur", "bleed", "unrespons", "unconsciou",
                "breath", "collaps", "pulse", "wound", "chest", "pain",
                "oxygen", "dialysi", "insulin", "medic", "casualt",
                "pinned", "trapp"),
    "truck": ("debri", "haul", "supplie", "supply", "water", "food",
              "tarp", "generator", "move", "clear", "road", "washed"),
    "generator": ("power", "outag", "electricit", "freezer", "fridge",
                  "oxygen", "concentrat", "ventilator", "medical", "fuel"),
}

# Words that mean the equipment is explicitly *not* wanted, or that the report
# is a note rather than a request. Checked first.
STAND_DOWN_WORDS = ("do not send", "dont send", "no need", "not urgent",
                    "for the record", "nobody hurt", "no damage",
                    "reporting in case", "please do not")


# Severity, by phrase, checked before the classifier gets a vote.
#
# This exists because we measured the classifier properly and it was not good
# enough to be the only thing deciding. Held out, naive Bayes alone gets 45%
# of these 55 reports right — against 36% for always guessing HIGH — and the
# way it fails is the way that matters: "child not breathing properly" came
# back MEDIUM, "gas smell, whole street evacuating" came back LOW. A bag of
# words has no idea that "breathing" is different from "fence".
#
# So the same fix that rescued equipment applies here. The phrases below are
# not mined from our corpus — they are the categories any triage protocol
# treats as immediate, which is the same START protocol the app already
# implements: airway, breathing, circulation, entrapment, hazardous material,
# structural collapse, and dependence on powered medical equipment.
#
# Writing them from the protocol rather than from our own failures matters.
# A lexicon tuned against the reports you measure on will score well on those
# reports and teach you nothing.
LIFE_THREAT_PHRASES = (
    # Airway and breathing.
    "not breathing", "cannot breathe", "can't breathe", "struggling to breathe",
    "stopped breathing", "choking", "unresponsive", "unconscious", "no pulse",
    # Circulation.
    "chest pain", "bleeding heavily", "severe bleeding", "losing blood",
    # Entrapment. Deliberately not "cannot get out" — the corpus has "tree
    # across the driveway, cannot get the car out", which is a blocked car
    # and a MEDIUM. The phrase has to name a trapped person, not a trapped
    # object.
    "trapped", "pinned", "stuck inside", "cannot get her out",
    "cannot get him out", "cannot get them out",
    # Hazardous material and live electricity.
    "gas smell", "smell of gas", "smell gas", "gas leak", "live wire",
    "power line down", "sparking", "arcing", "carbon monoxide",
    # Structural collapse.
    "collapsed", "collapsing", "caved in",
    # Powered medical dependence — a timer, not an inconvenience.
    "oxygen concentrator", "ventilator", "dialysis", "insulin",
    # Moving water on a person.
    "swept away", "water up to", "water is up to", "going under",
    # Somebody has already decided it is serious.
    "evacuating", "evacuate now",
)

# The opposite: phrases that say plainly this is not an emergency. Somebody
# who writes "reporting in case it gets worse" has told you the priority.
# Deliberately not "nobody hurt": the corpus has "road washed out at the
# bend, nobody hurt but nobody can pass", and an impassable road is still a
# problem. Nobody being hurt is not the same as nothing being wrong.
ROUTINE_PHRASES = (
    "not blocking", "no damage",
    "reporting in case", "in case it gets", "just letting", "keep an eye",
    "not near any", "phone works fine", "deeper than usual",
    "for the record", "no need", "not urgent",
)

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

# Fewer tokens than this and we say nothing. Two words is not enough to be
# confident about anything, and being confidently wrong is worse than silence.
MIN_TOKENS = 3

# Share of a report's words the model must have seen before, when the wording
# carries no English function words at all, for a suggestion to be offered.
#
# This exists because of the worst thing this file ever did. Typed in Spanish,
# *"mi madre no puede respirar"* — my mother cannot breathe — came back **LOW,
# at 51% confidence, and was shown**. Naive Bayes has no way to abstain: every
# word is unknown, every class falls back to its prior, and the arithmetic
# still produces a label and a number that looks like knowledge.
#
# Measured, not guessed. Across Spanish, German, Vietnamese and romanised
# Mandarin samples the model recognised at most 12% of the words. English
# reports it can actually read score 100%. 0.25 sits at double the margin over
# the worst false positive.
#
# Note what this is *not*: it is not language detection. It is the model
# saying it has never seen these words, which is true of "Barker Cypress
# underpass impassable, two Silverados abandoned" as well — one known word out
# of seven, and any label it produced there would be the prior talking. That
# report is refused too, and correctly.
MIN_KNOWN_SHARE = 0.25

# Decimal places kept before ranking the words behind a suggestion. Two words
# that are mathematically equally telling must come out equal, so the stated
# tie-break decides instead of the last bit of a float. Twelve is far below
# anything that could matter and far above double noise.
TIE_PLACES = 12

# Stripped in this order by _stem. Named rather than inlined because the
# browser copy of the classifier is generated from these, and a suffix list
# that lived in two places would be a suffix list that drifted.
_SUFFIXES = ("ing", "ed", "es", "s")

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


def _stem(word: str) -> str:
    """Crude suffix stripping. Split out so tokenise and surface_forms cannot
    drift apart — if they ever disagree, the explanation stops matching the
    decision, which is the one thing this file is not allowed to do."""
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _words(text: str):
    """The words the classifier will actually look at, before stemming."""
    for raw in re.findall(r"[a-z']+", (text or "").lower()):
        word = raw.replace("'", "")
        if len(word) < 2 or word in STOPWORDS:
            continue
        yield word


def tokenise(text: str) -> list[str]:
    """Words, lowercased, lightly stemmed.

    The stemming is crude on purpose — "flooding", "flooded" and "floods" all
    have to land on the same token or a fifty-example corpus never sees the
    same word twice.
    """
    return [_stem(word) for word in _words(text)]


def surface_forms(text: str) -> dict[str, str]:
    """Each stem, mapped back to the first word in the text that produced it.

    The model counts stems, which is right. Showing somebody a stem is not.
    "Suggested from: ris, upstair, fast" reads like three typos and quietly
    undermines the one thing the suggestion is for — a coordinator being able
    to see why, and disagree. "rising, upstairs, fast" reads like a reason.

    First occurrence wins, so the word shown is the one they typed rather than
    a later inflection of it.
    """
    forms: dict[str, str] = {}
    for word in _words(text):
        forms.setdefault(_stem(word), word)
    return forms


@dataclass
class Suggestion:
    priority: str
    confidence: float
    capabilities: list[str]
    equipment_reasons: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    confident: bool = True
    # True when the model has never seen these words. Distinct from merely
    # unconfident: below the confidence floor it has an opinion and is not
    # sure enough to say it, whereas here it has nothing at all. The
    # interface says which, because "I am unsure" and "I cannot read this"
    # should lead somebody to do different things.
    unreadable: bool = False

    def as_dict(self) -> dict:
        return {
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
            "capabilities": self.capabilities,
            "equipment_reasons": self.equipment_reasons,
            "reasons": self.reasons,
            "confident": self.confident,
            "unreadable": self.unreadable,
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

        Two words can earn exactly the same edge — "trash" (seen once, in LOW)
        and "street" (seen once each in HIGH and MEDIUM, three times in LOW)
        both come out at 0.8149015059934. Mathematically identical; as
        doubles, one of them ends ...488 and the other ...479, and which of
        the two a coordinator is shown depends on the last bit of a logarithm.

        That is not a tie-break, it is noise, and it took porting this to
        JavaScript to notice — two libm implementations rounded the same
        expression differently and the explanations diverged. So round the
        edge well below anything meaningful, and let a stated rule decide the
        rest: strongest first, then alphabetically. Boring, reproducible, and
        the same on every machine.
        """
        others = [x for x in self.labels if x != label]
        ranked = []
        for token in set(tokenise(text)):
            if token not in self.vocabulary:
                continue
            edge = self.weight(token, label) - max(
                self.weight(token, other) for other in others)
            if edge > 0:
                ranked.append((round(edge, TIE_PLACES), token))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
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


def equipment_for(text: str) -> list[tuple[str, str]]:
    """Equipment the wording implies, with the word that implied it.

    At most two. A report that appears to need everything is a report the
    model has not understood, and saying "boat, chainsaw, medical, truck,
    generator" is the same as saying nothing while looking confident.

    Returns [(capability, matched word)], strongest first, so the interface
    can show its reasoning the same way the priority suggestion does.
    """
    lowered = (text or "").lower()
    if any(phrase in lowered for phrase in STAND_DOWN_WORDS):
        return []

    tokens = set(tokenise(text))
    scored = []
    for capability, words in EQUIPMENT_WORDS.items():
        hits = [word for word in words if word in tokens]
        if hits:
            scored.append((len(hits), capability, hits[0]))

    # Most hits first, then alphabetically. Same rule as `why`, stated the
    # same way, so neither ordering is an accident of how a sort was written.
    scored.sort(key=lambda row: (-row[0], row[1]))
    # One clear winner beats two weak ones: only include a second if it has
    # real support of its own.
    keep = [(cap, word) for count, cap, word in scored if count >= 2][:2]
    return keep or [(cap, word) for _, cap, word in scored[:1]]


def severity_for(text: str) -> tuple[str, str] | None:
    """Priority the wording states outright, with the phrase that stated it.

    Returns None when nothing matches, which is the common case — most
    reports don't contain one of these and fall through to the classifier.

    Life-threatening is checked first. A report saying both "trapped" and
    "not blocking the road" is a trapped person next to an unblocked road.
    """
    lowered = " ".join((text or "").lower().split())

    for phrase in LIFE_THREAT_PHRASES:
        if phrase in lowered:
            return "HIGH", phrase

    for phrase in ROUTINE_PHRASES:
        if phrase in lowered:
            return "LOW", phrase

    return None


def _train():
    priority = NaiveBayes(PRIORITIES)
    similarity = Similarity()

    for text, label, _needed in CORPUS:
        priority.learn(text, label)
        similarity.learn(text)

    return priority, similarity


# Trained once, at import. The whole corpus is fifty-five short strings, so
# this costs about a millisecond and there is no model file to ship, version,
# or forget to commit.
_PRIORITY, _SIMILARITY = _train()


def readable(text: str) -> bool:
    """Has the model seen enough of these words to have anything to say?

    Two ways to pass, because emergency English fails either one alone.

    People type telegraphically when frightened — *"water rising fast two
    adults trapped upstairs"* contains no function words at all — so requiring
    them would refuse the corpus itself. And a real report is full of street
    names and brands the model has never seen, so requiring vocabulary alone
    would refuse *"Kingsland Blvd at Peek Rd, Toyota Tundra stalled midway"*.

    Either signal is enough. Together they cleanly separate English the model
    can work with from wording it cannot: see MIN_KNOWN_SHARE.
    """
    words = list(_all_words(text))
    if not words:
        return False
    if any(word in STOPWORDS for word in words):
        return True

    tokens = tokenise(text)
    if not tokens:
        return False
    known = sum(1 for token in tokens if token in _PRIORITY.vocabulary)
    return known / len(tokens) >= MIN_KNOWN_SHARE


def _all_words(text: str):
    """Every word, stopwords included. `_words` drops them; this is the one
    place they carry the signal rather than noise."""
    for raw in re.findall(r"[a-z']+", (text or "").lower()):
        word = raw.replace("'", "")
        if len(word) >= 2:
            yield word


def suggest(text: str) -> Suggestion:
    """Read a description and suggest a priority and what's needed.

    Always a suggestion. Nothing here writes to a report — the person filing
    it picks, and this only changes what the dropdown starts on.
    """
    if len(tokenise(text)) < MIN_TOKENS:
        # Two words is not enough to be confident about anything, and being
        # confidently wrong is worse than saying nothing.
        return Suggestion("MEDIUM", 0.0, [], {}, [], confident=False)

    if not readable(text):
        # Nothing to go on. Naive Bayes cannot abstain — with every word
        # unknown each class falls back to its prior and it still emits a
        # label and a confidence that reads like knowledge. So the abstaining
        # happens here instead.
        return Suggestion("MEDIUM", 0.0, [], {}, [], confident=False,
                          unreadable=True)

    stated = severity_for(text)
    if stated is not None:
        # The report says so in words. Trust that over the arithmetic, and
        # show the phrase, so a coordinator can see exactly what tripped it
        # and disagree in one glance.
        label, phrase = stated
        return Suggestion(
            priority=label,
            confidence=1.0,
            capabilities=[capability for capability, _ in equipment_for(text)],
            equipment_reasons={cap: word for cap, word in equipment_for(text)},
            reasons=[phrase],
            confident=True,
        )

    label, confidence = _PRIORITY.predict(text)

    # The model reasons in stems; the person reads words. Map back before
    # this reaches a screen.
    forms = surface_forms(text)
    reasons = [forms.get(stem, stem) for stem in _PRIORITY.why(text, label)]

    equipment = equipment_for(text)

    return Suggestion(
        priority=label,
        confidence=confidence,
        capabilities=[capability for capability, _ in equipment],
        equipment_reasons={cap: word for cap, word in equipment},
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


def export_model() -> dict:
    """Everything a browser needs to reach the same answer this file does.

    The classifier is Python and it runs on the server, which means the person
    filing at 2am with no signal — exactly the person the suggestion was built
    for — was the one person who never got it. This is how it gets to them.

    What ships is the *trained model*, not a second copy of the logic: the
    word counts, the lexicons, the stopwords, the thresholds. It is generated
    from the objects above, so the corpus has one home and this file is still
    it. `static/scripts/classify.js` is a plain evaluator over this data, and
    a parity test runs every corpus line plus the awkward cases through both
    and fails if they ever disagree by so much as a rounding error.

    Deliberately absent: anything to do with duplicates. Duplicate detection
    compares against the reports other people have open right now, and that
    list is the exact thing this app refuses to keep on a phone — a saved copy
    of who needs help is a lie that gets more convincing the longer it sits
    there. A priority is a fact about the words you typed and it travels. A
    duplicate is a fact about everybody else and it does not. So the browser
    suggests a priority offline, says plainly that it cannot check for
    duplicates yet, and the server does that check when the report lands.

    Written to `static/model/priority.json` by `flask --app app export-model`,
    committed, and served as a static file so the service worker keeps it
    under the same rule as the stylesheets: it is part of the app, not a claim
    about the world.
    """
    return {
        # Bumped when the shape changes, so a stale cached copy is detectable
        # rather than silently wrong.
        "format": 1,
        "labels": list(PRIORITIES),
        "capabilities": list(CAPABILITIES),
        "stopwords": sorted(STOPWORDS),
        "suffixes": list(_SUFFIXES),
        "min_confidence": MIN_CONFIDENCE,
        "min_tokens": MIN_TOKENS,
        "min_known_share": MIN_KNOWN_SHARE,
        "life_threat_phrases": list(LIFE_THREAT_PHRASES),
        "routine_phrases": list(ROUTINE_PHRASES),
        "stand_down_words": list(STAND_DOWN_WORDS),
        "equipment_words": {cap: list(words)
                            for cap, words in EQUIPMENT_WORDS.items()},
        "priors": {label: _PRIORITY.docs[label] for label in PRIORITIES},
        "totals": {label: _PRIORITY.totals[label] for label in PRIORITIES},
        "vocabulary_size": len(_PRIORITY.vocabulary),
        "counts": {label: dict(sorted(_PRIORITY.counts[label].items()))
                   for label in PRIORITIES},
    }


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
        "runs": ("locally, no network, no model file, deterministic — "
                 "and in the browser with no signal, from the same trained "
                 "model exported to static/model/priority.json"),
        "limits": [
            "English only",
            "trained on flood and storm reports, weaker on anything else",
            "bag of words, so it cannot read 'no longer trapped' correctly",
            "fifty-five examples is a demonstration, not a dataset",
            "English only — and it now says so instead of guessing: a report "
            "whose words it has never seen gets no suggestion at all",
            "duplicate detection misses rewordings that share no vocabulary",
            "duplicate detection cannot run offline at all — it compares "
            "against other people's open reports, which this app refuses to "
            "keep on a phone. The server runs it when the report arrives",
            "suggests only — the person filing the report always decides",
        ],
        "duplicate_threshold": DUPLICATE_THRESHOLD,
    }
