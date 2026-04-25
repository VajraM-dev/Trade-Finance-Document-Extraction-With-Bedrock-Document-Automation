export function fmtCurrency(n) {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(Number(n));
}

export function fmtBytes(n) {
  if (n === null || n === undefined) return "—";
  const u = ["B", "KB", "MB", "GB"];
  let v = Number(n);
  let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i ? 1 : 0)} ${u[i]}`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function fmtDuration(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function fmtPercent(n) {
  if (n === null || n === undefined) return "—";
  return `${(Number(n) * 100).toFixed(0)}%`;
}
