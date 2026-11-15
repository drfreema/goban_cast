"""Command line entry point. Real wiring lands in M1; this is the M0 stub."""

from __future__ import annotations

import argparse
import sys

from goban_cast import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goban-cast",
        description="Read a physical Go board with a webcam and overlay the game state.",
    )
    parser.add_argument("--version", action="version", version=f"goban_cast {__version__}")
    parser.add_argument(
        "--preview",
        metavar="PROFILE",
        help="render the overlay in a window instead of on a projector",
    )
    parser.add_argument(
        "--game",
        metavar="ID",
        type=int,
        help="attach to an existing online-go.com game id",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.preview is not None and args.game is not None:
        print(
            "goban_cast is at milestone M0: calibration, vision, overlay, and the OGS "
            "client are not implemented yet. See docs/plan.md.",
            file=sys.stderr,
        )
        return 2
    print(
        f"goban_cast {__version__} (pre-alpha, M0). "
        "Calibration, vision, overlay, and OGS client arrive in M1-M5; see docs/plan.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
