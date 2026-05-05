"""Tests for ryzen_mobile_power_optimizer.optimizer."""

import pytest

from ryzen_mobile_power_optimizer.optimizer import PowerOptimizer
from ryzen_mobile_power_optimizer.profiles import (
    DEFAULT_PROFILE_AC,
    DEFAULT_PROFILE_BATTERY,
    PROFILES,
)


# ---------------------------------------------------------------------------
# Fake hardware module used across all tests
# ---------------------------------------------------------------------------


class FakeHW:
    """Controllable stand-in for the hardware module."""

    def __init__(
        self,
        on_ac: bool = True,
        governor: str = "powersave",
        energy_pref: str = "balance_power",
        platform_profile: str = "balanced",
        write_ok: bool = True,
        ryzenadj_ok: bool = True,
    ):
        self._on_ac = on_ac
        self._governor = governor
        self._energy_pref = energy_pref
        self._platform_profile = platform_profile
        self._write_ok = write_ok
        self._ryzenadj_ok = ryzenadj_ok
        # Track calls
        self.set_governor_calls: list = []
        self.set_energy_perf_calls: list = []
        self.set_platform_profile_calls: list = []
        self.ryzenadj_calls: list = []

    def is_on_ac_power(self):
        return self._on_ac

    def get_current_governor(self, cpu=0):
        return self._governor

    def get_energy_perf_preference(self, cpu=0):
        return self._energy_pref

    def get_platform_profile(self):
        return self._platform_profile

    def set_governor(self, value):
        self.set_governor_calls.append(value)
        return self._write_ok

    def set_energy_perf_preference(self, value):
        self.set_energy_perf_calls.append(value)
        return self._write_ok

    def set_platform_profile(self, value):
        self.set_platform_profile_calls.append(value)
        return self._write_ok

    def apply_ryzenadj(self, tdp, fast, slow):
        self.ryzenadj_calls.append((tdp, fast, slow))
        return self._ryzenadj_ok


# ---------------------------------------------------------------------------
# available_profiles
# ---------------------------------------------------------------------------


class TestAvailableProfiles:
    def test_returns_all_profile_names(self):
        opt = PowerOptimizer(hw_module=FakeHW())
        assert set(opt.available_profiles) == set(PROFILES.keys())


# ---------------------------------------------------------------------------
# get_current_settings
# ---------------------------------------------------------------------------


class TestGetCurrentSettings:
    def test_returns_expected_keys(self):
        hw = FakeHW(
            on_ac=True,
            governor="powersave",
            energy_pref="balance_power",
            platform_profile="balanced",
        )
        settings = PowerOptimizer(hw_module=hw).get_current_settings()
        assert settings["on_ac_power"] is True
        assert settings["governor"] == "powersave"
        assert settings["energy_perf_preference"] == "balance_power"
        assert settings["platform_profile"] == "balanced"


# ---------------------------------------------------------------------------
# get_recommended_profile
# ---------------------------------------------------------------------------


class TestGetRecommendedProfile:
    def test_recommends_ac_default_on_ac(self):
        opt = PowerOptimizer(hw_module=FakeHW(on_ac=True))
        assert opt.get_recommended_profile() == DEFAULT_PROFILE_AC

    def test_recommends_battery_default_on_battery(self):
        opt = PowerOptimizer(hw_module=FakeHW(on_ac=False))
        assert opt.get_recommended_profile() == DEFAULT_PROFILE_BATTERY

    def test_recommends_ac_default_when_unknown(self):
        hw = FakeHW()
        hw._on_ac = None
        opt = PowerOptimizer(hw_module=hw)
        assert opt.get_recommended_profile() == DEFAULT_PROFILE_AC


# ---------------------------------------------------------------------------
# apply_profile
# ---------------------------------------------------------------------------


class TestApplyProfile:
    def test_raises_on_unknown_profile(self):
        opt = PowerOptimizer(hw_module=FakeHW())
        with pytest.raises(ValueError, match="Unknown profile"):
            opt.apply_profile("turbo-boost")

    def test_applies_correct_settings_for_balanced(self):
        hw = FakeHW()
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("balanced")

        profile = PROFILES["balanced"]
        assert hw.set_governor_calls == [profile.cpu_governor]
        assert hw.set_energy_perf_calls == [profile.energy_perf_preference]
        assert hw.set_platform_profile_calls == [profile.platform_profile]
        assert results["profile"] == "balanced"
        assert results["governor"] is True
        assert results["energy_perf_preference"] is True
        assert results["platform_profile"] is True

    def test_applies_correct_settings_for_power_saver(self):
        hw = FakeHW()
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("power-saver")

        profile = PROFILES["power-saver"]
        assert hw.set_governor_calls == [profile.cpu_governor]
        assert hw.set_energy_perf_calls == [profile.energy_perf_preference]
        assert hw.set_platform_profile_calls == [profile.platform_profile]

    def test_applies_correct_settings_for_performance(self):
        hw = FakeHW()
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("performance")

        profile = PROFILES["performance"]
        assert hw.set_governor_calls == [profile.cpu_governor]
        assert hw.set_energy_perf_calls == [profile.energy_perf_preference]
        assert hw.set_platform_profile_calls == [profile.platform_profile]

    def test_ryzenadj_not_called_by_default(self):
        hw = FakeHW()
        opt = PowerOptimizer(hw_module=hw)
        opt.apply_profile("performance")
        assert hw.ryzenadj_calls == []

    def test_ryzenadj_called_when_requested(self):
        hw = FakeHW()
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("performance", use_ryzenadj=True)

        profile = PROFILES["performance"]
        assert len(hw.ryzenadj_calls) == 1
        assert hw.ryzenadj_calls[0] == (
            profile.tdp_watt,
            profile.fast_limit_watt,
            profile.slow_limit_watt,
        )
        assert results["ryzenadj"] is True

    def test_ryzenadj_result_in_results(self):
        hw = FakeHW(ryzenadj_ok=False)
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("balanced", use_ryzenadj=True)
        assert results["ryzenadj"] is False

    def test_result_reflects_write_failures(self):
        hw = FakeHW(write_ok=False)
        opt = PowerOptimizer(hw_module=hw)
        results = opt.apply_profile("balanced")
        assert results["governor"] is False
        assert results["energy_perf_preference"] is False
        assert results["platform_profile"] is False

    def test_result_contains_profile_key(self):
        hw = FakeHW()
        results = PowerOptimizer(hw_module=hw).apply_profile("balanced")
        assert results["profile"] == "balanced"
