import { apiFetch } from "/js/api.js";
import { fmtCurrency, fmtDate, fmtDuration, fmtPercent } from "/js/format.js";

const POLL_INTERVAL_MS = 3000;

export async function renderJobDetail({ headerEl, pdfEl, fieldsEl, rawEl, jobId }) {
  let stop = false;

  async function tick() {
    const j = await apiFetch(`/api/v1/jobs/${jobId}`);
    headerEl.innerHTML = `
      <div class="flex flex-wrap items-baseline gap-3">
        <h2 class="text-lg font-semibold truncate">${j.original_filename}</h2>
        <span class="px-2 py-0.5 rounded text-xs bg-slate-200">${j.status}</span>
        <span class="text-sm text-slate-500">${j.matched_blueprint || ""}</span>
        <span class="text-sm text-slate-500">${j.pages_processed ?? "?"} pages</span>
        <span class="text-sm text-slate-500">${fmtCurrency(j.cost_usd)}</span>
        <span class="text-sm text-slate-500">${fmtDate(j.created_at)}</span>
      </div>
    `;

    if (j.status === "queued" || j.status === "processing") {
      fieldsEl.innerHTML = `<p class="text-slate-500 text-sm">Processing… polling every ${POLL_INTERVAL_MS / 1000}s.</p>`;
      if (!stop) setTimeout(tick, POLL_INTERVAL_MS);
      return;
    }
    if (j.status === "failed") {
      fieldsEl.innerHTML = `<p class="text-red-600 text-sm">Failed: ${j.error_code || "?"} — ${j.error_message || ""}</p>`;
      return;
    }

    if (!pdfEl.querySelector("iframe")) {
      const preview = await apiFetch(`/api/v1/jobs/${jobId}/preview`);
      pdfEl.innerHTML = `<iframe src="${preview.url}" class="w-full h-[80vh] border rounded"></iframe>`;
    }

    const fields = j.extracted_fields?.fields || {};
    const conf = j.extracted_fields?.confidences || {};
    fieldsEl.innerHTML = renderFields(fields, conf);
    rawEl.innerHTML = `<pre class="text-xs bg-slate-900 text-slate-100 p-3 rounded overflow-auto max-h-[60vh]">${
      escapeHtml(JSON.stringify(j, null, 2))
    }</pre>`;
  }

  await tick();
  return { stop: () => { stop = true; } };
}

function renderFields(fields, confidences) {
  const rows = [];
  for (const [k, v] of Object.entries(fields)) {
    if (Array.isArray(v) && v.length && typeof v[0] === "object") {
      rows.push(`<details class="border rounded mt-2"><summary class="cursor-pointer px-2 py-1 bg-slate-100">${k} (${v.length})</summary>${renderListTable(v, confidences[k])}</details>`);
    } else if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      rows.push(`<details class="border rounded mt-2"><summary class="cursor-pointer px-2 py-1 bg-slate-100">${k}</summary><div class="p-2">${renderObject(v, confidences[k])}</div></details>`);
    } else {
      const c = typeof confidences[k] === "number" ? `<span class="text-xs text-slate-500 ml-2">${fmtPercent(confidences[k])}</span>` : "";
      const display = Array.isArray(v) ? v.join(", ") : String(v);
      rows.push(`<div class="grid grid-cols-3 gap-2 py-1 text-sm border-b"><div class="text-slate-500">${k}</div><div class="col-span-2 break-all">${escapeHtml(display)}${c}</div></div>`);
    }
  }
  return rows.join("");
}

function renderObject(obj, conf) {
  const confMap = (conf && typeof conf === "object" && !Array.isArray(conf)) ? conf : {};
  const rows = [];
  for (const [k, v] of Object.entries(obj)) {
    let display;
    if (v === null || v === undefined) {
      display = "—";
    } else if (typeof v === "object") {
      display = `<pre class="text-xs bg-slate-50 p-1 rounded overflow-auto">${escapeHtml(JSON.stringify(v, null, 2))}</pre>`;
    } else {
      display = escapeHtml(String(v));
    }
    const c = typeof confMap[k] === "number" ? `<span class="text-xs text-slate-500 ml-2">${fmtPercent(confMap[k])}</span>` : "";
    rows.push(`<div class="grid grid-cols-3 gap-2 py-1 text-sm border-b"><div class="text-slate-500">${k}</div><div class="col-span-2 break-all">${display}${c}</div></div>`);
  }
  return rows.join("");
}

function renderListTable(rows, confArr) {
  const cols = Object.keys(rows[0]);
  const confs = Array.isArray(confArr) ? confArr : [];
  const head = `<tr class="bg-slate-50">${cols.map(c => `<th class="px-2 py-1 text-left text-xs">${c}</th>`).join("")}</tr>`;
  const body = rows.map((r, i) => {
    const rowConf = confs[i] && typeof confs[i] === "object" ? confs[i] : {};
    return `<tr class="border-t">${cols.map(c => {
      const cell = escapeHtml(String(r[c] ?? ""));
      const cv = typeof rowConf[c] === "number" ? `<div class="text-[10px] text-slate-400">${fmtPercent(rowConf[c])}</div>` : "";
      return `<td class="px-2 py-1 text-xs align-top">${cell}${cv}</td>`;
    }).join("")}</tr>`;
  }).join("");
  return `<table class="w-full">${head}${body}</table>`;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (m) => ({"&": "&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
}
