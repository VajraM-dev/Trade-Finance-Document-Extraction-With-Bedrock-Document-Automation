export function renderPaginator(container, { page, size, total, onPageChange }) {
  container.innerHTML = "";
  const totalPages = Math.max(1, Math.ceil(total / size));
  const wrap = document.createElement("div");
  wrap.className = "flex items-center justify-between text-sm text-slate-600 mt-4";
  wrap.innerHTML = `
    <div>Showing ${total === 0 ? 0 : (page - 1) * size + 1}–${Math.min(page * size, total)} of ${total}</div>
    <div class="flex gap-2">
      <button data-act="prev" class="px-3 py-1 border rounded ${page <= 1 ? "opacity-40 pointer-events-none" : ""}">Prev</button>
      <span class="px-2">${page} / ${totalPages}</span>
      <button data-act="next" class="px-3 py-1 border rounded ${page >= totalPages ? "opacity-40 pointer-events-none" : ""}">Next</button>
    </div>
  `;
  container.appendChild(wrap);
  wrap.querySelector('[data-act="prev"]').addEventListener("click", () => onPageChange(page - 1));
  wrap.querySelector('[data-act="next"]').addEventListener("click", () => onPageChange(page + 1));
}
