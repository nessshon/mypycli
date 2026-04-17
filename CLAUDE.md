# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`mypycli` is a Python 3.10+ framework (not an end-user CLI) for building extensible CLI applications: module system, interactive REPL, daemon mode, typed JSON storage, i18n. The console-script `mypycli` itself only exposes dev-tooling for managing bundled locale files; downstream apps define their own entry points via `Application(...).run()`.

Python target is `3.10` for both ruff and mypy. Source ships `py.typed`. Public API is re-exported from the top-level `mypycli/__init__.py` and from `mypycli.types`, `mypycli.utils`.

## Commands

```bash
# Tests (Python 3.10+ required by the package; the bundled .venv runs 3.9 — use system python or a fresh venv)
pytest                                          # full suite (testpaths configured in pyproject.toml)
pytest tests/test_application.py                # single file
pytest tests/test_application.py::test_pid_lifecycle   # single test
pytest tests/test_modules.py::TestModuleRegistry       # single test class
pytest -k "i18n"                                # by keyword
pytest -x                                       # stop on first failure

# Lint / format / type-check (configured in pyproject.toml; not in requirements.txt — install separately)
ruff check .
ruff format .
mypy mypycli                                    # strict mode is enabled

# Locales tooling (the only commands the bundled `mypycli` console script exposes)
mypycli locales init    # scaffold ./locales/{en,ru,zh}.yml from bundled defaults; skips existing files
mypycli locales sync    # refresh the `mypycli:` section in ./locales/*.yml without touching user keys
mypycli locales check   # validate consistency (exit 1 on drift); CI-friendly
```

The example app at `examples/i18n_demo.py` doubles as a smoke test: `LANG=ru_RU.UTF-8 python examples/i18n_demo.py`.

## Big-picture architecture

### `Application` is the wiring hub
`Application` (mypycli/application.py) owns `db`, `console`, `logger`, `worker`, `modules`, `translator`. Modules reach the rest via `self.app.*`. Lifecycle:
- `app.run()` → `cli/runner.py:run()` parses argv via `cli/parser.py:build_parser` and dispatches to `run_console` / `run_daemon` / `run_install` / `run_uninstall` / `run_update` / `run_logs`. `KeyboardInterrupt` becomes `SystemExit(130)` with a stderr message.
- `app.start()` loads the DB (`auto_create=True`), writes empty DB sections for non-Installable modules, resolves the active language (`db.language` → `LANG` env via `parse_lang_env` → `en` → first available), binds `mypycli.i18n.internal._`, sets the logger level (DEBUG iff `db.debug`), and attaches the rotating log file handler. Idempotent: `enable_file_logging` checks for an existing `RotatingFileHandler` before adding one.
- `app.stop()` stops the worker and closes per-module asyncio loops.
- `app.run_forever()` installs SIGTERM/SIGINT handlers and blocks on a `threading.Event` until shutdown.
- `app.is_running()` reads the PID file: `(False, None)` no file, `(False, pid)` stale, `(True, pid)` alive *or* EPERM (treated as alive — conservative, so we never start a duplicate daemon).

`Application` is `Generic[T]` over a `DatabaseSchema` subclass; `T` types `app.db`.

### Module system + interfaces
Concrete modules subclass `Module` (mypycli/modules/base.py). `__init_subclass__` enforces `name` is a non-empty string matching `_NAME_RE = [a-z0-9][a-z0-9_-]*`. Use `label` for display (casing/spaces). Skip the check on intermediate/mixin classes by setting `__abstract__ = True` directly on the class (SQLAlchemy convention; not inherited).

Capability interfaces live in `mypycli/modules/interfaces/*.py`. Each is `class X(Module, ABC)` with `@abstractmethod`s. Concrete modules inherit **only the interfaces** — `Module` is picked up transitively. Listing `Module` and an interface together causes an MRO conflict.

