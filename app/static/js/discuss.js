// ============================================================
// AI Meeting Router — 讨论页
// ============================================================

const form = document.querySelector("#discussion-form");
const thresholdInput = form.querySelector("[name='confidence_threshold']");
const thresholdValue = document.querySelector("#confidence-value");
const participantList = document.querySelector("#participant-list");
const compressorSelector = document.querySelector("#compressor-selector");
const streamEl = document.querySelector("#stream");
const finalAnswerEl = document.querySelector("#final-answer");
const statusEl = document.querySelector("#discussion-status");
const stopButton = document.querySelector("#stop-button");
const questionTextarea = form.querySelector("[name='question']");

let cards = new Map();

// ---------- textarea 自适应 ----------
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 300) + 'px';
}
function setupTextareaAutoResize() {
  if (!questionTextarea) return;
  autoResizeTextarea(questionTextarea);
  questionTextarea.addEventListener('input', () => autoResizeTextarea(questionTextarea));
  questionTextarea.addEventListener('paste', () => setTimeout(() => autoResizeTextarea(questionTextarea), 10));
}

// ---------- 状态 ----------
function setStatus(t) { statusEl.textContent = t || ""; }

// ---------- 参与者 ----------
async function loadParticipants() {
  const resp = await fetch("/api/ais");
  const ais = await resp.json();
  participantList.innerHTML = ais.length
    ? ais.map(ai => `<article class="participant-card"><strong>${ai.name}</strong><p>${ai.self_intro || "暂无自介"}</p></article>`).join("")
    : `<div class="participant-card">请先到配置页添加 AI。</div>`;

  // 填充压缩器选择器
  if (compressorSelector) {
    let optionsHtml = `<label class="compressor-option">
      <input type="radio" name="compressor" value="" checked>
      <span class="compressor-label">不设置压缩器</span>
    </label>`;
    optionsHtml += ais.map(ai => `
      <label class="compressor-option">
        <input type="radio" name="compressor" value="${ai.id}">
        <span class="compressor-label">${ai.name} <em>(${ai.model})</em></span>
      </label>`).join("");
    compressorSelector.innerHTML = optionsHtml;
  }
}

// ---------- 实时消息卡片 ----------
function createMessageCard(key, name, round) {
  const card = document.createElement("article");
  card.className = "message current";
  card.dataset.round = round;
  card.innerHTML = `<div class="message-head"><strong>${name}</strong><span>第 ${round} 轮 · 置信度 <b>--</b></span></div><div class="message-body"></div><details class="message-details"><summary>查看本轮调试日志</summary><pre class="message-details-content">日志加载中...</pre></details>`;
  streamEl.appendChild(card);
  cards.set(key, card);
  return card;
}

function updateConfidence(key, confidence, calibrated, calibration) {
  const card = cards.get(key);
  if (!card) return;
  let html = `第 ${card.dataset.round} 轮 · 置信度 <b>${confidence ?? "--"}</b>`;
  if (calibration && calibration !== 0) {
    html += ` (校准${calibration > 0 ? "+" : ""}${calibration}=<b>${calibrated ?? "--"}</b>)`;
  }
  card.querySelector(".message-head span").innerHTML = html;
}

// ---------- SSE 讨论 ----------
async function startDiscussion(event) {
  event.preventDefault();
  streamEl.innerHTML = "";
  finalAnswerEl.textContent = "讨论进行中…";
  cards = new Map();

  const payload = {
    question: form.querySelector("[name='question']").value.trim(),
    confidence_threshold: Number(thresholdInput.value),
    max_rounds: Number(form.querySelector("[name='max_rounds']").value),
    compressor_id: document.querySelector("input[name='compressor']:checked")?.value || null,
  };

  setStatus("连接中…");
  const resp = await fetch("/api/discussions", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) });
  if (!resp.ok) { const e = await resp.json(); setStatus(e.detail||"启动失败"); finalAnswerEl.textContent="未开始。"; return; }

  setStatus("讨论中…");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) processEventBlock(chunk);
  }
}

function processEventBlock(block) {
  const lines = block.split("\n");
  const event = lines.find(l => l.startsWith("event:"))?.slice(6).trim();
  const dl = lines.find(l => l.startsWith("data:"))?.slice(5).trim();
  if (!event || !dl) return;
  const data = JSON.parse(dl);

  if (event==="ai_start") { createMessageCard(`${data.ai_id}-${data.round}`,data.name,data.round); return; }
  if (event==="delta") { const c=cards.get(`${data.ai_id}-${data.round}`); if(c) c.querySelector(".message-body").textContent+=data.delta; return; }
  if (event==="ai_log") { const c=cards.get(`${data.ai_id}-${data.round}`); if(c){ const d=c.querySelector(".message-details-content"); if(d) d.textContent=`问题:\n${data.question}\n\n系统提示:\n${data.system_prompt}\n\n实际输入内容:\n${data.user_content}\n\n原始输出结果:\n${data.raw_output}`; } return; }
  if (event==="confidence") { updateConfidence(`${data.ai_id}-${data.round}`, data.confidence, data.calibrated, data.calibration); return; }
  if (event==="ai_end") { const c=cards.get(`${data.ai_id}-${data.round}`); if(c) c.classList.remove("current"); return; }
  if (event==="final_answer") { finalAnswerEl.textContent=data.answer||"未产生最终答案。"; return; }
  if (event==="done") { setStatus(`已结束：${data.reason}`); }
}

async function stopDiscussion() {
  await fetch("/api/discussions/stop", { method:"POST" });
  setStatus("已请求停止…");
}

// ---------- 初始化 ----------
thresholdInput.addEventListener("input", ()=>{ thresholdValue.textContent=thresholdInput.value; });
form.addEventListener("submit", startDiscussion);
stopButton.addEventListener("click", stopDiscussion);

function init() { loadParticipants(); setupTextareaAutoResize(); }
document.addEventListener("DOMContentLoaded", init);
if (document.readyState==="complete"||document.readyState==="interactive") init();
