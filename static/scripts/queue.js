// Check-ins that survive having no signal.
//
// A check-in is the one thing in DiresQ that has to work when the network
// doesn't — it's the message that says you're alive, and it gets sent from
// exactly the places where the network has fallen over. So it goes into
// localStorage first and onto the wire second.
//
// Three things make this safe rather than just optimistic:
//
//   * every check-in carries the time it was MADE, so the overdue timer
//     judges you on when you pressed the button, not when your phone found a
//     bar of signal;
//   * every check-in carries an id made before it is sent, so retrying is
//     free — the server recognises one it already has instead of logging you
//     twice;
//   * the queue is visible. A queue you can't see is a queue you don't trust,
//     and this one is meant to be trusted in the dark, in the rain.

const KEY = "diresq.queue.checkins";

// The server refuses anything older than twelve hours, so there is no point
// carrying one around past that. Drop it here rather than sending it to be
// rejected.
const MAX_AGE_HOURS = 12;

const RETRY_MS = 15000;

function newId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    // Older browsers. Doesn't need to be unguessable, only unique to us.
    return "cid-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10);
}

function read() {
    try {
        const raw = localStorage.getItem(KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (err) {
        // Private browsing, a full disk, or somebody's extension. A broken
        // queue must not take the page with it.
        return [];
    }
}

function write(items) {
    try {
        localStorage.setItem(KEY, JSON.stringify(items));
    } catch (err) {
        // Nothing sensible to do. The check-in is already on its way or lost;
        // crashing here would only lose the rest of them too.
    }
}

function fresh(items) {
    const cutoff = Date.now() - MAX_AGE_HOURS * 3600 * 1000;
    return items.filter(item => Date.parse(item.happened_at) > cutoff);
}

export function pending() {
    return fresh(read()).length;
}

function enqueue(checkin) {
    const items = fresh(read());
    items.push(checkin);
    write(items);
    announce();
}

function remove(clientId) {
    write(fresh(read()).filter(item => item.client_id !== clientId));
    announce();
}

// One custom event, so the pill and anything else can listen without this
// module knowing what the page looks like.
function announce() {
    document.dispatchEvent(
        new CustomEvent("diresq:queue", { detail: { pending: pending() } }));
}

async function post(checkin) {
    const res = await fetch("/api/checkin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(checkin),
    });

    if (res.ok) return "sent";

    // 4xx means the server looked at it and said no — too old, bad
    // timestamp, not your id. Retrying will get the same answer forever, so
    // stop carrying it.
    if (res.status >= 400 && res.status < 500) return "refused";

    // 5xx is the server having a bad time, which it may stop having.
    throw new Error("server error " + res.status);
}

let flushing = false;

export async function flush() {
    if (flushing) return;
    flushing = true;

    try {
        for (const checkin of fresh(read())) {
            let outcome;
            try {
                outcome = await post(checkin);
            } catch (err) {
                // Offline, or the server is down. Everything still queued
                // stays queued — stop here rather than hammering.
                break;
            }
            if (outcome === "sent" || outcome === "refused") {
                remove(checkin.client_id);
            }
        }
    } finally {
        flushing = false;
        announce();
    }
}

/** Send a check-in, or keep it until we can. Never throws. */
export async function send({ lat = null, lng = null } = {}) {
    const checkin = {
        client_id: newId(),
        lat,
        lng,
        // Recorded now, not when it eventually goes. This is the whole point.
        happened_at: new Date().toISOString(),
    };

    try {
        if (await post(checkin) === "sent") {
            announce();
            return { queued: false };
        }
        return { queued: false, refused: true };
    } catch (err) {
        enqueue(checkin);
        return { queued: true };
    }
}

// A pill in the corner saying how many are waiting. Built here rather than in
// the templates so every page that loads this module gets it.
function pill() {
    const el = document.createElement("div");
    el.className = "queue-pill";
    el.hidden = true;
    el.setAttribute("role", "status");
    document.body.appendChild(el);

    document.addEventListener("diresq:queue", (e) => {
        const n = e.detail.pending;
        el.hidden = n === 0;
        el.textContent = n === 1
            ? "1 check-in waiting for signal"
            : `${n} check-ins waiting for signal`;
    });
}

pill();
announce();
flush();

window.addEventListener("online", flush);
setInterval(flush, RETRY_MS);
