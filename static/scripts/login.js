const form = document.querySelector(".login-card");

form.addEventListener("submit", () => {

    const button = form.querySelector("button");

    button.disabled = true;
    button.textContent = "Logging in...";

});