/* Vega-Lite backend: spec component -> Vega-Lite spec, embedded via vega-embed (vega + vega-lite + vega-tooltip). */
window.DAT.backend = (function () {
  const vlConfig = (t) => ({
    background: t.surface, font: t.font,
    view: { stroke: null },
    axis: { labelColor: t.muted, titleColor: t.ink2, gridColor: t.grid, domainColor: t.axis, tickColor: t.axis, labelFont: t.font, titleFont: t.font, labelFontSize: 11 },
    legend: { labelColor: t.ink2, titleColor: t.ink2, labelFont: t.font, orient: "top", title: null, symbolType: "circle" },
    range: { category: t.series },
    mark: { tooltip: true },
  });
  const money = (c) => (c.format === "currency" ? "$,.0f" : ",.0f");
  const axisFmt = (c) => (c.format === "currency" ? "$~s" : "~s");

  // Long-form rows are what Vega-Lite wants; reshape the shell's aggregates.
  function rows(c, a) {
    if (c.type === "bar") return a.x.map((x, i) => ({ key: x, value: a.y[i], order: i }));
    if (c.type === "line") return a.series.flatMap((s) => a.x.map((x, i) => ({ month: x + "-01T00:00:00", series: s.name, value: s.values[i] })));
    if (c.type === "pie") return a.labels.map((l, i) => ({ key: l, value: a.values[i] }));
  }

  function vlSpec(c, a, ctx) {
    const t = ctx.theme();
    const common = { $schema: "https://vega.github.io/schema/vega-lite/v6.json", width: "container", height: "container", autosize: { type: "fit", contains: "padding" }, config: vlConfig(t), data: { name: "table", values: rows(c, a) } };
    if (c.type === "bar") return { ...common,
      mark: { type: "bar", cornerRadiusEnd: 4, color: t.series[0], cursor: "pointer" },
      encoding: { x: { field: "key", type: "nominal", sort: { field: "order" }, scale: { paddingInner: 0.4, paddingOuter: 0.2 }, axis: { title: null, labelAngle: 0, grid: false } },
        y: { field: "value", type: "quantitative", axis: { title: null, format: axisFmt(c), domain: false } },
        tooltip: [{ field: "key", title: c.x.field }, { field: "value", title: c.y.field, format: money(c) }] } };
    if (c.type === "line") return { ...common,
      params: [{ name: "zoom", select: { type: "interval", encodings: ["x"] }, bind: "scales" }],
      mark: { type: "line", point: { size: 50 }, strokeWidth: 2, invalid: "break-paths-show-domains" },
      encoding: { x: { field: "month", type: "temporal", timeUnit: "yearmonth", axis: { title: null, grid: false, format: "%b %y" } },
        y: { field: "value", type: "quantitative", axis: { title: null, format: axisFmt(c), domain: false } },
        color: { field: "series", type: "nominal", scale: { domain: a.series.map((s) => s.name), range: a.series.map((s) => t.series[s.color]) } },
        tooltip: [{ field: "month", type: "temporal", timeUnit: "yearmonth", title: "month" }, { field: "series" }, { field: "value", format: money(c) }] } };
    if (c.type === "pie") return { ...common,
      transform: [{ joinaggregate: [{ op: "sum", field: "value", as: "total" }] }, { calculate: "datum.value / datum.total", as: "share" }],
      mark: { type: "arc", innerRadius: 60, padAngle: 0.02, cornerRadius: 4, stroke: t.surface, strokeWidth: 2, cursor: "pointer" },
      encoding: { theta: { field: "value", type: "quantitative", stack: true },
        color: { field: "key", type: "nominal", scale: { domain: a.labels, range: a.colors.map((i) => t.series[i]) }, legend: { orient: "bottom" } },
        tooltip: [{ field: "key", title: c.category.field }, { field: "value", title: c.value.field, format: money(c) }, { field: "share", format: ".1%" }] } };
  }

  return {
    name: "Vega-Lite", version: `${vegaLite.version} (vega ${vega.version})`, license: "BSD-3-Clause",
    mount(c, el, a, ctx) {
      const holder = { view: null };
      vegaEmbed(el, vlSpec(c, a, ctx), { actions: false, renderer: "svg", tooltip: { theme: ctx.theme().dark ? "dark" : "light" } }).then((r) => {
        holder.view = r.view;
        const field = c.type === "bar" ? c.x.field : c.type === "pie" ? c.category.field : null;
        if (field) r.view.addEventListener("click", (_, item) => item?.datum?.key != null && ctx.onSelect(field, item.datum.key));
        new ResizeObserver(() => r.view.resize().run()).observe(el);
      });
      return holder;
    },
    update(c, holder, a, ctx) {
      if (holder.view) holder.view.change("table", vega.changeset().remove(() => true).insert(rows(c, a))).run();
    },
  };
})();
