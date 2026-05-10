const form = document.querySelector("#ai-form");
const listEl = document.querySelector("#ai-list");
const statusEl = document.querySelector("#config-status");
const resetButton = document.querySelector("#reset-form");

let ais = [];
let dragId = null;

function setStatus(message) {
  statusEl.textContent = message || "";
}

function formToPayload() {
  const data = new FormData(form);
  return {
    name: data.get("name")?.trim(),
    base_url: data.get("base_url")?.trim(),
    api_key: data.get("api_key")?.trim(),
    model: data.get("model")?.trim(),
    system_prompt: data.get("system_prompt")?.trim(),
    context_window: Number(data.get("context_window") || 8192),
    confidence_calibration: Number(data.get("confidence_calibration") || 0),
    enabled: form.querySelector("[name='enabled']").checked,
    self_intro: data.get("self_intro")?.trim() || "",
  };
}

function fillForm(ai = null) {
  form.reset();
  form.querySelector("[name='id']").value = ai?.id || "";
  form.querySelector("[name='name']").value = ai?.name || "";
  form.querySelector("[name='base_url']").value = ai?.base_url || "https://api.openai.com/v1";
  form.querySelector("[name='api_key']").value = ai?.api_key || "";
  form.querySelector("[name='model']").value = ai?.model || "gpt-4o-mini";
  form.querySelector("[name='system_prompt']").value = ai?.system_prompt || "";
  form.querySelector("[name='context_window']").value = ai?.context_window || 8192;
  form.querySelector("[name='confidence_calibration']").value = ai?.confidence_calibration ?? 0;
  form.querySelector("[name='enabled']").checked = ai?.enabled ?? true;
}

function renderList() {
  listEl.innerHTML = "";
  if (!ais.length) {
    listEl.innerHTML = `<div class="ai-card">还没有配置任何 AI。</div>`;
    return;
  }

  ais.forEach((ai, index) => {
    const status = ai.enabled ? ai.status || "checking" : "disabled";
    const statusLabel =
      status === "available"
        ? "可用"
        : status === "error"
        ? "报错"
        : status === "disabled"
        ? "已禁用"
        : "检测中";
    const statusClass =
      status === "available"
        ? "available"
        : status === "error"
        ? "error"
        : status === "disabled"
        ? "disabled"
        : "checking";
    const statusDetail = ai.status_detail ? ai.status_detail.replace(/"/g, "&quot;").replace(/</g, "&lt;") : "";
    const titleAttr = statusDetail ? `title="${statusDetail}"` : "";
    const errorDetailHtml = status === "error" && statusDetail
      ? `<span class="ai-status-error" title="${statusDetail}">${statusDetail}</span>`
      : "";

    const calib = ai.confidence_calibration ?? 0;
    const calibLabel = calib !== 0 ? ` · 校准 ${calib > 0 ? "+" : ""}${calib}` : "";

    const item = document.createElement("article");
    item.className = "ai-card ai-card-sortable";
    item.draggable = true;
    item.dataset.id = ai.id;
    item.innerHTML = `
      <div class="ai-card-head">
        <div class="ai-title-block">
          <span class="drag-handle" title="拖拽排序">::</span>
          <div>
            <strong>${ai.name}</strong>
            <div class="ai-meta">
              <span>${ai.model} · 窗口 ${ai.context_window}${calibLabel}</span>
              <span class="ai-status ${statusClass}" ${titleAttr}>${statusLabel}</span>
              ${errorDetailHtml}
            </div>
          </div>
        </div>
        <div>顺位 ${index + 1}</div>
      </div>
      <p>${ai.self_intro || "暂无自我介绍"}</p>
      <div class="ai-actions">
        <button class="ghost" data-action="toggle-enable" data-id="${ai.id}">${ai.enabled ? "禁用" : "启用"}</button>
        <button class="ghost" data-action="edit" data-id="${ai.id}">编辑</button>
        <button class="ghost" data-action="delete" data-id="${ai.id}">删除</button>
      </div>
    `;
    listEl.appendChild(item);
  });
}

async function loadStatuses() {
  if (!ais.length) {
    return;
  }

  const response = await fetch("/api/ais/status");
  if (!response.ok) {
    setStatus("AI 状态检测失败");
    return;
  }

  const statuses = await response.json();
  statuses.forEach((statusInfo) => {
    const ai = ais.find((item) => item.id === statusInfo.id);
    if (ai) {
      ai.status = statusInfo.status;
      ai.status_detail = statusInfo.detail;
    }
  });
  renderList();
  setStatus("AI 状态已更新。");
}

async function loadAis() {
  setStatus("加载 AI 配置...");
  const response = await fetch("/api/ais");
  ais = await response.json();
  renderList();
  setStatus("正在检测 AI 状态...");
  await loadStatuses();
}

async function saveAi(event) {
  event.preventDefault();
  const id = form.querySelector("[name='id']").value;
  const payload = formToPayload();
  const method = id ? "PUT" : "POST";
  const url = id ? `/api/ais/${id}` : "/api/ais";
  setStatus("保存中...");
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(data.detail || "保存失败");
    return;
  }
  if (data.self_intro_failed) {
    setStatus("自动生成自我介绍失败，已保存当前配置，请手动补充。");
  } else {
    setStatus("已保存。");
  }
  fillForm();
  await loadAis();
}

