// ============================================================
// AI Meeting Router — 历史记录页
// ============================================================

const historyList = document.querySelector("#history-list");
const historyDetail = document.querySelector("#history-detail");
let selectedCard = null;

// ---------- 时间格式化 ----------
function formatTimestamp(id) {
  if (!/^\d{14}$/.test(id)) return id;
  return `${id.slice(0,4)}-${id.slice(4,6)}-${id.slice(6,8)} ${id.slice(8,10)}:${id.slice(10,12)}:${id.slice(12,14)}`;
}

// ---------- 渲染历史列表 ----------
function renderHistoryList(items) {
  if (!items.length) {
    historyList.innerHTML = `<div class="history-empty">暂无历史讨论</div>`;
    return;
  }
  historyList.innerHTML = items.map(item => {
    const q = item.question || "";
    const a = item.final_answer || "";
    return `<article class="history-card" data-id="${item.id}">
      <div class="history-card-time">${formatTimestamp(item.id)}</div>
      <div class="history-card-q">${q.length > 50 ? q.slice(0,50)+'...' : q}</div>
      <div class="history-card-a">${a.length > 40 ? a.slice(0,40)+'...' : a || "（无答案）"}</div>
    </article>`;
  }).join("");
}

async function loadHistoryList() {
  if (!historyList) return;
  historyList.innerHTML = `<div class="history-empty">加载中…</div>`;
  try {
    const resp = await fetch("/api/discussions");
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    const items = await resp.json();
    renderHistoryList(items);
  } catch (err) {
    historyList.innerHTML = `<div class="history-empty">加载失败：${err.message}</div>`;
  }
}

// ---------- 加载详情 ----------
async function loadDetail(id) {
  if (selectedCard) selectedCard.classList.remove("selected");
  const card = historyList?.querySelector(`[data-id="${id}"]`);
  if (card) { card.classList.add("selected"); selectedCard = card; }

  historyDetail.innerHTML = `<div class="history-empty">加载中…</div>`;
  try {
    const resp = await fetch(`/api/discussions/${id}`);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    const record = await resp.json();

    const msgsHtml = (record.messages || []).map(m => `
      <div class="history-message">
        <div class="msg-header"><strong class="msg-ai-name">${m.ai_name}</strong><span class="msg-meta">第 ${m.round_number} 轮 · 置信度 ${m.confidence ?? "--"}</span></div>
        <div class="msg-content">${m.content}</div>
      </div>`).join("");

    historyDetail.innerHTML = `
      <div class="detail-section">
        <div class="detail-label">📋 问题</div>
        <div class="detail-text">${record.question || ""}</div>
      </div>
      <div class="detail-section">
        <div class="detail-label">✅ 最终答案</div>
        <div class="detail-text">${record.final_answer || "（无）"}</div>
      </div>
      <div class="detail-meta">
        <span>⏹ 结束原因：${record.stop_reason || "—"}</span>
        <span>🕐 ${formatTimestamp(record.id)}</span>
        <span>💬 ${record.metadata?.message_count ?? (record.messages||[]).length} 条消息</span>
      </div>
      <div class="detail-section">
        <div class="detail-label">📨 详细消息</div>
        <div class="messages-list">${msgsHtml}</div>
      </div>`;
  } catch (err) {
    historyDetail.innerHTML = `<div class="history-empty">读取失败：${err.message}</div>`;
  }
}

// ---------- 点击事件 ----------
historyList?.addEventListener("click", (e) => {
  const card = e.target.closest(".history-card");
  if (!card) return;
  loadDetail(card.dataset.id);
});

// ---------- 初始化 ----------
function init() {
  loadHistoryList();
}
document.addEventListener("DOMContentLoaded", init);
if (document.readyState === "complete" || document.readyState === "interactive") init();
