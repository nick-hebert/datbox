/* Shared dashboard shell: layout, filters, KPI cards, table, aggregation.
 * Library-specific code lives entirely in window.DAT.backend (mount/update). */
(function () {
  const { spec, data, backend } = window.DAT;
  const $ = (sel, root = document) => root.querySelector(sel);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) k === "class" ? (n.className = v) : k.startsWith("on") ? n.addEventListener(k.slice(2), v) : n.setAttribute(k, v);
    for (const k of kids) n.append(k);
    return n;
  };

  // ---- formatting ---------------------------------------------------------
  const fmt = {
    currency: new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }),
    integer: new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }),
    compact: new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }),
  };
  const format = (v, kind) => (v == null ? "" : kind === "currency" ? fmt.currency.format(v) : kind === "integer" ? fmt.integer.format(v) : typeof v === "number" ? fmt.integer.format(v) : String(v));
  const formatAxis = (v, kind) => (kind === "currency" ? "$" + fmt.compact.format(v) : fmt.compact.format(v));

  // ---- theme (read CSS custom properties so charts match the page) --------
  const theme = () => {
    const cs = getComputedStyle(document.documentElement);
    const g = (k) => cs.getPropertyValue(k).trim();
    return {
      dark: matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light",
      surface: g("--surface"), ink: g("--ink"), ink2: g("--ink-2"), muted: g("--muted"), grid: g("--grid"), axis: g("--axis"),
      series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => g("--s" + i)),
      font: 'system-ui, -apple-system, "Segoe UI", sans-serif',
    };
  };

  // ---- aggregation --------------------------------------------------------
  const AGG = {
    sum: (xs) => xs.reduce((a, b) => a + b, 0),
    count: (xs) => xs.length,
    mean: (xs) => (xs.length ? AGG.sum(xs) / xs.length : null),
    min: (xs) => Math.min(...xs), max: (xs) => Math.max(...xs),
  };
  const measure = (rows, m) => AGG[m.agg](rows.map((r) => r[m.field]));
  const groupBy = (rows, f) => { const g = new Map(); for (const r of rows) { const k = r[f]; (g.get(k) || g.set(k, []).get(k)).push(r); } return g; };
  const domain = (f) => [...new Set(data.map((r) => r[f]))].sort();

  // Series identity is fixed to the full-data domain so a filter never repaints survivors.
  const colorIndex = {};
  for (const c of spec.components) for (const f of [c.series?.field, c.category?.field].filter(Boolean)) colorIndex[f] = colorIndex[f] || Object.fromEntries(domain(f).map((v, i) => [v, i]));

  function aggregate(c, rows) {
    if (c.type === "kpi") return { value: measure(rows, c.measure) };
    if (c.type === "bar") {
      let pairs = [...groupBy(rows, c.x.field)].map(([k, g]) => [k, measure(g, c.y)]);
      if (c.sort === "desc") pairs.sort((a, b) => b[1] - a[1]); else if (c.sort === "asc") pairs.sort((a, b) => a[1] - b[1]); else pairs.sort((a, b) => (a[0] < b[0] ? -1 : 1));
      return { x: pairs.map((p) => p[0]), y: pairs.map((p) => p[1]) };
    }
    if (c.type === "line") {
      const xs = domain(c.x.field);                       // full x domain so gaps show as gaps
      const names = c.series ? domain(c.series.field) : [c.y.field];
      const series = names.map((name) => {
        const sub = c.series ? rows.filter((r) => r[c.series.field] === name) : rows;
        const byX = groupBy(sub, c.x.field);
        return { name, color: c.series ? colorIndex[c.series.field][name] : 0, values: xs.map((x) => (byX.has(x) ? measure(byX.get(x), c.y) : null)) };
      });
      return { x: xs, series };
    }
    if (c.type === "pie") {
      const names = domain(c.category.field);
      const byK = groupBy(rows, c.category.field);
      return { labels: names, values: names.map((n) => (byK.has(n) ? measure(byK.get(n), c.value) : 0)), colors: names.map((n) => colorIndex[c.category.field][n]) };
    }
    if (c.type === "table") return { rows };
  }

  // ---- state --------------------------------------------------------------
  const state = { filters: {}, sort: spec.components.find((c) => c.type === "table")?.sort || null, page: 0, search: "" };
  const filtered = () => data.filter((r) => Object.entries(state.filters).every(([f, v]) => v == null || r[f] === v));
  const setFilter = (field, value) => { state.filters[field] = state.filters[field] === value ? null : value; state.page = 0; render(); };

  // ---- build DOM ----------------------------------------------------------
  const page = el("div", { class: "page" });
  const head = el("header", {}, el("h1", {}, spec.title), el("span", { class: "sub" }, spec.subtitle || ""), el("span", { class: "badge" }, `${backend.name} ${backend.version}`));
  const filterRow = el("div", { class: "filters" });
  const selects = {};
  for (const f of spec.filters || []) {
    const s = el("select", { onchange: (e) => { state.filters[f.field] = e.target.value || null; state.page = 0; render(); } }, el("option", { value: "" }, "All"));
    for (const v of domain(f.field)) s.append(el("option", { value: v }, v));
    selects[f.field] = s;
    filterRow.append(el("label", {}, f.label || f.field.replace(/_/g, " "), s));
  }
  filterRow.append(el("button", { onclick: () => { state.filters = {}; state.page = 0; render(); } }, "Reset"), el("span", { class: "hint" }, "Click a bar or slice to filter · hover for values"));
  const grid = el("div", { class: "grid" });
  const cards = {};
  for (const c of spec.components) {
    const card = el("div", { class: `card ${c.type}`, style: `grid-column: span ${c.grid?.w || 12}; ${c.grid?.h ? "height:" + c.grid.h + "px" : ""}` }, el("h2", {}, c.title));
    if (c.type === "kpi") card.append(el("div", { class: "value" }), el("div", { class: "meta" }));
    else if (c.type === "table") card.append(el("div", { class: "table-wrap" }, el("table")), el("div", { class: "table-foot" }));
    else card.append(el("div", { class: "plot", id: "plot-" + c.id }));
    cards[c.id] = card; grid.append(card);
  }
  const foot = el("footer", {}, el("span", {}, `Source: ${spec.source.name} (${data.length.toLocaleString()} rows embedded)`), el("span", {}, `Renderer: ${backend.name} ${backend.version} · ${backend.license}`), el("span", {}, "Self-contained file · no network requests"));
  page.append(head, filterRow, grid, foot);
  document.body.append(page);

  // ---- renderers ----------------------------------------------------------
  const ctx = { theme, format, formatAxis, onSelect: setFilter };
  const mounted = {};

  function renderKpi(c, card, a) {
    $(".value", card).textContent = format(a.value, c.format);
    const n = filtered().length;
    $(".meta", card).textContent = n === data.length ? "all orders" : `${n.toLocaleString()} of ${data.length.toLocaleString()} orders`;
  }

  function renderTable(c, card, a) {
    let rows = a.rows;
    if (state.search) { const q = state.search.toLowerCase(); rows = rows.filter((r) => c.columns.some((col) => String(r[col.field]).toLowerCase().includes(q))); }
    if (state.sort) { const { field, dir } = state.sort; const s = dir === "desc" ? -1 : 1; rows = [...rows].sort((x, y) => (x[field] < y[field] ? -s : x[field] > y[field] ? s : 0)); }
    const ps = c.page_size || 25, pages = Math.max(1, Math.ceil(rows.length / ps)); state.page = Math.min(state.page, pages - 1);
    const slice = rows.slice(state.page * ps, (state.page + 1) * ps);
    const table = $("table", card); table.replaceChildren();
    const thead = el("tr");
    for (const col of c.columns) {
      const th = el("th", { class: (col.format ? "num " : "") + (state.sort?.field === col.field ? "sorted " + state.sort.dir : ""), onclick: () => { state.sort = { field: col.field, dir: state.sort?.field === col.field && state.sort.dir === "desc" ? "asc" : "desc" }; render(); } }, col.label || col.field);
      thead.append(th);
    }
    table.append(el("thead", {}, thead));
    const tbody = el("tbody");
    for (const r of slice) tbody.append(el("tr", {}, ...c.columns.map((col) => el("td", { class: col.format ? "num" : "" }, format(r[col.field], col.format)))));
    table.append(tbody);
    const ft = $(".table-foot", card); ft.replaceChildren(
      el("button", { onclick: () => { state.page--; render(); }, ...(state.page === 0 ? { disabled: "" } : {}) }, "‹ Prev"),
      el("span", {}, `${rows.length ? state.page * ps + 1 : 0}–${Math.min(rows.length, (state.page + 1) * ps)} of ${rows.length.toLocaleString()}`),
      el("button", { onclick: () => { state.page++; render(); }, ...(state.page >= pages - 1 ? { disabled: "" } : {}) }, "Next ›"),
      el("input", { type: "search", placeholder: "Search…", value: state.search, oninput: (e) => { state.search = e.target.value; state.page = 0; renderTable(c, card, aggregate(c, filtered())); } }));
  }

  function render() {
    const rows = filtered();
    for (const [f, s] of Object.entries(selects)) s.value = state.filters[f] || "";
    for (const c of spec.components) {
      const a = aggregate(c, rows), card = cards[c.id];
      if (c.type === "kpi") renderKpi(c, card, a);
      else if (c.type === "table") renderTable(c, card, a);
      else if (!mounted[c.id]) { mounted[c.id] = backend.mount(c, $(".plot", card), a, ctx); }
      else backend.update(c, mounted[c.id], a, ctx);
    }
  }
  render();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => location.reload());
  window.DAT.state = state; // for debugging / tests
})();
