from mypycli.types import BitUnit, ByteUnit

_BYTE_DIVISORS: dict[ByteUnit, int] = {
    ByteUnit.B: 1,
    ByteUnit.KiB: 1024,
    ByteUnit.KB: 10**3,
    ByteUnit.MiB: 1024**2,
    ByteUnit.MB: 10**6,
    ByteUnit.GiB: 1024**3,
    ByteUnit.GB: 10**9,
    ByteUnit.TiB: 1024**4,
    ByteUnit.TB: 10**12,
}

_BIT_DIVISORS: dict[BitUnit, int] = {
    BitUnit.bit: 1,
    BitUnit.kbit: 10**3,
    BitUnit.Mbit: 10**6,
    BitUnit.Gbit: 10**9,
    BitUnit.Tbit: 10**12,
}


def convert_bytes(value: int, unit: ByteUnit, *, decimals: int = 2) -> float:
    return round(value / _BYTE_DIVISORS[unit], decimals)


def convert_bits(value: int, unit: BitUnit, *, decimals: int = 2) -> float:
    return round(value * 8 / _BIT_DIVISORS[unit], decimals)
