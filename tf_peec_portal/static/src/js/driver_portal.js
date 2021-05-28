function showManual() {
    var manual_form = document.getElementById("manual_form");
    var manual_date = document.getElementById("manual_date");
    var manual_reason = document.getElementById("manual_reason");
    var is_manual = document.getElementById("is_manual");

    if (manual_form.style.display === "none") {
        manual_form.style.display = "block";
        manual_date.setAttribute("required", "required");
        manual_reason.setAttribute("required", "required");
        is_manual.value = 1;
    } else {
        manual_form.style.display = "none";
        manual_date.removeAttribute("required");
        manual_reason.removeAttribute("required");
        is_manual.value = 0;
    }
}

var tripModal = document.getElementById("tripModal");
var tripBtn = document.getElementById("tripBtn");
var tripCloseBtn = document.getElementById("trip-close");

tripBtn.onclick = function () {
    tripModal.style.display = "block";
}

tripCloseBtn.onclick = function () {
    tripModal.style.display = "none";
}

var weightModal = document.getElementById("weightModal");
var weightBtn = document.getElementById("weightBtn");
var weightCloseBtn = document.getElementById("weight-close");

weightBtn.onclick = function () {
    weightModal.style.display = "block";
}

weightCloseBtn.onclick = function () {
    weightModal.style.display = "none";
}

window.onclick = function (event) {
    if (event.target === tripModal || event.target === weightModal) {
        tripModal.style.display = "none";
        weightModal.style.display = "none";
    }
}

var checkerSelect = document.getElementById("checker_id");
var newCheckerLabel= document.getElementById("new_checker_label");
var newCheckerSelect = document.getElementById("new_checker");
checkerSelect.onchange = function() {
    if (checkerSelect.value === 'new') {
        newCheckerLabel.style.display = "block";
        newCheckerSelect.style.display = "block";
        newCheckerSelect.setAttribute("required", "required");
    }
    else {
        newCheckerLabel.style.display = "none";
        newCheckerSelect.style.display = "none";
        newCheckerSelect.removeAttribute("required");
    }
}