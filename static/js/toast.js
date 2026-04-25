let container;

function ensureContainer() {
  if (container) return container;
  container = document.createElement("div");
  container.className = "toast";
  document.body.appendChild(container);
  return container;
}

export function showToast(message, kind = "info", ttl = 5000) {
  const el = document.createElement("div");
  const palette = {
    info: "bg-slate-800 text-white",
    error: "bg-red-600 text-white",
    success: "bg-emerald-600 text-white",
  }[kind];
  el.className = `${palette} rounded-md shadow px-4 py-2 text-sm`;
  el.textContent = message;
  ensureContainer().appendChild(el);
  setTimeout(() => el.remove(), ttl);
}
