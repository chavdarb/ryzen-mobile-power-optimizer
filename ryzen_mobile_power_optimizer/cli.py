"""Command-line interface for Ryzen Mobile Power Optimizer.

Usage
-----
    ryzen-power-optimizer status
    ryzen-power-optimizer list
    ryzen-power-optimizer apply <profile> [--ryzenadj]
    ryzen-power-optimizer auto [--ryzenadj]
"""

import argparse
import sys
from typing import List, Optional

from . import profiles as _profiles
from .optimizer import PowerOptimizer


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ryzen-power-optimizer",
        description=(
            "Ryzen Mobile Power Optimizer — select optimal power profile "
            "settings for AMD Ryzen mobile processors."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    # status ---------------------------------------------------------------
    subparsers.add_parser("status", help="Show current power settings")

    # list -----------------------------------------------------------------
    subparsers.add_parser("list", help="List available power profiles")

    # apply ----------------------------------------------------------------
    apply_parser = subparsers.add_parser("apply", help="Apply a power profile")
    apply_parser.add_argument(
        "profile",
        choices=list(_profiles.PROFILES.keys()),
        help="Name of the profile to apply",
    )
    apply_parser.add_argument(
        "--ryzenadj",
        action="store_true",
        help="Also set TDP limits via ryzenadj (requires root)",
    )

    # auto -----------------------------------------------------------------
    auto_parser = subparsers.add_parser(
        "auto",
        help="Automatically apply the recommended profile for the current power source",
    )
    auto_parser.add_argument(
        "--ryzenadj",
        action="store_true",
        help="Also set TDP limits via ryzenadj (requires root)",
    )

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_status(opt: PowerOptimizer) -> int:
    settings = opt.get_current_settings()
    on_ac = settings["on_ac_power"]
    power_source = "AC" if on_ac else ("Battery" if on_ac is False else "Unknown")

    print("Current power settings:")
    print(f"  Power source            : {power_source}")
    print(f"  CPU governor            : {settings['governor'] or 'unknown'}")
    print(f"  Energy perf preference  : {settings['energy_perf_preference'] or 'unknown'}")
    print(f"  Platform profile        : {settings['platform_profile'] or 'unknown'}")
    print()
    print(f"Recommended profile: {opt.get_recommended_profile()}")
    return 0


def _cmd_list() -> int:
    print("Available power profiles:")
    for name, profile in _profiles.PROFILES.items():
        print(f"  {name:<15}  {profile.description}")
    return 0


def _cmd_apply(opt: PowerOptimizer, profile_name: str, use_ryzenadj: bool) -> int:
    print(f"Applying profile: {profile_name}")
    try:
        results = opt.apply_profile(profile_name, use_ryzenadj=use_ryzenadj)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    any_failed = False
    for key, value in results.items():
        if key == "profile":
            continue
        status = "OK" if value else "FAILED"
        if not value:
            any_failed = True
        print(f"  {key:<30} [{status}]")

    if any_failed:
        print(
            "\nSome settings could not be applied. "
            "Run as root or check kernel support.",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_auto(opt: PowerOptimizer, use_ryzenadj: bool) -> int:
    profile_name = opt.get_recommended_profile()
    print(f"Auto-selecting profile: {profile_name}")
    return _cmd_apply(opt, profile_name, use_ryzenadj)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    opt = PowerOptimizer()

    if args.command == "status":
        return _cmd_status(opt)
    if args.command == "list":
        return _cmd_list()
    if args.command == "apply":
        return _cmd_apply(opt, args.profile, args.ryzenadj)
    if args.command == "auto":
        return _cmd_auto(opt, args.ryzenadj)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
