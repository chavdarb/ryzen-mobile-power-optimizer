# Prerequisites & Installation Guide

## System Requirements

- **OS**: Ubuntu 20.04 LTS or later (tested on Ubuntu 26.04 LTS)
- **CPU**: AMD Ryzen (mobile/laptop)
- **Python**: 3.7+
- **Privileges**: Root/sudo access required

## Required Tools Installation

### 1. Install Python 3

```bash
sudo apt update
sudo apt install -y python3

# Verify installation
python3 --version
```

### 2. Install `ryzenadj` (Ryzen CPU Power Control)

```bash
# Ubuntu/Debian systems
sudo apt update
sudo apt install -y ryzenadj

# Verify installation
which ryzenadj
ryzenadj --version
```

**Alternative**: Build from source
```bash
git clone https://github.com/FlyGoat/RyzenAdj.git
cd RyzenAdj
meson build
ninja -C build
sudo ninja -C build install
```

### 3. Install `sysbench` (CPU Benchmark Tool)

```bash
sudo apt update
sudo apt install -y sysbench

# Verify installation
sysbench --version
```

### 4. Install `stress-ng` (CPU/Memory Stress Tool)

```bash
sudo apt update
sudo apt install -y stress-ng

# Verify installation
stress-ng --version
```

### 5. Ensure `ryzen_smu` Kernel Module is Loaded

```bash
# Check if module is loaded
lsmod | grep ryzen_smu

# If not loaded, load it manually
sudo modprobe ryzen_smu

# To auto-load on boot, add to /etc/modules
echo "ryzen_smu" | sudo tee -a /etc/modules
```

### 6. Sudo Usage (Security Recommendation)

Use the default `sudo` behavior (password required). This is the recommended and safer setup.

The scripts only need elevated privileges for `ryzenadj` operations. You can keep standard sudo prompts and run tests normally.

Avoid adding `NOPASSWD` sudo rules unless you explicitly accept the security tradeoff on your machine.

### 7. Python Standard Library (No External Dependencies Required)

The script uses only Python standard library modules:
- `subprocess` - run system commands
- `re` - parse command output
- `csv` - generate CSV reports
- `statistics` - calculate mean/deviation
- `datetime` - timestamp reports
- `os`, `sys` - file/system operations

No virtual environment is required for this project. A `venv` is optional if you prefer local package isolation.

**Optional** (for prettier terminal output):
```bash
pip install tabulate  # Makes CSV output look better in terminal
```

## Verification Script

Run this to verify all dependencies are installed:

```bash
#!/bin/bash

echo "Checking prerequisites..."

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VER=$(python3 --version | cut -d' ' -f2)
    echo "✓ Python 3: $PYTHON_VER"
else
    echo "✗ Python 3 not found. Install with: sudo apt install python3"
    exit 1
fi

# Check ryzenadj
if command -v ryzenadj &> /dev/null; then
    echo "✓ ryzenadj installed"
else
    echo "✗ ryzenadj not found. Install with: sudo apt install ryzenadj"
    exit 1
fi

# Check sysbench
if command -v sysbench &> /dev/null; then
    echo "✓ sysbench installed"
else
    echo "✗ sysbench not found. Install with: sudo apt install sysbench"
    exit 1
fi

# Check stress-ng
if command -v stress-ng &> /dev/null; then
    echo "✓ stress-ng installed"
else
    echo "✗ stress-ng not found. Install with: sudo apt install stress-ng"
    exit 1
fi

# Check ryzen_smu kernel module
if lsmod | grep -q ryzen_smu; then
    echo "✓ ryzen_smu kernel module loaded"
else
    echo "⚠ ryzen_smu kernel module not loaded. Load with: sudo modprobe ryzen_smu"
fi

# Check sudo access
if sudo -n true 2>/dev/null; then
    echo "✓ sudo credentials are currently cached"
else
    echo "ℹ sudo will prompt for your password when needed (recommended default)"
fi

echo ""
echo "All prerequisites ready!"
```

Save as `check_prereq.sh`, make executable with `chmod +x check_prereq.sh`, and run with `./check_prereq.sh`.

## Troubleshooting

### "ryzenadj not found"
```bash
# Verify it's in PATH
which ryzenadj
# If not found, may need to build from source
```

### "Permission denied" when running ryzenadj
```bash
# Check sudo access
sudo ryzenadj -i

# If you need password, add to sudoers (see step 6 above)
```

### "ryzen_smu kernel module not found"
```bash
# This module should come with linux-headers
sudo apt install -y linux-headers-$(uname -r)

# Rebuild and load
sudo modprobe ryzen_smu
```

### sysbench output parsing errors
```bash
# Check sysbench output format
sysbench cpu --threads=1 --time=5 run

# Output should contain "events per second:"
```

## Quick Start

After installing all prerequisites:

```bash
cd /path/to/ryzen-mobile-power-optimizer
python3 power_optimizer.py
```

Run standalone stability tests for current settings:

```bash
cd /path/to/ryzen-mobile-power-optimizer
python3 cpu_stability_test.py
```

Follow the interactive prompts to configure and run either workflow.
