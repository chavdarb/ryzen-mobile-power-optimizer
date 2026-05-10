# Ryzen Mobile Power Optimizer

A Python harness that finds the optimal power settings for AMD Ryzen mobile processors on Ubuntu Linux. It iterates over CPU power limits, benchmarks performance at each step, and produces a report to identify the best performance-per-watt sweet spot.

## How It Works

The script steps through CPU power levels from a configurable starting point up to the system maximum (1W increments), running `sysbench` benchmarks at each level and recording performance. The final CSV report shows performance gain per watt, making it easy to spot where increasing power stops delivering proportional performance.

## Requirements

- Ubuntu 20.04 LTS or later
- AMD Ryzen mobile CPU with `ryzen_smu` kernel module
- `ryzenadj` — to read and set CPU power limits
- `sysbench` — CPU benchmark tool
- `stress-ng` — CPU and memory stress tool
- Python 3.7+
- `sudo` access

See [prerequisites.md](prerequisites.md) for detailed installation instructions.

See [power-configuration.md](power-configuration.md) for detailed instructions on how to make custom power settings persistent.

## Current Configuration

The current persistent baseline profile uses:

- CPU governor: `performance`
- CO undervolt: `-15 mV` (`set-coall=0xFFFEB`)

For full setup and systemd/udev integration details, see [power-configuration.md](power-configuration.md).

## Usage

### Power Sweep Optimizer

```bash
python3 power_optimizer.py
```

### Standalone Stability Test

This script tests the current configuration by running CPU scaling from 1..N logical cores with both `sysbench` and `stress-ng`, then runs a memory-pressure stage and scans kernel logs for instability indicators.

```bash
python3 cpu_stability_test.py
```

CLI-first mode with defaults and no interactive prompts:

```bash
python3 cpu_stability_test.py --no-prompt
```

Quick smoke test (short duration):

```bash
python3 cpu_stability_test.py --duration 20 --end-cores 4
```
