"""Tests for the command line interface."""

from pathlib import Path

import pytest

from pqsuci.cli import main

IMSI = "999700000000001"


def _keygen(tmp_path: Path, scheme: str, name: str) -> tuple[Path, Path]:
    prefix = tmp_path / name
    assert main(["keygen", "--scheme", scheme, "--out", str(prefix)]) == 0
    return Path(f"{prefix}.priv.hex"), Path(f"{prefix}.pub.hex")


@pytest.mark.parametrize("scheme", ["profile-a", "mlkem768"])
def test_cli_round_trip(scheme: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    priv, pub = _keygen(tmp_path, scheme, "hn")
    assert priv.exists() and pub.exists()
    capsys.readouterr()
    assert main(["conceal", "--scheme", scheme, "--imsi", IMSI, "--pub", str(pub)]) == 0
    suci = capsys.readouterr().out.strip()
    assert suci.startswith("suci-0-999-70-0000-")
    assert main(["deconceal", "--suci", suci, "--priv", str(priv)]) == 0
    assert capsys.readouterr().out.strip() == IMSI


@pytest.mark.parametrize("scheme", ["profile-a", "mlkem768"])
def test_cli_wrong_key_fails(
    scheme: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, pub = _keygen(tmp_path, scheme, "hn")
    wrong_priv, _ = _keygen(tmp_path, scheme, "other")
    capsys.readouterr()
    assert main(["conceal", "--scheme", scheme, "--imsi", IMSI, "--pub", str(pub)]) == 0
    suci = capsys.readouterr().out.strip()
    assert main(["deconceal", "--suci", suci, "--priv", str(wrong_priv)]) == 1
    assert "failed" in capsys.readouterr().err


def test_cli_null_scheme(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["conceal", "--scheme", "null", "--imsi", IMSI]) == 0
    suci = capsys.readouterr().out.strip()
    assert suci == "suci-0-999-70-0000-0-0-0000000001"
    assert main(["deconceal", "--suci", suci]) == 0
    assert capsys.readouterr().out.strip() == IMSI