| interface | abstract methods / properties | discovered for |
|---|---|---|
| `Startable` | `on_start()`, `on_stop()` | REPL session entry/exit (console only, never daemon) |
| `Statusable` | `show_status()` | the built-in `status` REPL command |
| `Daemonic` | `on_daemon()` | the `daemon` CLI subcommand |
| `Installable` | `on_install()`, `on_uninstall()` | `install` / `uninstall` CLI subcommands |
| `Updatable` | `on_update()`, property `version` | the `update` CLI subcommand and `versions` REPL command |
| `Commandable` | `get_commands() -> list[Command]` | extends the REPL with module-specific commands |

`mypycli/modules/interfaces/__init__.py` exports `ALL_INTERFACES` for introspection (used by `cmd_modules`).

`cli/parser.py` discovers interfaces via `ModuleRegistry.by_interface(..., enabled_only=False)`: a subcommand is offered only when ≥1 module implements it. The base parser always has `logs` (with `-n`/`-f`/`--level`/`--module`/`--all`). `cli/runner.py:_ROOT_REQUIRED = {"install", "update", "uninstall"}` — these refuse to run as non-root with a `sudo`/`su -c`/`Run as root.` hint via `_exit_not_root`. `_shared.require_install` exits 1 if any **mandatory** Installable module has no DB section, before runtime commands proceed.

`Module.is_enabled` is "module name is a key under `db.modules`": `Installable.on_install` writes that key, `Application._register_non_installables()` writes `{}` for non-Installable modules at start. Returns `True` before the DB is loaded so the parser sees all modules during construction. Subclasses can override (`@property def is_enabled` returning `False` for hard-disable).

### Database — typed JSON with module sections
`Database[T]` (mypycli/database/store.py) is a single JSON file with three concerns:
- **App schema fields** (`T`, a `DatabaseSchema` subclass): surfaced as `app.db.<field>` via `__getattr__`/`__setattr__` proxy. Schema fields go to `_data`; unknown attributes set on `Database` are stored as instance attrs and *not* persisted.
- **Framework-owned extras**: `db.debug` (bool) and `db.language` (str) — first-class properties backed by `set_extra`/`get_extra`. `db set debug true` / `db set language ru` print "Restart the application…" via `cmd_db_set`.
- **Per-module sections** under `modules.<module.name>` — each module declaring `db_schema` reaches its section via `self.db`. **Each `self.db` access materializes a fresh Pydantic instance from disk** (no caching) so daemon ↔ REPL writes stay coherent. Field assignment routes back through `patch_module_data` for atomic shallow merges.

Auto-save: `DatabaseSchema.__setattr__` fires `_on_patch` (preferred — fires on top-field path) or `_on_save` (zero-arg). `_wire_model` / `_wire_subtree_to_field` recursively bind nested `BaseModel` fields so deep mutations also persist (`mod.db.inner.value = 42` works).

I/O: `read_json_locked` / `write_json_locked` (mypycli/database/utils.py) wrap reads in `fcntl.LOCK_SH` and writes in `fcntl.LOCK_EX` + `os.fsync` for crash-safety. Reads transparently reload when the file `mtime` changes (`_refresh_if_stale`); corrupt JSON warns to the configured logger and keeps the in-memory copy. Concurrent saves don't corrupt the file (covered by `TestThreadSafety`).

`get_by_path` / `set_by_path` / `set_by_path_str` accept dot-paths spanning all three concerns, including `modules.<name>.<field>`. `set_by_path_str` parses bool aliases (`true`/`false`, case-insensitive, trimmed), JSON, then bare strings.

