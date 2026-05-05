"""Core optimizer logic for Ryzen mobile power management.

:class:`PowerOptimizer` is the main entry-point for programmatic use.  It
wraps the hardware layer and profile definitions, providing a clean API that
is easy to test (the hardware module can be swapped out via dependency
injection).
"""

from typing import Any, Dict, Optional

from . import hardware as _hw
from . import profiles as _profiles


class PowerOptimizer:
    """Selects and applies optimal power profiles for Ryzen mobile processors.

    Parameters
    ----------
    hw_module:
        Hardware interaction module.  Defaults to
        :mod:`ryzen_mobile_power_optimizer.hardware`.  Pass a mock here in
        tests to avoid touching real sysfs paths.
    """

    def __init__(self, hw_module: Any = None) -> None:
        self._hw = hw_module if hw_module is not None else _hw

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def available_profiles(self) -> list:
        """Names of all known power profiles."""
        return list(_profiles.PROFILES.keys())

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_current_settings(self) -> Dict[str, Any]:
        """Return a snapshot of the active power-related settings."""
        return {
            "on_ac_power": self._hw.is_on_ac_power(),
            "governor": self._hw.get_current_governor(),
            "energy_perf_preference": self._hw.get_energy_perf_preference(),
            "platform_profile": self._hw.get_platform_profile(),
        }

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    def get_recommended_profile(self) -> str:
        """Suggest a profile name based on the current power source.

        Returns :data:`~ryzen_mobile_power_optimizer.profiles.DEFAULT_PROFILE_AC`
        when connected to AC power (or when the power source is unknown) and
        :data:`~ryzen_mobile_power_optimizer.profiles.DEFAULT_PROFILE_BATTERY`
        when running on battery.
        """
        on_ac = self._hw.is_on_ac_power()
        if on_ac is False:
            return _profiles.DEFAULT_PROFILE_BATTERY
        return _profiles.DEFAULT_PROFILE_AC

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply_profile(
        self, profile_name: str, use_ryzenadj: bool = False
    ) -> Dict[str, Any]:
        """Apply a named power profile.

        Parameters
        ----------
        profile_name:
            One of the keys in :data:`~ryzen_mobile_power_optimizer.profiles.PROFILES`.
        use_ryzenadj:
            When ``True`` and the profile has TDP values defined, *ryzenadj*
            is invoked to apply STAPM / fast / slow TDP limits.

        Returns
        -------
        dict
            Mapping of setting names to ``True`` (applied successfully) or
            ``False`` (write failed).  The key ``"profile"`` holds the name.

        Raises
        ------
        ValueError
            If *profile_name* is not a known profile.
        """
        if profile_name not in _profiles.PROFILES:
            raise ValueError(
                f"Unknown profile '{profile_name}'. "
                f"Available profiles: {self.available_profiles}"
            )

        profile = _profiles.PROFILES[profile_name]
        results: Dict[str, Any] = {
            "profile": profile_name,
            "governor": self._hw.set_governor(profile.cpu_governor),
            "energy_perf_preference": self._hw.set_energy_perf_preference(
                profile.energy_perf_preference
            ),
            "platform_profile": self._hw.set_platform_profile(
                profile.platform_profile
            ),
        }

        if use_ryzenadj and profile.tdp_watt is not None:
            results["ryzenadj"] = self._hw.apply_ryzenadj(
                profile.tdp_watt,
                profile.fast_limit_watt,
                profile.slow_limit_watt,
            )

        return results
