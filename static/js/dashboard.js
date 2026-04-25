import { apiFetch } from "/js/api.js";
import { fmtCurrency, fmtPercent } from "/js/format.js";

export async function renderDashboard({ statsEl, byTypeChartEl, recentChartEl }) {
  const data = await apiFetch("/api/v1/admin/dashboard");

  statsEl.innerHTML = ["today", "last_7d", "last_30d"].map((k) => {
    const b = data[k];
    const label = { today: "Today", last_7d: "Last 7 days", last_30d: "Last 30 days" }[k];
    return `
      <div class="bg-white p-4 rounded-lg shadow-sm">
        <div class="text-xs text-slate-500 uppercase">${label}</div>
        <div class="mt-1 text-2xl font-semibold">${b.jobs}</div>
        <div class="text-xs text-slate-500">jobs · ${b.pages} pages · ${fmtCurrency(b.cost_usd)} · success ${fmtPercent(b.success_rate)}</div>
      </div>
    `;
  }).join("");

  const labels = Object.keys(data.by_doc_type);
  const counts = Object.values(data.by_doc_type);
  // eslint-disable-next-line no-undef
  new Chart(byTypeChartEl, {
    type: "pie",
    data: { labels, datasets: [{ data: counts, backgroundColor: ["#0f766e", "#1d4ed8", "#7c3aed", "#94a3b8"] }] },
    options: { plugins: { legend: { position: "bottom" } } },
  });

  const recent = await apiFetch("/api/v1/admin/jobs?size=100");
  const buckets = {};
  for (const j of recent.items) {
    const day = (j.created_at || "").slice(0, 10);
    buckets[day] = (buckets[day] || 0) + 1;
  }
  const days = Object.keys(buckets).sort();
  // eslint-disable-next-line no-undef
  new Chart(recentChartEl, {
    type: "line",
    data: { labels: days, datasets: [{ data: days.map(d => buckets[d]), borderColor: "#1e293b", tension: 0.3 }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}
