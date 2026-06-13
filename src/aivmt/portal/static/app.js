/* AIVMT 病历录入门户 — 前端逻辑(原生 JS,无构建步骤、无外部依赖)。
 * 校验的最终标准在服务器端(aivmt.case_schema / case_lint);本文件只做收集与展示。
 * TODO_COLLAB 占位符在表单中显示为空,保存时由服务器重新标记 —— 前端绝不臆造临床内容。 */
"use strict";

const TODO = "TODO_COLLAB";
const $ = (id) => document.getElementById(id);

/* ---------- 工具 ---------- */
function clean(v) { return (v === null || v === undefined) ? "" : String(v); }
function showValue(v) { const s = clean(v); return s === TODO ? "" : s; }
function linesToList(text) {
  return clean(text).split("\n").map((s) => s.trim()).filter((s) => s && s !== TODO);
}
function listToLines(list) {
  if (!Array.isArray(list)) return "";
  return list.map(showValue).filter(Boolean).join("\n");
}
async function api(method, url, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(url, opts);
  let data = null;
  try { data = await resp.json(); } catch (_e) { data = null; }
  return { status: resp.status, data };
}

/* ---------- 动态行(隐藏信息 / 干扰项 / 评分清单) ---------- */
const ROW_DEFS = {
  hidden_info: {
    idKey: "info_id", idPrefix: "hi_",
    fields: [
      { key: "content", ph: "内容:学生问到时才透露的事实", tag: "textarea" },
      { key: "trigger", ph: "触发条件(必填):学生问到什么才透露", tag: "textarea" },
    ],
  },
  red_herrings: {
    idKey: "herring_id", idPrefix: "rh_",
    fields: [
      { key: "content", ph: "内容:良性但分散注意力的信息", tag: "textarea" },
      { key: "note", ph: "备注(选填)", tag: "textarea" },
    ],
  },
  history_checklist: {
    idKey: "item_id", idPrefix: "hx_",
    fields: [
      { key: "text", ph: "评分要点,如 询问末次月经/停经时间", tag: "textarea" },
      { key: "weight", ph: "权重(默认 1.0)", tag: "input" },
    ],
  },
};

function addRow(kind, values) {
  const def = ROW_DEFS[kind];
  const box = $("rows-" + kind);
  const row = document.createElement("div");
  row.className = "row";

  const idInput = document.createElement("input");
  idInput.placeholder = "编号";
  idInput.dataset.key = def.idKey;
  idInput.value = values && values[def.idKey] ? showValue(values[def.idKey])
    : def.idPrefix + (box.children.length + 1);
  row.appendChild(idInput);

  def.fields.forEach((f) => {
    const el = document.createElement(f.tag);
    if (f.tag === "textarea") el.rows = 1;
    el.placeholder = f.ph;
    el.dataset.key = f.key;
    el.value = values ? showValue(values[f.key]) : "";
    row.appendChild(el);
  });

  const del = document.createElement("button");
  del.type = "button"; del.className = "del"; del.textContent = "✕"; del.title = "删除本条";
  del.addEventListener("click", () => row.remove());
  row.appendChild(del);
  box.appendChild(row);
}

function readRows(kind) {
  return Array.from($("rows-" + kind).querySelectorAll(".row")).map((row) => {
    const out = {};
    row.querySelectorAll("[data-key]").forEach((el) => { out[el.dataset.key] = el.value.trim(); });
    return out;
  });
}

function setRows(kind, list) {
  $("rows-" + kind).innerHTML = "";
  (Array.isArray(list) ? list : []).forEach((item) => addRow(kind, item || {}));
}

/* ---------- 表单 <-> 草稿 ---------- */
const HPI_KEYS = ["onset", "location", "duration", "character", "aggravating", "relieving", "timing", "severity"];
const OBGYN_KEYS = ["lmp", "menstrual_history", "obstetric_history", "contraception", "sexual_history"];
const LIST_KEYS = ["pmh", "medications", "allergies", "family_history", "social_history", "pertinent_negatives"];