### Two-channel I/O — never mix the channels
This is the load-bearing UX rule. Both `console/console.py` and `logger.py` open with module-level docstrings spelling it out (the only two modules that have module docstrings — D100 is otherwise ignored).
- **`app.console.*`** writes to **stdout** for the REPL UX (banners, prompts, tables, panels, JSON, progress lines). Daemon mode never invokes the console.
- **`self.logger`** / **`app.logger`** writes to a **`RotatingFileHandler`** at `<work_dir>/<name>.log` (`5 * 1_048_576` bytes × 5 backups, `PlainFormatter` — `[LEVEL] timestamp <thread> name: msg`). The logger never touches stdout (a `NullHandler` absorbs records before `enable_file_logging`). Module loggers are `logging.getLogger(f"{app.name}.{module.name}")`.

When adding output, ask "is this UX or a diagnostic?" The answer dictates the channel.

### Console (REPL)
`Console(ConsoleOutput, ConsoleInput)` mixes static-method utilities. Built-in commands (`db show/get/set`, `status`, `modules`, `versions`, `history`, `clear`, `help`, `exit`) come from `console/builtin.py`. User commands are appended via `console.add_command(Command(...))`. `_dispatch` walks `Command.children` recursively. Tab-completion via `readline`; history persists to `<work_dir>/<app.name>.history` as a `_HistorySchema` (capped at 100 entries).

Prompts have two equivalent surfaces: direct methods (`console.input/secret/confirm/select/multiselect`) and declarative dataclasses (`Input/Secret/Confirm/Select/Multiselect` from `mypycli.types`) dispatched by `console.ask`. TTY vs non-TTY behavior diverges — TTY uses `_edit_line` (raw mode, full editor); non-TTY falls back to `input()`/`getpass.getpass()`. Validators returning a string-error retry on TTY (preserved buffer for `Input`, fresh for `Secret`) and raise `ValueError` on non-TTY.

`ProgressLine` (mypycli/console/progress.py) is a context manager. TTY: `\r\x1b[2K` rewrites the line, cursor hidden via `\x1b[?25l`/`\x1b[?25h` (restored on exception via `__exit__`). Non-TTY: standalone lines, no cursor codes. With `total=N` the `update()` auto-prepends a counter `[n/total]` (gray on TTY).

ANSI helpers (mypycli/console/ansi.py): `colorize_text`, `colorize_threshold(value, threshold, logic="less"|"more")`, `render_color_text(str|ColorText)`, `visible_len` (strips ANSI), `box_chars(style_name)` (`ROUNDED`/`SHARP`/`DOUBLE`/`ASCII`, unknown falls back to `ROUNDED`).

### i18n — strict, library + app split
`Translator` (mypycli/i18n/translator.py) eager-loads one flat catalog from `<locales_dir>/<lang>.yml` via `loader.load_flat`. Keys are dotted (`flatten` walks nested dicts). Missing keys **raise** `LookupError` — there is no fallback. `mypycli locales check` runs in CI to catch drift.

YAML rules enforced by the loader:
- Root must be a mapping.
- Keys must be strings (rejects unquoted YAML 1.1 booleans like `yes`/`no`/`on`/`off` — they parse as bool, not str).
- Values must be strings (no ints, lists).
- Leaf-vs-branch collisions raise `FlattenError`.

Library-owned strings live under the `mypycli:` top-level YAML key; downstream-app keys use any other top level. `cmd_sync` updates only the `mypycli:` section, leaving user keys intact.

`mypycli.i18n.internal._` is a process-bound shortcut used by library code (`console/*`). It auto-prefixes keys with `mypycli.` and must be `bind()`-ed before console code runs (`app.start()` does this). The autouse pytest fixture `_reset_i18n_internal` in `tests/conftest.py` binds the real catalog and resets between tests so console handlers exercised directly don't blow up with `RuntimeError("Translator not bound")`.

### Worker / async bridge
`Worker` (mypycli/utils/worker.py) holds named `Task` / `CycleTask` instances. Tasks are daemon threads; `task.stop()` sets a `threading.Event`, but the callable must cooperate. `CycleTask` keeps running on exception (logs and continues) and waits on the stop event between cycles for interruptibility. `Worker.add` raises on duplicate names. `Module.run_task` / `run_cycle` auto-name `<module.name>.<func_or_suffix>` so logs and `threadName` are module-attributed.

