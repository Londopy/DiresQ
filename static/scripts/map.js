const map = L.map("map").setView([-2.5,118],5);

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