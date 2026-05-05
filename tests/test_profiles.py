"""Tests for ryzen_mobile_power_optimizer.profiles."""

import pytest
from ryzen_mobile_power_optimizer.profiles import (
    DEFAULT_PROFILE_AC,
    DEFAULT_PROFILE_BATTERY,
    PROFILES,
    PowerProfile,
)


class TestProfileDefinitions:
    def test_required_profiles_exist(self):
        for name in ("power-saver", "balanced", "performance"):
            assert name in PROFILES

    def test_profiles_are_power_profile_instances(self):
        for profile in PROFILES.values():
            assert isinstance(profile, PowerProfile)

    def test_profile_names_match_keys(self):
        for key, profile in PROFILES.items():
            assert profile.name == key

    def test_required_fields_not_empty(self):
        for profile in PROFILES.values():
            assert profile.description
            assert profile.cpu_governor
            assert profile.energy_perf_preference
            assert profile.platform_profile

    def test_tdp_values_positive_when_set(self):
        for profile in PROFILES.values():
            if profile.tdp_watt is not None:
                assert profile.tdp_watt > 0
            if profile.fast_limit_watt is not None:
                assert profile.fast_limit_watt > 0
            if profile.slow_limit_watt is not None:
                assert profile.slow_limit_watt > 0

    def test_fast_limit_gte_slow_limit(self):
        for profile in PROFILES.values():
            if profile.fast_limit_watt is not None and profile.slow_limit_watt is not None:
                assert profile.fast_limit_watt >= profile.slow_limit_watt

    def test_profiles_are_immutable(self):
        profile = PROFILES["balanced"]
        with pytest.raises((AttributeError, TypeError)):
            profile.cpu_governor = "performance"  # type: ignore[misc]


class TestDefaultProfiles:
    def test_default_ac_profile_exists(self):
        assert DEFAULT_PROFILE_AC in PROFILES

    def test_default_battery_profile_exists(self):
        assert DEFAULT_PROFILE_BATTERY in PROFILES

    def test_defaults_are_different(self):
        assert DEFAULT_PROFILE_AC != DEFAULT_PROFILE_BATTERY

    def test_power_saver_is_battery_default(self):
        assert DEFAULT_PROFILE_BATTERY == "power-saver"

    def test_balanced_is_ac_default(self):
        assert DEFAULT_PROFILE_AC == "balanced"


class TestProfileOrdering:
    """Performance profile should have higher TDP than balanced which should
    be higher than power-saver."""

    def test_performance_tdp_gt_balanced(self):
        perf = PROFILES["performance"]
        bal = PROFILES["balanced"]
        if perf.tdp_watt is not None and bal.tdp_watt is not None:
            assert perf.tdp_watt > bal.tdp_watt

    def test_balanced_tdp_gt_power_saver(self):
        bal = PROFILES["balanced"]
        saver = PROFILES["power-saver"]
        if bal.tdp_watt is not None and saver.tdp_watt is not None:
            assert bal.tdp_watt > saver.tdp_watt
