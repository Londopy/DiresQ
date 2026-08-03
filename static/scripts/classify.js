// The priority classifier, running on the phone.
//
// WHY THIS FILE EXISTS
// --------------------
// The suggestion was built for one person in particular: somebody filing a
// report at 2am, frightened, untrained, being asked by a dropdown how severe
// their own emergency is. That person is the most likely of anyone to have no
// signal — a flood takes the cell towers out along with everything else — and
// until this file existed they were the one person the classifier never
// reached. It ran in Python, on a server, over a network that was gone.
//
// WHAT THIS IS NOT
// ----------------
// It is not a second copy of the classifier. The corpus, the lexicons and the
// thresholds all live in `classify.py` and nowhere else; this reads the
// trained model out of `/static/model/priority.json`, which is generated from
// that file by `flask --app app export-model`. Two implementations of one
// model is a drift bug waiting to happen, so there is a parity test that runs
// every line of the corpus and a pile of awkward cases through both and fails
// if the answers differ.
//
// The arithmetic below is the same arithmetic, in the same order:
//
//   1. too few words -> say nothing
//   2. a phrase that states the severity outright -> trust it, show the phrase
//   3. otherwise multinomial naive Bayes over the exported counts
//   4. below the confidence floor -> say nothing rather than guess
//
// WHAT IT DELIBERATELY CANNOT DO
// ------------------------------
// Duplicates. That check compares your description against the reports
// everyone else has open right now, and DiresQ refuses to keep that list on a
// phone — a saved copy of who needs help is a lie that gets more convincing
// the longer it sits there. A priority is a fact about the words you typed and
// it travels offline. A duplicate is a fact about everybody else and it does
// not. So offline you get the priority, you are told plainly that the
// duplicate check has not run, and the server runs it the moment the report
// lands.

const MODEL_URL = "/static/model/priority.json";

let model = null;
let loading = null;

/** Fetch the model once. Cached by the service worker, so this works offline
 *  on any device that has loaded the app at least once with a connection. */
export async function load() {
    if (model) return model;
    if (!loading) {
        loading = fetch(MODEL_URL, { credentials: "same-origin" })
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                // An older or newer artifact is not something to guess at.
                model = data && data.format === 1 ? data : null;
                return model;
            })
            .catch(() => null);
    }
    return loading;
}

/** True once the model is in hand. The form asks before promising anything. */
export function ready() {
    return model !== null;
}

function stem(word) {
    for (const suffix of model.suffixes) {
        if (word.length > suffix.length + 2 && word.endsWith(suffix)) {
            return word.slice(0, -suffix.length);
        }
    }
    return word;
}

