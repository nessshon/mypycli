import os
import re
import shutil
import time
from pathlib import Path

import psutil

from mypycli.types import (
    CpuInfo,
    DiskIOInfo,
    DiskSpaceInfo,
    HardwareInfo,
    MemoryInfo,
    NetworkIOInfo,
    OSInfo,
)

_IGNORE_DISK_RE = re.compile(r"^(loop|ram|zram|md|dm-|fd|sr)")


class SysInfo:
    @property
    def uptime(self) -> int:
        return int(time.time() - psutil.boot_time())

    @property
    def os(self) -> OSInfo:
        uname = os.uname()
        return OSInfo(
            name=uname.sysname,
            release=uname.release,
            version=uname.version,
            machine=uname.machine,
        )

    @property
    def hardware(self) -> HardwareInfo:
        product_name = _detect_product_name()
        is_virtualized = None
        if product_name is not None:
            markers = ("virtual", "kvm", "qemu", "vmware")
            is_virtualized = any(m in product_name.lower() for m in markers)
        return HardwareInfo(
            product_name=product_name,
            is_virtualized=is_virtualized,
        )

    @property
    def cpu(self) -> CpuInfo:
        try:
            load1, load5, load15 = os.getloadavg()
        except (OSError, AttributeError):
            load1 = load5 = load15 = 0.0
        return CpuInfo(
            name=_detect_cpu_name(),
            count_logical=psutil.cpu_count(logical=True) or 1,
            count_physical=psutil.cpu_count(logical=False) or 1,
            load_1m=load1,
            load_5m=load5,
            load_15m=load15,
        )

    @property
    def ram(self) -> MemoryInfo:
        memory = psutil.virtual_memory()
        return MemoryInfo(
            total=memory.total,
            used=memory.used,
            free=memory.free,
            usage_percent=memory.percent,
        )

    @property
    def swap(self) -> MemoryInfo:
        memory = psutil.swap_memory()
        return MemoryInfo(
            total=memory.total,
            used=memory.used,
            free=memory.free,
            usage_percent=memory.percent,
        )

    @property
    def disks_usage(self) -> dict[str, DiskSpaceInfo]:
        result: dict[str, DiskSpaceInfo] = {}
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            result[part.mountpoint] = DiskSpaceInfo(
                path=part.mountpoint,
                total=usage.total,
                used=usage.used,
                free=usage.free,
                usage_percent=usage.percent,
                device_name=part.device,
            )
        return result

    @property
    def disks_io(self) -> dict[str, DiskIOInfo]:
        result: dict[str, DiskIOInfo] = {}
        raw = psutil.disk_io_counters(perdisk=True)
        whole_disks = _list_whole_disks()
        for name, stats in raw.items():
            if _IGNORE_DISK_RE.match(name):
                continue
            if whole_disks is not None and name not in whole_disks:
                continue
            result[name] = DiskIOInfo(
                read_bytes=stats.read_bytes,
                write_bytes=stats.write_bytes,
                read_count=stats.read_count,
                write_count=stats.write_count,
                busy_time=getattr(stats, "busy_time", 0),
            )
        return result

    @property
    def networks_io(self) -> dict[str, NetworkIOInfo]:
        result: dict[str, NetworkIOInfo] = {}
        raw = psutil.net_io_counters(pernic=True)
        for name, stats in raw.items():
            result[name] = NetworkIOInfo(
                bytes_sent=stats.bytes_sent,
                bytes_recv=stats.bytes_recv,
                packets_sent=stats.packets_sent,
                packets_recv=stats.packets_recv,
            )
        return result

    @staticmethod
    def get_disk_usage(target: str) -> DiskSpaceInfo:
        path, device = _detect_disk_target(target)
        total_space, used_space, free_space = shutil.disk_usage(path)
        usage_percent = round(used_space / total_space * 100, 1) if total_space else 0.0
        return DiskSpaceInfo(
            path=path,
            total=total_space,
            used=used_space,
            free=free_space,
            usage_percent=usage_percent,
            device_name=device,
        )

    @staticmethod
    def get_disk_io(target: str) -> DiskIOInfo:
        _path, device = _detect_disk_target(target)
        if device is None:
            raise ValueError(f"Cannot resolve device for: {target}")

        key = device.removeprefix("/dev/")
        counters = psutil.disk_io_counters(perdisk=True)
        if key not in counters:
            raise KeyError(f"No I/O counters for device: {device} (target={target})")

        stats = counters[key]
        return DiskIOInfo(
            read_bytes=stats.read_bytes,
            write_bytes=stats.write_bytes,
            read_count=stats.read_count,
            write_count=stats.write_count,
            busy_time=getattr(stats, "busy_time", 0),
        )

    def get_network_io(self, interface: str) -> NetworkIOInfo:
        nics = self.networks_io
        if interface not in nics:
            raise KeyError(f"Unknown interface: {interface}. Available: {', '.join(nics)}")
        return nics[interface]


def _list_whole_disks() -> frozenset[str] | None:
    try:
        return frozenset(os.listdir("/sys/block"))
    except OSError:
        return None


def _detect_cpu_name() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.rstrip("\n").startswith("model name"):
                    return line.partition(":")[2].strip()
    except FileNotFoundError:
        pass
    return None


def _detect_product_name() -> str | None:
    try:
        with open("/sys/class/dmi/id/product_name", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        pass
    return None


def _detect_disk_target(target: str) -> tuple[str, str | None]:
    partitions = psutil.disk_partitions(all=False)
    is_device_path = target.startswith("/dev/")
    is_bare_device = "/" not in target

    if is_device_path or is_bare_device:
        device = f"/dev/{target}" if is_bare_device else target
        for part in partitions:
            if part.device == device:
                return part.mountpoint, device
        return "", device

    resolved = Path(target).resolve()
    for part in sorted(partitions, key=lambda p: len(p.mountpoint), reverse=True):
        if resolved.is_relative_to(part.mountpoint):
            return target, part.device

    return target, None


sysinfo = SysInfo()
