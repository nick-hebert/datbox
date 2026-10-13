/* Plotly.js backend: spec component -> {data, layout, config}. */
window.DAT.backend = (function () {
  const layoutBase = (t) => ({
    paper_bgcolor: t.surface, plot_bgcolor: t.surface, font: { family: t.font, color: t.ink2, size: 12 },
    margin: { l: 8, r: 16, t: 28, b: 8, pad: 0 }, autosize: true,
    hoverlabel: { bgcolor: t.surface, bordercolor: t.grid, font: { color: t.ink, family: t.font } },
    colorway: t.series,
  });
  const axis = (t, extra = {}) => ({ gridcolor: t.grid, linecolor: t.axis, zerolinecolor: t.axis, tickfont: { color: t.muted }, automargin: true, fixedrange: false, ...extra });
  const config = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "toImage"], displayModeBar: "hover" };

  function figure(c, a, ctx) {
    const t = ctx.theme();
    const tick = c.format === "currency" ? { tickprefix: "$", tickformat: "~s" } : { tickformat: "~s" };
    const hov = c.format === "currency" ? "$,.0f" : ",.0f";
    if (c.type === "bar") return {
      data: [{ type: "bar", x: a.x, y: a.y, marker: { color: t.series[0], cornerradius: 4 }, hovertemplate: `%{x}<br><b>%{y:${hov}}</b><extra></extra>` }],
      layout: { ...layoutBase(t), bargap: 0.4, xaxis: axis(t, { showgrid: false, fixedrange: true }), yaxis: axis(t, { ...tick, showline: false }) },
    };
    if (c.type === "line") return {
      data: a.series.map((s) => ({ type: "scatter", mode: "lines+markers", name: s.name, x: a.x, y: s.values, connectgaps: false,
        line: { width: 2, color: t.series[s.color] }, marker: { size: 7, color: t.series[s.color] }, hovertemplate: `%{y:${hov}}<extra>%{fullData.name}</extra>` })),
      layout: { ...layoutBase(t), hovermode: "x unified", margin: { l: 8, r: 16, t: 36, b: 8 },
        legend: { orientation: "h", x: 0, y: 1.12, font: { color: t.ink2 } },
        xaxis: axis(t, { showgrid: false, rangeslider: { visible: true, thickness: 0.08, bgcolor: t.surface, bordercolor: t.grid, borderwidth: 1 } }),
        yaxis: axis(t, { ...tick, showline: false }) },
    };
    if (c.type === "pie") return {
      data: [{ type: "pie", labels: a.labels, values: a.values, hole: 0.62, sort: false, direction: "clockwise",
        marker: { colors: a.colors.map((i) => t.series[i]), line: { color: t.surface, width: 2 } },
        textinfo: "label+percent", textposition: "outside", textfont: { color: t.ink2 }, hovertemplate: `%{label}<br><b>%{value:${hov}}</b> · %{percent}<extra></extra>` }],
      layout: { ...layoutBase(t), showlegend: true, legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.08, font: { color: t.ink2 } }, margin: { l: 16, r: 16, t: 24, b: 8 } },
    };
  }

  return {
    name: "Plotly.js", version: Plotly.version, license: "MIT",
    mount(c, el, a, ctx) {
      const f = figure(c, a, ctx);
      Plotly.newPlot(el, f.data, f.layout, config);
      const field = c.type === "bar" ? c.x.field : c.type === "pie" ? c.category.field : null;
      if (field) el.on("plotly_click", (e) => ctx.onSelect(field, c.type === "pie" ? e.points[0].label : e.points[0].x));
      new ResizeObserver(() => Plotly.Plots.resize(el)).observe(el);
      return el;
    },
    update(c, el, a, ctx) { const f = figure(c, a, ctx); Plotly.react(el, f.data, f.layout, config); },
  };
})();
