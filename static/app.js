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

    const communication = document.querySelector("[data-communication]");
    if (communication) {
        const statePanel = document.querySelector("[data-socket-status]");
        const stateLabel = document.querySelector("[data-socket-state]");
        const log = document.querySelector("[data-chat-log]");
        const emptyChat = document.querySelector("[data-chat-empty]");
        const feedback = document.querySelector("[data-socket-feedback]");
        const fileList = document.querySelector("[data-received-files]");
        const emptyFiles = document.querySelector("[data-received-empty]");
        const fileCount = document.querySelector("[data-received-count]");
        const seenFiles = new Set();
        let cursor = 0;
        let knownFiles = 0;
        let polling = false;

        const endpoint = (name) => communication.dataset[name];
        const request = async (url, options = {}) => {
            const response = await fetch(url, options);
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.erro || "Não foi possível concluir a operação.");
            return data;
        };
        const showFeedback = (message, isError = false) => {
            feedback.textContent = message || "";
            feedback.classList.toggle("is-error", isError);
        };
        const updateState = (estado) => {
            statePanel.dataset.state = estado || "desconectado";
            const labels = {
                conectado: "Conectado",
                conectando: "Conectando…",
                reconectando: "Reconectando…",
                desconectando: "Desconectando…",
                desconectado: "Desconectado",
            };
            stateLabel.textContent = labels[estado] || estado || "Desconectado";
        };
        const appendMessage = (event) => {
            emptyChat?.remove();
            const item = document.createElement("article");
            item.className = `chat-message ${event.tipo === "enviada" ? "outgoing" : ""} ${event.tipo === "erro" ? "chat-error" : ""}`;
            const heading = document.createElement("div");
            heading.className = "chat-message-meta";
            const who = document.createElement("strong");
            who.textContent = event.tipo === "enviada" ? `Patrimônio → ${event.destinatario || "todos"}`
                : event.tipo === "sistema" ? "Sistema" : event.tipo === "erro" ? "Aviso" : "Servidor / sistema";
            const when = document.createElement("time");
            when.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
            heading.append(who, when);
            const body = document.createElement("p");
            body.textContent = event.mensagem || "";
            item.append(heading, body);
            log.append(item);
            log.scrollTop = log.scrollHeight;
        };
        const addReceivedFile = (file) => {
            if (!file || seenFiles.has(file.token)) return;
            seenFiles.add(file.token);
            emptyFiles?.remove();
            knownFiles += 1;
            fileCount.textContent = `${knownFiles} arquivo${knownFiles === 1 ? "" : "s"}`;

            const card = document.createElement("article");
            card.className = "received-file";
            const icon = document.createElement("span");
            icon.className = "received-file-icon";
            icon.innerHTML = '<i class="ti ti-file-type-xml"></i>';
            const copy = document.createElement("span");
            copy.className = "received-file-copy";
            const name = document.createElement("strong");
            name.textContent = file.nome;
            const meta = document.createElement("small");
            meta.textContent = `De ${file.remetente} · ${(file.tamanho / 1024).toFixed(1)} KB`;
            copy.append(name, meta);
            const actions = document.createElement("div");
            actions.className = "received-file-actions";
            const download = document.createElement("a");
            download.className = "btn small";
            download.href = `/api/socket/arquivo/${encodeURIComponent(file.token)}`;
            download.innerHTML = '<i class="ti ti-download"></i> Baixar';
            actions.append(download);
            if (file.nome.toLowerCase().endsWith(".xml")) {
                const importButton = document.createElement("button");
                importButton.type = "button";
                importButton.className = "btn small primary";
                importButton.innerHTML = '<i class="ti ti-file-check"></i> Validar e importar';
                importButton.addEventListener("click", async () => {
                    importButton.disabled = true;
                    try {
                        const result = await request(`/api/socket/arquivo/${encodeURIComponent(file.token)}/importar`, { method: "POST" });
                        showFeedback(`${result.mensagem} ${result.inseridos} novos, ${result.atualizados} atualizados, ${result.erros.length} com erro(s).`);
                        appendMessage({ tipo: "sistema", mensagem: `XML ${file.nome} validado e processado pelo lote ${result.lote}.` });
                    } catch (error) {
                        showFeedback(error.message, true);
                        appendMessage({ tipo: "erro", mensagem: `Falha ao importar ${file.nome}: ${error.message}` });
                    } finally {
                        importButton.disabled = false;
                    }
                });
                actions.append(importButton);
            }
            card.append(icon, copy, actions);
            fileList.prepend(card);
        };
        const poll = async () => {
            if (polling) return;
            polling = true;
            try {
                const data = await request(`${endpoint("statusUrl")}?desde=${cursor}`);
                updateState(data.estado);
                if (data.erro && data.estado === "reconectando") showFeedback(data.erro, true);
                (data.eventos || []).forEach((event) => {
                    cursor = Math.max(cursor, event.id || 0);
                    if (event.tipo === "arquivo") addReceivedFile(event.arquivo);
                    appendMessage(event);
                });
                (data.arquivos || []).forEach(addReceivedFile);
                cursor = Math.max(cursor, data.cursor || 0);
            } catch (error) {
                updateState("desconectado");
            } finally {
                polling = false;
                window.setTimeout(poll, 1400);
            }
        };

        document.querySelector("[data-socket-connect]")?.addEventListener("click", async () => {
            const nome = document.querySelector("#socket-name").value.trim();
            try {
                const data = await request(endpoint("connectUrl"), {
                    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome }),
                });
                updateState(data.estado);
                showFeedback(`Solicitada conexão como ${data.nome}.`);
            } catch (error) { showFeedback(error.message, true); }
        });
        document.querySelector("[data-socket-disconnect]")?.addEventListener("click", async () => {
            try {
                const data = await request(endpoint("disconnectUrl"), { method: "POST" });
                updateState(data.estado);
                showFeedback("Desconexão solicitada.");
            } catch (error) { showFeedback(error.message, true); }
        });
        document.querySelector("[data-message-form]")?.addEventListener("submit", async (event) => {
            event.preventDefault();
            const message = document.querySelector("#chat-message");
            const destination = document.querySelector("#message-destination");
            try {
                await request(endpoint("messageUrl"), {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mensagem: message.value, destino: destination.value }),
                });
                showFeedback(destination.value.trim() ? `Mensagem enviada para ${destination.value.trim()}.` : "Mensagem enviada para todos.");
                message.value = "";
            } catch (error) { showFeedback(error.message, true); }
        });
        document.querySelector("[data-file-form]")?.addEventListener("submit", async (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            const selected = data.get("arquivo");
            if (!selected?.name) { showFeedback("Escolha um arquivo primeiro.", true); return; }
            try {
                const result = await request(endpoint("fileUrl"), { method: "POST", body: data });
                showFeedback(result.mensagem);
                appendMessage({ tipo: "sistema", mensagem: result.mensagem });
                form.reset();
                document.querySelector("[data-picked-file]").textContent = "Escolher arquivo";
            } catch (error) { showFeedback(error.message, true); }
        });
        document.querySelector("#socket-file")?.addEventListener("change", (event) => {
            document.querySelector("[data-picked-file]").textContent = event.target.files?.[0]?.name || "Escolher arquivo";
        });
        document.querySelector("[data-send-rh]")?.addEventListener("click", async () => {
            try {
                const destino = document.querySelector("#file-destination").value.trim() || "rh";
                const result = await request(endpoint("sendRhUrl"), {
                    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ destino }),
                });
                showFeedback(result.mensagem);
                appendMessage({ tipo: "sistema", mensagem: `${result.mensagem} ${(result.tamanho / 1024).toFixed(1)} KB.` });
            } catch (error) { showFeedback(error.message, true); }
        });

        poll();
    }
})();
