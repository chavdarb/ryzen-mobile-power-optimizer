# Ryzen Mobile Power Optimizer

A Python harness that finds the optimal power settings for AMD Ryzen mobile processors on Ubuntu Linux. It iterates over CPU power limits, benchmarks performance at each step, and produces a report to identify the best performance-per-watt sweet spot.

## How It Works

The script steps through CPU power levels from a configurable starting point up to the system maximum (1W increments), running `sysbench` benchmarks at each level and recording performance. The final CSV report shows performance gain per watt, making it easy to spot where increasing power stops delivering proportional performance.

## Requirements

- Ubuntu 20.04 LTS or later
- AMD Ryzen mobile CPU with `ryzen_smu` kernel module
- `ryzenadj` — to read and set CPU power limits
- `sysbench` — CPU benchmark tool
- Python 3.7+
- `sudo` access

See [prerequisites.md](prerequisites.md) for detailed installation instructions.

## Usage

```bash
python3 power_optimizer.py
```
