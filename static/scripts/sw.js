// Keeps map tiles you have already seen.
//
// The map is the one part of DiresQ that fetches from somebody else's server,
// which makes it the first thing to break when the network does. Tiles do not
// change — a road is in the same place next week — so they are safe to keep
// and serve back from disk.
//
// WHAT THIS DOES NOT DO
// ---------------------
// It does not download an area in advance. That would make the map work
// somewhere you have never looked, which is usually exactly where the
// disaster is, and it is also explicitly against the OpenStreetMap tile usage
// policy. Bulk downloading gets your users blocked, and rightly.
//
// So the honest description is: the map keeps working where you have already
// been. That is worth having and it is not the same as an offline map.

const TILES = "diresq-tiles-v1";
const SHELL = "diresq-shell-v1";

// Tiles are about 15 KB each, so this is roughly 20 MB — a few hundred
// blocks at street zoom. Somebody's phone is not ours to fill.
const MAX_TILES = 1200;

// Pages and assets worth having when the network is gone. Deliberately short:
// caching the feed would show somebody a stale list of who needs help, which
// is worse than showing them nothing.
const SHELL_FILES = [
    "/static/styles/map.css",
    "/static/styles/nav.css",
    "/static/styles/a11y.css",
    "/static/scripts/map.js",
];

const isTile = (url) =>
    url.hostname.endsWith("tile.openstreetmap.org");

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(SHELL)
            .then((cache) => cache.addAll(SHELL_FILES))
            // One missing file must not stop the worker installing.
            .catch(() => undefined)
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    // Drop caches from older versions of this file, or they accumulate
    // forever on a device that has visited across a few deploys.
    event.waitUntil(
        caches.keys().then((names) => Promise.all(
            names
                .filter((name) => name !== TILES && name !== SHELL)
                .map((name) => caches.delete(name))
        )).then(() => self.clients.claim())
    );
});

/** Keep the cache under MAX_TILES, oldest first. */
async function trim(cache) {
    const keys = await cache.keys();
    if (keys.length <= MAX_TILES) return;
    // Cache keys come back in insertion order, so the front is the oldest.
    await Promise.all(
        keys.slice(0, keys.length - MAX_TILES).map((key) => cache.delete(key))
    );
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;

    const url = new URL(request.url);

    if (isTile(url)) {
        // Cache-first. A tile we have is always as good as a tile we would
        // fetch, and this is what makes the map usable with no signal.
        event.respondWith((async () => {
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
                // Offline and never seen this tile. Returning a 504 rather
                // than throwing lets Leaflet draw its empty-tile placeholder
                // instead of logging an exception per tile.
                return new Response("", { status: 504, statusText: "offline" });
            }
        })());
        return;
    }

    // Our own static assets: network first, fall back to whatever we kept.
    // Network first because a stale stylesheet is a confusing bug, and this
    // path only matters when the network has actually gone.
    if (url.origin === self.location.origin
        && url.pathname.startsWith("/static/")) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    if (response.ok) {
                        caches.open(SHELL).then((c) => c.put(request, response.clone()));
                    }
                    return response;
                })
                .catch(() => caches.match(request).then(
                    (hit) => hit || Response.error()))
        );
    }

    // Everything else — pages, the API, check-ins — goes straight to the
    // network. A cached report feed is a lie about who needs help, and the
    // offline queue already handles check-ins properly.
});
