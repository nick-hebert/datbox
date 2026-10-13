/* ECharts backend: spec component -> echarts option. */
window.DAT.backend = (function () {
  const base = (t, c) => ({
    animationDuration: 300,
    textStyle: { fontFamily: t.font, color: t.ink2 },
    color: t.series,
    tooltip: { backgroundColor: t.surface, borderColor: t.grid, textStyle: { color: t.ink }, valueFormatter: (v) => c.fmt(v) },
    grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
  });
  const axisStyle = (t) => ({ axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false }, axisLabel: { color: t.muted }, splitLine: { lineStyle: { color: t.grid } } });

  function option(c, a, ctx) {
    const t = ctx.theme(); const F = { fmt: (v) => ctx.format(v, c.format), ax: (v) => ctx.formatAxis(v, c.format) };
    if (c.type === "bar") return {
      ...base(t, F), tooltip: { ...base(t, F).tooltip, trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: { type: "category", data: a.x, ...axisStyle(t), splitLine: { show: false } },
      yAxis: { type: "value", ...axisStyle(t), axisLine: { show: false }, axisLabel: { color: t.muted, formatter: F.ax } },
      series: [{ type: "bar", data: a.y, barMaxWidth: 48, itemStyle: { borderRadius: [4, 4, 0, 0], color: t.series[0] }, emphasis: { itemStyle: { color: t.series[0], opacity: 0.85 } } }],
    };
    if (c.type === "line") return {
      ...base(t, F), tooltip: { ...base(t, F).tooltip, trigger: "axis" },
      legend: { top: 0, left: 0, icon: "circle", textStyle: { color: t.ink2 } },
      grid: { ...base(t, F).grid, top: 36, bottom: 44 },
      dataZoom: [{ type: "inside", filterMode: "none" }, { type: "slider", height: 18, bottom: 6, borderColor: t.grid, backgroundColor: t.surface, fillerColor: t.grid, handleStyle: { color: t.axis }, textStyle: { color: t.muted }, dataBackground: { lineStyle: { color: t.axis }, areaStyle: { color: t.grid } } }],
      xAxis: { type: "category", data: a.x, boundaryGap: false, ...axisStyle(t), splitLine: { show: false } },
      yAxis: { type: "value", ...axisStyle(t), axisLine: { show: false }, axisLabel: { color: t.muted, formatter: F.ax } },
      series: a.series.map((s) => ({ name: s.name, type: "line", data: s.values, smooth: false, symbolSize: 7, lineStyle: { width: 2 }, color: t.series[s.color], connectNulls: false })),
    };
    if (c.type === "pie") return {
      ...base(t, F), grid: undefined,
      tooltip: { ...base(t, F).tooltip, trigger: "item", formatter: (p) => `${p.name}<br/><b>${F.fmt(p.value)}</b> · ${p.percent}%` },
      legend: { bottom: 0, icon: "circle", textStyle: { color: t.ink2 } },
      series: [{ type: "pie", radius: ["44%", "66%"], center: ["50%", "46%"], itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 },
        label: { color: t.ink2, formatter: "{d}%", edgeDistance: 10 }, labelLine: { lineStyle: { color: t.axis } },
        data: a.labels.map((l, i) => ({ name: l, value: a.values[i], itemStyle: { color: t.series[a.colors[i]] } })) }],
    };
  }

  return {
    name: "ECharts", version: echarts.version, license: "Apache-2.0",
    mount(c, el, a, ctx) {
      const chart = echarts.init(el, null, { renderer: "canvas" });
      chart.setOption(option(c, a, ctx));
      const field = c.type === "bar" ? c.x.field : c.type === "pie" ? c.category.field : null;
      if (field) chart.on("click", (p) => ctx.onSelect(field, p.name));
      new ResizeObserver(() => chart.resize()).observe(el);
      return chart;
    },
    update(c, chart, a, ctx) { chart.setOption(option(c, a, ctx), { replaceMerge: ["series", "xAxis"] }); },
  };
})();
