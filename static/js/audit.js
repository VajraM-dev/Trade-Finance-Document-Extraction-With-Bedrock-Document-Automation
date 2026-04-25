import { apiFetch } from "/js/api.js";
import { fmtDate } from "/js/format.js";
import { renderPaginator } from "/js/pagination.js";

export async function renderAudit({ tableEl, paginatorEl, filters }) {
  let page = Number(filters.page || 1);
  const size = 20;

  async function load(p) {
    page = p;
    const params = new URLSearchParams({ ...filters, page: String(page), size: String(size) });
    const data = await apiFetch(`/api/v1/admin/audit-log?${params}`);
    tableEl.innerHTML = `
      <table class="w-full text-sm">
        <thead class="bg-slate-100 text-xs uppercase text-slate-600">
          <tr>
            <th class="p-2 text-left">When</th>
            <th class="p-2 text-left">Actor</th>
            <th class="p-2 text-left">Action</th>
            <th class="p-2 text-left">Target</th>
            <th class="p-2 text-left">IP</th>
            <th class="p-2 text-left">Metadata</th>
          </tr>
        </thead>
        <tbody>
          ${data.items.map(e => `
            <tr class="border-t">
              <td class="p-2">${fmtDate(e.created_at)}</td>
              <td class="p-2 font-mono text-xs">${e.actor_user_id || "—"}</td>
              <td class="p-2">${e.action}</td>
              <td class="p-2 font-mono text-xs">${e.target_user_id || "—"}</td>
              <td class="p-2">${e.ip || "—"}</td>
              <td class="p-2 text-xs"><code>${escapeJson(e.metadata)}</code></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
    renderPaginator(paginatorEl, { page, size, total: data.total, onPageChange: load });
  }

  await load(page);
}

function escapeJson(o) {
  return JSON.stringify(o).replace(/[<>&]/g, m => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[m]));
}
