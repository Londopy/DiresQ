const search=document.getElementById("search");

const reports=document.querySelectorAll(".report-card");

const checks=document.querySelectorAll("input[type=checkbox]");

function filter(){

const text=search.value.toLowerCase();

const enabled=[...checks]
.filter(c=>c.checked)
.map(c=>c.value);

reports.forEach(card=>{

const title=card.dataset.title;

const priority=card.dataset.priority;

const matchTitle=
title.includes(text);

const matchPriority=
enabled.includes(priority);

card.style.display=
(matchTitle&&matchPriority)
?
"block"
:
"none";

});

}

search.addEventListener("input",filter);

checks.forEach(c=>
c.addEventListener("change",filter)
);

const btn=document.getElementById("filterBtn");

const sidebar=document.getElementById("sidebar");

function setMenuState(isOpen) {

    sidebar.classList.toggle("show", isOpen);
    btn.classList.toggle("active", isOpen);
    btn.setAttribute("aria-expanded", String(isOpen));
    btn.setAttribute("aria-label", isOpen ? "Close filters" : "Open filters");

}

if (btn && sidebar) {

    btn.addEventListener("click", event => {

        event.stopPropagation();
        setMenuState(!sidebar.classList.contains("show"));

    });

    document.addEventListener("click", event => {

        if (window.innerWidth > 768 || !sidebar.classList.contains("show")) {
            return;
        }

        if (!sidebar.contains(event.target) && !btn.contains(event.target)) {
            setMenuState(false);
        }

    });

    document.addEventListener("keydown", event => {

        if (event.key === "Escape") {
            setMenuState(false);
        }

    });

}