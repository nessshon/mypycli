import ipaddress
import json
import subprocess

import requests

from mypycli.utils.system import run

DEFAULT_PUBLIC_IP_URLS = [
    "https://ifconfig.me/ip",
    "https://api.ipify.org",
    "https://ipinfo.io/ip",
]

DEFAULT_PING_HOSTS = [
    "45.129.96.53",
    "2.56.126.137",
    "91.194.11.68",
    "103.106.3.171",
    "45.12.134.214",
    "5.154.181.153",
    "138.124.184.27",
]


def get_ping(host: str, *, count: int = 1, timeout: int = 3) -> float | None:
    try:
        result = run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            timeout=(count * timeout) + 1,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if "min/avg/max" not in line:
            continue
        try:
            stats = line.split("=", 1)[1].strip().split()[0]
            return float(stats.split("/")[1])
        except (IndexError, ValueError):
            return None

    return None


def get_pings(hosts: list[str] | None = None) -> dict[str, float | None]:
    if hosts is None:
        hosts = DEFAULT_PING_HOSTS

    result: dict[str, float | None] = {}
    for host in hosts:
        result[host] = get_ping(host, count=3, timeout=5)

    return result


def get_public_ip(urls: list[str] | None = None, *, timeout: float = 10) -> str | None:
    if urls is None:
        urls = DEFAULT_PUBLIC_IP_URLS

    for url in urls:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            text = response.text.strip()
            ipaddress.IPv4Address(text)
        except (requests.RequestException, ipaddress.AddressValueError):
            continue

        return text
    return None


def get_network_interface() -> str | None:
    try:
        result = run(["ip", "--json", "route", "show", "default"], timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    try:
        routes = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not routes:
        return None

    interface = routes[0].get("dev")
    return str(interface) if interface else None
