// What DiresQ keeps on the device, and what it refuses to.
//
// THE RULE
// --------
// Cache things that stay true with no network. Refuse to cache things that
// stop being true the moment they are written.
//
// A map tile stays true — the road is where it was last week. Your own
// assignment stays true — you committed to it, and no server can change that
// while you are out of contact. The stylesheet stays true. So does the
// trained classifier: it is a fixed set of word counts, no more a claim about
// the world right now than the stylesheet is, and keeping it is what lets
// somebody filing at 2am with no signal still get a suggested priority.
//
// The report feed does not. Neither does the accountability board. Both are
// claims about other people right now, and a saved copy of "who needs help"
// is a lie that gets more convincing the longer it sits there. Somebody
// reading a stale feed in a flood would drive to an address that has already
// been cleared, while the street that filed thirty seconds ago is invisible
// to them. So those are never cached, and offline they are absent rather
// than wrong.
//
// WHAT THIS DOES NOT DO
// ---------------------
// It does not download map tiles in advance. That would make the map work
// somewhere you have never looked — usually exactly where the disaster is —
// and it is against the OpenStreetMap tile usage policy. Bulk downloading
// gets your users blocked, and rightly.
//
// So the honest description is: the map keeps working where you have already
// been, and the app keeps working for the job you already took.

const TILES = "diresq-tiles-v1";
const SHELL = "diresq-shell-v4";
const MINE = "diresq-mine-v1";

// Tiles are about 15 KB each, so this is roughly 20 MB — a few hundred
// blocks at street zoom. Somebody's phone is not ours to fill.
const MAX_TILES = 1200;

// Everything needed to render the offline page from a cold start with no
// network. If one of these is missing the page still loads, just unstyled —
// worse, but not broken.
const SHELL_FILES = [
    "/offline",
    "/static/styles/offline.css",
    "/static/scripts/offline.js",
    "/static/styles/map.css",
    "/static/styles/nav.css",
    "/static/styles/a11y.css",
    "/static/scripts/map.js",
    "/static/manifest.webmanifest",
    "/static/images/icon-192.png",

    // Filing a report with no signal. The outbox that writes it to the device
    // before the network sees it, and the trained classifier that suggests a
    // priority when the server cannot be asked.
    //
    // The model is data, not a claim: a frozen table of word counts generated
    // from classify.py. It says nothing about who needs help right now, which
    // is the test everything in this list has to pass.
    "/static/model/priority.json",
    "/static/scripts/classify.js",
    "/static/scripts/reportqueue.js",
    "/static/scripts/report_file.js",
    "/static/scripts/suggest.js",
    "/static/styles/report_make.css",

    // The location picker. Leaflet itself is on a CDN and stays there — this
    // file is written to survive its absence, but only if the file is here.
    "/static/scripts/report_make.js",
];

// Pages we keep a copy of once you have actually opened them, so they still
// come up with no signal. Only the report form, and only because an offline
// queue you cannot reach the form for is an offline queue that does nothing.
//
// Kept lazily rather than at install, for two reasons. It needs a session, so
// fetching it at install time — before anyone has logged in — would 302 to
// the login page, and `addAll` rejects atomically, quietly costing the whole
// shell. And the honest promise is the same one the tiles make: it works
// where you have already been.
//
// The form is a blank form. It says nothing about who needs help, so it does
// not fall foul of the rule at the top of this file. The one thing it does
// carry — a server-minted id that makes a no-JavaScript double-submit safe —
// would go stale in a cache, so report_file.js replaces it on load. A browser
// running this worker is by definition a browser running JavaScript.
const OFFLINE_PAGES = ["/report/new"];

const isTile = (url) => url.hostname.endsWith("tile.openstreetmap.org");

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(SHELL)
            .then((cache) => cache.addAll(SHELL_FILES))
            // One missing file must not stop the worker installing. A worker
            // that fails to install leaves the app with no offline support at
            // all, which is a worse failure than a missing stylesheet.
            .catch(() => undefined)
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    // Drop caches from older versions of this file, or they accumulate
    // forever on a device that has visited across a few deploys.
    const keep = [TILES, SHELL, MINE];
    event.waitUntil(
        caches.keys().then((names) => Promise.all(
            names.filter((name) => !keep.includes(name))
                 .map((name) => caches.delete(name))
        )).then(() => self.clients.claim())
    );
});

