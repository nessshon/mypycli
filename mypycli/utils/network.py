from __future__ import annotations

import ipaddress
import json
import platform
import socket
import struct
import subprocess

from mypycli.utils.system import run


def ip_to_int(addr: str, *, signed: bool = True) -> int:
    """Convert a dotted-quad IPv4 address to its 32-bit network-order integer form.

    :param addr: Dotted-quad IPv4 address.
    :param signed: When ``True`` (default) interprets the 32 bits as signed
        (``!i``); ``False`` yields unsigned (``!I``).
    """
    fmt = "!i" if signed else "!I"
    result: int = struct.unpack(fmt, socket.inet_aton(addr))[0]
    return result


def int_to_ip(value: int, *, signed: bool = True) -> str:
    """Convert a 32-bit network-order integer back to a dotted-quad IPv4 address.

    :param value: 32-bit integer encoding of an IPv4 address.
    :param signed: Must match the ``signed`` flag used to encode the integer (default ``True``).
    """
    fmt = "!i" if signed else "!I"
    return socket.inet_ntoa(struct.pack(fmt, value))


def is_port_open(host: str, port: int, *, timeout: float = 3) -> bool:
    """Return whether a TCP connection to ``host:port`` succeeds within ``timeout`` seconds.

    :param host: Target hostname or IP address.
    :param port: TCP port to probe.
    :param timeout: Connection timeout in seconds.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def get_public_ip(*, timeout: float = 10) -> str | None:
    """Query external echo services to discover the host's public IPv4 (requires network).

    Tries ifconfig.me, ipinfo.io, and ipify in order, validating each response as IPv4.

    :param timeout: Per-service request timeout in seconds.
    :returns: Public IPv4 string, or ``None`` if all services failed.
    """
    import requests

    services = (
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
        "https://api.ipify.org",
    )
    for url in services:
        try:
            text = requests.get(url, timeout=timeout).text.strip()
            ipaddress.IPv4Address(text)
        except Exception:  # noqa: S112 — silent fallthrough across services
            continue
        return text
    return None


def get_network_interface() -> str | None:
    """Detect the system's default-route network interface name.

    Uses ``ifconfig egress`` on OpenBSD, ``route -n get default`` on macOS, and ``ip --json route`` on Linux.

    :returns: Interface name, or ``None`` if the platform tool fails or output cannot be parsed.
    """
    system = platform.system()

    if system == "OpenBSD":
        try:
            result = run(["ifconfig", "egress"], timeout=5)
            return result.stdout.split(":")[0]
        except (subprocess.TimeoutExpired, IndexError):
            return None

    if system == "Darwin":
        try:
            result = run(["route", "-n", "get", "default"], timeout=5)
            for line in result.stdout.splitlines():
                if "interface" in line:
                    return line.split(":")[1].strip()
        except (subprocess.TimeoutExpired, IndexError):
            return None
        return None

    try:
        result = run(["ip", "--json", "route", "show", "default"], timeout=5)
        routes: list[dict[str, str]] = json.loads(result.stdout)
        return routes[0]["dev"]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError, KeyError):
        return None


def ping_latency(host: str, *, count: int = 3, timeout: int = 5) -> float | None:
    """Measure average ICMP round-trip latency to ``host`` in milliseconds.

    Invokes the system ``ping`` binary; the ``-W`` flag is interpreted as milliseconds on macOS and seconds elsewhere.

    :param host: Target hostname or IP address.
    :param count: Number of echo requests to send.
    :param timeout: Per-packet wait in seconds.
    :returns: Average RTT in ms, or ``None`` if the host is unreachable, ping fails, or output cannot be parsed.
    """
    is_macos = platform.system() == "Darwin"
    wait_value = str(timeout * 1000) if is_macos else str(timeout)
    try:
        result = run(
            ["ping", "-c", str(count), "-W", wait_value, host],
            timeout=timeout * count + 5,
        )
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0:
        return None

    for line in reversed(result.stdout.splitlines()):
        if "avg" in line:
            try:
                return float(line.split("=")[1].split("/")[1])
            except (IndexError, ValueError):
                return None
    return None