Each module also has a lazily-spawned asyncio loop in a daemon thread (`run_async` ↔ `open_async_loop` / `close_async_loop`) for sync-from-async bridging.

### Utilities
`mypycli.utils` re-exports curated helpers (see `utils/__init__.py:__all__`):
- system: `run`, `run_as_root` (sudo→su fallback, cached via `lru_cache`; `CalledProcessError.cmd` is the *unwrapped* args), `is_root`, `is_tty`
- daemon: `read_pid`, `is_alive` (returns `True`/`False`/`None` for EPERM)
- config: `read_config(path, Model)`, `write_config` (atomic via `<path>.tmp` + rename, preserves mode/ownership best-effort)
- errors: `format_validation_error` (one-line `field.path: msg; ...` from a pydantic `ValidationError`)
- convert: `format_bytes`/`format_bitrate` (binary 1024 vs decimal 1000), `format_duration`/`format_time_ago` with `lang: Literal["en", "ru", "zh"]` (Russian plural via `n%10/n%100`), `parse_bytes`/`parse_duration` (e.g. `"1h30m"`)
- network: `ip_to_int`/`int_to_ip` (`signed: bool = True` matters), `is_port_open`, `get_public_ip` (3 services with silent fallthrough — single `# noqa: S112`), `get_network_interface` (Darwin/OpenBSD/Linux), `ping_latency`
- sysinfo: `SysInfo` (each property reads fresh — psutil + `/proc` + sysctl), module-level singleton `sysinfo = SysInfo()`
- service: `SystemdService` / `SystemdTimer` (atomic write via tmp + `mv` as root, then `daemon-reload`)
- github: `RemoteGitRepo` / `LocalGitRepo` / `RepoInfo` / `GitError`, `_parse_git_url` (HTTPS, `git@`, `owner/repo` shorthand, `/tree/<ref>` suffix), PEP 440 version logic via `packaging`
- worker: `Task` / `CycleTask` / `Worker`

## Coding style — match the existing conventions exactly

This codebase has a tight, consistent style. New code must blend in.

### Headers, imports, type-only blocks
- Every `.py` starts with `from __future__ import annotations`. PEP 604 unions everywhere (`X | None`, never `Optional`).
- Import order: stdlib (`import` then `from` within the group) → third-party → `mypycli.*` (`known-first-party = ["mypycli"]`).
- Use `from collections.abc import Callable, Iterable, Iterator, Sequence` — never from `typing`.
- Anything used **only in annotations** lives under `if TYPE_CHECKING:` at the bottom of the imports. Examples: `from pathlib import Path`, `from collections.abc import Callable`, `from mypycli.application import Application`, `import logging`, `import subprocess`, `from typing import Any` (when only annotations need it).
- Aliased internal imports use a leading `_`: `from mypycli.i18n import internal as _i18n_internal`, `import time as _time`.
- The single ruff exception: `from mypycli.types import Color, ColorText  # noqa: TC001` in `console/ansi.py` because `ColorText` is used at runtime via `isinstance`.

### Formatting
- ruff format / `quote-style = "double"`. Line length 120.
- f-strings for interpolation (no `%`-format, no `.format()` outside translation templates).
- No trailing punctuation in error messages destined for `raise` — match existing wording (e.g. `"Translator not bound — did you call app.start()?"`).
- No emojis in code or docstrings (exception: bundled YAML locales and `cmd_init` console output use `✓` / `skip`).

### Comments — almost none
- The code is self-explanatory through naming. Block comments are absent.
- Inline comments only for non-obvious nuance — typically one short clause:
  - `# alive is None means EPERM — process exists but belongs to another user;` (application.py)
  - `# Only the touched field is persisted; defaults live in the schema.` (test)
  - `# ``modules`` is sourced from disk on demand, never cached in memory` (database/store.py)
