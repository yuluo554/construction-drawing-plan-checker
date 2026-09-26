/* 前端逻辑：上传→校核→结果面板→PDF bbox 证据定位 */
const { createApp, reactive } = Vue;

pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdf.worker.min.js";

const state = reactive({
  version: "v0.5 阶段5",
  drawing: null, plan: null,
  uploading: "", checking: false, progressText: "",
  rag: true, report: null, reportId: "",
  pdfShow: false, pdfPage: 1, pdfRects: [],
  _pdfDoc: null, _drawingCard: null,
});

async function doUpload(e, kind) {
  const file = e.target.files[0];
  if (!file) return;
  state.uploading = kind;
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    state[kind] = data;
    state._drawingCard = null;
    if (kind === "drawing" && data.pdf) preloadPdf(data.id);
  } catch (err) {
    alert("上传失败：" + err.message);
  } finally {
    state.uploading = "";
    e.target.value = "";
  }
}

async function preloadPdf(id) {
  try {
    const buf = await fetch(`/api/source/${id}`).then(r => r.arrayBuffer());
    state._pdfDoc = await pdfjsLib.getDocument({ data: buf }).promise;
  } catch (e) { /* 非致命 */ }
}

async function doCheck() {
  state.checking = true;
  state.progressText = "规则引擎三通道校核中（一致性/危大/存在性）…";
  try {
    const r = await fetch("/api/check", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drawing_id: state.drawing.id, plan_id: state.plan.id, rag: state.rag }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    state.report = data.report;
    state.reportId = data.report_id;
  } catch (err) {
    alert("校核失败：" + err.message);
  } finally {
    state.checking = false;
  }
}

function evRaw(f) {
  const ev = f["证据"] || {};
  const parts = [];
  if (ev["图纸"]) parts.push("图纸原文：" + ev["图纸"]);
  if (ev["方案"]) parts.push("方案原文：" + ev["方案"]);
  return parts.join(" ｜ ");
}

/* 从图纸参数卡按证据原文反查 bbox */
function findBbox(f) {
  const ev = f["证据"] || {};
  const raw = ev["图纸"] || f["图纸"] || "";
  if (!raw || !state._drawingCard) return null;
  const norm = s => (s || "").replace(/\s+/g, "");
  for (const p of state._drawingCard.parameters) {
    const e = p.evidence || {};
    if (e.bbox && e.raw && (norm(raw).includes(norm(e.raw).slice(0, 18)) || norm(e.raw).includes(norm(raw).slice(0, 18)))) {
      f._bbox = e.bbox; f._page = e.page || 1;
      return e.bbox;
    }
  }
  return null;
}

function locatable(f) {
  return !!(state.drawing && state.drawing.pdf && state._pdfDoc);
}

async function locate(f) {
  if (!state._drawingCard) {
    state._drawingCard = await fetch(`/api/card/${state.drawing.id}`).then(r => r.json());
  }
  const bbox = f._bbox || findBbox(f);
  if (!bbox) { alert("该项证据无坐标信息，无法在 PDF 中定位"); return; }
  const page = Math.max(f._page || 1, 1);
  state.pdfShow = true; state.pdfPage = page; state.pdfRects = [];
  const pdfPage = await state._pdfDoc.getPage(page);
  const scale = 1.6;
  const viewport = pdfPage.getViewport({ scale });
  const canvas = document.getElementById("pdf-canvas");
  canvas.width = viewport.width; canvas.height = viewport.height;
  await pdfPage.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  state.pdfRects.push({
    left: bbox[0] * scale, top: bbox[1] * scale,
    width: (bbox[2] - bbox[0]) * scale, height: (bbox[3] - bbox[1]) * scale,
  });
  setTimeout(() => state.pdfShow && document.querySelector(".pdf-view")?.scrollIntoView({ behavior: "smooth" }), 60);
}

function rectStyle(r) {
  return { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" };
}
function badgeClass(level) {
  return { "致命": "fatal", "一般": "warn", "提示": "info" }[level] || "info";
}
function verdictClass() {
  const s = state.report && state.report.summary;
  if (!s) return "";
  return s["致命"] > 0 ? "fatal" : (s["一般"] > 0 ? "warn" : "info");
}

createApp({
  setup() { return Object.assign(state, { doUpload, doCheck, locate, rectStyle, badgeClass, verdictClass, evRaw, locatable }); },
}).mount("#app");
