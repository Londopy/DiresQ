// Submitting the report form, in a way that survives having no signal.
//
// The form works with JavaScript off: it posts to /report/new and the server
// renders a redirect. This layers on top, and only takes over once it is sure
// it can do the job better — which means once it has written the report to
// disk. If localStorage refuses us, this gets out of the way and lets the
// plain form post happen, because a report that cannot be saved locally is
// better off failing loudly at the server than disappearing quietly here.
//
// The sequence, and the order is the point:
//
//   1. write it down, with an id, before touching the network
//   2. try to send
//   3. sent  -> go to the report
//      not   -> stay here and say plainly that it is saved and waiting
//
// See reportqueue.js for why step 1 comes first.

import { file, pending, newId } from "./reportqueue.js";

const form = document.querySelector("form.report-card")
    || document.querySelector("form");
const button = document.querySelector(".submit-btn");

// The hidden id the server rendered into the page is what makes a
// no-JavaScript double-submit safe. It is also the one thing on this page
// that must not come out of a cache: the service worker keeps a copy of this
// form so it can be opened with no signal, and a cached form would hand the
// same id to two genuinely different reports — quietly filing the second as a
// resend of the first, which is the failure this id exists to prevent,
// arriving from the opposite direction.
//
// So replace it on load. A browser running the worker is running JavaScript,
// so this always gets the chance.
const token = form?.querySelector("[name=client_id]");
if (token) token.value = newId();

// Where anything this module has to say gets said. A live region, because
// somebody who has just pressed Submit with no signal needs to be told,
// whether or not they can see the corner of the screen.
const status = document.createElement("div");
status.className = "file-status";
status.hidden = true;
status.setAttribute("role", "status");
status.setAttribute("aria-live", "polite");
button?.insertAdjacentElement("beforebegin", status);

function say(html, kind) {
    status.className = `file-status ${kind}`;
    // Unhide before writing. A live region that is still `hidden` when its
    // content changes is not reliably announced, and this is the one message
    // on the page somebody cannot afford to miss.
    status.hidden = false;
    status.innerHTML = html;
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function busy(on, label) {
    if (!button) return;
    button.disabled = on;
    button.textContent = on ? label : "Submit Report";
}

function fields() {
    const data = new FormData(form);
    return {
        subject: (data.get("subject") || "").trim(),
        description: (data.get("description") || "").trim(),
        priority: (data.get("priority") || "").trim().toUpperCase(),
        lat: data.get("lat"),
        lng: data.get("lng"),
    };
}

form?.addEventListener("submit", async (event) => {
    // Let the browser's own validation run first. If the form is incomplete
    // the native path already says so, in the right place, in the right
    // language, and we should not be queueing a report with no location.
    if (form.checkValidity && !form.checkValidity()) return;

    event.preventDefault();
    busy(true, "Saving...");

    let outcome;
    try {
        outcome = await file(fields());
    } catch (err) {
        outcome = { stored: false, sent: false };
    }

    if (!outcome.stored) {
        // We could not write it down, so we cannot promise anything. Hand it
        // back to the plain form post, which either works or fails visibly.
        busy(true, "Submitting...");
        form.submit();
        return;
    }

    if (outcome.sent && outcome.url && !outcome.refused) {
        location.assign(outcome.url);
        return;
    }

    if (outcome.refused) {
        busy(false);
        say(`<strong>The server would not take this report.</strong>
             ${esc(outcome.error || "Check the fields and try again.")}`,
            "refused");
        return;
    }

    // Queued. Say what that means, without overclaiming: it is on this phone,
    // it is not yet anywhere else, and nobody is coming because of it yet.
    busy(false);
    const n = pending();
    say(`<strong>Saved on this phone. Not sent yet.</strong>
         There is no connection, so nobody has seen this. It sends by itself
         the moment there is signal &mdash; you can close the app.
         ${n > 1 ? `${n} reports are waiting.` : ""}
         <span class="again">If this is life-threatening, call 911 now.</span>`,
        "queued");
});

// The queue flushes on its own; this is only so somebody still looking at the
// page finds out it went, and can follow it.
document.addEventListener("diresq:reportsent", (event) => {
    const { url, refused, error } = event.detail;
    if (refused) {
        say(`<strong>The server would not take a queued report.</strong>
             ${esc(error || "It has been dropped rather than retried forever.")}`,
            "refused");
        return;
    }
    say(`<strong>Sent.</strong> Your report is on the feed now.
         ${url ? `<a href="${esc(url)}">Open it</a>` : ""}`, "sent");
});
