const form = document.querySelector("form");

form.addEventListener("submit", () => {

    const button = document.querySelector(".submit-btn");

    button.disabled = true;
    button.textContent = "Submitting...";

});