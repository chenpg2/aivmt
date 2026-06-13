/* AIVMT 教师评分门户 — 前端逻辑(原生 JS,无构建步骤、无外部依赖)。
 * 盲评保证:本前端只请求 /api/next(返回去标识转写 + turns),从不请求任何系统评分。
 * 范围校验的最终标准在服务器端(faculty_portal.scoring);本文件仅做收集与即时提示。 */
"use strict";

const $ = (id) => document.getElementById(id);

/* 评分维度顺序必须与服务器端 SCORE_FIELDS 一致(5 个 SEGUE 要素 + 病史完整度 + 临床推理 + 总体)。 */
const FIELDS = [
  { key: "set_the_stage", name: "1. 开场(Set the stage)",
    anchor: "0 = 未自我介绍/未说明目的;1 = 自我介绍、说明来意并建立融洽关系" },
  { key: "elicit_information", name: "2. 采集信息(Elicit information)",
    anchor: "0 = 几乎不提问/只问封闭式;1 = 系统、开放式地引出病史" },
  { key: "give_information", name: "3. 提供信息(Give information)",
    anchor: "0 = 未给任何解释/反馈;1 = 用病人能懂的语言清晰说明" },
  { key: "understand_perspective", name: "4. 理解病人视角(Understand perspective)",
    anchor: "0 = 忽视病人的担忧与情绪;1 = 主动了解想法、顾虑与期望" },
  { key: "end_encounter", name: "5. 结束问诊(End the encounter)",
    anchor: "0 = 突兀结束;1 = 小结、答疑并妥善收尾" },
  { key: "history_completion", name: "6. 病史完整度(History completion)",
    anchor: "0 = 关键病史几乎全部遗漏;1 = 应问要点基本问全" },
  { key: "reasoning", name: "7. 临床推理(Clinical reasoning)",
    anchor: "0 = 提问无目的、无鉴别思路;1 = 围绕鉴别诊断有条理地追问" },
  { key: "overall", name: "8. 总体表现(Overall)",
    anchor: "0 = 完全未达标;1 = 总体表现优秀" },
];

let raterId = "";

/* ---------- API ---------- */
async function api(method, url, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(url, opts);
  let data = null;
  try { data = await resp.json(); } catch (_e) { data = null; }
  return { status: resp.status, data };
}
function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
}

/* ---------- 进度 ---------- */
function renderProgress(p) {
  const total = p.total || 0;
  const scored = p.scored || 0;
  $("progress-text").textContent = `${scored} / ${total}`;
  $("bar-fill").style.width = total ? `${Math.round((scored / total) * 100)}%` : "0%";
}

/* ---------- 评分表单 ---------- */
function buildScoreFields() {
  const box = $("score-fields");
  box.innerHTML = "";
  FIELDS.forEach((f) => {
    const item = document.createElement("div");
    item.className = "score-item";
    item.dataset.key = f.key;
    item.innerHTML =
      `<div class="si-head"><span class="si-name">${escapeHtml(f.name)}</span></div>` +
      `<div class="si-anchor">${escapeHtml(f.anchor)}</div>` +
      `<div class="si-controls">` +
      `<input type="range" min="0" max="1" step="0.05" value="0.5" data-role="range">` +
      `<input type="number" min="0" max="1" step="0.05" value="0.5" data-role="number">` +
      `</div>`;
    box.appendChild(item);
    const range = item.querySelector('[data-role="range"]');
    const number = item.querySelector('[data-role="number"]');
    range.addEventListener("input", () => { number.value = range.value; markRange(item, number.value); });
    number.addEventListener("input", () => {
      const v = parseFloat(number.value);
      if (Number.isFinite(v)) range.value = String(Math.min(1, Math.max(0, v)));
      markRange(item, number.value);
    });
  });
}
function markRange(item, raw) {
  const v = parseFloat(raw);
  item.classList.toggle("bad", !(Number.isFinite(v) && v >= 0 && v <= 1));
}
function resetScoreFields() {
  $("score-fields").querySelectorAll(".score-item").forEach((item) => {
    item.classList.remove("bad");
    item.querySelector('[data-role="range"]').value = "0.5";
    item.querySelector('[data-role="number"]').value = "0.5";
  });
  $("f-notes").value = "";
}
function collectScores() {
  const out = { encounter_id: currentEncounterId, rater_id: raterId, notes: $("f-notes").value };
  $("score-fields").querySelectorAll(".score-item").forEach((item) => {
    out[item.dataset.key] = item.querySelector('[data-role="number"]').value;
  });
  return out;
}

