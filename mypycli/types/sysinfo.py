from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CpuInfo:
    """CPU snapshot with identification and load averages.

    :param name: CPU model name, or ``None`` if unavailable.
    :param count_logical: Number of logical cores.
    :param count_physical: Number of physical cores.
    :param load_1m: System load average over the last 1 minute.
    :param load_5m: System load average over the last 5 minutes.
    :param load_15m: System load average over the last 15 minutes.
    """

    name: str | None
    count_logical: int
    count_physical: int
    load_1m: float
    load_5m: float
    load_15m: float


@dataclass(frozen=True)
class MemoryInfo:
    """Memory snapshot for RAM or swap.

    :param total: Total memory in bytes.
    :param used: Used memory in bytes.
    :param free: Truly unused memory in bytes.
    :param available: Memory available for allocation; for RAM includes reclaimable cache, for swap equals ``free``.
    :param percent: Usage percentage in the ``0..100`` range.
    """

    total: int
    used: int
    free: int
    available: int
    percent: float


@dataclass(frozen=True)
class DiskSpace:
    """Disk usage snapshot for a filesystem path.

    :param path: Filesystem path that was queried.
    :param total: Total disk space in bytes.
    :param used: Used space in bytes.
    :param free: Free space in bytes.
    :param percent: Usage percentage in the ``0..100`` range.
    :param device: Backing device name, or ``None`` if unavailable.
    """

    path: str
    total: int
    used: int
    free: int
    percent: float
    device: str | None


@dataclass(frozen=True)
class OsInfo:
    """Operating system identification.

    :param name: OS name.
    :param release: Kernel or OS release identifier.
    :param version: Full version string.
    :param arch: Machine architecture.
    """

    name: str
    release: str
    version: str
    arch: str


@dataclass(frozen=True)
class HardwareInfo:
    """Hardware identification derived from DMI.

    :param product_name: Lowercased DMI product name, or ``None`` if unavailable.
    """

    product_name: str | None

    @property
    def is_virtualized(self) -> bool | None:
        """Report whether the system appears to run under virtualization.

        :returns: ``True`` if known virtualization markers match, ``False`` otherwise,
            or ``None`` if ``product_name`` is unavailable.
        """
        if self.product_name is None:
            return None
        markers = ("virtual", "kvm", "qemu", "vmware", "xen", "hyperv", "bochs")
        return any(m in self.product_name for m in markers)


@dataclass(frozen=True)
class DiskIO:
    """Cumulative disk I/O counters since boot.

    :param read_bytes: Total bytes read.
    :param write_bytes: Total bytes written.
    :param read_count: Total number of read operations.
    :param write_count: Total number of write operations.
    :param busy_time_ms: Total time spent servicing I/O, in milliseconds.
    """

    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int
    busy_time_ms: int


@dataclass(frozen=True)
class NetworkIO:
    """Cumulative network I/O counters since boot.

    :param bytes_sent: Total bytes transmitted.
    :param bytes_recv: Total bytes received.
    :param packets_sent: Total packets transmitted.
    :param packets_recv: Total packets received.
    """

    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