- Every `# noqa:` carries an em-dash justification. Existing exceptions (study them before adding new ones):
  - `# noqa: S112 — silent fallthrough across services` (network.py:66)
  - `# noqa: PERF203 — continue-on-error is intentional` (uninstall.py, update.py per-module loops)
  - `# noqa: TC001` (ansi.py, runtime use of a TYPE_CHECKING import)

### Docstrings — RST, terse, every param documented when there is one
- Style: reStructuredText. `:param X:`, `:returns:`, `:raises Foo:`. **Never** Google/NumPy.
- Use double-backticks for inline code, types, special values: ``None``, ``True``, ``self.app``, ``Color.RED``, ``[a-z0-9][a-z0-9_-]*``.
- First line is one sentence in the third person, written as a description of behavior: "Load JSON from disk; create with defaults when missing and ``auto_create``." Avoid "This method...", "Returns...".
- Multi-line: summary, blank line, paragraph(s), blank line, `:param:` / `:returns:` / `:raises:` block.
- pydocstyle ignores: `D100` (no module-level docstring), `D101`/`D102`/`D103`/`D105`/`D107` (no required docstring on public class/method/function/magic/`__init__`), `D203`/`D213` (resolves D211/D212 conflicts). Consequence: tiny self-explanatory methods and `__init__` typically have no docstring; the class-level docstring's `:param:` block documents constructor args instead.
- Module-level docstring: only two files have one — `console/console.py` and `logger.py`. They exist solely to document the two-channel rule. Don't add module docstrings elsewhere.
- For `@property`: the first line often *is* the description of the returned value (no `:returns:` needed): "Whether the underlying thread has been started…", "Return the path to the PID file."
- `:cvar X:` documents class variables (see `Module` class docstring).
- Internal helpers with `_` prefix often have a one-line docstring, sometimes none. Match nearby style.

### Type system
- `mypy --strict` with `python_version = "3.10"`, `pretty = true`, `warn_unreachable = true`.
- Enabled extra error codes: `ignore-without-code`, `redundant-cast`, `truthy-bool`. Disabled: `type-abstract`.
- `Generic[T]` with bounded `TypeVar`s declared at module top: `T = TypeVar("T", bound=DatabaseSchema)`, `_R = TypeVar("_R")`.
- `ClassVar[...]` for mutable/typed class attrs (`name: ClassVar[str]`, `mandatory: ClassVar[bool] = False`, `_SUFFIX: ClassVar[str] = ""`).
- `Literal["en", "ru", "zh"]` for closed string sets (locale codes, "less"/"more").
- When silencing pydantic validation in tests: `# type: ignore[arg-type]` or `[assignment]` with the specific code (required by `ignore-without-code`).

### Naming
- `snake_case` functions/methods/locals. `PascalCase` classes. `UPPER_SNAKE` module-level constants (`_BYTE_UNITS`, `_NAME_RE`, `_DURATION_FORMS`, `SYSTEMD_DIR`, `_LIB_LOCALES`, `_ROOT_REQUIRED`, `DEFAULT_DATEFMT`).
- Private helpers and constants prefixed `_` (`_read_key`, `_clear_lines`, `_resolve_message`, `_HistorySchema`).
- ANSI/control char constants spelled out as `_ARROW_UP`, `_CTRL_C`, `_BACKSPACE_KEYS`, `_POINTER`, `_RADIO_ON`.
- Unused parameters get a `_` prefix: `def cmd_clear(_app, _args)`, `def __exit__(self, exc_type, exc, tb)`.
- Test classes group cases: `class TestX:` with `def test_some_specific_behavior_described_in_full(self): ...`. Module-level fixture/helper classes use `_` prefix: `_Plain`, `_Schema`, `_DaemonicMod`.

