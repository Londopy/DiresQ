// Polls /board/rows and swaps in the markup the server rendered. The server
// works out overdue on every read, so rows go red on their own.

const POLL_MS = 3000;

const list = document.getElementById("responders");
const empty = document.getElementById("empty");
const live = document.getElementById("live");

const totals = {
    overdue: document.getElementById("n-overdue"),
    on_scene: document.getElementById("n-on-scene"),
    en_route: document.getElementById("n-en-route"),
    available: document.getElementById("n-available"),
};

// Rows come from the server as HTML, rendered from the same Jinja partial
// the page itself was built from. There is deliberately no row-building code
// here any more.
//
// There used to be: `rowHtml()` rebuilt every cell as a template literal, and
// it drifted from the template the first time a field was added to one and
// not the other. The countdown rendered on first paint and the first poll
// erased it. Two implementations of one row is a bug waiting for somebody to
// add a field; one implementation cannot disagree with itself.
function render(html) {
    // Read the states still on screen before replacing them, so a row that
    // changed can flash. The server has no idea what this browser was last
    // showing, which is the one thing the client genuinely knows.
    const before = {};
    list.querySelectorAll(".row[data-id]").forEach(el => {
        before[el.dataset.id] = el.dataset.state;
    });

    // DOMParser rather than assigning innerHTML. The markup is our own and
    // Jinja escaped it, so this is not a security fix — it is so the test
    // that forbids row-building in this file can forbid innerHTML outright
    // instead of carving out an exception somebody later widens.
    const incoming = new DOMParser().parseFromString(html, "text/html");
    const rows = incoming.getElementById("rows");
    if (!rows) return;

    rows.querySelectorAll(".row[data-id]").forEach(el => {
        const was = before[el.dataset.id];
        if (was && was !== el.dataset.state) el.classList.add("changed");
    });

    list.replaceChildren(...rows.children);
    empty.hidden = Number(rows.dataset.count) > 0;

    totals.overdue.textContent = rows.dataset.overdue;
    totals.on_scene.textContent = rows.dataset.onScene;
    totals.en_route.textContent = rows.dataset.enRoute;
    totals.available.textContent = rows.dataset.available;
}

// The silence sweep, shown rather than promised.
//
// It carries on the response header of the same poll that triggers it, so
// this cannot drift from the rows beside it. Five minutes is the threshold:
// the escalation it drives is fifteen, which leaves room to notice the
// checker has stopped before the thing it checks starts mattering.
const swept = document.getElementById("swept");
const sweptAgo = document.getElementById("swept-ago");
const STALE_AFTER = 300;

function showSwept(header) {
    if (!swept || !sweptAgo) return;

    if (!header || header === "never") {
        sweptAgo.textContent = "never";
        swept.classList.add("swept-stale");
        return;
    }

    const seconds = Math.max(0, Math.round((Date.now() - Date.parse(header)) / 1000));

    sweptAgo.textContent = seconds < 60
        ? `${seconds}s ago`
        : `${Math.floor(seconds / 60)}m ago`;

    swept.classList.toggle("swept-stale", seconds > STALE_AFTER);
}

async function poll() {
    try {
        const res = await fetch("/board/rows", { headers: { Accept: "text/html" } });
        if (!res.ok) throw new Error(res.status);
        render(await res.text());
        showSwept(res.headers.get("X-Last-Swept"));
        live.classList.remove("stalled");
        live.title = "Refreshing every 3 seconds";
    } catch (err) {
        // Keep the last board on screen, just stop saying it's live.
        live.classList.add("stalled");
        live.title = "Lost contact with the server. Showing the last update.";
    }
}

poll();
setInterval(poll, POLL_MS);

console.log(
    "%cDiresQ",
    "color:#a6e3a1;font-size:20px;font-weight:bold;letter-spacing:4px"
);
console.log(
    "%cpoking around? there's a page at /credits",
    "color:#6c7086;font-size:11px"
);