/** The words the classifier looks at, before stemming. */
function words(text) {
    const stop = new Set(model.stopwords);
    const out = [];
    for (const raw of String(text || "").toLowerCase().match(/[a-z']+/g) || []) {
        const word = raw.replace(/'/g, "");
        if (word.length < 2 || stop.has(word)) continue;
        out.push(word);
    }
    return out;
}

function tokenise(text) {
    return words(text).map(stem);
}

/** Each stem mapped back to the first word in the text that produced it.
 *  The model counts stems; showing somebody a stem reads like a typo and
 *  quietly undermines the only thing the suggestion is for. */
function surfaceForms(text) {
    const forms = new Map();
    for (const word of words(text)) {
        const key = stem(word);
        if (!forms.has(key)) forms.set(key, word);
    }
    return forms;
}

// Decimal places kept before ranking. Mirrors TIE_PLACES in classify.py, and
// has to stay in step with it — the parity test is what says so.
const TIE_PLACES = 12;

function round(value) {
    // Python's round() is banker's rounding; at twelve places on values this
    // size the two never separate, and the point is only to erase the last
    // bit or two of float noise before a comparison.
    return Number(value.toFixed(TIE_PLACES));
}

/** Ascending string order, the way Python compares two str. Both are code
 *  point order for the lowercase ASCII these tokens are made of. */
function compare(a, b) {
    return a < b ? -1 : a > b ? 1 : 0;
}

/** log P(token | label), Laplace-smoothed. Same expression as the Python. */
function weight(token, label) {
    const seen = model.counts[label][token] || 0;
    return Math.log((seen + 1)
        / (model.totals[label] + model.vocabulary_size + 1));
}

function scores(tokens) {
    const totalDocs = model.labels.reduce((n, l) => n + model.priors[l], 0) || 1;
    const out = {};
    for (const label of model.labels) {
        let score = Math.log((model.priors[label] || 1) / totalDocs);
        for (const token of tokens) score += weight(token, label);
        out[label] = score;
    }
    return out;
}

function predict(text) {
    const tokens = tokenise(text);
    const all = scores(tokens);

    // Python's `max(scores, key=scores.get)` keeps the first on a tie, and its
    // dict is in label order. Strictly-greater over the same order matches it.
    let best = model.labels[0];
    for (const label of model.labels) {
        if (all[label] > all[best]) best = label;
    }

    // Subtract the max before exponentiating, or a long description underflows
    // to zero and every confidence comes out as a confident 1.0.
    const top = all[best];
    let sum = 0;
    for (const label of model.labels) sum += Math.exp(all[label] - top);
    return [best, Math.exp(all[best] - top) / sum];
}

/** The words that pushed hardest towards this label, ranked by how much more
 *  likely each is here than anywhere else. A word common everywhere explains
 *  nothing. */
function why(text, label, limit = 3) {
    const others = model.labels.filter((l) => l !== label);
    const vocabulary = new Set(Object.keys(model.counts[label]));
    for (const other of others) {
        for (const token of Object.keys(model.counts[other])) {
            vocabulary.add(token);
        }
    }

    const ranked = [];
    for (const token of new Set(tokenise(text))) {
        if (!vocabulary.has(token)) continue;
        const rival = Math.max(...others.map((o) => weight(token, o)));
        // Rounded before ranking, and this is the reason the rounding exists
        // at all. Two words can be exactly as telling as each other, and V8's
        // Math.log and CPython's math.log disagree about the last bit of the
        // same expression — so without this, the browser and the server show
        // a coordinator different explanations for identical input. Found by
        // the parity test, which is the only way it could have been found.
        const edge = round(weight(token, label) - rival);
        if (edge > 0) ranked.push([edge, token]);
    }

    // Strongest first, then alphabetically. The same stated rule as the
    // Python, written the same way round.
    ranked.sort((a, b) => (b[0] - a[0]) || compare(a[1], b[1]));
    return ranked.slice(0, limit).map(([, token]) => token);
}

/** Equipment the wording implies, with the word that implied it. At most two:
 *  a report that appears to need everything is a report nothing understood. */
function equipmentFor(text) {
    const lowered = String(text || "").toLowerCase();
    if (model.stand_down_words.some((phrase) => lowered.includes(phrase))) {
        return [];
    }

    const tokens = new Set(tokenise(text));
    const scored = [];
    for (const [capability, list] of Object.entries(model.equipment_words)) {
        const hits = list.filter((word) => tokens.has(word));
        if (hits.length) scored.push([hits.length, capability, hits[0]]);
    }

    // Most hits first, then alphabetically. Counts are integers, so there is
    // no float noise here — but the rule is written the same way as `why` so
    // that neither ordering looks like an accident of how a sort was typed.
    scored.sort((a, b) => (b[0] - a[0]) || compare(a[1], b[1]));

    const strong = scored.filter(([count]) => count >= 2).slice(0, 2);
    const keep = strong.length ? strong : scored.slice(0, 1);
    return keep.map(([, capability, word]) => [capability, word]);
}

/** Priority the wording states outright, with the phrase that stated it.
 *  Life-threatening is checked first: a report saying both "trapped" and
 *  "not blocking the road" is a trapped person next to an unblocked road. */
function severityFor(text) {
    const lowered = String(text || "").toLowerCase().split(/\s+/)
        .filter(Boolean).join(" ");
    for (const phrase of model.life_threat_phrases) {
        if (lowered.includes(phrase)) return ["HIGH", phrase];
    }
    for (const phrase of model.routine_phrases) {
        if (lowered.includes(phrase)) return ["LOW", phrase];
    }
    return null;
}

/**
 * Suggest a priority and equipment for a description. Never a decision.
 *
 * Returns the same shape `/api/suggest` does, minus `duplicates` — which is
 * absent rather than empty, because an empty list would read as "we checked
 * and found none" and nothing has checked anything.
 */
export function suggest(text) {
    if (!model) return null;

    const capsOf = (pairs) => ({
        capabilities: pairs.map(([capability]) => capability),
        equipment_reasons: Object.fromEntries(pairs),
    });

    if (tokenise(text).length < model.min_tokens) {
        return {
            priority: "MEDIUM",
            confidence: 0.0,
            capabilities: [],
            equipment_reasons: {},
            reasons: [],
            confident: false,
            offline: true,
        };
    }

    const stated = severityFor(text);
    if (stated) {
        const [label, phrase] = stated;
        return {
            priority: label,
            confidence: 1.0,
            ...capsOf(equipmentFor(text)),
            reasons: [phrase],
            confident: true,
            offline: true,
        };
    }

    const [label, confidence] = predict(text);
    const forms = surfaceForms(text);

    return {
        priority: label,
        confidence,
        ...capsOf(equipmentFor(text)),
        reasons: why(text, label).map((s) => forms.get(s) || s),
        confident: confidence >= model.min_confidence,
        offline: true,
    };
}
