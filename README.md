# dat: the Data Analyst Toolbox

Portable, zero-infrastructure utilities for data analysts. Every output is a single
self-contained file you can drop on a file share; nothing needs a server to view.

**Status: pre-alpha.** The namespace is claimed and the plugin architecture is in place.
First real module (`datbox-viz`, YAML + DuckDB → single-file HTML dashboards) is in progress.

```bash
pip install datbox
dat --help
```

## Packages

| Package | Purpose | Status |
|---|---|---|
| `datbox` | Umbrella meta-package | published |
| `datbox-core` | `dat` CLI, plugin registry, config, secrets, writers | published (skeleton) |
| `datbox-fake` | Realistic, seeded, schema-driven fake data | planned (v0.1) |
| `datbox-viz` | Single-file HTML dashboard generator | planned (v0.1) |

## Development

```bash
uv sync
uv run ruff check . && uv run pyright && uv run pytest
uv run dat --help
```

## License

Apache-2.0. See [LICENSE](LICENSE).
