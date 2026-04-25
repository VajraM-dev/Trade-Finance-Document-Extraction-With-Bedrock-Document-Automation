export function readQuery() {
  return Object.fromEntries(new URLSearchParams(location.search).entries());
}

export function writeQuery(obj) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, v);
  }
  const next = `${location.pathname}?${sp.toString()}`;
  history.replaceState(null, "", next);
}

export function bindFilterForm(form, onChange) {
  form.addEventListener("change", () => {
    const data = Object.fromEntries(new FormData(form));
    onChange(data);
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    onChange(Object.fromEntries(new FormData(form)));
  });
}
