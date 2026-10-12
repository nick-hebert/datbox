# datbox

**dat** is the Data Analyst Toolbox: a family of independently installable, zero-infrastructure
utilities for data analysts. Every output is a single self-contained file; nothing needs a server.

```bash
pip install datbox
dat --help
```

`datbox` is the umbrella package. It installs `datbox-core` (the `dat` CLI) and, as modules
are released, will pull in the full toolbox. Install individual modules (`datbox-viz`,
`datbox-fake`, ...) if you only want one.

Project home: https://github.com/nick-hebert/datbox
