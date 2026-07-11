# 📦 MyPyCLI

![Python Versions](https://img.shields.io/badge/Python-3.10%20--%203.14-black?color=FFE873&labelColor=3776AB)
[![License](https://img.shields.io/github/license/nessshon/mypycli)](https://github.com/nessshon/mypycli/blob/main/LICENSE)

### Python framework for extensible CLI applications

Modules with capability interfaces, interactive console, daemon mode, and non-interactive install/update/uninstall.

**Features**

- **Modules** — capability interfaces: Commandable, Installable, Updatable, Startable, Statusable, Daemonic
- **Console** — interactive REPL with nested commands, completion, history, and rich tables/panels
- **Daemon** — background mode with PID guard and per-module worker cycles
- **Prompts** — text, number, secret, confirm, select — each overridable via environment variables
- **Localization** — YAML catalogs (en, ru, zh) with bundled framework strings overlay
- **Utilities** — systemd services, git repositories, system info, JSON file storage, network helpers

## Installation

```bash
pip install git+https://github.com/nessshon/mypycli
```

## Usage

```python
from pathlib import Path

from mypycli.application import Application
from mypycli.modules import Installable
from mypycli.utils.github import GitRepo


class MyService(Installable):
    name = "my-service"
    mandatory = True

    def on_install(self) -> None:
        GitRepo.clone("https://github.com/me/my-service", "/usr/src/my-service", force=True)

    def on_uninstall(self) -> None: ...


app = Application(
    "myapp",
    "My App",
    debug=False,
    work_dir="/var/lib/myapp",
    logs_dir="/var/log/myapp",
    locales_dir=Path(__file__).parent / "locales",
)
app.register_module(MyService)
app.run()
```

```bash
myapp                          # interactive console
myapp --daemon                 # run Daemonic modules
myapp install --modules extra  # non-interactive install
myapp update                   # update modules, show version table
myapp uninstall --yes          # remove everything without prompt
```

## Localization

Locale files in `locales/` hold only the application's own keys; bundled `mypycli.*` strings (en, ru, zh) resolve automatically and can be overridden by the same key.

```bash
mypycli init  # copy the bundled catalogs into ./locales/ as a starting point
```

## License

This repository is distributed under the [MIT License](https://github.com/nessshon/mypycli/blob/main/LICENSE).
