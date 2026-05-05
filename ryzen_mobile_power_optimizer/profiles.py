"""Power profile definitions for Ryzen mobile processors.

Each profile bundles CPU governor, energy-performance preference, ACPI
platform-profile, and optional ryzenadj TDP limits into a single named
configuration that can be applied atomically by the optimizer.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PowerProfile:
    """Immutable description of a named power profile."""

    name: str
    description: str
    cpu_governor: str
    energy_perf_preference: str
    platform_profile: str
    tdp_watt: Optional[int] = None
    fast_limit_watt: Optional[int] = None
    slow_limit_watt: Optional[int] = None


# Available profiles, keyed by their canonical name.
PROFILES: Dict[str, PowerProfile] = {
    "power-saver": PowerProfile(
        name="power-saver",
        description="Maximum battery life with minimal power draw",
        cpu_governor="powersave",
        energy_perf_preference="power",
        platform_profile="low-power",
        tdp_watt=10,
        fast_limit_watt=12,
        slow_limit_watt=10,
    ),
    "balanced": PowerProfile(
        name="balanced",
        description="Balance between performance and power efficiency",
        cpu_governor="powersave",
        energy_perf_preference="balance_power",
        platform_profile="balanced",
        tdp_watt=15,
        fast_limit_watt=20,
        slow_limit_watt=15,
    ),
    "performance": PowerProfile(
        name="performance",
        description="Maximum performance with higher power consumption",
        cpu_governor="performance",
        energy_perf_preference="performance",
        platform_profile="performance",
        tdp_watt=25,
        fast_limit_watt=35,
        slow_limit_watt=25,
    ),
}

# Default profiles chosen automatically when the power source changes.
DEFAULT_PROFILE_AC: str = "balanced"
DEFAULT_PROFILE_BATTERY: str = "power-saver"
