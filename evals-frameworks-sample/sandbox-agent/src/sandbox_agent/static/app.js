const $ = (sel) => document.querySelector(sel);

let agents = [];
let current = null; // selected agent name
let viewing = null; // session id being watched
let poll = null;
let seq = 0;

function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "onclick") node.addEventListener("click", value);
    else node.setAttribute(key, value);
  }
  for (const kid of kids) {
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || res.statusText));
  }
  return body;
}

async function loadAgents() {
  agents = await api("/api/agents");
  const list = $("#agents");
  list.replaceChildren();
  for (const a of agents) {
    list.append(
      el(
        "li",
        { class: a.name === current ? "active" : "", onclick: () => selectAgent(a.name) },
        a.name,
        el("span", { class: "tag" }, a.run_mode),
        a.builtin ? el("span", { class: "tag" }, "built-in") : ""
      )
    );
  }
}

function selectAgent(name) {
  current = name;
  viewing = null;
  clearInterval(poll);
  loadAgents();
  renderDetail();
}

function renderDetail() {
  const a = agents.find((x) => x.name === current);
  const section = $("#detail");
  section.replaceChildren();
  if (!a) return;
  section.append(
    el("h2", {}, a.name),
    el("p", { class: "muted" }, a.instructions),
    el("p", {}, `Tools: ${a.tools.join(", ")} · max steps ${a.max_steps} · mode: ${a.run_mode}`),
    runForm(a),
    el("h3", {}, "Sessions"),
    el("ul", { id: "sessions", class: "list" }),
    el("div", { id: "viewer" })
  );
  loadSessions();
}

function runForm(agent) {
  const form = el("form", { class: "card" });
  form.innerHTML = `
    <label>Task
      <textarea name="task" rows="3" required placeholder="What should this agent do in its sandbox?"></textarea>
    </label>
    <label>Optional data file, saved to /workspace/data.csv
      <textarea name="file_text" rows="3" placeholder="Paste CSV contents here"></textarea>
    </label>
    <button type="submit">Run in new sandbox</button>
    <p class="err" data-role="runErr"></p>`;
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = { task: fd.get("task"), file_text: fd.get("file_text") || null };
    try {
      const s = await api(`/api/agents/${encodeURIComponent(agent.name)}/sessions`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      form.reset();
      openSession(s.id);
    } catch (err) {
      form.querySelector('[data-role="runErr"]').textContent = err.message;
    }
  });
  return form;
}

async function loadSessions() {
  const ul = $("#sessions");
  if (!ul || !current) return;
  const list = await api(`/api/sessions?agent=${encodeURIComponent(current)}`);
  ul.replaceChildren();
  for (const s of list) {
    ul.append(el("li", { onclick: () => openSession(s.id) }, `${s.task.slice(0, 70)} — ${s.status}`));
  }
  if (!list.length) ul.append(el("li", { class: "muted" }, "No sessions yet"));
}

function openSession(id) {
  clearInterval(poll);
  viewing = id;
  seq = 0;
  $("#viewer").replaceChildren(
    el("h3", {}, `Session ${id}`),
    el("p", { id: "status" }),
    el("div", { id: "pending" }),
    el("ol", { id: "trace", class: "trace" }),
    el("div", { id: "result" })
  );
  tick();
  poll = setInterval(tick, 1000);
}

async function tick() {
  const id = viewing;
  if (!id) return;
  let s;
  try {
    s = await api(`/api/sessions/${id}?since=${seq}`);
  } catch (err) {
    clearInterval(poll);
    if (id === viewing && $("#status")) $("#status").textContent = err.message;
    return;
  }
  if (id !== viewing) return;

  for (const ev of s.events) renderEvent(ev);
  seq = s.next_seq;
  $("#status").textContent = `status: ${s.status}`;
  renderPending(s.pending);

  if (s.status !== "running" && s.status !== "waiting_approval") {
    clearInterval(poll);
    renderResult(s);
    loadSessions();
  }
}

function renderEvent(ev) {
  const trace = $("#trace");
  if (!trace) return;
  let text;
  switch (ev.type) {
    case "sandbox_started":
      text = "Sandbox created for this session";
      break;
    case "tool_proposed":
      text = `step ${ev.step}: proposes ${ev.name}(${ev.arguments})`;
      break;
    case "tool_result":
      text = ev.error ? `  ↳ error: ${ev.error}` : `  ↳ ${ev.result}`;
      break;
    case "final":
      text = `Final answer: ${ev.answer}`;
      break;
    default:
      text = JSON.stringify(ev);
  }
  if (text.length > 1200) text = text.slice(0, 1200) + " …";
  trace.append(el("li", { class: ev.type }, text));
}

function renderPending(p) {
  const box = $("#pending");
  if (!box) return;
  box.replaceChildren();
  if (!p) return;
  box.append(
    el(
      "div",
      { class: "approval" },
      el("strong", {}, "Approval needed: "),
      `${p.name}(${p.arguments})`,
      el(
        "div",
        {},
        el("button", { onclick: () => decide(p.id, true) }, "Allow"),
        " ",
        el("button", { class: "deny", onclick: () => decide(p.id, false) }, "Deny")
      )
    )
  );
}

async function decide(pendingId, allow) {
  try {
    await api(`/api/sessions/${viewing}/decisions`, {
      method: "POST",
      body: JSON.stringify({ pending_id: pendingId, allow }),
    });
  } catch (err) {
    alert(err.message);
  }
}

function renderResult(s) {
  const box = $("#result");
  if (!box) return;
  if (s.error) {
    box.append(el("p", { class: "err" }, `Error: ${s.error}`));
  } else if (s.result) {
    box.append(
      el(
        "p",
        { class: "muted" },
        `Stop reason: ${s.result.stop_reason} · steps: ${s.result.steps}. Sandbox deleted when the run ended.`
      )
    );
  }
}

async function createAgent(e) {
  e.preventDefault();
  const form = e.target;
  const err = $("#newAgentErr");
  err.textContent = "";
  const fd = new FormData(form);
  const body = {
    name: fd.get("name").trim(),
    instructions: fd.get("instructions"),
    tools: fd.getAll("tools"),
    max_steps: Number(fd.get("max_steps")),
    run_mode: fd.get("run_mode"),
  };
  try {
    await api("/api/agents", { method: "POST", body: JSON.stringify(body) });
    form.reset();
    await loadAgents();
    selectAgent(body.name);
  } catch (ex) {
    err.textContent = ex.message;
  }
}

async function init() {
  const tools = await api("/api/tools");
  const boxes = $("#toolBoxes");
  for (const t of tools) {
    const cb = el("input", { type: "checkbox", name: "tools", value: t.name });
    cb.checked = ["run_shell", "read_file", "write_file"].includes(t.name);
    boxes.append(el("label", { class: "inline" }, cb, ` ${t.name} `, el("span", { class: "muted" }, t.description)));
  }
  $("#newAgent").addEventListener("submit", createAgent);
  await loadAgents();
}

init();
