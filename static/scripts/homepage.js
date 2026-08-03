const search = document.getElementById("search");
const checks = document.querySelectorAll("input[type=checkbox]");
const list = document.querySelector(".reports");

// Re-queried every time, because the cards get replaced on each poll.
function filter() {

    const text = search.value.toLowerCase();

    const enabled = [...checks]
        .filter(c => c.checked)
        .map(c => c.value);

    document.querySelectorAll(".report-card").forEach(card => {

        const title = card.dataset.title;
        const priority = card.dataset.priority;

        const matchTitle = title.includes(text);
        const matchPriority = enabled.includes(priority);

        // The card is wrapped in an <a>, so hide that or the link stays.
        const wrapper = card.closest(".report-link") || card;
        wrapper.style.display = (matchTitle && matchPriority) ? "" : "none";

    });

}

search.addEventListener("input", filter);
checks.forEach(c => c.addEventListener("change", filter));

// --- live feed -----------------------------------------------------------
// Someone marking a scene overstaffed two streets away should move the cards
// here without anyone pressing anything.

const POLL_MS = 4000;

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function countText(r) {
    const responding = r.en_route_count + r.on_scene_count;
    if (!responding) return "0 responding";

    // "to 1 incident" only where it changes the reading. On a single report
    // it is noise; on a grouped one it is the difference between two
    // comfortable rows and six people at one address.
    const one = r.duplicate_count > 1 ? " to 1 incident" : "";

    if (r.on_scene_count && r.en_route_count) {
        return `${r.on_scene_count} on scene, ${r.en_route_count} en route${one}`;
    }
    if (r.on_scene_count) return `${r.on_scene_count} on scene${one}`;
    return `${r.en_route_count} en route${one}`;
}

function cardHtml(r) {
    const responding = r.en_route_count + r.on_scene_count;
    const staffing = r.staffing === "unstaffed" ? "" :
        `<span class="staffing ${r.staffing}">
            ${esc(r.staffing.replace(/_/g, " ").toUpperCase())}
        </span>`;

    const merged = r.duplicate_count > 1 ? `
        <p class="merged-flag">
            <strong>${r.duplicate_count} reports, one incident.</strong>
            Counted once below, and everyone going is counted once too.
            Open it to see each report separately &mdash; nothing has been
            merged.
        </p>` : "";

    // stale_minutes, not minutes_old: on a grouped incident the freshest
    // report and the one that arrived late need not be the same report, and
    // combining them would make a false sentence out of two true facts.
    const stale = r.synced_late ? `
        <p class="stale">
            <strong>Written ${r.stale_minutes === null ? "earlier"
                : `${r.stale_minutes} minute${r.stale_minutes === 1 ? "" : "s"} ago`},
                reached us later.</strong>
            Filed with no signal. It may already have been dealt with.
        </p>` : "";

    return `
    <a href="/report/${r.id}" class="report-link">
        <article class="report-card${r.duplicate_count > 1 ? " merged" : ""}"
                 data-title="${esc(r.subject.toLowerCase())}"
                 data-priority="${esc(r.priority)}">
            <h2>${esc(r.subject)}</h2>
            <span class="priority ${esc(r.priority.toLowerCase())}">
                ${esc(r.priority)}
            </span>
            <p>${esc(r.description.slice(0, 120))}...</p>
            ${merged}
            ${stale}
            <div class="responders">
                <span class="count${responding === 0 ? " nobody" : ""}">
                    ${countText(r)}
                </span>
                ${staffing}
            </div>
        </article>
    </a>`;
}

// Only redraw when something actually changed, otherwise typing in the search
// box fights the poll.
let lastSeen = "";

async function poll() {
    try {
        // Incidents, not reports: two duplicates of one flood are one row
        // here. The map still polls /api/reports, because two people
        // reporting from opposite ends of a street pinned two real places.
        const res = await fetch("/api/incidents", {
            headers: { Accept: "application/json" },
        });
        if (!res.ok) return;

        const reports = await res.json();
        const fingerprint = reports
            .map(r => `${r.id}:${r.staffing}:${r.en_route_count}`
                      + `:${r.on_scene_count}:${r.duplicate_count}`)
            .join("|");

        if (fingerprint === lastSeen) return;
        lastSeen = fingerprint;

        list.innerHTML = reports.map(cardHtml).join("");
        filter();
    } catch (err) {
        // Offline or server down. Leave the cards that are already there.
    }
}

if (list) {
    setInterval(poll, POLL_MS);
}

// --- filter drawer on mobile --------------------------------------------

const btn = document.getElementById("filterBtn");
const sidebar = document.getElementById("sidebar");

function setMenuState(isOpen) {

    sidebar.classList.toggle("show", isOpen);
    btn.classList.toggle("active", isOpen);
    btn.setAttribute("aria-expanded", String(isOpen));
    btn.setAttribute("aria-label", isOpen ? "Close filters" : "Open filters");

}

if (btn && sidebar) {

    btn.addEventListener("click", event => {

        event.stopPropagation();
        setMenuState(!sidebar.classList.contains("show"));

    });

    document.addEventListener("click", event => {

        if (window.innerWidth > 768 || !sidebar.classList.contains("show")) {
            return;
        }

        if (!sidebar.contains(event.target) && !btn.contains(event.target)) {
            setMenuState(false);
        }

    });

    document.addEventListener("keydown", event => {

        if (event.key === "Escape") {
            setMenuState(false);
        }

    });

}
