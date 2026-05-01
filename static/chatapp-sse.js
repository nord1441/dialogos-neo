// Minimal SSE-aware composer. Posts the form via fetch and parses the
// streaming SSE response by hand. Standalone — does not require htmx.
(() => {
  const form = document.getElementById("composer");
  if (!form) return;
  const messagesEl = document.querySelector(form.dataset.target || "#messages");
  const textarea = form.querySelector("textarea[name=content]");
  const sendBtn = form.querySelector("button[type=submit]");

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

  async function submit(ev) {
    ev.preventDefault();
    const content = textarea.value.trim();
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