function collectDraft() {
  const hpi = { associated_symptoms: linesToList($("f-hpi-associated_symptoms").value) };
  HPI_KEYS.forEach((k) => { hpi[k] = $("f-hpi-" + k).value.trim(); });
  const obgyn = {};
  OBGYN_KEYS.forEach((k) => { obgyn[k] = $("f-obgyn-" + k).value.trim(); });
  const draft = {
    case_id: $("f-case_id").value.trim(),
    version: $("f-version").value.trim(),
    title: $("f-title").value.trim(),
    language: $("f-language").value,
    specialty: $("f-specialty").value.trim(),
    difficulty: $("f-difficulty").value,
    demographics: {
      age: $("f-age").value.trim(), sex: $("f-sex").value,
      occupation: $("f-occupation").value.trim(), marital_status: $("f-marital_status").value.trim(),
    },
    chief_complaint: $("f-chief_complaint").value.trim(),
    hpi, obgyn,
    hidden_info: readRows("hidden_info"),
    red_herrings: readRows("red_herrings"),
    history_checklist: readRows("history_checklist"),
    emotional_state: $("f-emotional_state").value.trim(),
    disclosure_profile: $("f-disclosure_profile").value.trim(),
    persona: $("f-persona").value.trim(),
  };
  LIST_KEYS.forEach((k) => { draft[k] = linesToList($("f-" + k).value); });
  return draft;
}

function fillForm(c) {
  $("f-case_id").value = showValue(c.case_id);
  $("f-version").value = showValue(c.version);
  $("f-title").value = showValue(c.title);
  $("f-language").value = clean(c.language) || "zh";
  $("f-specialty").value = showValue(c.specialty);
  $("f-difficulty").value = clean(c.difficulty) || "moderate";
  const demo = c.demographics || {};
  $("f-age").value = showValue(demo.age);
  $("f-sex").value = clean(demo.sex) === TODO ? "" : clean(demo.sex);
  $("f-occupation").value = showValue(demo.occupation);
  $("f-marital_status").value = showValue(demo.marital_status);
  $("f-chief_complaint").value = showValue(c.chief_complaint);
  const hpi = c.hpi || {};
  HPI_KEYS.forEach((k) => { $("f-hpi-" + k).value = showValue(hpi[k]); });
  $("f-hpi-associated_symptoms").value = listToLines(hpi.associated_symptoms);
  LIST_KEYS.forEach((k) => { $("f-" + k).value = listToLines(c[k]); });
  const ob = c.obgyn || {};
  OBGYN_KEYS.forEach((k) => { $("f-obgyn-" + k).value = showValue(ob[k]); });
  setRows("hidden_info", c.hidden_info);
  setRows("red_herrings", c.red_herrings);
  setRows("history_checklist", c.history_checklist);
  $("f-emotional_state").value = showValue(c.emotional_state);
  $("f-disclosure_profile").value = showValue(c.disclosure_profile);
  $("f-persona").value = showValue(c.persona);
  $("f-overwrite").checked = false;
}

function newCase() {
  fillForm({ language: "zh", specialty: "obgyn", difficulty: "moderate", version: "1.0.0" });
  setRows("history_checklist", [{}]);
  showMessages([], [], "已清空表单,可开始录入新病例。");
}

