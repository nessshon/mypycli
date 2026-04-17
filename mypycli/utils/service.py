from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from mypycli.utils.system import run, run_as_root

if TYPE_CHECKING:
    import subprocess

SYSTEMD_DIR = Path("/etc/systemd/system")


class _SystemdUnit:
    """Shared control and inspection of a systemd unit under ``/etc/systemd/system``.

    :param name: Unit name without the suffix (``.service``/``.timer``).
    """

    _SUFFIX: ClassVar[str] = ""

    def __init__(self, name: str) -> None:
        self.name = name
        self._unit = f"{name}{self._SUFFIX}"
        self._unit_path = SYSTEMD_DIR / self._unit

    def start(self) -> None:
        """Start the unit via ``systemctl start``."""
        self._systemctl("start", self._unit)

    def stop(self) -> None:
        """Stop the unit via ``systemctl stop``."""
        self._systemctl("stop", self._unit)

    def enable(self) -> None:
        """Enable the unit so it activates automatically on boot."""
        self._systemctl("enable", self._unit)

    def disable(self) -> None:
        """Disable autostart on boot without stopping an active unit."""
        self._systemctl("disable", self._unit)

    def remove(self) -> None:
        """Stop, disable, delete the unit file, and reload systemd."""
        self._systemctl("stop", self._unit)
        self._systemctl("disable", self._unit)
        if self._unit_path.exists():
            run_as_root(["rm", str(self._unit_path)])
        self._daemon_reload()

    @property
    def is_active(self) -> bool:
        """Whether ``systemctl is-active`` reports the unit as currently running."""
        return self._query("is-active", self._unit).returncode == 0

    @property
    def is_enabled(self) -> bool:
        """Whether ``systemctl is-enabled`` reports the unit as configured to start on boot."""
        return self._query("is-enabled", self._unit).returncode == 0

    @property
    def exists(self) -> bool:
        """Whether the unit file is present under ``/etc/systemd/system``."""
        return self._unit_path.exists()

    @staticmethod
    def _systemctl(command: str, unit: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a privileged ``systemctl`` command against ``unit``."""
        return run_as_root(["systemctl", command, unit, *args])

    @staticmethod
    def _query(command: str, unit: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Read-only ``systemctl`` query; does not escalate so it never prompts for a password."""
        return run(["systemctl", command, unit, *args], capture=True)

    @staticmethod
    def _daemon_reload() -> None:
        """Run ``systemctl daemon-reload`` as root; raises on failure."""
        result = run_as_root(["systemctl", "daemon-reload"])
        if result.returncode != 0:
            raise RuntimeError("systemctl daemon-reload failed")

    @staticmethod
    def _write_unit(path: Path, content: str) -> None:
        """Write ``content`` to ``path`` atomically via a temp file and ``mv`` as root."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=path.suffix,
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(content)
            tmp_path = f.name
        result = run_as_root(["mv", tmp_path, str(path)])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to write unit file: {path}")


class SystemdService(_SystemdUnit):
    """Create, control, and inspect a systemd ``.service`` unit."""

    _SUFFIX: ClassVar[str] = ".service"

    def create(
        self,
        *,
        exec_start: str,
        user: str,
        group: str | None = None,
        work_dir: str | None = None,
        environment: dict[str, str] | None = None,
        description: str = "",
        after: str = "network.target",
        restart: str = "on-failure",
        restart_sec: int = 10,
        service_type: str = "simple",
    ) -> None:
        """Write the ``.service`` unit file atomically and run ``systemctl daemon-reload``.

        :param exec_start: Command line for ``ExecStart=``.
        :param user: ``User=`` to run the service as.
        :param group: ``Group=`` override; falls back to ``user`` when ``None``.
        :param work_dir: ``WorkingDirectory=``; omitted when ``None``.
        :param environment: Mapping written as one ``Environment=KEY=VALUE`` line per entry.
        :param description: ``Description=``; falls back to the service name when empty.
        :param after: ``After=`` ordering dependency.
        :param restart: ``Restart=`` policy; ignored for ``oneshot`` services.
        :param restart_sec: ``RestartSec=`` in seconds; ignored for ``oneshot``.
        :param service_type: ``Type=`` value (``simple``, ``forking``, ``oneshot``, ...).
        :raises RuntimeError: If writing the unit file or daemon-reload fails.
        """
        lines = [
            "[Unit]",
            f"Description={description or self.name}",
            f"After={after}",
            "",
            "[Service]",
            f"Type={service_type}",
            f"User={user}",
            f"Group={group or user}",
        ]

        if work_dir:
            lines.append(f"WorkingDirectory={work_dir}")

        if environment:
            for key, value in environment.items():
                lines.append(f"Environment={key}={value}")

        lines.append(f"ExecStart={exec_start}")

        if service_type != "oneshot":
            lines.append(f"Restart={restart}")
            lines.append(f"RestartSec={restart_sec}")

        lines.extend(["", "[Install]", "WantedBy=multi-user.target", ""])

        self._write_unit(self._unit_path, "\n".join(lines))
        self._daemon_reload()

    def restart(self) -> None:
        """Restart the service via ``systemctl restart``."""
        self._systemctl("restart", self._unit)

    @property
    def uptime(self) -> int | None:
        """Seconds elapsed since the service entered the active state, or ``None`` if inactive."""
        if not self.is_active:
            return None
        result = self._query("show", self._unit, "--property=ActiveEnterTimestampMonotonic")
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
        prefix = "ActiveEnterTimestampMonotonic="
        if not line.startswith(prefix):
            return None
        start_usec = int(line[len(prefix) :])
        now_usec = int(time.clock_gettime(time.CLOCK_MONOTONIC) * 1_000_000)
        return (now_usec - start_usec) // 1_000_000

    @property
    def pid(self) -> int | None:
        """Main PID of the service process; ``None`` when the service is not running."""
        result = self._query("show", self._unit, "--property=MainPID")
        if result.returncode != 0:
            return None
        line = result.stdout.strip()
        prefix = "MainPID="
        if not line.startswith(prefix):
            return None
        pid = int(line[len(prefix) :])
        return pid if pid > 0 else None


class SystemdTimer(_SystemdUnit):
    """Create, control, and inspect a systemd ``.timer`` unit.

    The generated timer activates the service sharing its ``name``; that target
    service must be created separately via ``SystemdService``.
    """

    _SUFFIX: ClassVar[str] = ".timer"

    def create(
        self,
        *,
        on_calendar: str = "daily",
        persistent: bool = True,
        description: str = "",
    ) -> None:
        """Write the ``.timer`` unit file atomically and run ``systemctl daemon-reload``.

        :param on_calendar: ``OnCalendar=`` expression (e.g. ``daily``, ``*-*-* 03:00:00``).
        :param persistent: When ``True``, runs immediately on boot if the last scheduled run was missed.
        :param description: ``Description=``; falls back to ``"<name> timer"`` when empty.
        :raises RuntimeError: If writing the unit file or daemon-reload fails.
        """
        lines = [
            "[Unit]",
            f"Description={description or f'{self.name} timer'}",
            "",
            "[Timer]",
            f"OnCalendar={on_calendar}",
            f"Persistent={'true' if persistent else 'false'}",
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ]
        self._write_unit(self._unit_path, "\n".join(lines))
        self._daemon_reload()
