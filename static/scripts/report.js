// Stops double-submits, and puts the check-in button through the offline
// queue so it works with no signal.

import { send } from "./queue.js";

document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", () => {
        // The check-in form handles its own button, because it never leaves
        // the page and a permanently disabled button is worse than none.
        if (form.id === "checkin-form") return;
        const button = form.querySelector("button");
        if (button) {
            button.disabled = true;
            button.textContent = "…";
        }
    });
});

const checkin = document.getElementById("checkin-form");

// Asks for a position, gives up after five seconds. A check-in with no
// coordinates still counts — "I'm alive" is the part that matters, and GPS
// indoors in a storm often just doesn't arrive.
function position() {
    return new Promise(resolve => {
        if (!navigator.geolocation) return resolve({});
        navigator.geolocation.getCurrentPosition(
            pos => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
            () => resolve({}),
            { timeout: 5000 }
        );
    });
}

function say(button, text, ms = 2500) {
    button.textContent = text;
    setTimeout(() => {
        button.textContent = "Check in";
        button.disabled = false;
    }, ms);
}

if (checkin) {
    checkin.addEventListener("submit", async (e) => {
        // Without JavaScript this form posts normally and the server handles
        // it. With JavaScript we take it over, so a failed send becomes a
        // queued one instead of an error page.
        e.preventDefault();

        const button = checkin.querySelector("button");
        button.disabled = true;
        button.textContent = "…";

        const result = await send(await position());

        if (result.queued) {
            say(button, "Saved — will send", 3500);
        } else if (result.refused) {
            say(button, "Rejected");
        } else {
            say(button, "Checked in");
        }
    });
}