/** Keep the tile cache under MAX_TILES, oldest first. */
async function trim(cache) {
    const keys = await cache.keys();
    if (keys.length <= MAX_TILES) return;
    // Cache keys come back in insertion order, so the front is the oldest.
    await Promise.all(
        keys.slice(0, keys.length - MAX_TILES).map((key) => cache.delete(key))
    );
}

/** Map tiles: cache-first. A tile we have is as good as one we would fetch. */
async function tile(request) {
    const cache = await caches.open(TILES);
    const hit = await cache.match(request);
    if (hit) return hit;

    try {
        const response = await fetch(request);

        // A tile is an <img> with no crossOrigin attribute, so the request
        // reaches us in no-cors mode and comes back *opaque*: readable by the
        // browser, unreadable by us, and reporting status 0 with ok false.
        //
        // Testing `response.ok` alone therefore never stored a single tile.
        // Nothing failed loudly — the map worked online, because the opaque
        // response is returned and drawn either way — so the cache appeared
        // to exist and was empty. The one moment it mattered, with no signal,
        // was the one moment nobody was watching a console.
        const usable = response.ok || response.type === "opaque";

        if (usable) {
            await cache.put(request, response.clone());
            trim(cache);          // deliberately not awaited
        }
        return response;
    } catch (err) {
        // Offline and never seen this tile. A 504 lets Leaflet draw its
        // empty-tile placeholder instead of logging an exception per tile.
        return new Response("", { status: 504, statusText: "offline" });
    }
}

/** Your own state: network-first, but keep the last good copy. */
async function mine(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(MINE);
            await cache.put("/api/me", response.clone());
        }
        return response;
    } catch (err) {
        // 504 rather than silently handing back the cached body: a live
        // request for your state should fail honestly. The offline page reads
        // the cache directly, where the staleness is labelled on screen.
        return new Response("{}", {
            status: 504,
            headers: { "Content-Type": "application/json" },
        });
    }
}

/** Pages: network-first, falling back to the offline page — or, for the few
 *  pages in OFFLINE_PAGES, to the copy taken last time you opened them. */
async function page(request) {
    const path = new URL(request.url).pathname;
    const keepable = OFFLINE_PAGES.includes(path);

    try {
        const response = await fetch(request);
        // Only store a real page. A redirect to the login wall is not the
        // report form, and caching one would strand somebody offline on a
        // page telling them to sign in.
        if (keepable && response.ok && response.type !== "opaqueredirect") {
            const cache = await caches.open(SHELL);
            cache.put(path, response.clone());
        }
        return response;
    } catch (err) {
        if (keepable) {
            const saved = await caches.match(path);
            if (saved) return saved;
        }
        const hit = await caches.match("/offline");
        return hit || new Response(
            "You are offline, and this device has not saved the offline page.",
            { status: 503, headers: { "Content-Type": "text/plain" } });
    }
}

/** Our own static files: network-first, so a stale stylesheet can't linger. */
async function asset(request) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(SHELL);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        return (await caches.match(request)) || Response.error();
    }
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;

    const url = new URL(request.url);

    if (isTile(url)) {
        event.respondWith(tile(request));
        return;
    }

    if (url.origin !== self.location.origin) return;

    if (url.pathname === "/api/me") {
        event.respondWith(mine(request));
        return;
    }

    // Every other API call goes straight to the network and is never stored.
    // /api/reports and /api/responders are the two this matters most for.
    if (url.pathname.startsWith("/api/")) return;

    if (request.mode === "navigate") {
        event.respondWith(page(request));
        return;
    }

    if (url.pathname.startsWith("/static/")) {
        event.respondWith(asset(request));
    }
});
