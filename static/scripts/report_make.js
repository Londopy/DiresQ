// The map and the location picker. Submitting is report_file.js's job — it
// has to write the report to disk before the network sees it, and that is a
// different concern from where the pin goes.
//
// Two things this file must survive, because /report/new is the one page the
// app promises works with no signal:
//
//   * Leaflet is loaded from a CDN. With no network it is simply not there,
//     and `L` is undefined. That must not take the picker down with it — the
//     button below does not need a map, or a network, to work.
//   * The pin is drawn in CSS, not fetched. Leaflet's default marker is a PNG
//     resolved relative to leaflet.css, so it lives on the CDN too: blocked by
//     our own image policy online, and absent offline. A div with a border
//     radius has neither problem.

// A map is a convenience here, not the mechanism. Guard rather than assume.
const mapReady = typeof L !== "undefined";

const mapBox = document.getElementById("map");

const latInput = document.getElementById("lat");
const lngInput = document.getElementById("lng");

const locationText = document.getElementById("locationText");

let map = null;
let marker = null;

if (mapReady) {

    map = L.map("map").setView([-2.5, 118], 5);

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution: "© OpenStreetMap"
        }
    ).addTo(map);

    map.on("click", (e) => {

        setLocation(
            e.latlng.lat,
            e.latlng.lng
        );

    });

} else {

    // No map to click, so stop offering a map to click. The button is the
    // whole picker now, and saying so is better than an empty grey box.
    mapBox.hidden = true;

    locationText.textContent =
        "No map right now. Use the button above to drop your position.";

}

/** The picked spot. Drawn, not downloaded — see the note at the top. */
function locationPin() {

    return L.divIcon({
        className: "",
        html: `<span class="pin pin-picked"></span>`,
        iconSize: [22, 22],

        // A 22px square rotated 45° puts its point 11 + 15.6 below the top,
        // so the tip lands on the coordinate rather than the body of the pin.
        iconAnchor: [11, 27],
    });

}

function setLocation(lat, lng) {

    latInput.value = lat;
    lngInput.value = lng;

    locationText.textContent =
        `${lat.toFixed(6)}, ${lng.toFixed(6)}`;

    if (!map) {
        return;
    }

    if (marker) {

        map.removeLayer(marker);

    }

    marker =
        L.marker([lat, lng], { icon: locationPin() }).addTo(map);

}

// If the form came back with an error, the coordinates it already had are
// rendered into the hidden inputs. Redraw them, or the page contradicts
// itself: a location is set, and the text still asks you to set one.
if (latInput.value && lngInput.value) {

    const lat = parseFloat(latInput.value);
    const lng = parseFloat(lngInput.value);

    if (Number.isFinite(lat) && Number.isFinite(lng)) {

        if (map) {
            map.setView([lat, lng], 15);
        }

        setLocation(lat, lng);

    }

}

document
.getElementById("myLocation")
.addEventListener("click", () => {

    if (!navigator.geolocation) {

        locationText.textContent =
            "This device will not share a position. Pick the spot on the map.";

        return;

    }

    locationText.textContent = "Finding you…";

    navigator.geolocation.getCurrentPosition(

        (pos) => {

            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;

            if (map) {
                map.setView([lat, lng], 15);
            }

            setLocation(lat, lng);

        },

        // Without this the button did nothing at all on a denied permission
        // or a timeout, and "nothing happened" is the one response somebody
        // standing at an incident cannot act on.
        (err) => {

            locationText.textContent =
                err.code === err.PERMISSION_DENIED
                    ? "Location permission is off. Turn it on, or pick the spot on the map."
                    : "Could not get a position. Try again, or pick the spot on the map.";

        },

        // GPS is a sensor, not a network call: this is the path that has to
        // work when nothing else does. Give it time to get a real fix.
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0,
        }

    );

});
