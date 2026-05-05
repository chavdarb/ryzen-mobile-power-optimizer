"""Tests for ryzen_mobile_power_optimizer.hardware.

The sysfs and subprocess calls are patched so that tests run without
root privileges or real hardware.
"""

import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

import ryzen_mobile_power_optimizer.hardware as hw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_returns(content: str):
    """Return a context-manager mock whose read() returns *content*."""
    return mock_open(read_data=content)


# ---------------------------------------------------------------------------
# read_sysfs
# ---------------------------------------------------------------------------


class TestReadSysfs:
    def test_returns_stripped_content(self, tmp_path):
        p = tmp_path / "value"
        p.write_text("powersave\n")
        assert hw.read_sysfs(str(p)) == "powersave"

    def test_returns_none_on_missing_file(self):
        assert hw.read_sysfs("/nonexistent/path/value") is None


# ---------------------------------------------------------------------------
# write_sysfs
# ---------------------------------------------------------------------------


class TestWriteSysfs:
    def test_writes_value(self, tmp_path):
        p = tmp_path / "governor"
        p.write_text("")
        assert hw.write_sysfs(str(p), "performance") is True
        assert p.read_text() == "performance"

    def test_returns_false_on_permission_error(self):
        with patch("builtins.open", side_effect=OSError("permission denied")):
            assert hw.write_sysfs("/sys/fake", "value") is False


# ---------------------------------------------------------------------------
# get_cpu_count
# ---------------------------------------------------------------------------


class TestGetCpuCount:
    def test_returns_integer(self):
        with patch("glob.glob", return_value=["/sys/cpu0", "/sys/cpu1", "/sys/cpu2"]):
            assert hw.get_cpu_count() == 3

    def test_returns_zero_when_no_cpus_found(self):
        with patch("glob.glob", return_value=[]):
            assert hw.get_cpu_count() == 0


# ---------------------------------------------------------------------------
# is_on_ac_power
# ---------------------------------------------------------------------------


class TestIsOnAcPower:
    def test_true_when_ac_online(self, tmp_path):
        ac = tmp_path / "AC0" / "online"
        ac.parent.mkdir()
        ac.write_text("1")
        with patch("glob.glob", side_effect=lambda p: [str(ac)] if "online" in p else []):
            assert hw.is_on_ac_power() is True

    def test_false_when_battery_present_and_ac_offline(self, tmp_path):
        ac = tmp_path / "AC0" / "online"
        ac.parent.mkdir()
        ac.write_text("0")
        bat = tmp_path / "BAT0" / "status"
        bat.parent.mkdir()
        bat.write_text("Discharging")

        def _glob(pattern):
            if "online" in pattern:
                return [str(ac)]
            if "BAT*/status" in pattern:
                return [str(bat)]
            return []

        with patch("glob.glob", side_effect=_glob):
            assert hw.is_on_ac_power() is False

    def test_none_when_no_power_supply_found(self):
        with patch("glob.glob", return_value=[]):
            assert hw.is_on_ac_power() is None


# ---------------------------------------------------------------------------
# Governor helpers
# ---------------------------------------------------------------------------


class TestGovernor:
    def test_get_current_governor(self, tmp_path):
        p = tmp_path / "governor"
        p.write_text("powersave")
        with patch.object(hw, "read_sysfs", return_value="powersave"):
            assert hw.get_current_governor(0) == "powersave"

    def test_set_governor_all_cpus(self):
        written = {}

        def _write(path, value):
            written[path] = value
            return True

        with patch.object(hw, "get_cpu_count", return_value=4), \
             patch.object(hw, "write_sysfs", side_effect=_write):
            result = hw.set_governor("performance")

        assert result is True
        assert len(written) == 4
        assert all(v == "performance" for v in written.values())

    def test_set_governor_returns_false_on_partial_failure(self):
        call_count = {"n": 0}

        def _write(path, value):
            call_count["n"] += 1
            return call_count["n"] % 2 == 0  # fail odd CPUs

        with patch.object(hw, "get_cpu_count", return_value=4), \
             patch.object(hw, "write_sysfs", side_effect=_write):
            result = hw.set_governor("powersave")

        assert result is False


# ---------------------------------------------------------------------------
# Energy performance preference helpers
# ---------------------------------------------------------------------------


class TestEnergyPerfPreference:
    def test_get_energy_perf_preference(self):
        with patch.object(hw, "read_sysfs", return_value="balance_power"):
            assert hw.get_energy_perf_preference(0) == "balance_power"

    def test_set_energy_perf_preference_all_cpus(self):
        written = {}

        def _write(path, value):
            written[path] = value
            return True

        with patch.object(hw, "get_cpu_count", return_value=2), \
             patch.object(hw, "write_sysfs", side_effect=_write):
            result = hw.set_energy_perf_preference("power")

        assert result is True
        assert len(written) == 2


# ---------------------------------------------------------------------------
# Platform profile helpers
# ---------------------------------------------------------------------------


class TestPlatformProfile:
    def test_get_platform_profile(self):
        with patch.object(hw, "read_sysfs", return_value="balanced"):
            assert hw.get_platform_profile() == "balanced"

    def test_set_platform_profile(self):
        with patch.object(hw, "write_sysfs", return_value=True):
            assert hw.set_platform_profile("performance") is True

    def test_get_available_platform_profiles(self):
        with patch.object(hw, "read_sysfs", return_value="low-power balanced performance"):
            profiles = hw.get_available_platform_profiles()
        assert profiles == ["low-power", "balanced", "performance"]

    def test_get_available_platform_profiles_empty_when_not_supported(self):
        with patch.object(hw, "read_sysfs", return_value=None):
            assert hw.get_available_platform_profiles() == []


# ---------------------------------------------------------------------------
# apply_ryzenadj
# ---------------------------------------------------------------------------


class TestApplyRyzenadj:
    def test_success_calls_ryzenadj_with_milliwatts(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = hw.apply_ryzenadj(15, 20, 15)

        assert result is True
        call_args = mock_run.call_args[0][0]
        assert "--stapm-limit=15000" in call_args
        assert "--fast-limit=20000" in call_args
        assert "--slow-limit=15000" in call_args

    def test_returns_false_when_ryzenadj_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert hw.apply_ryzenadj(15, 20, 15) is False

    def test_returns_false_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            assert hw.apply_ryzenadj(15, 20, 15) is False

    def test_returns_false_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ryzenadj", 10)):
            assert hw.apply_ryzenadj(15, 20, 15) is False
