# datbox-core

The core of **dat**, the Data Analyst Toolbox. Provides the `dat` command-line entry point
and the plugin registry that other `datbox-*` packages register their subcommands with.

```bash
pip install datbox-core
dat --help
```

Other modules (`datbox-viz`, `datbox-fake`, ...) add subcommands automatically when installed.