async function reorder(ids) {
  setStatus("排序已更新，保存中...");
  const response = await fetch("/api/ais/order", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  if (!response.ok) {
    setStatus("排序保存失败");
    await loadAis();
    return;
  }
  ais = await response.json();
  renderList();
  setStatus("排序已保存。");
}

function getCard(target) {
  return target.closest(".ai-card-sortable");
}

listEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  const ai = ais.find((item) => item.id === id);
  if (!ai) return;

  if (action === "edit") {
    fillForm(ai);
    setStatus(`正在编辑 ${ai.name}`);
    return;
  }

  if (action === "toggle-enable") {
    const nextEnabled = !ai.enabled;
    const response = await fetch(`/api/ais/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: nextEnabled }),
    });
    if (!response.ok) {
      const data = await response.json();
      setStatus(data.detail || "切换启用状态失败");
      return;
    }
    await loadAis();
    setStatus(`${ai.name} 已${nextEnabled ? "启用" : "禁用"}`);
    return;
  }

  if (action === "delete") {
    await fetch(`/api/ais/${id}`, { method: "DELETE" });
    await loadAis();
    setStatus("已删除。");
  }
});

listEl.addEventListener("dragstart", (event) => {
  const card = getCard(event.target);
  if (!card) return;
  dragId = card.dataset.id;
  card.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", dragId);
});

listEl.addEventListener("dragover", (event) => {
  event.preventDefault();
  const card = getCard(event.target);
  if (!card || card.dataset.id === dragId) return;
  listEl.querySelectorAll(".drop-target").forEach((node) => node.classList.remove("drop-target"));
  card.classList.add("drop-target");
});

listEl.addEventListener("dragleave", (event) => {
  const card = getCard(event.target);
  if (card) {
    card.classList.remove("drop-target");
  }
});

listEl.addEventListener("drop", async (event) => {
  event.preventDefault();
  const targetCard = getCard(event.target);
  if (!targetCard || !dragId || targetCard.dataset.id === dragId) return;

  const draggedIndex = ais.findIndex((item) => item.id === dragId);
  const targetIndex = ais.findIndex((item) => item.id === targetCard.dataset.id);
  if (draggedIndex === -1 || targetIndex === -1) return;

  const reordered = [...ais];
  const [draggedItem] = reordered.splice(draggedIndex, 1);
  reordered.splice(targetIndex, 0, draggedItem);
  dragId = null;
  await reorder(reordered.map((item) => item.id));
});

listEl.addEventListener("dragend", () => {
  dragId = null;
  listEl.querySelectorAll(".dragging, .drop-target").forEach((node) => {
    node.classList.remove("dragging", "drop-target");
  });
});

form.addEventListener("submit", saveAi);
resetButton.addEventListener("click", () => {
  fillForm();
  setStatus("");
});

loadAis();
