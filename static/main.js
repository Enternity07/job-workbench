"use strict";
const $ = id => document.getElementById(id);
let sessionToken = "", report = null, records = [], toastTimer;
const statuses = ["待投递", "已投递", "面试中", "已录用", "已结束"];
function node(tag, text, cls) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; }
function toast(message) { $("toast").textContent = message; $("toast").hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $("toast").hidden = true, 4500); }
async function api(path, method = "GET", data) {
  const response = await fetch(path, { method, headers: {"Content-Type": "application/json", "X-Local-Token": sessionToken}, body: data === undefined ? undefined : JSON.stringify(data) });
  const result = await response.json(); if (!response.ok) throw new Error(result.error || "请求失败"); return result;
}
function page(name) {
  for (const key of ["match", "track", "practice"]) $("page-" + key).hidden = key !== name;
  document.querySelectorAll(".nav").forEach(el => el.classList.toggle("active", el.dataset.page === name));
  $("crumb").textContent = {match:"岗位对照", track:"投递记录", practice:"面试练习"}[name];
  history.replaceState(null, "", "#" + name);
  if (name === "track") loadRecords(); if (name === "practice") renderQuestions();
}
document.querySelectorAll(".nav").forEach(el => el.addEventListener("click", () => page(el.dataset.page)));
document.querySelector(".brand").addEventListener("click", event => { event.preventDefault(); page("match"); });
function resetReport() { report = null; $("result-empty").hidden = false; $("result-content").hidden = true; $("export-report").disabled = true; }
for (const id of ["jd", "resume"]) $(id).addEventListener("input", resetReport);
$("sample").addEventListener("click", () => {
  if (($("jd").value || $("resume").value) && !confirm("这会替换输入框中的文本，是否载入虚构示例？")) return;
  $("jd").value = "【虚构示例岗位】AI 应用开发实习生\n需要 Python、HTML、CSS、JavaScript 基础；了解 SQLite 和 API。\n使用过 Codex 或 Claude Code，能把项目跑起来；有 Git 和自动化测试经验加分。";
  $("resume").value = "【虚构示例简历，并非求职者真实经历】\n使用 Codex 辅助搭建 Python 小工具，界面采用 HTML、CSS、JavaScript。\n使用 SQLite 保存记录，完成本地部署。正在学习接口设计和单元测试。";
  resetReport();
  toast("已载入虚构示例，请点击开始对照");
});
$("analyze-form").addEventListener("submit", async event => {
  event.preventDefault(); $("analyze").disabled = true; $("analyze").textContent = "正在对照…";
  try { report = await api("/api/analyze", "POST", {jd:$("jd").value, resume:$("resume").value}); renderReport(); toast("对照完成，可展开查看原文证据"); }
  catch (error) { toast(error.message); }
  finally { $("analyze").disabled = false; $("analyze").textContent = "开始对照 →"; }
});
function renderReport() {
  $("result-empty").hidden = true; $("result-content").hidden = false; $("export-report").disabled = false;
  $("score").textContent = report.coverage === null ? "—" : report.coverage; $("score-unit").hidden = report.coverage === null;
  $("score-note").textContent = report.required ? `岗位中识别到 ${report.required} 项关键词，简历提及其中 ${report.covered.length} 项。` : "未识别到内置词表中的关键词，请人工核对岗位原文。";
  $("meter-fill").style.width = (report.coverage || 0) + "%";
  $("counts").textContent = `已提及 ${report.covered.length} / 待补证据 ${report.missing.length}`;
  $("evidence").replaceChildren();
  for (const [items, covered] of [[report.missing, false], [report.covered, true]]) for (const item of items) {
    const details = node("details", undefined, "evidence-row"), summary = node("summary"), line = node("span", undefined, "evidence-title");
    line.append(node("span", item.skill), node("span", covered ? "简历已提及" : "待补证据", "badge" + (covered ? "" : " missing"))); summary.append(line); details.append(summary);
    for (const [label, evidence] of [["岗位原文", item.job_evidence], ["简历原文", item.resume_evidence]]) if (evidence) {
      const source = node("div", undefined, "source"); source.append(node("strong", label + "："), document.createTextNode(evidence.join("；"))); details.append(source);
    }
    if (!covered) details.append(node("p", "若有相关经历，补上真实项目或操作；还不会就先练习，别只堆关键词。", "source"));
    $("evidence").append(details);
  }
  $("notice").textContent = report.notice;
}
function download(name, text, type) { const url = URL.createObjectURL(new Blob([text], {type})); const a = node("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
$("export-report").addEventListener("click", () => {
  if (!report) return;
  const lines = ["# 岗位文字对照报告", "", `文字覆盖率：${report.coverage === null ? "未识别关键词" : report.coverage + "%"}`, "", report.notice, "", "## 待补证据", ...report.missing.map(x => `- ${x.skill}：${x.job_evidence.join("；")}`), "", "## 简历已提及", ...report.covered.map(x => `- ${x.skill}\n  岗位：${x.job_evidence.join("；")}\n  简历：${x.resume_evidence.join("；")}`), "", "## 面试练习", ...report.questions.map(x => `- ${x.question}\n  提示：${x.guide}`)];
  download("岗位对照报告.md", lines.join("\n"), "text/markdown;charset=utf-8");
});
$("to-practice").addEventListener("click", () => page("practice")); $("back-match").addEventListener("click", () => page("match"));
function renderQuestions() {
  $("questions").replaceChildren();
  if (!report) { $("questions").append(node("div", "先完成一次岗位对照，这里就会出现对应的练习题。", "practice-empty")); return; }
  report.questions.forEach((question, index) => { const card = node("article", undefined, "question-card"), top = node("div", undefined, "question-top"), detail = node("details"); top.append(node("span", String(index + 1).padStart(2,"0") + " / " + question.skill), node("span", question.priority)); detail.append(node("summary", "展开回答提示"), node("p", question.guide)); card.append(top, node("h3", question.question), detail); $("questions").append(card); });
}
async function loadRecords() { try { records = (await api("/api/applications")).items; renderRecords(); } catch (error) { toast(error.message); } }
function localDate() { const now = new Date(); return [now.getFullYear(), String(now.getMonth()+1).padStart(2,"0"), String(now.getDate()).padStart(2,"0")].join("-"); }
function renderRecords() {
  const pending = records.filter(x => !["已录用","已结束"].includes(x.status) && x.next_date && x.next_date <= localDate()).length;
  $("stats").replaceChildren();
  for (const [label, value] of [["全部记录", records.length], ["已投递 / 面试中", records.filter(x => ["已投递","面试中"].includes(x.status)).length], ["已录用", records.filter(x => x.status === "已录用").length], ["今日及逾期待跟进", pending]]) { const stat = node("div", undefined, "stat"); stat.append(node("div", label, "stat-label"), node("div", String(value).padStart(2,"0"), "stat-number")); $("stats").append(stat); }
  const query = $("search").value.trim().toLowerCase(), status = $("status-filter").value;
  const visible = records.filter(x => (!status || x.status === status) && `${x.company} ${x.role} ${x.note}`.toLowerCase().includes(query));
  $("record-count").textContent = `${visible.length} 条记录`; $("records").replaceChildren(); $("records-empty").hidden = visible.length > 0;
  $("records-empty").querySelector("h3").textContent = records.length ? "没有找到符合条件的记录。" : "第一份投递，从这里记起。";
  $("records-empty").querySelector("p").textContent = records.length ? "试试调整搜索内容或状态筛选。" : "点击“新增投递”，记录公司、岗位与下一步行动。";
  for (const item of visible) {
    const row = node("tr"), company = node("td"), state = node("td"), ops = node("td"), actions = node("div", undefined, "row-actions");
    company.append(node("strong", item.company), node("small", item.role)); state.append(node("span", item.status, "badge" + (item.status === "待投递" ? " missing" : "")));
    const edit = node("button", "编辑"), remove = node("button", "删除", "delete"); edit.setAttribute("aria-label", `编辑 ${item.company}`); remove.setAttribute("aria-label", `删除 ${item.company}`);
    edit.addEventListener("click", () => openRecord(item)); remove.addEventListener("click", async () => { if (!confirm(`删除“${item.company}”的这条记录？`)) return; try { await api(`/api/applications/${item.id}`, "DELETE"); await loadRecords(); toast("记录已删除"); } catch(error) { toast(error.message); } });
    actions.append(edit, remove); ops.append(actions); row.append(company, state, node("td", item.next_date || "未设置"), node("td", item.note || "—"), ops); $("records").append(row);
  }
}
$("search").addEventListener("input", renderRecords); $("status-filter").addEventListener("change", renderRecords);
function openRecord(item) { $("record-form").reset(); $("record-id").value = item?.id || ""; $("dialog-title").textContent = item ? "编辑投递" : "新增投递"; for (const [field, id] of [["company","company"],["role","role"],["status","status"],["next_date","next-date"],["note","note"]]) $(id).value = item?.[field] || (field === "status" ? statuses[0] : ""); $("record-dialog").showModal(); }
$("new-record").addEventListener("click", () => openRecord()); for (const id of ["close-dialog","cancel-dialog"]) $(id).addEventListener("click", () => $("record-dialog").close());
$("record-form").addEventListener("submit", async event => { event.preventDefault(); const id = $("record-id").value; $("save-record").disabled = true; try { await api("/api/applications" + (id ? "/" + id : ""), id ? "PUT" : "POST", {company:$("company").value, role:$("role").value, status:$("status").value, next_date:$("next-date").value, note:$("note").value}); $("record-dialog").close(); await loadRecords(); toast("记录已保存到本机"); } catch(error) { toast(error.message); } finally { $("save-record").disabled = false; } });
$("export-records").addEventListener("click", () => { download("投递记录.json", JSON.stringify({version:1, exported_at:new Date().toISOString(), items:records}, null, 2), "application/json;charset=utf-8"); toast("已导出全部记录"); });
(async () => { try { sessionToken = (await api("/api/session")).token; const name = location.hash.slice(1); page(["match","track","practice"].includes(name) ? name : "match"); } catch(error) { toast("连接失败，请确认 Python 服务正在运行。"); } })();
