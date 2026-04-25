import { apiFetch } from "/js/api.js";
import { fmtBytes, fmtCurrency, fmtDate } from "/js/format.js";
import { renderPaginator } from "/js/pagination.js";

const STATUS_BADGE = {
  queued: "bg-slate-200 text-slate-800",
  processing: "bg-amber-200 text-amber-800",
  success: "bg-emerald-200 text-emerald-800",
  failed: "bg-red-200 text-red-800",
};

export async function renderJobList({ tableEl, paginatorEl, baseUrl = "/api/v1/jobs", filters = {}, detailUrl = (id) => `/customer/job.html?id=${id}` }) {
  let page = Number(filters.page || 1);
  const size = 20;

  async function load(p) {
    page = p;
    const params = new URLSearchParams({ ...filters, page: String(page), size: String(size) });
    const data = await apiFetch(`${baseUrl}?${params}`);
    tableEl.innerHTML = "";
    const head = `
      <thead class="bg-slate-100 text-slate-600 text-left text-xs uppercase">
        <tr>
          <th class="p-2">Status</th>
          <th class="p-2">Doc Type</th>
          <th class="p-2">File</th>
          <th class="p-2">Size</th>
          <th class="p-2">Pages</th>
          <th class="p-2">Cost</th>
          <th class="p-2">Created</th>
        </tr>
      </thead>`;
    const rows = data.items.map(j => `
      <tr class="border-t hover:bg-slate-50 cursor-pointer" data-id="${j.id}">
        <td class="p-2"><span class="px-2 py-0.5 rounded text-xs ${STATUS_BADGE[j.status] || ""}">${j.status}</span></td>
        <td class="p-2">${j.matched_blueprint || "—"}</td>
        <td class="p-2 truncate max-w-xs">${j.original_filename}</td>
        <td class="p-2">${fmtBytes(j.file_size_bytes)}</td>
        <td class="p-2">${j.pages_processed ?? "—"}</td>
        <td class="p-2">${fmtCurrency(j.cost_usd)}</td>
        <td class="p-2">${fmtDate(j.created_at)}</td>
      </tr>`).join("");
    tableEl.innerHTML = `<table class="w-full text-sm">${head}<tbody>${rows}</tbody></table>`;
    tableEl.querySelectorAll("tr[data-id]").forEach(tr => {
      tr.addEventListener("click", () => location.href = detailUrl(tr.dataset.id));
    });
    renderPaginator(paginatorEl, { page, size, total: data.total, onPageChange: load });
  }

  await load(page);
  return { reload: () => load(page) };
}
