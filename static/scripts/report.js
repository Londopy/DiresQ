// Stops double-submits, and attaches your position to a check-in if the
// browser will give one. Everything still works if it won't.

document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button");
        if (button) {
            button.disabled = true;
            button.textContent = "…";
        }
    });
});

const checkin = document.getElementById("checkin-form");

if (checkin && navigator.geolocation) {
    checkin.addEventListener("submit", (e) => {
        const lat = document.getElementById("checkin-lat");
        if (lat.value) return;

        // Hold the form while we ask for a fix, then send it either way.
        e.preventDefault();
        navigator.geolocation.getCurrentPosition(
            pos => {
                lat.value = pos.coords.latitude;
                document.getElementById("checkin-lng").value = pos.coords.longitude;
                checkin.submit();
            },
            () => checkin.submit(),
            { timeout: 5000 }
        );
    });
}
