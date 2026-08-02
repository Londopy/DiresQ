// What DiresQ keeps on the device, and what it refuses to.
//
// THE RULE
// --------
// Cache things that stay true with no network. Refuse to cache things that
// stop being true the moment they are written.
//
// A map tile stays true — the road is where it was last week. Your own
// assignment stays true — you committed to it, and no server can change that
// while you are out of contact. The stylesheet stays true.
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
const SHELL = "diresq-shell-v2";
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
];

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
        if (response.ok) {
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

/** Pages: network-first, falling back to the offline page. */
async function page(request) {
    try {
        return await fetch(request);
    } catch (err) {
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
