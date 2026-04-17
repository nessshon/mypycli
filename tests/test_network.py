from __future__ import annotations

import socket

import pytest

from mypycli.utils.network import int_to_ip, ip_to_int, is_port_open


class TestIpConversion:
    @pytest.mark.parametrize(
        ("addr", "signed_int", "unsigned_int"),
        [
            ("0.0.0.0", 0, 0),
            ("127.0.0.1", 2130706433, 2130706433),
            ("192.168.1.1", -1062731519, 3232235777),
            ("255.255.255.255", -1, 4294967295),
        ],
    )
    def test_encode_matches_both_signings(self, addr: str, signed_int: int, unsigned_int: int) -> None:
        assert ip_to_int(addr) == signed_int
        assert ip_to_int(addr, signed=False) == unsigned_int
        assert int_to_ip(signed_int) == addr
        assert int_to_ip(unsigned_int, signed=False) == addr

    def test_invalid_address_raises(self) -> None:
        with pytest.raises(OSError):
            ip_to_int("999.999.999.999")


class TestIsPortOpen:
    def test_detects_open_and_closed(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            assert is_port_open("127.0.0.1", port, timeout=1) is True
        finally:
            server.close()
        assert is_port_open("127.0.0.1", port, timeout=1) is False
