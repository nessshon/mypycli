from __future__ import annotations

import pytest

from mypycli.types.sysinfo import HardwareInfo
from mypycli.utils.sysinfo import SysInfo


class TestHardwareInfoVirtualization:
    def test_none_product_gives_none(self) -> None:
        assert HardwareInfo(product_name=None).is_virtualized is None

    def test_bare_metal_not_virtualized(self) -> None:
        assert HardwareInfo(product_name="dell poweredge r720").is_virtualized is False

    @pytest.mark.parametrize(
        "product_name",
        [
            "kvm",
            "qemu standard pc",
            "vmware virtual platform",
            "xen domu",
            "microsoft hyperv",
            "bochs",
        ],
    )
    def test_known_virt_markers(self, product_name: str) -> None:
        assert HardwareInfo(product_name=product_name).is_virtualized is True


class TestSysInfoSmoke:
    def test_properties_return_without_errors(self) -> None:
        info = SysInfo()
        assert info.cpu.count_logical >= 1
        assert info.ram.total > 0
        assert info.os.name
        assert info.uptime >= 0
        assert isinstance(info.all_disk_usage, dict)
        assert isinstance(info.all_network_io, dict)

    def test_get_unknown_device_returns_none(self) -> None:
        info = SysInfo()
        assert info.get_disk_io("definitely-not-a-device") is None
        assert info.get_network_io("definitely-not-an-iface") is None
