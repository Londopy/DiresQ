// Polls /api/responders and redraws. The server works out overdue on every
// read, so rows go red on their own.

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

// Used to flash a row when its state changes.
let lastStates = {};

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function label(state) {
    return state.replace(/_/g, " ").toUpperCase();
}

function rowHtml(r) {
    const caps = r.capabilities
        .map(c => `<span class="cap">${esc(c)}</span>`)
        .join("");

    const doing = r.assignment
        ? `<a href="/report/${r.assignment.report_id}">${esc(r.assignment.report_subject)}</a>` +
          (r.assignment.staffing_vote
              ? `<span class="vote">said ${esc(r.assignment.staffing_vote.replace(/_/g, " "))}</span>`
              : "")
        : `<span class="idle">not assigned</span>`;

    const ago = r.minutes_since_contact === null
        ? `<span class="ago idle">no contact yet</span>`
        : `<span class="ago">last contact ${r.minutes_since_contact} min ago</span>`;

    const pos = r.last_position
        ? `<span class="pos">${r.last_position.lat.toFixed(4)}, ${r.last_position.lng.toFixed(4)}</span>`
        : `<span class="pos idle">no position</span>`;

    const changed = lastStates[r.id] && lastStates[r.id] !== r.state ? " changed" : "";

    return `
    <article class="row ${r.state}${changed}">
        <div class="who">
            <h2>${esc(r.username)}</h2>
            <div class="caps">${caps}</div>
        </div>
        <div class="state">
            <span class="badge ${r.state}">${label(r.state)}</span>
        </div>
        <div class="doing">${doing}</div>
        <div class="contact">${ago}${pos}</div>
    </article>`;
}

function render(responders) {
    const counts = { overdue: 0, on_scene: 0, en_route: 0, available: 0 };
    responders.forEach(r => { counts[r.state] = (counts[r.state] || 0) + 1; });
    Object.entries(totals).forEach(([k, el]) => { el.textContent = counts[k] || 0; });

    list.innerHTML = responders.map(rowHtml).join("");
    empty.hidden = responders.length > 0;

    lastStates = {};
    responders.forEach(r => { lastStates[r.id] = r.state; });
}

async function poll() {
    try {
        const res = await fetch("/api/responders", { headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error(res.status);
        render(await res.json());
        live.classList.remove("stalled");
        live.title = "Refreshing every 3 seconds";
    } catch (err) {
        // Keep the last board on screen, just stop saying it's live.
        live.classList.add("stalled");
        live.title = "Lost contact with the server. Showing the last update.";
    }
}

// Seed from the server-rendered rows so the first poll doesn't flash everything.
document.querySelectorAll(".row").forEach((el, i) => { lastStates[i] = null; });

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
