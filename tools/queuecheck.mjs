// Runs the real `reportqueue.js` against a fake browser and prints what it
// did, as JSON, so a Python test can assert on behaviour rather than on the
// shape of the source.
//
// Most of the queue's tests read the file and check that two statements are
// in the right order, because the bugs there are invisible at runtime and
// obvious in the source. This is the other half: the expiry path has real
// logic in it — split the queue, move one half somewhere it will be noticed,
// write the other half back — and "the words `strand(expired)` appear in the
// file" does not prove any of that happened.
//
// It matters most for the case it was written for. A report that runs out of
// time used to be filtered out on read and never mentioned: somebody pressed
// submit, was told it was saved, and half a day later it was gone. That is
// the silent disappearance this whole project argues against, so the fix
// deserves a test that actually watches it work.
//
//     node tools/queuecheck.mjs
//
// Prints one JSON object. Exits non-zero if the module cannot even load.

import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "static", "scripts", "reportqueue.js");

// --- the smallest browser the module will accept -------------------------
const store = new Map();
globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
};
globalThis.document = {
    addEventListener() {},
    createElement: () => ({ setAttribute() {}, style: {} }),
    body: { appendChild() {} },
    dispatchEvent() {},
};
globalThis.CustomEvent = class {
    constructor(type, options) { this.type = type; Object.assign(this, options); }
};
globalThis.window = { addEventListener() {}, crypto: globalThis.crypto };
globalThis.setInterval = () => 0;
// Offline, always. Nothing here should reach a network, and if it tries we
// want to find out rather than quietly succeed against a real server.
globalThis.fetch = async () => { throw new Error("offline"); };

const QUEUE = "diresq.queue.reports";
const agedHours = (n) => new Date(Date.now() - n * 3600 * 1000).toISOString();

store.set(QUEUE, JSON.stringify([
    {
        client_id: "too-old",
        subject: "Water rising on Kingsland",
        description: "Two adults upstairs, cannot get out",
        written_at: agedHours(13),      // past MAX_AGE_HOURS
    },
    {
        client_id: "still-good",
        subject: "Tree down",
        description: "Across the drive",
        written_at: agedHours(1),
    },
]));

// A bare .js file in a directory with no package.json is read as CommonJS,
// where `export` is a syntax error. A data URL is always a module and needs
// no scratch directory. These are the shipped file's own bytes.
const asModule = "data:text/javascript;base64,"
    + Buffer.from(await readFile(source, "utf8"), "utf8").toString("base64");
const queue = await import(asModule);

const lost = queue.stranded();
const afterSift = JSON.parse(store.getItem?.(QUEUE) ?? store.get(QUEUE));

queue.clearStranded();

console.log(JSON.stringify({
    // The fresh one is still sendable; the expired one is not counted as
    // waiting, because it is not.
    pending: queue.pending(),
    // ...but it has not been thrown away.
    stranded: lost.length,
    stranded_subject: lost[0]?.subject ?? null,
    // Their own words, which the queue is now the only copy of.
    stranded_description: lost[0]?.description ?? null,
    // Actually removed, rather than filtered on every read and written back.
    queue_ids: afterSift.map((item) => item.client_id),
    // Dismissing what they have read must not touch anything still sendable.
    stranded_after_clear: queue.stranded().length,
    pending_after_clear: queue.pending(),
}));
