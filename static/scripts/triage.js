// Hides questions START wouldn't ask, then posts the answers.

const form = document.getElementById("triage-form");
const result = document.getElementById("result");

const rateQ = document.getElementById("rate-q");
const pulseQ = document.getElementById("pulse-q");
const commandsQ = document.getElementById("commands-q");
const breathingQ = document.getElementById("breathing-q");

function picked(name) {
    const el = form.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value === "true" : null;
}

// START stops as soon as it has an answer, so hide the rest.
function updateVisible() {
    const canWalk = picked("can_walk");
    const breathing = picked("breathing");

    breathingQ.hidden = canWalk === true;
    rateQ.hidden = canWalk === true || breathing === false;
    pulseQ.hidden = canWalk === true || breathing === false;
    commandsQ.hidden = canWalk === true || breathing === false;
}

form.addEventListener("change", updateVisible);
updateVisible();

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
        can_walk: picked("can_walk"),
        breathing: picked("breathing"),
        respiratory_rate: form.respiratory_rate.value,
        has_radial_pulse: picked("has_radial_pulse"),
        follows_commands: picked("follows_commands"),
    };

    const res = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    const data = await res.json();
    result.hidden = false;

    if (!res.ok) {
        document.getElementById("r-priority").textContent = "Need more";
        document.getElementById("r-priority").className = "priority";
        document.getElementById("r-explanation").textContent = data.error;
        document.getElementById("r-severity").textContent = "—";
        return;
    }

    document.getElementById("r-priority").textContent = data.priority.toUpperCase();
    document.getElementById("r-priority").className =
        "priority " + data.priority.toLowerCase();
    document.getElementById("r-explanation").textContent = data.explanation;
    document.getElementById("r-severity").textContent = data.severity;
    document.getElementById("r-use").href =
        "/report/new?priority=" + encodeURIComponent(data.severity);

    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
