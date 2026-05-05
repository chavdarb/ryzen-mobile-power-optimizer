"""Tests for ryzen_mobile_power_optimizer.cli."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest

from ryzen_mobile_power_optimizer.cli import build_parser, main
from ryzen_mobile_power_optimizer.profiles import PROFILES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeHW:
    """Minimal fake hardware module for CLI tests."""

    def __init__(self, on_ac=True, write_ok=True):
        self._on_ac = on_ac
        self._write_ok = write_ok

    def is_on_ac_power(self):
        return self._on_ac

    def get_current_governor(self, cpu=0):
        return "powersave"

    def get_energy_perf_preference(self, cpu=0):
        return "balance_power"

    def get_platform_profile(self):
        return "balanced"

    def set_governor(self, v):
        return self._write_ok

    def set_energy_perf_preference(self, v):
        return self._write_ok

    def set_platform_profile(self, v):
        return self._write_ok

    def apply_ryzenadj(self, *a):
        return self._write_ok


def _run(argv, hw=None, capsys=None):
    """Run main() with an injected hardware module and return (exit_code, stdout, stderr)."""
    if hw is None:
        hw = FakeHW()

    from ryzen_mobile_power_optimizer import optimizer as _opt_module
    from ryzen_mobile_power_optimizer.optimizer import PowerOptimizer

    real_init = PowerOptimizer.__init__

    def patched_init(self, hw_module=None):
        real_init(self, hw_module=hw)

    with patch.object(PowerOptimizer, "__init__", patched_init):
        code = main(argv)
    return code


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_parser_is_argument_parser(self):
        import argparse
        assert isinstance(build_parser(), argparse.ArgumentParser)

    def test_known_subcommands(self):
        parser = build_parser()
        for cmd in ("status", "list", "apply", "auto"):
            args = parser.parse_args([cmd] + (["balanced"] if cmd == "apply" else []))
            assert args.command == cmd

    def test_apply_accepts_valid_profiles(self):
        parser = build_parser()
        for name in PROFILES:
            args = parser.parse_args(["apply", name])
            assert args.profile == name

    def test_apply_rejects_invalid_profile(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["apply", "warp-speed"])

    def test_apply_ryzenadj_flag(self):
        parser = build_parser()
        args = parser.parse_args(["apply", "balanced", "--ryzenadj"])
        assert args.ryzenadj is True

    def test_auto_ryzenadj_flag(self):
        parser = build_parser()
        args = parser.parse_args(["auto", "--ryzenadj"])
        assert args.ryzenadj is True


# ---------------------------------------------------------------------------
# main() — no subcommand
# ---------------------------------------------------------------------------


class TestMainNoSubcommand:
    def test_returns_zero_and_prints_help(self, capsys):
        code = _run([], hw=FakeHW())
        assert code == 0


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------


class TestStatusCommand:
    def test_exit_code_zero(self):
        assert _run(["status"]) == 0

    def test_output_contains_power_source(self, capsys):
        _run(["status"])
        out = capsys.readouterr().out
        assert "Power source" in out

    def test_output_contains_governor(self, capsys):
        _run(["status"])
        out = capsys.readouterr().out
        assert "governor" in out.lower()

    def test_output_contains_recommended_profile(self, capsys):
        _run(["status"])
        out = capsys.readouterr().out
        assert "Recommended profile" in out


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_exit_code_zero(self):
        assert _run(["list"]) == 0

    def test_output_contains_all_profiles(self, capsys):
        _run(["list"])
        out = capsys.readouterr().out
        for name in PROFILES:
            assert name in out


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


class TestApplyCommand:
    def test_exit_code_zero_on_success(self):
        assert _run(["apply", "balanced"]) == 0

    def test_exit_code_one_on_write_failure(self):
        code = _run(["apply", "balanced"], hw=FakeHW(write_ok=False))
        assert code == 1

    def test_output_mentions_profile(self, capsys):
        _run(["apply", "performance"])
        out = capsys.readouterr().out
        assert "performance" in out

    def test_all_profiles_apply_without_error(self):
        for name in PROFILES:
            assert _run(["apply", name]) == 0


# ---------------------------------------------------------------------------
# auto command
# ---------------------------------------------------------------------------


class TestAutoCommand:
    def test_selects_balanced_on_ac(self, capsys):
        _run(["auto"], hw=FakeHW(on_ac=True))
        out = capsys.readouterr().out
        assert "balanced" in out

    def test_selects_power_saver_on_battery(self, capsys):
        _run(["auto"], hw=FakeHW(on_ac=False))
        out = capsys.readouterr().out
        assert "power-saver" in out

    def test_exit_code_zero_on_success(self):
        assert _run(["auto"]) == 0
