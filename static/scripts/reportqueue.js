// Reports that survive having no signal — and, unlike a check-in, survive
// being sent twice.
//
// WHY THIS IS NOT queue.js
// ------------------------
// The check-in queue tries the network first and only writes to localStorage
// when that fails. For a check-in that is fine: the message is "I am alive",
// and losing one in flight costs a timer that resets a minute later.
//
// A report is not that. Sending one twice creates a second incident, and
// duplicate incidents are how six people end up at one address while the next
// street has nobody — the precise failure this whole project exists to
// prevent. And "did that send?" is exactly the question a dying connection is
// built to make unanswerable.
//
// So this is an outbox, not a retry buffer, and the order is the whole design:
//
//   1. mint an id and write the report to localStorage
//   2. only then touch the network
//   3. only delete it once the server has said, in so many words, that it has
//      it — either "I wrote this" or "I already had this"
//
// Because step 1 happens before step 2, the id is on disk before anything can
// go wrong. A phone that dies mid-request, a browser killed by the OS, a tab
// closed in a panic: the retry after the restart carries the same id, the
// server recognises it, and hands back the report it already wrote instead of
// filing a second one. A client-side guard would have been erased by the
// restart; a UNIQUE constraint alone would only complain after the duplicate
// had already been attempted. The check is server-side, before the INSERT.
//
// WHEN IT WAS WRITTEN, NOT WHEN IT ARRIVED
// ----------------------------------------
// Every queued report carries `written_at`, stamped when the person pressed
// Submit. A report typed forty minutes ago describes a house that may already
// have been cleared, and the feed says so rather than rendering it as
// something that has only just come in.

const KEY = "diresq.queue.reports";

// The server refuses anything older than twelve hours, so carrying one past
// that only earns a rejection. Drop it here instead — but say so, because a
// report vanishing silently is its own kind of lie.
const MAX_AGE_HOURS = 12;

const RETRY_MS = 15000;

export function newId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    // Older browsers. It doesn't need to be unguessable, only unique to us.
    return "rid-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
}

function read() {
    try {
        const raw = localStorage.getItem(KEY);
        const items = raw ? JSON.parse(raw) : [];
        return Array.isArray(items) ? items : [];
    } catch (err) {
        // Private browsing, a full disk, somebody's extension. A broken queue
        // must not take the page down with it.
        return [];
    }
}

/** Write the queue, and say whether it actually landed on disk.
 *
 *  The return value matters here in a way it doesn't for check-ins: if we
 *  cannot persist, we must not promise the report is safe, and the caller
 *  falls back to a plain form post so the person at least finds out now.
 */
function write(items) {
    try {
        localStorage.setItem(KEY, JSON.stringify(items));
        return true;
    } catch (err) {
        return false;
    }
}

function fresh(items) {
    const cutoff = Date.now() - MAX_AGE_HOURS * 3600 * 1000;
    return items.filter((item) => Date.parse(item.written_at) > cutoff);
}

export function pending() {
    return fresh(read()).length;
}

function remove(clientId) {
    write(fresh(read()).filter((item) => item.client_id !== clientId));
    announce();
}

function announce() {
    document.dispatchEvent(
        new CustomEvent("diresq:reportqueue", { detail: { pending: pending() } }));
}

async function post(report) {
    const res = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(report),
    });

    // 201 wrote it, 200 means the server already had this exact id. Both are
    // "done", and that equivalence is the entire reason the id exists.
    if (res.ok) return { done: true, body: await res.json().catch(() => ({})) };

    // 4xx: the server looked at it and said no — too old, missing a field,
    // somebody else's id. Retrying earns the same answer forever.
    if (res.status >= 400 && res.status < 500) {
        return { done: true, refused: true,
                 body: await res.json().catch(() => ({})) };
    }

    // 5xx is the server having a bad time, which it may stop having.
    throw new Error("server error " + res.status);
}

let flushing = false;

/** Try to send everything waiting. Never throws. */
export async function flush() {
    if (flushing) return;
    flushing = true;

    try {
        for (const report of fresh(read())) {
            let outcome;
            try {
                outcome = await post(report);
            } catch (err) {
                // Offline, or the server is down. Stop here rather than
                // hammering; everything still queued stays queued.
                break;
            }
            if (outcome.done) {
                remove(report.client_id);
                document.dispatchEvent(new CustomEvent("diresq:reportsent", {
                    detail: { report, ...outcome.body, refused: !!outcome.refused },
                }));
            }
        }
    } finally {
        flushing = false;
        announce();
    }
}

/**
 * File a report. Writes it down before trying to send it.
 *
 * Returns `{ stored, sent, url, duplicate, possible_duplicate }`.
 * `stored: false` means localStorage refused us and the caller must not
 * pretend the report is safe anywhere.
 */
export async function file(fields) {
    const report = {
        ...fields,
        client_id: newId(),
        // Stamped now, at the press of the button. Not when it eventually
        // goes. This is the difference between "a house needs help" and "a
        // house needed help forty minutes ago".
        written_at: new Date().toISOString(),
    };

    // Disk first. Everything after this line is allowed to fail.
    const items = fresh(read());
    items.push(report);
    if (!write(items)) return { stored: false, sent: false };
    announce();

    try {
        const outcome = await post(report);
        remove(report.client_id);
        return { stored: true, sent: true, refused: !!outcome.refused,
                 ...outcome.body };
    } catch (err) {
        // Still on disk, still queued, still carrying the same id.
        return { stored: true, sent: false };
    }
}

/** A pill in the corner saying how many are waiting. A queue you cannot see
 *  is a queue you do not trust, and this one has to be trusted in the dark.
 *
 *  Deliberately not a live region, unlike the check-in pill. On the report
 *  form the status line above the button is the announcement, and it already
 *  says how many are waiting — two live regions firing on one action means a
 *  screen reader reads the same fact twice and the important half is the one
 *  that gets talked over. This is the visual copy of something already said.
 */
function pill() {
    const el = document.createElement("div");
    el.className = "queue-pill reports";
    el.hidden = true;
    el.setAttribute("aria-hidden", "true");
    document.body.appendChild(el);

    document.addEventListener("diresq:reportqueue", (e) => {
        const n = e.detail.pending;
        el.hidden = n === 0;
        el.textContent = n === 1
            ? "1 report waiting for signal"
            : `${n} reports waiting for signal`;
    });
}

pill();
announce();
flush();

window.addEventListener("online", flush);
setInterval(flush, RETRY_MS);