### Class patterns
- `@dataclass(frozen=True)` for value/snapshot types (every `mypycli.types.sysinfo` class, `ColorText`, all prompts in `mypycli.types.prompts`, `RepoInfo`).
- `@dataclass` (mutable) only when callers are expected to construct *and* mutate (`Command`).
- `field(default_factory=list)` for mutable defaults; never bare `[]` / `{}` as defaults.
- `@cached_property` for derived values that depend on stable upstream state and are expensive (`LocalGitRepo.author/repo_name/remote`). When state changes, invalidate explicitly: `self.__dict__.pop(cached, None)` (see `LocalGitRepo.set_origin`).
- `Enum`s use lowercase string values: `RED = "red"`. ANSI codes live separately in `_COLOR_CODES`.
- `IntEnum` only when the integer values are meaningful — `ByteUnit(int, Enum)` with `KB = 1024`.
- Pydantic models for: schema (`DatabaseSchema(BaseModel)` with `ConfigDict(validate_assignment=True, populate_by_name=True)`), config files (`read_config(path, Model)`).
- ABC + `@abstractmethod` for capability interfaces; pair with `Module` (e.g. `class Daemonic(Module, ABC):`).

### Error handling
- Custom exceptions inherit `Exception` (`GitError`) or a more specific built-in (`FlattenError(ValueError)`). One-line class with a docstring describing when it's raised; no extra members.
- `raise X(...) from e` whenever re-raising — preserves cause; explicit `from None` when intentionally suppressing (`raise SystemExit(130) from None`).
- `contextlib.suppress(...)` for truly best-effort fallbacks (config.py chown).
- CLI exits use `raise SystemExit(N)` with a stderr message printed first via `print(..., file=sys.stderr)`. Codes: `1` for failure, `130` for KeyboardInterrupt.
- Catch tuples are concrete: `except (FileNotFoundError, ValueError, OSError):` — never bare `except:`.
- Per-module loops in `run_uninstall` / `run_update` collect failures into `failed: list[tuple[str, Exception]]` and call `exit_with_failures` after the loop (continue-on-error is intentional).

### Threading
- `daemon=True` on every background `Thread`.
- `threading.Event` for cooperative cancellation; `threading.RLock` when methods can re-enter (Database); `threading.Lock` for simple critical sections (Worker registry).
- Reads/writes that must be durable: `fcntl.LOCK_EX` + `os.fsync` (database/utils.py).

### Pydantic / Database wiring
- `model_validate(raw)`, `model_dump(...)`, `model_dump_json(...)` — Pydantic 2 API.
- `model_fields` (class attr, dict) for iteration; `model_config = ConfigDict(...)` for settings.
- Internal hooks set via `object.__setattr__(model, "_on_save", cb)` to bypass Pydantic's `__setattr__` machinery.
- `_wire_model` recursion: when assigning a fresh `BaseModel` to a field, call `_wire_subtree_to_field` so descendants also fire on mutation.

### Tests
- `pytest` (no other framework). `testpaths = ["tests"]`.
- `from __future__ import annotations` + `if TYPE_CHECKING:` blocks for `Path`, `MonkeyPatch`, `CaptureFixture`.
- Test classes group related cases (`class TestX:`); standalone `def test_*` functions for one-off behaviors.
- Fixture/helper classes inside tests use `_` prefix and ClassVar names matching the regex (`_DaemonicMod`, `_InstallableMod`).
- `@pytest.mark.parametrize(("key1", "key2"), [(...), ...])` — tuple of names for clarity, even with one parameter.
- Standard mock pattern for app-shaped objects:
  ```python
  app = MagicMock()
  app.name = "test"
  app.db.is_loaded = False  # keep Module.is_enabled True pre-load
  registry = ModuleRegistry()
  for cls in module_classes:
      registry.register(cls(app))
  app.modules = registry
  ```