/* ---------- 消息展示 ---------- */
function showMessages(errors, warnings, okText) {
  const box = $("messages");
  box.innerHTML = "";
  const block = (cls, title, items) => {
    const div = document.createElement("div");
    div.className = "box " + cls;
    const ul = (items || []).map((it) => `<li>${escapeHtml(it.message || it)}</li>`).join("");
    div.innerHTML = `<strong>${title}</strong>` + (ul ? `<ul>${ul}</ul>` : "");
    box.appendChild(div);
  };
  if (errors && errors.length) block("err", `存在 ${errors.length} 处错误,未保存:`, errors);
  if (warnings && warnings.length) block("warn", `提示:${warnings.length} 个留空字段已标记为 TODO_COLLAB 待补`, warnings);
  if (okText && !(errors && errors.length)) block("ok", okText, []);
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function escapeHtml(s) {
  return clean(s).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
}

/* ---------- 病例列表 ---------- */
async function refreshList() {
  const { status, data } = await api("GET", "/api/cases");
  const ul = $("case-list");
  ul.innerHTML = "";
  if (status !== 200 || !Array.isArray(data)) {
    ul.innerHTML = '<li class="muted">列表加载失败</li>';
    return;
  }
  if (!data.length) { ul.innerHTML = '<li class="muted">(目前没有病例)</li>'; return; }
  data.forEach((c) => {
    const li = document.createElement("li");
    const badge = c.n_errors > 0 ? `<span class="badge err">错误 ${c.n_errors}</span>`
      : c.n_warnings > 0 ? `<span class="badge warn">待补 ${c.n_warnings}</span>`
        : '<span class="badge ok">通过</span>';
    li.innerHTML = `<span class="cid">${escapeHtml(c.case_id)}</span>` +
      `<span class="ctitle">${escapeHtml(c.title || "")}</span>` + badge;
    li.addEventListener("click", () => loadCase(c.case_id, li));
    ul.appendChild(li);
  });
}

async function loadCase(caseId, li) {
  const { status, data } = await api("GET", "/api/cases/" + encodeURIComponent(caseId));
  if (status !== 200) { showMessages([{ message: "加载病例失败:" + (data && data.detail ? data.detail : status) }], []); return; }
  fillForm(data.case || {});
  document.querySelectorAll("#case-list li").forEach((el) => el.classList.remove("active"));
  if (li) li.classList.add("active");
  const warns = (data.lint && data.lint.warnings ? data.lint.warnings : []).map((w) => ({ message: w }));
  const errs = (data.lint && data.lint.errors ? data.lint.errors : []).map((e) => ({ message: e }));
  showMessages(errs, warns, `已载入病例 ${caseId};修改后点击"保存病例"(需勾选覆盖)。`);
  switchTab("form");
}

/* ---------- 校验 / 保存 / 预览 ---------- */
async function validateDraft() {
  const { data } = await api("POST", "/api/validate", collectDraft());
  if (!data) { showMessages([{ message: "服务器无响应" }], []); return; }
  showMessages(data.errors, data.warnings, data.ok ? "校验通过,可以保存。" : null);
}

async function saveCase() {
  const overwrite = $("f-overwrite").checked;
  const { status, data } = await api("POST", "/api/cases", { case: collectDraft(), overwrite });
  if (status === 409) {
    showMessages([{ message: (data && data.detail) || "病例已存在" }], []);
    return;
  }
  if (status === 422) {
    const det = (data && data.detail) || {};
    showMessages(det.errors || [{ message: "校验未通过" }], det.warnings || []);
    return;
  }
  if (status !== 200 || !data) {
    showMessages([{ message: "保存失败:" + ((data && data.detail) || status) }], []);
    return;
  }
  showMessages([], data.warnings, `已保存到 ${data.path}。`);
  refreshList();
}

let previews = null;
let currentDiff = "easy";
async function makePreview() {
  const { status, data } = await api("POST", "/api/preview", collectDraft());
  if (status === 422) {
    const det = (data && data.detail) || {};
    showMessages(det.errors || [], det.warnings || []);
    $("preview-text").textContent = "(表单未通过校验,请先修正错误)";
    return;
  }
  if (status !== 200 || !data) { $("preview-text").textContent = "(预览失败)"; return; }
  previews = data.previews;
  renderPreview(currentDiff);
  showMessages([], [], "预览已生成(确定性编译,未调用大模型)。");
}
function renderPreview(diff) {
  currentDiff = diff;
  document.querySelectorAll(".ptab").forEach((b) => b.classList.toggle("active", b.dataset.diff === diff));
  $("preview-text").textContent = previews && previews[diff] ? previews[diff].prompt : "(尚未生成预览)";
}

/* ---------- 标签页 ---------- */
function switchTab(which) {
  $("tab-form").classList.toggle("active", which === "form");
  $("tab-preview").classList.toggle("active", which === "preview");
  $("case-form").classList.toggle("hidden", which !== "form");
  $("preview-panel").classList.toggle("hidden", which !== "preview");
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $("btn-refresh").addEventListener("click", refreshList);
  $("btn-new").addEventListener("click", newCase);
  $("btn-validate").addEventListener("click", validateDraft);
  $("btn-save").addEventListener("click", saveCase);
  $("btn-preview").addEventListener("click", makePreview);
  $("tab-form").addEventListener("click", () => switchTab("form"));
  $("tab-preview").addEventListener("click", () => switchTab("preview"));
  document.querySelectorAll("button.add").forEach((b) =>
    b.addEventListener("click", () => addRow(b.dataset.add)));
  document.querySelectorAll(".ptab").forEach((b) =>
    b.addEventListener("click", () => renderPreview(b.dataset.diff)));
  setRows("history_checklist", [{}]);
  refreshList();
});
