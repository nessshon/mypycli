# mypycli

A Python framework for building extensible CLI applications with a module system, interactive REPL console, daemon mode, and i18n out of the box.

> Requires Python 3.10+.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Application](#application)
- [Modules](#modules)
  - [Module interfaces](#module-interfaces)
- [CLI Modes](#cli-modes)
- [Console](#console)
  - [Built-in REPL commands](#built-in-repl-commands)
  - [Prompts](#prompts)
  - [Output helpers](#output-helpers)
- [Database](#database)
- [Logger](#logger)
- [Worker](#worker)
- [i18n](#i18n)
- [Utilities](#utilities)
- [Types](#types)
- [Putting It Together](#putting-it-together)
- [Example](#example)

## Installation

```bash
pip install mypycli
```

## Quick Start

Bootstrap the locales folder first (creates `./locales/{en,ru,zh}.yml` with the bundled defaults):

```bash
mypycli locales init
```

Then write the app:

```python
from pathlib import Path

from mypycli import Application, DatabaseSchema, Translator

translator = Translator(Path(__file__).parent / "locales")

app = Application(
    db_schema=DatabaseSchema,
    work_dir=Path(__file__).parent / "data",
    name="myapp",
    label="My App",
    translator=translator,
)
app.run()
```

Run:

```bash
python myapp.py         # REPL
python myapp.py logs    # show the log file
```

## Application

`Application` wires together the database, console, worker, logger, and module registry. Everything hangs off the `app` instance.

```python
from mypycli import Application, DatabaseSchema, Translator

app = Application(
    db_schema=MySchema,             # DatabaseSchema subclass
    work_dir="./data",              # holds .pid, .log, .db, .history
    translator=translator,          # Translator instance
    name="myapp",                   # required identifier (lowercased)
    label="My App",                 # optional display name
    modules=[MyModule],             # list of Module subclasses to register
    welcome=None,                   # None = default banner, "" = no banner
    goodbye=None,
    env_prefix="MYAPP",             # optional, enables MYAPP_* env lookups
)
```

Attributes available from inside modules via `self.app`:

| attribute | purpose |
|---|---|
| `app.db` | typed JSON database (`Database[T]`) |
| `app.console` | REPL + prompts + output helpers |
| `app.logger` | framework logger (`<app.name>`) |
| `app.worker` | background task registry |
| `app.modules` | module registry |
| `app.translator` | current i18n `Translator` |
| `app.work_dir` | resolved working directory |
| `app.pid_path`, `app.log_path` | derived paths |
| `app.is_running()` | daemon alive check |

Lifecycle: `app.run()` parses CLI args and dispatches. `app.start()` loads the DB, resolves language, attaches the file log. `app.stop()` stops the worker and closes module event loops.

## Modules

Inherit `Module` and set a `name`:

```python
from mypycli import Module

class MyModule(Module):
    name = "mymod"
    label = "My Module"       # optional display label
    mandatory = False         # True -> auto-installed/enabled
    db_schema = MySchema      # optional per-module typed storage (see Database)
```

Inside a module, framework services are one attribute away:

| attribute | purpose |
|---|---|
| `self.app` | back-reference to the application |
| `self.db` | typed per-module storage (requires `db_schema`) |
| `self.logger` | child logger `<app.name>.<module.name>` |
| `self.display_name` | `label` or `name` |
| `self.is_enabled` | whether the module is active |

Background helpers that name tasks after the module automatically:

```python
self.run_task(self._background_job)                  # fire-and-forget
self.run_cycle(self._poll, seconds=30)               # periodic loop
result = self.run_async(self._some_coroutine())      # sync ↔ async bridge
```

### Module interfaces

Concrete modules implement zero or more interfaces. Each adds a capability the framework discovers by type. Every interface already inherits from `Module`, so list only the interfaces as bases — **do not** also list `Module` (it triggers an MRO conflict).

| interface | purpose |
|---|---|
| `Startable` | REPL session hooks: `on_start()` / `on_stop()` |
| `Statusable` | renders live status via `show_status()` |
| `Daemonic` | registers workers in `on_daemon()` |
| `Installable` | `on_install()` / `on_uninstall()` |
| `Updatable` | `version` property + `on_update()` |
| `Commandable` | contributes commands via `get_commands()` |

```python
from mypycli import Statusable

class Prometheus(Statusable):
    name = "prometheus"

    def show_status(self) -> None:
        self.app.console.print(f"{self.display_name}: running")
```

Combine multiple interfaces by listing them all — `Module` is picked up transitively:

```python
from mypycli import Daemonic, Statusable

class Heartbeat(Statusable, Daemonic):
    name = "heartbeat"
    ...
```

## CLI Modes

A `myapp` built on mypycli automatically gets these commands when matching modules exist:

| command | condition | action |
|---|---|---|
| `myapp` | always | enters REPL (`console` mode) |
| `myapp install` | has `Installable` | runs `on_install` for mandatory + selected modules |
| `myapp uninstall` | has `Installable` | calls `on_uninstall` in reverse order |
| `myapp update` | has `Updatable` | calls `on_update` on every Updatable module |
| `myapp daemon` | has `Daemonic` | starts background workers via `on_daemon` |
| `myapp logs [-n N] [-f] [--level L] [--module M] [--all]` | always | tails the log file |

`install` / `update` / `uninstall` require root and exit with a `sudo` / `su` hint otherwise.

## Console

`app.console` is a `Console` instance mixing `ConsoleInput` and `ConsoleOutput`. It drives the REPL, renders text, and asks the user questions.

### Built-in REPL commands

| command | purpose |
|---|---|
| `help [group]` | list commands or subcommands |
| `status` | calls `show_status()` on each `Statusable` module |
| `modules` | table of registered modules and capabilities |
| `versions` | table of component versions (`Updatable` modules) |
| `history` | persisted command history |
| `clear` | clear the terminal |
| `db show` | pretty-print the full JSON database |
| `db get <field>` | read a field by dotted path |
| `db set <field> <value>` | write a field (JSON or bare string); prints "restart required" for `debug` / `language` |
| `exit` | leave the REPL |

Modules add their own commands by implementing `Commandable` and returning a list of `Command` objects:

```python
from mypycli import Commandable
from mypycli.types import Command

class MyModule(Commandable):
    name = "mymod"

    def get_commands(self) -> list[Command]:
        return [Command("greet", self._greet, "Say hi", usage="<name>")]

    def _greet(self, app, args: list[str]) -> None:
        app.console.print(f"Hello {args[0]}!")
```

### Prompts

Two equivalent styles. **Direct methods** take a prompt string (most common):

```python
proceed = app.console.confirm("Proceed?", default=True)
name = app.console.input("Your name")
token = app.console.secret("Paste the token")
pick = app.console.select("Pick one", choices=["a", "b", "c"])
picks = app.console.multiselect("Pick many", choices=["a", "b", "c"])
```

**Declarative** — useful when a prompt is data passed around (e.g. a module returning a list of questions). Each dataclass lives in `mypycli.types`; `console.ask` dispatches on the type:

```python
from mypycli.types import Confirm, Input, Multiselect, Secret, Select

proceed = app.console.ask(Confirm(prompt="Proceed?", default=True))
name = app.console.ask(Input(prompt="Your name"))
token = app.console.ask(Secret(prompt="Paste the token"))
pick = app.console.ask(Select(prompt="Pick one", choices=["a", "b", "c"]))
picks = app.console.ask(Multiselect(prompt="Pick many", choices=["a", "b", "c"]))
```

`Input` and `Secret` accept a `validate=callable` that returns an error string to reject input; on TTY the prompt is retried with the entered buffer preserved, on non-TTY a `ValueError` is raised.

### Output helpers

`ConsoleOutput` methods are available both as static utilities and via `app.console`:

```python
from mypycli.types import BoxStyle, Color, ColorText

rows = [
    [ColorText("Name", Color.CYAN), ColorText("Value", Color.CYAN)],
    ["interval", "30"],
]
app.console.print("hello", color=Color.GREEN)
app.console.print_table(rows, style=BoxStyle.ROUNDED)
app.console.print_panel([("label", "value"), ("other", "x")], header="Info")
app.console.print_json({"k": 1})
app.console.print_line(40)
```

`print_progress()` returns a context manager that rewrites one terminal line on each `update` (TTY) or prints standalone lines (pipe/redirect). Pass `total=N` to auto-prepend a `[n/total]` counter:

```python
with app.console.print_progress(total=3) as line:
    line.update("step one")
    line.update("step two")
    line.update("step three")
    line.finish("done", color=Color.GREEN)  # finish/fail carry no counter
```

## Database

`Database[T]` is a JSON file with auto-save on field assignment. The schema is a pydantic `DatabaseSchema` subclass:

```python
from mypycli import DatabaseSchema

class MySchema(DatabaseSchema):
    interval: int = 30
    enabled: bool = True
```

Fields mutate in place:

```python
app.db.interval = 60   # persists immediately
```

Two framework-owned extras are always present:

- `app.db.debug` (bool) — toggled via `db set debug true`; controls log level on next start.
- `app.db.language` (str) — set on first run from `LANG`; change via `db set language ru`.

Each module with `db_schema` gets its own typed section under `modules.<module.name>` in the same file, accessed as `self.db` inside the module.

Generic access by dotted path:

```python
found, value = app.db.get_by_path("interval")
app.db.set_by_path_str("interval", "60")
```

## Logger

`app.logger` writes to a single sink: a `RotatingFileHandler` at `<work_dir>/<name>.log` (5MB × 5 backups), attached automatically by `app.start()` and formatted as plain text. Stdout is reserved for the `Console` UX channel — the logger never writes there.

Modules get a pre-configured child logger via `self.logger` (named `<app.name>.<module.name>`). Use it as a normal Python logger:

```python
self.logger.info(f"polling {host}")
self.logger.exception("handler failed")   # captures traceback automatically
```

Tail the log live with `myapp logs -f`.

## Worker

`app.worker` owns the background tasks. Use it directly in daemon code or via the shortcuts on `Module`.

```python
# Simple one-shot:
app.worker.run(do_something, name="bootstrap")

# Periodic:
app.worker.cycle(poll, seconds=60, name="poller")

# Or pass a Task/CycleTask instance:
from mypycli.utils import CycleTask
app.worker.add(CycleTask(poll, app.logger, seconds=60, name="poller"))
```

All tasks are daemon threads with a cooperative stop event (`task.stop()`).

## i18n

Translations live in `./locales/<lang>.yml`. Library-owned strings are under the `mypycli:` top-level key; your app keys go at any other top level.

```yaml
"mypycli":
  "console":
    "welcome": "..."
"dashboard":
  "title": "..."
```

Create or refresh the folder with the bundled defaults:

```bash
mypycli locales init          # scaffold (skip existing)
mypycli locales sync          # refresh mypycli: section
mypycli locales check         # verify consistency (CI-friendly, exit 1 on drift)
```

The effective language is chosen at `app.start()`: `db.language` → `LANG` env → first of `en` / any available. Strict: a missing translation key raises `LookupError` (tests/`locales check` catch this before deploy).

Use it in your app code:

```python
_ = app.translator
_("dashboard.title")                       # "Dashboard"
_("messages.greeting", name="Alice")       # "Hello, Alice!"
```

## Utilities

Importable from `mypycli.utils`:

| name | purpose |
|---|---|
| `run(args, capture=True, timeout=30, check=False)` | wrapper around `subprocess.run` |
| `run_as_root(args, ...)` | same, wrapping with `sudo` / `su -c` when needed |
| `is_root()`, `is_tty()` | environment predicates |
| `read_pid(path)`, `is_alive(pid)` | daemon PID utilities |
| `read_config(path, Model)`, `write_config(path, model)` | atomic JSON config I/O via pydantic |
| `format_validation_error(exc)` | short one-line summary of a pydantic `ValidationError` |
| `format_bytes`, `format_bitrate` | byte / bit-rate formatters |
| `format_duration`, `format_time_ago` | duration formatters with correct plural; `lang: Literal["en", "ru", "zh"]` — default `"en"` |
| `parse_bytes`, `parse_duration` | reverse parsers |
| `bytes_to(n, ByteUnit.MB)` | raw unit conversion |
| `Task`, `CycleTask`, `Worker` | background-task primitives |
| `ip_to_int`, `int_to_ip`, `is_port_open`, `get_public_ip`, `get_network_interface`, `ping_latency` | network helpers |
| `SysInfo`, `sysinfo()` | CPU / RAM / swap / disks / net I/O snapshots |
| `SystemdService`, `SystemdTimer` | create, control, and inspect systemd units |
| `BaseGitRepo`, `RemoteGitRepo`, `LocalGitRepo`, `RepoInfo`, `GitError` | GitHub-aware git wrappers |

## Types

From `mypycli.types`:

- `Color` — ANSI color names (`RED`, `GREEN`, `BRIGHT_CYAN`, ...).
- `ColorText(text, color)` — text bound to a color for rendering.
- `BoxStyle` — `ROUNDED`, `SHARP`, `DOUBLE`, `ASCII` for tables and panels.
- `Command(name, handler, description, usage, children, expand)` — console command descriptor with optional subcommands.
- `Input`, `Secret`, `Confirm`, `Select`, `Multiselect` — declarative prompts, dispatched by `console.ask`.
- `ByteUnit` — powers-of-1024 unit enum used by `bytes_to`.
- `CpuInfo`, `MemoryInfo`, `DiskSpace`, `DiskIO`, `NetworkIO`, `HardwareInfo`, `OsInfo` — `SysInfo` result types.

## Putting It Together

A small module that polls a URL, reports status in the REPL, and runs in daemon mode:

```python
# myapp/modules/pinger.py
from mypycli import Daemonic, DatabaseSchema, Statusable
from mypycli.utils import is_port_open


class PingerSchema(DatabaseSchema):
    host: str = "example.com"
    port: int = 443
    interval: int = 30
    last_ok: bool = False


class Pinger(Statusable, Daemonic):
    name = "pinger"
    db_schema = PingerSchema

    def show_status(self) -> None:
        state = "up" if self.db.last_ok else "down"
        self.app.console.print(f"{self.db.host}:{self.db.port} — {state}")

    def on_daemon(self) -> None:
        self.run_cycle(self._check, seconds=self.db.interval)

    def _check(self) -> None:
        ok = is_port_open(self.db.host, self.db.port)
        self.db.last_ok = ok                            # persists immediately
        self.logger.info(f"{self.db.host}:{self.db.port} -> {ok}")
```

Wire it into an app:

```python
# myapp/__main__.py
from pathlib import Path
from mypycli import Application, DatabaseSchema, Translator
from myapp.modules.pinger import Pinger

translator = Translator(Path(__file__).parent.parent / "locales")

app = Application(
    db_schema=DatabaseSchema,
    work_dir=Path(__file__).parent.parent / "data",
    translator=translator,
    name="myapp",
    label="My App",
    modules=[Pinger],
)
app.run()
```

Use:

```bash
python -m myapp             # REPL: type `status`, `modules`, `db show`, `exit`
python -m myapp daemon      # background loop, persists `last_ok` on each tick
python -m myapp logs -f     # tail what the daemon is writing
```

## Example

A minimal runnable demo lives at `examples/i18n_demo.py`:

```bash
LANG=ru_RU.UTF-8 python examples/i18n_demo.py
```

shows:

```
Добро пожаловать в Demo App!
Наберите help чтобы увидеть доступные команды.
demo>
```
