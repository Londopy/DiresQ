// Shared by the login and sign-up forms.
//
// None of this validates anything the server doesn't check again. It just
// tells you what went wrong before you find out the slow way.

// Caps lock is the classic one. The password field shows dots either way, so
// you type it three times and blame yourself.
function watchCapsLock(field) {
    const warning = document.createElement("p");
    warning.className = "caps-warning";
    warning.hidden = true;
    warning.setAttribute("role", "status");
    warning.textContent = "Caps Lock is on";
    field.insertAdjacentElement("afterend", warning);

    function check(event) {
        // Only reliable once a key event has happened, which is why there's
        // nothing to show until you start typing.
        if (typeof event.getModifierState !== "function") return;
        warning.hidden = !event.getModifierState("CapsLock");
    }

    field.addEventListener("keydown", check);
    field.addEventListener("keyup", check);
    field.addEventListener("blur", () => { warning.hidden = true; });
}

// A password you cannot read is a password you cannot check.
function addReveal(field) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "reveal";
    button.textContent = "show";
    button.setAttribute("aria-label", "Show password");

    field.insertAdjacentElement("afterend", button);
    field.parentElement.classList.add("has-reveal");

    button.addEventListener("click", () => {
        const hidden = field.type === "password";
        field.type = hidden ? "text" : "password";
        button.textContent = hidden ? "hide" : "show";
        button.setAttribute("aria-label", hidden ? "Hide password" : "Show password");
        field.focus();
    });
}

// Tells you the two boxes disagree while you're still looking at them,
// instead of after a round trip that clears both.
function matchConfirm(password, confirm) {
    function check() {
        const mismatch = confirm.value && confirm.value !== password.value;
        confirm.setCustomValidity(mismatch ? "Passwords do not match" : "");
        confirm.classList.toggle("mismatch", Boolean(mismatch));
    }
    password.addEventListener("input", check);
    confirm.addEventListener("input", check);
}

// Double-clicking submit on a slow connection is how you end up with two
// accounts, or two of anything.
function submitOnce(form) {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button[type=submit]");
        if (!button) return;
        // A disabled button isn't submitted, so this has to run after the
        // browser has already taken the form.
        setTimeout(() => {
            button.disabled = true;
            button.dataset.was = button.textContent;
            button.textContent = "Working...";
        }, 0);
    });
}

const form = document.querySelector("form.login-card");

if (form) {
    const password = form.querySelector("input[name=password]");
    const confirm = form.querySelector("input[name=confirm_password]");

    form.querySelectorAll("input[type=password]").forEach(watchCapsLock);
    if (password) addReveal(password);
    if (password && confirm) matchConfirm(password, confirm);
    submitOnce(form);

    // Errors come back rendered server-side, so focus the first empty field
    // rather than making someone hunt for where they left off.
    const first = [...form.querySelectorAll("input")].find(i => !i.value);
    if (first) first.focus();
}
