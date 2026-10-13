# datbox-core

The core of **dat**, the Data Analyst Toolbox. Provides the `dat` command-line entry point,
the plugin registry other `datbox-*` packages register their subcommands with, and the
foundations every module shares: profiles, sources, secrets, logging, and output writers.

```bash
pip install datbox-core
dat --help
dat config init      # starter ~/.config/dat/profiles.yml
dat config show      # the resolved profile, secrets shown as locations only
```

## Profiles

One `profiles.yml` per user (`~/.config/dat/profiles.yml`, or `$XDG_CONFIG_HOME/dat/`,
or `$DAT_CONFIG_DIR/`) and an optional `dat.yml` per project, found by walking up from the
current directory. Same schema; project profiles merge over user profiles of the same name.

```yaml
default: dev
profiles:
  dev:
    sources:
      marts: { type: duckdb, path: ~/dbt/target/dev.duckdb, table: fct_orders }
      raw:   { type: csv, path: data/raw.csv, delimiter: ";" }
    secrets:
      api_token: { env: SF_API_TOKEN }           # or "keyring:dat/dev/api_token"
    settings:
      salesforce: { instance_url: https://example.my.salesforce.com }
```

Pick a profile with `--profile`, `$DAT_PROFILE`, or `default:`. Relative source paths are
anchored at the config file that declares them.

## Secrets

Never in files. Declare where a secret lives (`env:` / `keyring:`), or declare nothing and
`profile.secret("api_token")` looks for `$DAT_DEV_API_TOKEN`, then `$DAT_API_TOKEN`, then
the OS keyring (`service=dat`, `username=dev/api_token`). Keyring support is optional:
`pip install datbox-core[keyring]`.

## For module authors

```python
from pydantic import BaseModel
from datbox_core.config import load_profile
from datbox_core.writers import write

class SalesforceSettings(BaseModel):
    instance_url: str

profile = load_profile()                              # honours --profile / $DAT_PROFILE
settings = profile.section("salesforce", SalesforceSettings)
token = profile.secret("api_token")
frame = profile.source("marts").load()                # polars LazyFrame
write(frame, "out/fct_orders.parquet")                # or .csv / .duckdb
```

Register a subcommand with an entry point and `dat <name>` exists on install:

```toml
[project.entry-points."datbox.plugins"]
viz = "datbox_viz.cli:app"
```
