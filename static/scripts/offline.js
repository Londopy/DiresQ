// Renders the offline page from whatever the service worker last kept.
//
// Everything here comes from /api/me, which is only ever about the person
// holding the phone. Nothing on this page describes anybody else, because
// nothing about anybody else stays true while you cannot reach the server.

const RETRY_MS = 5000;

/** The cached copy, or null if the worker never got one. */
async function lastKnown() {
    if (!("caches" in window)) return null;
    try {
        const hit = await caches.match("/api/me");
        return hit ? await hit.json() : null;
    } catch (err) {
        return null;
    }
}

function when(iso) {
    if (!iso) return "";
    const at = new Date(iso);
    if (Number.isNaN(at.getTime())) return "";
    return at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function overdue(iso) {
    if (!iso) return false;
    const due = new Date(iso);
    return !Number.isNaN(due.getTime()) && Date.now() > due.getTime();
}

function show(id) { document.getElementById(id).hidden = false; }

function render(me) {
    if (!me) return;   // never cached; the static copy above still reads fine

    if (!me.assignment) {
        show("nothing");
    } else {
        const a = me.assignment;
        document.getElementById("subject").textContent = a.subject;
        document.getElementById("status").textContent =
            a.status === "on_scene" ? "On scene" : "En route";

        const due = document.getElementById("due");
        if (a.check_in_by) {
            const late = overdue(a.check_in_by);
            due.textContent = late
                ? `Check-in was due at ${when(a.check_in_by)}`
                : `Check in by ${when(a.check_in_by)}`;
            // Say it out loud rather than only colouring it — this is the one
            // line on the page somebody needs to act on.
            due.className = late ? "due late" : "due";
            if (late) due.setAttribute("role", "status");
        }
        show("mine");
    }

    if (me.last_position) {
        document.getElementById("position").textContent =
            `Last position sent: ${me.last_position.lat.toFixed(4)}, `
            + `${me.last_position.lng.toFixed(4)} at ${when(me.last_position.at)}`;
    }

    // Never let a cached page pass itself off as a live one.
    document.getElementById("asof").textContent =
        `Saved at ${when(me.as_of)}. Nothing here has been refreshed since.`;
}

/** Go back to whatever they were trying to reach, once there is signal. */
async function retry() {
    try {
        const probe = await fetch("/disclaimer", { method: "HEAD",
                                                   cache: "no-store" });
        if (probe.ok) {
            location.replace("/board");
            return true;
        }
    } catch (err) {
        // Still offline. Not an error worth showing — they can see the page.
    }
    return false;
}

document.getElementById("retry").addEventListener("click", retry);

// The browser fires this the moment the radio comes back, which is usually
// before anybody thinks to press the button.
window.addEventListener("online", retry);
setInterval(retry, RETRY_MS);

lastKnown().then(render);
