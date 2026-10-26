"""Tests for MSIN BCD coding and SUCI string handling."""

import pytest

from pqsuci.suci_format import Suci, bcd_to_msin, msin_to_bcd, parse_suci


@pytest.mark.parametrize(
    ("msin", "bcd"),
    [
        ("0000000001", bytes.fromhex("0000000010")),
        ("123", bytes.fromhex("21f3")),
        ("12", bytes.fromhex("21")),
        ("1", bytes.fromhex("f1")),
    ],
)
def test_bcd_known_values(msin: str, bcd: bytes) -> None:
    assert msin_to_bcd(msin) == bcd
    assert bcd_to_msin(bcd) == msin


@pytest.mark.parametrize("msin", ["0", "00", "123456789", "0123456789", "9" * 11])
def test_bcd_round_trip(msin: str) -> None:
    assert bcd_to_msin(msin_to_bcd(msin)) == msin


@pytest.mark.parametrize("bad", ["", "12a", "1 2", "-1", "1.5"])
def test_msin_to_bcd_rejects_non_digits(bad: str) -> None:
    with pytest.raises(ValueError):
        msin_to_bcd(bad)


@pytest.mark.parametrize("bad", [b"\xab", b"\x1a", b"\xff\x11"])
def test_bcd_to_msin_rejects_invalid_nibbles(bad: bytes) -> None:
    with pytest.raises(ValueError):
        bcd_to_msin(bad)


@pytest.mark.parametrize(
    "suci",
    [
        Suci("999", "70", "0000", 0, 0, "0000000001"),
        Suci("310", "260", "1234", 1, 1, "ab" * 40),
        Suci("001", "01", "0", 12, 5, "00ff"),
    ],
)
def test_suci_string_round_trip(suci: Suci) -> None:
    assert parse_suci(suci.to_string()) == suci


def test_to_string_layout() -> None:
    s = Suci("999", "70", "0000", 0, 0, "0000000001")
    assert s.to_string() == "suci-0-999-70-0000-0-0-0000000001"


def test_parse_strips_whitespace() -> None:
    assert parse_suci("  suci-0-999-70-0000-0-0-0000000001\n").mnc == "70"


@pytest.mark.parametrize(
    ("text", "mnc"), [("suci-0-310-260-0-1-1-ab", "260"), ("suci-0-310-26-0-1-1-ab", "26")]
)
def test_two_and_three_digit_mnc(text: str, mnc: str) -> None:
    assert parse_suci(text).mnc == mnc


@pytest.mark.parametrize(
    "text",
    [
        "imsi-0-999-70-0000-0-0-01",
        "suci-1-999-70-0000-0-0-01",
        "suci-0-99-70-0000-0-0-01",
        "suci-0-9999-70-0000-0-0-01",
        "suci-0-99a-70-0000-0-0-01",
        "suci-0-999-7-0000-0-0-01",
        "suci-0-999-7000-0000-0-0-01",
        "suci-0-999-7x-0000-0-0-01",
        "suci-0-999-70-0000-0-0",
        "suci-0-999-70-0000-0-0-01-extra",
        "",
    ],
)
def test_parse_errors(text: str) -> None:
    with pytest.raises(ValueError):
        parse_suci(text)


def test_null_scheme_output_bytes_is_bcd() -> None:
    s = parse_suci("suci-0-999-70-0000-0-0-0000000001")
    assert s.output_bytes == bytes.fromhex("0000000010")


def test_protected_scheme_output_bytes_is_hex() -> None:
    s = parse_suci("suci-0-999-70-0000-1-1-00ff10")
    assert s.output_bytes == bytes.fromhex("00ff10")
