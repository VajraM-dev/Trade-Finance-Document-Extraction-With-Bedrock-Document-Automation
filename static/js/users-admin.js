import { apiFetch } from "/js/api.js";
import { fmtDate } from "/js/format.js";
import { renderPaginator } from "/js/pagination.js";

export async function renderUsers({ tableEl, paginatorEl, filters }) {
  let page = Number(filters.page || 1);
  const size = 20;

  async function load(p) {
    page = p;
    const params = new URLSearchParams({ ...filters, page: String(page), size: String(size) });
    const data = await apiFetch(`/api/v1/admin/users?${params}`);
    tableEl.innerHTML = `
      <table class="w-full text-sm">
        <thead class="bg-slate-100 text-xs uppercase text-slate-600">
          <tr>
            <th class="p-2 text-left">Username</th>
            <th class="p-2 text-left">Email</th>
            <th class="p-2 text-left">Role</th>
            <th class="p-2 text-left">Status</th>
            <th class="p-2 text-left">Created</th>
            <th class="p-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${data.items.map(u => `
            <tr class="border-t" data-id="${u.id}">
              <td class="p-2"><a href="/admin/user.html?id=${u.id}" class="text-blue-600 hover:underline">${u.username}</a></td>
              <td class="p-2">${u.email}</td>
              <td class="p-2">${u.role}</td>
              <td class="p-2">${u.status}</td>
              <td class="p-2">${fmtDate(u.created_at)}</td>
              <td class="p-2 text-right space-x-2">
                <button data-act="suspend" class="text-amber-700 hover:underline">${u.status === "active" ? "Suspend" : "Unsuspend"}</button>
                <button data-act="rotate" class="text-blue-700 hover:underline">Rotate key</button>
                <button data-act="delete" class="text-red-700 hover:underline">Delete</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    tableEl.querySelectorAll("tr[data-id]").forEach((tr) => {
      const id = tr.dataset.id;
      tr.querySelector('[data-act="suspend"]').addEventListener("click", async () => {
        const next = tr.querySelector('[data-act="suspend"]').textContent === "Suspend" ? "suspended" : "active";
        await apiFetch(`/api/v1/admin/users/${id}`, { method: "PATCH", json: { status: next } });
        load(page);
      });
      tr.querySelector('[data-act="rotate"]').addEventListener("click", async () => {
        const fresh = await apiFetch(`/api/v1/admin/users/${id}/api-key/rotate`, { method: "POST" });
        prompt("Customer's new API key (shown once):", fresh.api_key);
      });
      tr.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        if (!confirm("Delete this user?")) return;
        await apiFetch(`/api/v1/admin/users/${id}`, { method: "DELETE" });
        load(page);
      });
    });

    renderPaginator(paginatorEl, { page, size, total: data.total, onPageChange: load });
  }

  await load(page);
  return { reload: () => load(page) };
}
