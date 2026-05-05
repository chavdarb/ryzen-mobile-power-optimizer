"""Hardware interaction layer for Ryzen mobile power management.

Reads and writes sysfs knobs that control CPU governor, AMD P-state energy
performance preferences, and ACPI platform profiles.  Optionally calls the
*ryzenadj* utility for fine-grained TDP adjustment.

All sysfs helpers return ``None`` / ``False`` instead of raising exceptions so
that the optimizer can degrade gracefully on kernels or hardware that do not
expose a particular knob.
"""

import glob as _glob
import os
import subprocess
from typing import List, Optional

# ---------------------------------------------------------------------------
# sysfs path templates
# ---------------------------------------------------------------------------
_CPU_GOVERNOR_TMPL = "/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor"
_ENERGY_PERF_PREF_TMPL = (
    "/sys/devices/system/cpu/cpu{cpu}/cpufreq/energy_performance_preference"
)
_PLATFORM_PROFILE_PATH = "/sys/firmware/acpi/platform_profile"
_PLATFORM_PROFILE_CHOICES_PATH = "/sys/firmware/acpi/platform_profile_choices"
_AC_ONLINE_GLOB = "/sys/class/power_supply/*/online"
_BATTERY_STATUS_GLOB = "/sys/class/power_supply/BAT*/status"


# ---------------------------------------------------------------------------
# Low-level sysfs helpers
# ---------------------------------------------------------------------------


def read_sysfs(path: str) -> Optional[str]:
    """Return the stripped contents of a sysfs file, or ``None`` on error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def write_sysfs(path: str, value: str) -> bool:
    """Write *value* to a sysfs file.  Returns ``True`` on success."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(value)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# CPU topology helpers
# ---------------------------------------------------------------------------


def get_cpu_count() -> int:
    """Return the number of logical CPUs present in the system."""
    return len(_glob.glob("/sys/devices/system/cpu/cpu[0-9]*"))


# ---------------------------------------------------------------------------
# Power source detection
# ---------------------------------------------------------------------------


def is_on_ac_power() -> Optional[bool]:
    """Return ``True`` if on AC power, ``False`` if on battery, ``None`` if
    the power source cannot be determined."""
    for path in _glob.glob(_AC_ONLINE_GLOB):
        if read_sysfs(path) == "1":
            return True
    if _glob.glob(_BATTERY_STATUS_GLOB):
        return False
    return None


# ---------------------------------------------------------------------------
# CPU governor
# ---------------------------------------------------------------------------


def get_current_governor(cpu: int = 0) -> Optional[str]:
    """Return the active scaling governor for *cpu* (default: cpu0)."""
    return read_sysfs(_CPU_GOVERNOR_TMPL.format(cpu=cpu))


def get_available_governors(cpu: int = 0) -> List[str]:
    """Return the list of governors supported by *cpu*."""
    value = read_sysfs(
        f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_available_governors"
    )
    return value.split() if value else []


def set_governor(governor: str) -> bool:
    """Set the CPU scaling governor for all logical CPUs.

    Returns ``True`` if every write succeeded.
    """
    cpu_count = get_cpu_count()
    return all(
        write_sysfs(_CPU_GOVERNOR_TMPL.format(cpu=i), governor)
        for i in range(cpu_count)
    )


# ---------------------------------------------------------------------------
# AMD P-state energy performance preference
# ---------------------------------------------------------------------------


def get_energy_perf_preference(cpu: int = 0) -> Optional[str]:
    """Return the energy performance preference for *cpu* (default: cpu0)."""
    return read_sysfs(_ENERGY_PERF_PREF_TMPL.format(cpu=cpu))


def set_energy_perf_preference(preference: str) -> bool:
    """Set the energy performance preference for all logical CPUs.

    Returns ``True`` if every write succeeded.
    """
    cpu_count = get_cpu_count()
    return all(
        write_sysfs(_ENERGY_PERF_PREF_TMPL.format(cpu=i), preference)
        for i in range(cpu_count)
    )


# ---------------------------------------------------------------------------
# ACPI platform profile
# ---------------------------------------------------------------------------


def get_platform_profile() -> Optional[str]:
    """Return the current ACPI platform profile."""
    return read_sysfs(_PLATFORM_PROFILE_PATH)


def get_available_platform_profiles() -> List[str]:
    """Return the list of ACPI platform profiles supported by the firmware."""
    value = read_sysfs(_PLATFORM_PROFILE_CHOICES_PATH)
    return value.split() if value else []


def set_platform_profile(profile: str) -> bool:
    """Set the ACPI platform profile.  Returns ``True`` on success."""
    return write_sysfs(_PLATFORM_PROFILE_PATH, profile)


# ---------------------------------------------------------------------------
# ryzenadj — optional fine-grained TDP control
# ---------------------------------------------------------------------------


def apply_ryzenadj(
    tdp_watt: int,
    fast_limit_watt: int,
    slow_limit_watt: int,
    timeout: int = 10,
) -> bool:
    """Invoke *ryzenadj* to apply STAPM / fast / slow TDP limits.

    Milliwatt values are derived by multiplying the watt arguments by 1000.
    Returns ``True`` on success, ``False`` if *ryzenadj* is not found, returns
    a non-zero exit code, or times out.
    """
    try:
        result = subprocess.run(
            [
                "ryzenadj",
                f"--stapm-limit={tdp_watt * 1000}",
                f"--fast-limit={fast_limit_watt * 1000}",
                f"--slow-limit={slow_limit_watt * 1000}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
