// Registers the service worker, and keeps one thing warm in its cache.
//
// Loaded on every page. It used to live in map.js, back when the worker only
// kept map tiles — but somebody who installs DiresQ from the board and never
// opens the map should still have the app work with the network off, and
// under the old arrangement they didn't.
//
// Needs HTTPS or localhost. Browsers refuse to register a worker anywhere
// else, so this quietly does nothing when you're testing over a LAN address.

if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js")
            .then(warm)
            .catch(() => {
                // Unsupported, blocked, or not a secure context. Every page
                // works exactly as before; it just won't remember anything.
            });
    });
}

/**
 * Ask for your own state once, so the worker has a copy to fall back on.
 *
 * This is the only thing fetched purely to be cached, and it is worth the
 * request: /api/me is what the offline page renders from, and a phone that
 * loses signal before ever calling it shows an empty offline page at exactly
 * the moment somebody needs to know when they're due to check in.
 *
 * Everything else the app knows is about other people, and deliberately isn't
 * kept — see the long comment at the top of sw.js.
 */
function warm() {
    // Anonymous visitors have no state to keep, and asking would just be a
    // redirect to the login page.
    if (!document.body || document.body.dataset.signedIn !== "yes") return;

    fetch("/api/me", { credentials: "same-origin" }).catch(() => {
        // Already offline. The worker will serve whatever it has.
    });
}