/* ---------- 转写展示 ---------- */
function renderTranscript(t) {
  $("enc-meta").textContent = `编号 ${t.encounter_id} · 病例 ${t.case_id} · ${t.language}`;
  const box = $("transcript");
  box.innerHTML = "";
  (t.turns || []).forEach((turn) => {
    const div = document.createElement("div");
    div.className = "turn " + (turn.speaker === "patient" ? "patient" : "student");
    const role = turn.speaker === "patient" ? "病人" : "学生";
    div.innerHTML = `<span class="role">${role}</span>${escapeHtml(turn.text)}`;
    box.appendChild(div);
  });
  box.scrollTop = 0;
}

/* ---------- 消息 ---------- */
function showMessage(kind, html) {
  const box = $("messages");
  box.innerHTML = `<div class="box ${kind}">${html}</div>`;
  if (kind === "ok") setTimeout(() => { if (box.firstChild) box.innerHTML = ""; }, 2500);
}
function clearMessage() { $("messages").innerHTML = ""; }

/* ---------- 流程 ---------- */
let currentEncounterId = null;

async function startSession() {
  const rid = $("rater-id").value.trim();
  if (!rid) { $("login-msg").textContent = "请先输入评分者编号。"; $("login-msg").className = "msg err"; return; }
  const { status, data } = await api("GET", "/api/session/" + encodeURIComponent(rid));
  if (status !== 200 || !data) {
    $("login-msg").textContent = "无法开始会话(" + status + ")。请联系技术同事。";
    $("login-msg").className = "msg err";
    return;
  }
  raterId = rid;
  $("who-rater").textContent = rid;
  $("login").classList.add("hidden");
  $("workbench").classList.remove("hidden");
  buildScoreFields();
  renderProgress(data);
  loadNext();
}

async function loadNext() {
  clearMessage();
  const { status, data } = await api("GET", "/api/next/" + encodeURIComponent(raterId));
  if (status !== 200 || !data) { showMessage("err", "加载下一条转写失败。"); return; }
  renderProgress(data.progress);
  if (data.done || !data.transcript) {
    currentEncounterId = null;
    $("score-panel").classList.add("hidden");
    $("done-panel").classList.remove("hidden");
    return;
  }
  $("done-panel").classList.add("hidden");
  $("score-panel").classList.remove("hidden");
  currentEncounterId = data.transcript.encounter_id;
  renderTranscript(data.transcript);
  resetScoreFields();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function submitScore() {
  if (!currentEncounterId) return;
  const btn = $("btn-submit");
  btn.disabled = true;
  const { status, data } = await api("POST", "/api/score", { submission: collectScores(), overwrite: false });
  btn.disabled = false;
  if (status === 422) {
    const errs = (data && data.detail && data.detail.errors) || [];
    errs.forEach((e) => {
      const item = $("score-fields").querySelector(`.score-item[data-key="${e.field}"]`);
      if (item) item.classList.add("bad");
    });
    const lis = errs.map((e) => `<li>${escapeHtml(e.field)}:${escapeHtml(e.message)}</li>`).join("");
    showMessage("err", `<strong>有 ${errs.length} 项不合规,未保存:</strong><ul>${lis}</ul>`);
    return;
  }
  if (status === 409) { showMessage("err", "本条已评过分,已跳过。"); loadNext(); return; }
  if (status !== 200 || !data) { showMessage("err", "提交失败(" + status + ")。"); return; }
  showMessage("ok", "已保存 ✅,进入下一条。");
  loadNext();
}

function logout() {
  raterId = "";
  currentEncounterId = null;
  $("workbench").classList.add("hidden");
  $("login").classList.remove("hidden");
  $("rater-id").value = "";
  $("login-msg").textContent = "";
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $("btn-start").addEventListener("click", startSession);
  $("rater-id").addEventListener("keydown", (e) => { if (e.key === "Enter") startSession(); });
  $("btn-submit").addEventListener("click", submitScore);
  $("btn-logout").addEventListener("click", logout);
});
