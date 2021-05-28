var addModal = document.getElementById("addModal");
var addBtn = document.getElementById("addBtn");
var closeBtn = document.getElementsByClassName("modal-close")[0];

addBtn.onclick = function () {
    addModal.style.display = "block";
}

closeBtn.onclick = function () {
    addModal.style.display = "none";
}

window.onclick = function (event) {
    if (event.target == addModal) {
        addModal.style.display = "none";
    }
}
