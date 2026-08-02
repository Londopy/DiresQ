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

reports.forEach(report=>{

    if(report.priority==="HIGH") high++;
    if(report.priority==="MEDIUM") medium++;
    if(report.priority==="LOW") low++;

    const marker=L.marker([report.latitude,report.longitude])
    .addTo(map)
    .bindPopup(`
        <b>${report.subject}</b><br>
        ${report.priority}<br>
        <a href="/report/${report.id}">
            Open Report
        </a>
    `);

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

fetch("/api/responders")
.then(res => res.json())
.then(responders => {

    responders.forEach(responder => {

        const pos = responder.last_position;
        if(!pos || pos.lat == null || pos.lng == null){
            return;
        }

        L.circleMarker(
            [pos.lat, pos.lng],
            {
                radius:8,
                color:"#89b4fa",
                fillColor:"#89b4fa",
                fillOpacity:1
            }
        )
        .addTo(map)
        .bindPopup(`
            <b>${responder.username}</b><br>
            🚑 ${responder.state || "Active Responder"}
        `);

    });

});