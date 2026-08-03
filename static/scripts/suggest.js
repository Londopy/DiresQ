// Reads the description as you type and suggests how bad it is.
//
// The suggestion never overwrites what you chose. If you touch the priority
// dropdown yourself, this stops touching it for the rest of the form —
// somebody who has made a decision about their own emergency should not have
// software arguing with them.
//
// TWO SOURCES, AND THE PANEL SAYS WHICH
// -------------------------------------
// Online it asks the server, which runs the classifier and also compares the
// description against every report currently open.
//
// Offline it runs the same trained model in the browser (`classify.js`) and
// gets the priority and the equipment — but not the duplicate check, because
// that compares against other people's open reports and DiresQ refuses to
// keep that list on a phone. A saved copy of who needs help is a lie that
// gets more convincing the longer it sits there.
//
// So offline the panel shows the priority and says, in a sentence, that
// nothing has checked whether somebody has already reported this, and that
// the server will when the report sends. Silence there would be read as
// "checked, found nothing", which is the one thing it must not mean.

import { load, suggest as offlineSuggest } from "./classify.js";

const form = document.querySelector("form.report-card")
    || document.querySelector("form");
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

// Fetched once, kept by the service worker under the same rule as the
// stylesheets: it is part of the app, not a claim about the world. If it
// never arrives the offline path simply doesn't exist, and the form is the
// form it always was.
load();

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function render(result) {
    if (!result || !result.confident) {
        // Below the confidence floor it says nothing rather than guessing at
        // somebody in the middle of an emergency.
        panel.hidden = true;
        return;
    }

    const caps = result.capabilities.length
        ? `<span class="caps">${result.capabilities.map(esc).join(" · ")}</span>`
        : "";

    // Absent, not empty. `duplicates: []` means "we looked and found none";
    // no property at all means nothing has looked. Those are different enough
    // that the panel has to say which.
    const checked = Array.isArray(result.duplicates);

    const dupes = checked ? result.duplicates.map((d) =>
        `<a class="dupe" href="/report/${encodeURIComponent(d.id)}">
            Already reported? &ldquo;${esc(d.subject)}&rdquo;
         </a>`).join("") : "";

    const unchecked = checked ? "" : `
        <p class="unchecked">
            <strong>Not checked against other reports.</strong>
            That needs everyone else's, and this device does not keep them.
            The server checks the moment this sends.
        </p>`;

    const markup = `
        <div class="row">
            <span class="tag ${esc(result.priority.toLowerCase())}">${esc(result.priority)}</span>
            <span class="sure">${Math.round(result.confidence * 100)}% sure</span>
            ${caps}
            ${result.offline ? '<span class="whence">worked out on this phone</span>' : ""}
        </div>
        <p class="why">
            Suggested from: ${result.reasons.map(esc).join(", ") || "the wording"}.
            You decide &mdash; change it if it's wrong.
        </p>
        ${dupes}
        ${unchecked}`;

    // Only touch the panel when the answer has actually changed. It is a live
    // region and it re-runs on every pause in typing, so rewriting identical
    // markup means a screen reader reads the whole suggestion out again — and
    // offline, where the panel also carries the sentence about the duplicate
    // check not having run, that is a paragraph repeated at somebody every
    // few seconds while they are trying to describe an emergency.
    if (panel.hidden || panel.innerHTML !== markup) {
        panel.hidden = false;
        panel.innerHTML = markup;
    }

    if (!yours && priority) priority.value = result.priority;
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
            credentials: "same-origin",
            body: JSON.stringify({ text }),
        });
        if (res.ok) {
            render(await res.json());
            return;
        }
        // A 4xx or 5xx is the server answering, not the network being gone.
        // Falling back to the phone here would be answering a different
        // question than the one that failed.
        panel.hidden = true;
    } catch (err) {
        // No connection — and this is the person the suggestion was built
        // for, filing at 2am with the towers down. Run it here instead.
        render(offlineSuggest(text));
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
