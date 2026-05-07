# RyzenAdj Power Configuration on Ubuntu 26.04

This document captures the exact system configuration used to persist final Ryzen power limits on an Ubuntu 26.04 laptop.

It covers these goals:

1. Create a power configuration script with correct privileges.
2. Apply power settings on system startup.
3. Re-apply settings on AC connect and disconnect events.
4. Re-apply settings after suspend/resume.

## Final Power Profile

The power optimizer test was executed on the following configuration, while connected to AC power, on the Balanced power profile:

```
OS: Ubuntu 26.04 (Resolute Raccoon) x86_64
Host: ASUS Vivobook S 14 M3407HA_M3407HA (1.0)
Kernel: Linux 7.0.0-15-generic
Uptime: 16 hours, 9 mins
Packages: 2197 (dpkg), 16 (snap)
Shell: bash 5.3.9
Display (NCP0061): 2560x1600 @ 1.67x in 14", 60 Hz [Built-in]
DE: GNOME 50.1
WM: Mutter (Wayland)
WM Theme: Yaru-dark
Theme: Yaru-dark [GTK2/3/4]
Icons: Yaru-dark [GTK2/3/4]
Font: Ubuntu Sans (11pt) [GTK2/3/4]
Cursor: Yaru (24px)
Terminal: code 1.118.1
CPU: AMD Ryzen 9 270 (16) @ 5.26 GHz
GPU: AMD Radeon 780M Graphics [Integrated]
Memory: 7.22 GiB / 30.11 GiB (24%)
Swap: 0 B / 8.00 GiB (0%)
Disk (/): 32.03 GiB / 54.70 GiB (59%) - ext4
Disk (/home): 31.29 GiB / 882.35 GiB (4%) - ext4
Local IP (wlp1s0): 192.168.1.28/24
Battery (X160745): 97% (9 hours, 21 mins remaining) [Discharging]
Locale: en_US.UTF-8
```

The test was run with no undervolt, as well as with -15 mV and -20 mV undervolt settings.

You can use this calculator for the proper hex value:
https://www.calculator.net/hex-calculator.html?number1=100000&c2op=-&number2=15&calctype=op&x=Calculate
(example pre-filled for -15 mV)

Usually -15 mV is the optimal safe value.

> Caution! Undervolting might cause stability issues. Test the undervolted settings using the attached stability test.

Results can be found in the `results` folder.
We were able to achieve 7W lower sustained power usage (27W), while retaining the default performance of the 35W balanced power mode.

Final stable command:

```bash
/usr/local/bin/ryzenadj --slow-limit=27000 --fast-limit=32000 --set-coall=0xFFFE0 --power-saving
```

Values used:

1. `slow-limit=27000` (27W sustained power envelope)
2. `fast-limit=32000` (32W short boost envelope)
3. `set-coall=0xFFFE0` (-20 mV CO undervolt)
4. `--power-saving` (RyzenAdj power-saving mode)

## 1. Power Configuration Script

Create the script at `/usr/local/sbin/apply-ryzenadj.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

/usr/local/bin/ryzenadj --slow-limit=27000 --fast-limit=32000 --set-coall=0xFFFE0 --power-saving
```

Set secure ownership and executable permissions:

```bash
sudo chown root:root /usr/local/sbin/apply-ryzenadj.sh
sudo chmod 0755 /usr/local/sbin/apply-ryzenadj.sh
```

What this file does:

1. Provides one controlled entry point for applying the final power profile.
2. Runs with strict shell safety flags (`set -euo pipefail`) so failures stop immediately.
3. Can be reused by multiple triggers (boot, AC events, resume) without duplicating command logic.

## 2. Apply on System Startup

Create `/etc/systemd/system/ryzenadj-apply.service`:

```ini
[Unit]
Description=Apply RyzenAdj power profile
After=multi-user.target
ConditionPathExists=/usr/local/bin/ryzenadj

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/apply-ryzenadj.sh

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ryzenadj-apply.service
```

What this file does:

1. Runs exactly once per boot (`Type=oneshot`).
2. Ensures `ryzenadj` exists before execution (`ConditionPathExists`).
3. Makes the profile persistent across reboots (`WantedBy=multi-user.target`).

## 3. Apply on AC Connect/Disconnect

Current rule file `/etc/udev/rules.d/99-ryzenadj-ac.rules`:

```udev
SUBSYSTEM=="power_supply", ATTR{online}=="1", RUN+="/usr/bin/systemctl start ryzenadj-apply.service"
SUBSYSTEM=="power_supply", ATTR{online}=="0", RUN+="/usr/bin/systemctl start ryzenadj-apply.service"
```

Reload udev rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=power_supply
```

What this file does:

1. Watches power supply state changes.
2. Triggers `ryzenadj-apply.service` when AC is connected (`online==1`) and disconnected (`online==0`).
3. Re-applies your fixed profile after charger state transitions.

### Optional Improvement: AC/Battery Split Behavior

Your current rule is valid and re-applies one profile for both states. If you want different limits for AC and battery, split behavior is recommended.

Recommended approach:

1. Keep the same udev trigger model.
2. Update `apply-ryzenadj.sh` to detect AC state and apply an AC profile or battery profile conditionally.
3. Or create separate `ryzenadj-ac.service` and `ryzenadj-battery.service` units and trigger each one from dedicated udev rules.

This is optional and not required for your current fixed-profile setup.

## 4. Apply After Suspend/Resume

Create `/etc/systemd/system/ryzenadj-resume.service`:

```ini
[Unit]
Description=Re-apply RyzenAdj power profile after resume
After=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=/usr/local/sbin/apply-ryzenadj.sh

[Install]
WantedBy=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
```

Enable the resume service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ryzenadj-resume.service
```

What this file does:

1. Re-applies the profile after sleep-related transitions.
2. Waits 5 seconds before execution so resume finishes device/power reinitialization.
3. Prevents firmware or kernel resume defaults from leaving different power limits active.

## Verification

Check service installation state:

```bash
systemctl list-unit-files --type=service | grep -i ryzen
```

Expected units:

1. `ryzenadj-apply.service` enabled
2. `ryzenadj-resume.service` enabled

Check unit definitions:

```bash
sudo systemctl cat ryzenadj-apply.service
sudo systemctl cat ryzenadj-resume.service
```

Check runtime power limits:

```bash
sudo ryzenadj -i | grep -E 'PPT LIMIT FAST|PPT LIMIT SLOW'
```

Expected values should match the configured profile (`FAST ~= 32.000`, `SLOW ~= 27.000`).

Functional checks:

1. Reboot and verify limits are applied.
2. Plug and unplug AC, then verify limits again.
3. Suspend and resume, then verify limits again.

## Rollback and Disable

Stop and disable services:

```bash
sudo systemctl disable --now ryzenadj-apply.service
sudo systemctl disable ryzenadj-resume.service
```

Remove systemd unit files:

```bash
sudo rm -f /etc/systemd/system/ryzenadj-apply.service
sudo rm -f /etc/systemd/system/ryzenadj-resume.service
sudo systemctl daemon-reload
```

Remove udev rule and reload:

```bash
sudo rm -f /etc/udev/rules.d/99-ryzenadj-ac.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=power_supply
```

Optional cleanup of apply script:

```bash
sudo rm -f /usr/local/sbin/apply-ryzenadj.sh
```

After rollback, power limits will no longer be automatically re-applied by this setup.