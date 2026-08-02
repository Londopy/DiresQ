const form = document.querySelector("form");
const button = document.querySelector(".rescue-btn");

form.addEventListener("submit", () => {
    button.disabled = true;
    button.textContent = "Sending...";
});