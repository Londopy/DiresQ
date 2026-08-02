const form = document.querySelector(".login-card");

form.addEventListener("submit", (e) => {

    const password = form.password.value;
    const confirm = form.confirm_password.value;

    if (password !== confirm) {
        e.preventDefault();
        alert("Passwords do not match.");
        return;
    }

    const button = form.querySelector("button");
    button.disabled = true;
    button.textContent = "Creating account...";

});