- `app.start.side_effect = lambda: app.db.load(auto_create=True)` to simulate the real start path.
- `pytest.raises(X, match="…")` with a regex/substring of the user-visible message.
- Direct access to dunder/private attrs from tests is allowed when needed: `db._data`, `internal._active = None`. Don't extend this to production code.
- Test names spell out the behavior in full: `test_corrupt_json_keeps_current_data`, `test_external_modification_detected`, `test_command_in_error_is_unwrapped_original`. Avoid `test_x_works`.
- Per-file ruff overrides for `tests/**`: ignored S101 (assert), S104/105/106 (binds/passwords), B017 (broad raises), D (docstrings), RUF012 (mutable class defaults).

### Ruff selection (don't drift from this in new code)
Active rule sets: D, E, W, F, I, B, C4, UP, SIM, TCH, PERF, T10, T20, PIE, PLE, RET, RUF, S.

Project-wide ignores (in pyproject.toml — don't repeat as `# noqa`):
- `D100/D101/D102/D103/D105/D107/D203/D213` (see Docstrings above)
- `T201` (`print()` is intentional — the framework writes user-facing UX directly)
- `S603/S605/S607` (subprocess without full path / shell — intentional for system commands)
- `S108` (`/tmp` usage intentional)

Per-file ignores: `__init__.py` → F401, D104; `tests/**` → S101, S104, S105, S106, B017, D, RUF012.

### File layout pattern
A typical file lays out in this order:
1. `from __future__ import annotations`
2. stdlib imports
3. third-party imports
4. mypycli imports
5. `if TYPE_CHECKING:` block
6. Module-level constants (`UPPER_SNAKE`, regex `re.compile(...)`)
7. Public classes (with full class-level docstrings)
8. Public functions
9. Private helpers (`_` prefix, often small)
10. Module-level singletons (`sysinfo = SysInfo()`)

`__init__.py` files contain *only* re-exports and a sorted `__all__` list — no logic.

### Public API surface
Top-level `mypycli`: `Application`, `Module`, all 6 interfaces, `ModuleRegistry`, `Database`, `DatabaseSchema`, `Translator`. `mypycli.types`: enums, dataclasses, `Command`, prompts, sysinfo result types. `mypycli.utils`: utilities listed above. Adding to the public API means re-exporting from these `__init__.py`s and updating `__all__` (kept alphabetically sorted).

When introducing a **new module interface**: add the file under `mypycli/modules/interfaces/`, re-export from `interfaces/__init__.py` (and add to `ALL_INTERFACES`), re-export from `modules/__init__.py` and the top-level `mypycli/__init__.py`, then — if it should expose a CLI subcommand — wire detection into `cli/parser.py:build_parser` and a handler in `cli/commands/` (re-exported from `cli/commands/__init__.py`); register the dispatch branch in `cli/runner.py:run`. Decide whether the command needs root (`_ROOT_REQUIRED`) and whether `require_install(app)` should run first.

## Quick reference — gotchas worth re-checking before edits

- `Module` class declaration: list interfaces only — adding `Module` again triggers MRO failure.
- `self.db` returns a *fresh* instance every call. Storing the reference and mutating later is fine (auto-save still wires up), but don't compare identity (`mod.db is mod.db` is `False` — there's a test for this).
- `db.debug` and `db.language` are framework-owned extras, not schema fields. They are written even on first auto-create.
- Translator missing key → `LookupError`. There is no fallback; CI catches drift.
- `print()` is the UX channel; `logger.*` is the diagnostics channel. Don't route diagnostics to stdout, and don't route UX to the logger.
- New Python files start with `from __future__ import annotations`. Use `if TYPE_CHECKING:` for annotation-only imports.
- No module-level docstrings (D100 is ignored on purpose). Two existing exceptions document the two-channel rule.
- `# noqa:` always carries an em-dash justification.
- The bundled `.venv` runs Python 3.9; `pytest` from it will pick up `from __future__ import annotations`-friendly code but `requires-python = ">=3.10"`. Run tests in a 3.10+ environment.
