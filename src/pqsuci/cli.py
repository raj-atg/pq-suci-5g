"""Command line interface: `pqsuci keygen|conceal|deconceal`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pqsuci.dem import DeconcealError
from pqsuci.schemes import SCHEMES, conceal_imsi, deconceal_suci
from pqsuci.suci_format import parse_suci


def _read_hex(path: str) -> bytes:
    return bytes.fromhex(Path(path).read_text().strip())


def cmd_keygen(args: argparse.Namespace) -> int:
    """Write <prefix>.priv.hex and <prefix>.pub.hex."""
    priv, pub = SCHEMES[args.scheme].keygen()
    Path(f"{args.out}.priv.hex").write_text(priv.hex() + "\n")
    Path(f"{args.out}.pub.hex").write_text(pub.hex() + "\n")
    print(f"wrote {args.out}.priv.hex ({len(priv)} B) and {args.out}.pub.hex ({len(pub)} B)")
    return 0


def cmd_conceal(args: argparse.Namespace) -> int:
    """Print the SUCI string for an IMSI."""
    pub = _read_hex(args.pub) if args.pub else b""
    suci = conceal_imsi(
        SCHEMES[args.scheme], pub, args.imsi, args.mnc_len, args.key_id, args.routing
    )
    print(suci.to_string())
    return 0


def cmd_deconceal(args: argparse.Namespace) -> int:
    """Print the IMSI recovered from a SUCI string."""
    priv = _read_hex(args.priv) if args.priv else b""
    try:
        print(deconceal_suci(parse_suci(args.suci), priv))
    except DeconcealError as exc:
        print(f"de-concealment failed: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    p = argparse.ArgumentParser(prog="pqsuci", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    k = sub.add_parser("keygen", help="generate a home network key pair")
    k.add_argument("--scheme", choices=sorted(SCHEMES), required=True)
    k.add_argument("--out", required=True, help="output path prefix")
    k.set_defaults(func=cmd_keygen)

    c = sub.add_parser("conceal", help="IMSI -> SUCI")
    c.add_argument("--scheme", choices=sorted(SCHEMES), required=True)
    c.add_argument("--imsi", required=True)
    c.add_argument("--pub", help="file with the home network public key in hex")
    c.add_argument("--mnc-len", type=int, default=2)
    c.add_argument("--key-id", type=int, default=1)
    c.add_argument("--routing", default="0000")
    c.set_defaults(func=cmd_conceal)

    d = sub.add_parser("deconceal", help="SUCI -> IMSI")
    d.add_argument("--suci", required=True)
    d.add_argument("--priv", help="file with the home network private key in hex")
    d.set_defaults(func=cmd_deconceal)
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
