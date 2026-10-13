"""Build the OQ-1 prototype dashboards: one YAML spec, three chart libraries.

Usage: python build.py [--node-modules PATH] [--out DIR]
Produces oq1-echarts.html, oq1-plotly.html, oq1-vegalite.html — each a single
self-contained file per the 03_ARCHITECTURE.md contract.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

HERE = Path(__file__).parent
RT = HERE / "runtime"

# Each backend: (slug, human name, [(vendored file, license file)], backend js)
BACKENDS = {
    "echarts": {
        "label": "ECharts",
        "libs": [("echarts/dist/echarts.min.js", "echarts/LICENSE")],
        "backend": RT / "backend_echarts.js",
    },
    "plotly": {
        "label": "Plotly.js",
        "libs": [
            ("plotly.js-basic-dist-min/plotly-basic.min.js", "plotly.js-basic-dist-min/LICENSE")
        ],
        "backend": RT / "backend_plotly.js",
    },
    "vegalite": {
        "label": "Vega-Lite",
        "libs": [
            ("vega/build/vega.min.js", "vega/LICENSE"),
            ("vega-lite/build/vega-lite.min.js", "vega-lite/LICENSE"),
            ("vega-embed/build/vega-embed.min.js", "vega-embed/LICENSE"),
        ],
        "backend": RT / "backend_vegalite.js",
    },
}


def script_safe(js: str) -> str:
    """Inline JS must not contain a literal '</script'."""
    return re.sub(r"</(script)", r"<\\/\1", js, flags=re.IGNORECASE)


def json_for_script(obj) -> str:
    return (
        json.dumps(obj, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def vendored(nm: Path, lib: str, license_path: str) -> str:
    js = (nm / lib).read_text(encoding="utf-8")
    pkg = json.loads((nm / lib.split("/")[0] / "package.json").read_text())
    header = (
        f"/*! {pkg['name']} v{pkg['version']} — {pkg.get('license', '?')} — "
        "vendored by datbox-viz; see LICENSE text below */\n"
    )
    # Bundles with no license header in the minified file get the package's
    # LICENSE prepended (ADR-003 §3).
    if not js.lstrip().startswith(("/*", "//")):
        lic = (nm / license_path).read_text(encoding="utf-8").strip().replace("*/", "* /")
        header += "/*\n" + lic + "\n*/\n"
    return header + script_safe(js)


def build(slug: str, spec: dict, data: list, nm: Path, out_dir: Path) -> Path:
    b = BACKENDS[slug]
    libs = "\n".join(f"<script>\n{vendored(nm, lib, lic)}\n</script>" for lib, lic in b["libs"])
    css = (RT / "shell.css").read_text()
    shell = script_safe((RT / "shell.js").read_text())
    backend = script_safe(b["backend"].read_text())
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{spec["title"]} — {b["label"]} (OQ-1 prototype)</title>
<!-- datbox-viz OQ-1 prototype. Self-contained: no external scripts, styles, fonts, or requests.
     This file embeds its data; treat it with the same care as the data inside it. -->
<style>
{css}
</style>
</head>
<body>
<noscript>This dashboard needs JavaScript enabled.</noscript>
{libs}
<script>
window.DAT = {{ spec: {json_for_script(spec)}, data: {json_for_script(data)} }};
</script>
<script>
{backend}
</script>
<script>
{shell}
</script>
</body>
</html>
"""
    out = out_dir / f"oq1-{slug}.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-modules", type=Path, default=Path("node_modules"))
    ap.add_argument("--out", type=Path, default=HERE / "dist")
    ap.add_argument("--only", nargs="*", default=list(BACKENDS))
    a = ap.parse_args()
    a.out.mkdir(exist_ok=True)
    spec = yaml.safe_load((HERE / "dashboard.yml").read_text())
    data = json.loads((HERE / spec["source"]["path"]).read_text())
    for slug in a.only:
        p = build(slug, spec, data, a.node_modules, a.out)
        print(f"{p.name:22s} {p.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
