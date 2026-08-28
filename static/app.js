(() => {
    const toggle = document.querySelector(".sidebar-toggle");
    const scrim = document.querySelector(".sidebar-scrim");

    const closeSidebar = () => {
        document.body.classList.remove("sidebar-open");
        toggle?.setAttribute("aria-expanded", "false");
    };

    toggle?.addEventListener("click", () => {
        const isOpen = document.body.classList.toggle("sidebar-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });
    scrim?.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeSidebar();
    });

    const dropZone = document.querySelector("[data-file-drop]");
    const fileInput = document.querySelector("[data-file-input]");
    const fileName = document.querySelector("[data-file-name]");

    const updateFileName = () => {
        const selected = fileInput?.files?.[0];
        if (fileName) {
            fileName.textContent = selected
                ? `${selected.name} · ${(selected.size / 1024).toFixed(1)} KB`
                : "Nenhum arquivo selecionado";
        }
    };

    fileInput?.addEventListener("change", updateFileName);
    ["dragenter", "dragover"].forEach((eventName) => {
        dropZone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.add("drag-over");
        });
    });
    ["dragleave", "drop"].forEach((eventName) => {
        dropZone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove("drag-over");
        });
    });
    dropZone?.addEventListener("drop", (event) => {
        const files = event.dataTransfer?.files;
        if (fileInput && files?.length) {
            fileInput.files = files;
            updateFileName();
        }
    });
})();
