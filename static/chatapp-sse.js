// Composer + SSE client. Standalone — no htmx required.
// - drag/drop, paste, and file picker for image attachments
// - uploads each file to /p/{slug}/attachments, then stages a markdown ref
// - submits the combined message body and streams the SSE response
(() => {
  const form = document.getElementById("composer");
  if (!form) return;

  const messagesEl = document.querySelector(form.dataset.target || "#messages");
  const textarea = form.querySelector("textarea[name=content]");
  const sendBtn = form.querySelector("button[type=submit]");
  const attachBtn = document.getElementById("attach-btn");
  const attachInput = document.getElementById("attach-input");
  const tray = document.getElementById("attachments-tray");
  const newSessionBtn = document.getElementById("new-session-btn");

  const attachUrl = form.dataset.attachmentsUrl;
  const sessionsUrl = form.dataset.sessionsUrl;

  // Pending attachments staged for the next send.
  const pending = []; // [{ rel_path, markdown, blobUrl }]

  function renderTray() {
    tray.innerHTML = "";
    if (pending.length === 0) {
      tray.hidden = true;
      return;
    }
    tray.hidden = false;
    pending.forEach((p, i) => {
      const wrap = document.createElement("div");
      wrap.className = "attachment-chip";
      const img = document.createElement("img");
      img.src = p.blobUrl;
      img.alt = p.rel_path;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "chip-remove";
      rm.textContent = "×";
      rm.title = "remove";
      rm.addEventListener("click", () => {
        URL.revokeObjectURL(p.blobUrl);
        pending.splice(i, 1);
        renderTray();
      });
      wrap.appendChild(img);
      wrap.appendChild(rm);
      tray.appendChild(wrap);
    });
  }

  async function uploadFile(file) {
    const fd = new FormData();
    fd.append("file", file, file.name || "upload.png");
    const resp = await fetch(attachUrl, { method: "POST", body: fd });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`upload failed (${resp.status}): ${text}`);
    }
    const data = await resp.json();
    pending.push({
      rel_path: data.rel_path,
      markdown: data.markdown,
      blobUrl: URL.createObjectURL(file),
    });
    renderTray();
  }

  async function handleFiles(files) {
    for (const f of files) {
      if (!f.type.startsWith("image/")) continue;
      try {
        await uploadFile(f);
      } catch (e) {
        alert(e.message || String(e));
      }
    }
  }

  if (attachBtn && attachInput) {
    attachBtn.addEventListener("click", () => attachInput.click());
    attachInput.addEventListener("change", async () => {
      await handleFiles(attachInput.files);
      attachInput.value = "";
    });
  }

  // Drag and drop
  ["dragenter", "dragover"].forEach((ev) => {
    form.addEventListener(ev, (e) => {
      if (!e.dataTransfer || !e.dataTransfer.types.includes("Files")) return;
      e.preventDefault();
      form.classList.add("drag-active");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    form.addEventListener(ev, () => form.classList.remove("drag-active"));
  });
  form.addEventListener("drop", async (e) => {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    e.preventDefault();
    await handleFiles(e.dataTransfer.files);
  });

  // Paste image from clipboard
  textarea.addEventListener("paste", async (e) => {
    if (!e.clipboardData) return;
    const files = [...e.clipboardData.items]
      .filter((it) => it.kind === "file")
      .map((it) => it.getAsFile())
      .filter(Boolean);
    if (files.length === 0) return;
    e.preventDefault();
    await handleFiles(files);
  });

  // New session button (session strategy only)
  if (newSessionBtn && sessionsUrl) {
    newSessionBtn.addEventListener("click", async () => {
      const resp = await fetch(sessionsUrl, { method: "POST" });
      if (resp.ok) window.location.reload();
      else alert(`session create failed: ${resp.status}`);
    });
  }

  function appendMessageBlock(role, htmlOrText, asHtml) {
    const article = document.createElement("article");
    article.className = `msg msg-${role}`;
    const header = document.createElement("header");
    header.className = "role";
    header.textContent = role;
    const body = document.createElement("div");
    body.className = "body";
    if (asHtml) body.innerHTML = htmlOrText;
    else body.textContent = htmlOrText;
    article.appendChild(header);
    article.appendChild(body);
    messagesEl.appendChild(article);
    article.scrollIntoView({ behavior: "smooth", block: "end" });
    return body;
  }

  async function* parseSSE(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const evt = { event: "message", data: "" };
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) evt.event = line.slice(6).trim();
          else if (line.startsWith("data:")) {
            evt.data += (evt.data ? "\n" : "") + line.slice(5).trim();
          }
        }
        yield evt;
      }
    }
  }

  function buildContent() {
    const text = textarea.value.trim();
    if (pending.length === 0) return text;
    const refs = pending.map((p) => p.markdown).join("\n");
    // Put images on top so the LLM sees them first; text follows.
    return text ? `${refs}\n\n${text}` : refs;
  }

  async function submit(ev) {
    ev.preventDefault();
    const content = buildContent();
    if (!content) return;

    sendBtn.disabled = true;
    textarea.disabled = true;

    const fd = new FormData();
    fd.append("content", content);

    let resp;
    try {
      resp = await fetch(form.action, {
        method: "POST",
        body: fd,
        headers: { Accept: "text/event-stream" },
      });
    } catch (e) {
      sendBtn.disabled = false;
      textarea.disabled = false;
      alert("network error: " + e);
      return;
    }

    if (!resp.ok) {
      const text = await resp.text();
      alert(`error ${resp.status}: ${text}`);
      sendBtn.disabled = false;
      textarea.disabled = false;
      return;
    }

    let assistantBody = null;
    for await (const evt of parseSSE(resp)) {
      try {
        const payload = evt.data ? JSON.parse(evt.data) : {};
        if (evt.event === "setup") {
          appendMessageBlock("user", payload.user_html, true);
          assistantBody = appendMessageBlock("assistant", "", true);
          textarea.value = "";
          // Clear staged attachments now that they are in history.
          pending.forEach((p) => URL.revokeObjectURL(p.blobUrl));
          pending.length = 0;
          renderTray();
        } else if (evt.event === "chunk" && assistantBody) {
          assistantBody.innerHTML = payload.html || "";
        } else if (evt.event === "done") {
          break;
        }
      } catch (e) {
        console.error("bad SSE payload", evt, e);
      }
    }

    sendBtn.disabled = false;
    textarea.disabled = false;
    textarea.focus();
  }

  form.addEventListener("submit", submit);

  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      form.requestSubmit();
    }
  });
})();
