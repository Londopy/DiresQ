const form = document.querySelector("form");

form.addEventListener("submit", () => {

    const button = document.querySelector(".submit-btn");

    button.disabled = true;
    button.textContent = "Submitting...";

});

const map = L.map("map").setView([-2.5,118],5);

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution:"© OpenStreetMap"
    }
).addTo(map);

let marker = null;

const latInput = document.getElementById("lat");
const lngInput = document.getElementById("lng");

const locationText =
document.getElementById("locationText");

function setLocation(lat,lng){

    latInput.value = lat;
    lngInput.value = lng;

    locationText.textContent =
        `${lat.toFixed(6)}, ${lng.toFixed(6)}`;

    if(marker){

        map.removeLayer(marker);

    }

    marker =
        L.marker([lat,lng]).addTo(map);

}

map.on("click",(e)=>{

    setLocation(
        e.latlng.lat,
        e.latlng.lng
    );

});

document
.getElementById("myLocation")
.addEventListener("click",()=>{

    navigator.geolocation.getCurrentPosition(pos=>{

        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;

        map.setView([lat,lng],15);

        setLocation(lat,lng);

    });

});