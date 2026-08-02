// Reads the description as you type and asks the server what it makes of it.
//
// The suggestion never overwrites what you chose. If you touch the priority
// dropdown yourself, this stops touching it for the rest of the form —
// somebody who has made a decision about their own emergency should not have
// software arguing with them.

const form = document.querySelector("form.report-card") || document.querySelector("form");
const description = document.querySelector("[name=description]");
const priority = document.querySelector("[name=priority]");

// Once you pick a priority yourself, we stop setting it.
let yours = false;
priority?.addEventListener("change", () => { yours = true; });

const panel = document.createElement("div");
panel.className = "suggestion";
panel.hidden = true;
panel.setAttribute("role", "status");
description?.insertAdjacentElement("afterend", panel);

function render(result) {
    if (!result.confident) {
        // Below the confidence floor it says nothing rather than guessing at
        // somebody in the middle of an emergency.
        panel.hidden = true;
        return;
    }

    const caps = result.capabilities.length
        ? `<span class="caps">${result.capabilities.map(esc).join(" · ")}</span>`
        : "";

    const dupes = (result.duplicates || []).map(d =>
        `<a class="dupe" href="/report/${d.id}">
            Already reported? &ldquo;${esc(d.subject)}&rdquo;
         </a>`).join("");

    panel.innerHTML = `
        <div class="row">
            <span class="tag ${result.priority.toLowerCase()}">${result.priority}</span>
            <span class="sure">${Math.round(result.confidence * 100)}% sure</span>
            ${caps}
        </div>
        <p class="why">
            Suggested from: ${result.reasons.map(esc).join(", ") || "the wording"}.
            You decide &mdash; change it if it's wrong.
        </p>
        ${dupes}`;
    panel.hidden = false;

    if (!yours && priority) priority.value = result.priority;
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

let timer;
let inFlight = false;

async function ask() {
    const text = description.value.trim();
    if (text.length < 15 || inFlight) return;

    inFlight = true;
    try {
        const res = await fetch("/api/suggest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
        if (res.ok) render(await res.json());
    } catch (err) {
        // No connection. The form still works; you just pick the priority
        // yourself, which is what happens without JavaScript anyway.
        panel.hidden = true;
    } finally {
        inFlight = false;
    }
}

// Wait for a pause in typing. Firing on every keystroke would classify
// half-written words and flicker the answer while somebody is mid-sentence.
description?.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(ask, 450);
});
