from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path

import psutil

from mypycli.types.sysinfo import (
    CpuInfo,
    DiskIO,
    DiskSpace,
    HardwareInfo,
    MemoryInfo,
    NetworkIO,
    OsInfo,
)


class SysInfo:
    """Collector of system hardware, OS, and I/O snapshots; every property query returns fresh data."""

    @property
    def cpu(self) -> CpuInfo:
        """CPU model name, logical/physical core counts, and 1/5/15-minute load averages.

        Load averages fall back to 0.0 on platforms without ``os.getloadavg`` (e.g. Windows).
        """
        try:
            load_1m, load_5m, load_15m = os.getloadavg()
        except (OSError, AttributeError):
            load_1m = load_5m = load_15m = 0.0
        return CpuInfo(
            name=_read_cpu_name(),
            count_logical=psutil.cpu_count(logical=True) or 1,
            count_physical=psutil.cpu_count(logical=False) or 1,
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
        )

    @property
    def ram(self) -> MemoryInfo:
        """Physical RAM snapshot with ``available`` reflecting memory reclaimable without swapping."""
        m = psutil.virtual_memory()
        return MemoryInfo(
            total=m.total,
            used=m.used,
            free=m.free,
            available=m.available,
            percent=m.percent,
        )

    @property
    def swap(self) -> MemoryInfo:
        """Swap space snapshot; ``available`` equals ``free`` since swap has no reclaimable equivalent."""
        s = psutil.swap_memory()
        return MemoryInfo(
            total=s.total,
            used=s.used,
            free=s.free,
            available=s.free,
            percent=s.percent,
        )

    @property
    def os(self) -> OsInfo:
        """OS identification (name, release, version, architecture), sourced from ``os.uname`` where available."""
        if hasattr(os, "uname"):
            u = os.uname()
            return OsInfo(name=u.sysname, release=u.release, version=u.version, arch=u.machine)
        return OsInfo(
            name=platform.system(),
            release=platform.release(),
            version=platform.version(),
            arch=platform.machine(),
        )

    @property
    def hardware(self) -> HardwareInfo:
        """Hardware identity read from Linux DMI (``/sys/class/dmi/id/product_name``); empty on non-Linux."""
        return HardwareInfo(product_name=_read_product_name())

    @property
    def uptime(self) -> int:
        """Whole seconds elapsed since the kernel boot time."""
        return int(time.time() - psutil.boot_time())

    @property
    def all_disk_usage(self) -> dict[str, DiskSpace]:
        """Usage per mounted physical filesystem keyed by mount point; entries that error on ``statvfs`` are skipped."""
        result: dict[str, DiskSpace] = {}
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            result[part.mountpoint] = DiskSpace(
                path=part.mountpoint,
                total=u.total,
                used=u.used,
                free=u.free,
                percent=u.percent,
                device=_short_device(part.device),
            )
        return result

    @property
    def all_disk_io(self) -> dict[str, DiskIO]:
        """Per-disk cumulative I/O counters keyed by device name; empty when psutil reports no data."""
        raw = psutil.disk_io_counters(perdisk=True)
        if not raw:
            return {}
        return {name: _make_disk_io(stats) for name, stats in raw.items()}

    @property
    def all_network_io(self) -> dict[str, NetworkIO]:
        """Per-interface cumulative network I/O counters keyed by interface name."""
        raw = psutil.net_io_counters(pernic=True)
        return {
            name: NetworkIO(
                bytes_sent=s.bytes_sent,
                bytes_recv=s.bytes_recv,
                packets_sent=s.packets_sent,
                packets_recv=s.packets_recv,
            )
            for name, s in raw.items()
        }

    @staticmethod
    def get_disk_usage(path: str) -> DiskSpace:
        """Disk usage for the filesystem containing ``path``.

        The backing device is resolved by longest mount-point match.

        :param path: Filesystem path to query.
        :raises OSError: If the path does not exist or cannot be stat'ed.
        """
        u = psutil.disk_usage(path)
        return DiskSpace(
            path=path,
            total=u.total,
            used=u.used,
            free=u.free,
            percent=u.percent,
            device=_device_for_path(path),
        )

    def get_disk_io(self, device: str) -> DiskIO | None:
        """Look up I/O counters for a single disk by short device name.

        :param device: Device name without the ``/dev/`` prefix.
        :returns: DiskIO for the device, or ``None`` if unknown to the kernel.
        """
        return self.all_disk_io.get(device)

    def get_network_io(self, interface: str) -> NetworkIO | None:
        """Look up I/O counters for a single network interface by name.

        :param interface: Network interface name.
        :returns: NetworkIO for the interface, or ``None`` if the interface does not exist.
        """
        return self.all_network_io.get(interface)


sysinfo = SysInfo()


def _read_cpu_name() -> str | None:
    """Read the CPU model string from ``/proc/cpuinfo`` on Linux or ``sysctl machdep.cpu.brand_string`` on macOS."""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    _, _, value = line.partition(":")
                    return value.strip() or None
    except OSError:
        pass

    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode == 0:
            return result.stdout.strip() or None
    return None


def _read_product_name() -> str | None:
    """Read the DMI product name on Linux and return it lowercased; ``None`` when unavailable."""
    try:
        value = Path("/sys/class/dmi/id/product_name").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value.lower() or None


def _short_device(device: str) -> str | None:
    """Strip a leading ``/dev/`` from a device path; ``None`` if the input is empty.

    :param device: Device path to shorten.
    """
    if not device:
        return None
    if device.startswith("/dev/"):
        return device[len("/dev/") :]
    return device


def _device_for_path(path: str) -> str | None:
    """Resolve the backing device of ``path`` by picking the partition with the longest matching mount point.

    :param path: Filesystem path to resolve.
    """
    try:
        abs_path = os.path.realpath(path)
    except OSError:
        return None

    best_device: str | None = None
    best_len = -1
    for part in psutil.disk_partitions(all=False):
        mp = part.mountpoint
        matches = abs_path == mp or abs_path.startswith(mp.rstrip("/") + "/")
        if matches and len(mp) > best_len:
            best_device = _short_device(part.device)
            best_len = len(mp)
    return best_device


def _make_disk_io(stats: object) -> DiskIO:
    """Convert a psutil disk I/O counter into a DiskIO, defaulting missing fields to 0.

    ``busy_time`` is absent on macOS and Windows, so ``busy_time_ms`` falls back to 0 there.

    :param stats: psutil disk I/O counter object.
    """
    return DiskIO(
        read_bytes=getattr(stats, "read_bytes", 0),
        write_bytes=getattr(stats, "write_bytes", 0),
        read_count=getattr(stats, "read_count", 0),
        write_count=getattr(stats, "write_count", 0),
        busy_time_ms=getattr(stats, "busy_time", 0),
    )
