import tempfile
import time
from pathlib import Path

import psutil

from mypycli.types import ServiceStatus
from mypycli.utils.system import run, run_as_root

SYSTEMD_DIR = Path("/etc/systemd/system")


class SystemdService:
    def __init__(self, name: str) -> None:
        self.name = name
        self.unit = f"{name}.service"
        self.unit_path = SYSTEMD_DIR / self.unit

    def create(
        self,
        *,
        user: str,
        group: str | None = None,
        work_dir: str | None = None,
        description: str = "",
        exec_start: str,
        exec_stop_post: str | None = None,
        after: str = "network.target",
        restart: str = "always",
        restart_sec: int = 30,
        service_type: str = "simple",
        environment: dict[str, str] | None = None,
        extra: dict[str, str] | None = None,
    ) -> None:
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
        if exec_stop_post is None:
            exec_stop_post = f"/bin/echo {self.name} service down"

        lines.append(f"ExecStart={exec_start}")
        lines.append(f"ExecStopPost={exec_stop_post}")

        if service_type != "oneshot":
            lines.append(f"Restart={restart}")
            lines.append(f"RestartSec={restart_sec}")
        if extra:
            for key, value in extra.items():
                lines.append(f"{key}={value}")

        lines.extend(["", "[Install]", "WantedBy=multi-user.target", ""])

        self._write_unit("\n".join(lines))
        self._daemon_reload()

    def remove(self) -> None:
        self.stop()
        self.disable()
        if self.unit_path.exists():
            run_as_root(["rm", str(self.unit_path)])
        self._daemon_reload()

    def start(self) -> None:
        run_as_root(["systemctl", "start", self.unit])

    def stop(self) -> None:
        run_as_root(["systemctl", "stop", self.unit])

    def restart(self) -> None:
        run_as_root(["systemctl", "restart", self.unit])

    def enable(self) -> None:
        run_as_root(["systemctl", "enable", self.unit])

    def disable(self) -> None:
        run_as_root(["systemctl", "disable", self.unit])

    @property
    def exists(self) -> bool:
        return self.unit_path.exists()

    @property
    def is_enabled(self) -> bool:
        result = run(["systemctl", "is-enabled", self.unit], capture=True)
        return result.returncode == 0

    def status(self) -> ServiceStatus:
        result = run(
            [
                "systemctl",
                "show",
                self.unit,
                "--property=ActiveState,MainPID",
            ],
            capture=True,
        )

        active = False
        pid: int | None = None
        if result.returncode == 0:
            for raw in result.stdout.splitlines():
                key, _, value = raw.partition("=")
                value = value.strip()
                if key == "ActiveState":
                    active = value in ("active", "reloading")
                elif key == "MainPID":
                    pid = self._parse_pid(value)

        uptime = self._parse_uptime(pid) if active else None
        return ServiceStatus(active=active, pid=pid, uptime=uptime)

    def _write_unit(self, content: str) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".service",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = run_as_root(["install", "-m", "644", tmp_path, str(self.unit_path)])
            if result.returncode != 0:
                raise RuntimeError(f"failed to write unit file: {self.unit_path}")
        finally:
            Path(tmp_path).unlink()

    @staticmethod
    def _daemon_reload() -> None:
        result = run_as_root(["systemctl", "daemon-reload"])
        if result.returncode != 0:
            raise RuntimeError("systemctl daemon-reload failed")

    @staticmethod
    def _parse_uptime(pid: int | None) -> int | None:
        if pid is None:
            return None
        try:
            uptime = int(time.time() - psutil.Process(pid).create_time())
            return max(0, uptime)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    @staticmethod
    def _parse_pid(value: str) -> int | None:
        try:
            pid = int(value)
        except ValueError:
            pid = 0
        return pid if pid > 0 else None
