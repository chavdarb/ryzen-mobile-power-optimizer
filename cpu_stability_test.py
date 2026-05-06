#!/usr/bin/env python3
"""
Standalone CPU Stability Test Harness

Tests current system stability under the active power configuration by stepping
CPU load from 1 core up to N cores, running both sysbench and stress-ng at each
step. Includes an additional memory-pressure stage and a post-run kernel/system
log scan.
"""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime


LOG_KEYWORDS = [
    "mce",
    "machine check",
    "watchdog",
    "segfault",
    "general protection fault",
    "thermal",
    "throttl",
    "hardware error",
    "amdgpu: ring",
    "soft lockup",
    "hard lockup",
]


def run_command(cmd, check=False, shell=False):
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        shell=shell,
    )

    if check and result.returncode != 0:
        print(f"ERROR: command failed: {cmd}")
        if result.stderr:
            print(result.stderr.strip())
        sys.exit(1)

    return result.returncode, result.stdout, result.stderr


def prompt_int(message, default, minimum=None, maximum=None):
    """Prompt for integer input with validation and default fallback."""
    while True:
        raw = input(f"{message} (default {default}): ").strip()
        if not raw:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                print("Invalid number, try again.")
                continue

        if minimum is not None and value < minimum:
            print(f"Value must be >= {minimum}")
            continue

        if maximum is not None and value > maximum:
            print(f"Value must be <= {maximum}")
            continue

        return value


def prompt_bool(message, default=True):
    """Prompt for yes/no input with default fallback."""
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{message} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer y or n.")


def parse_events_per_second(output):
    """Parse sysbench events per second from command output."""
    match = re.search(r"events per second:\s+([\d.]+)", output)
    if not match:
        return None
    return float(match.group(1))


def parse_stressng_bogo_ops(output):
    """Parse stress-ng bogo ops/s metric if available."""
    for line in output.splitlines():
        lowered = line.lower()
        if "metrc:" not in lowered:
            continue

        # Skip metric table header rows.
        if "stressor" in lowered or "(secs)" in lowered:
            continue

        # Expected data row shape:
        # stress-ng: metrc: [pid] cpu 10722 5.00 5.00 0.00 2144.23 2144.50
        payload = re.sub(r"^.*\]\s+", "", line).strip()
        parts = payload.split()
        if len(parts) < 7:
            continue

        # Use real-time bogo ops/s (penultimate column).
        try:
            return float(parts[-2])
        except ValueError:
            continue

    return None


def check_required_tools():
    """Ensure required tools are available in PATH."""
    required = ["python3", "sysbench", "stress-ng"]
    missing = [tool for tool in required if shutil.which(tool) is None]

    if missing:
        print("ERROR: missing required tools:")
        for tool in missing:
            print(f"  - {tool}")
        print("Install prerequisites and rerun.")
        sys.exit(1)


def get_logical_core_count():
    """Return number of online logical cores via nproc."""
    rc, stdout, _ = run_command(["nproc"], check=False)
    if rc != 0:
        print("ERROR: failed to detect CPU core count with nproc")
        sys.exit(1)

    try:
        value = int(stdout.strip())
    except ValueError:
        print("ERROR: invalid nproc output")
        sys.exit(1)

    if value < 1:
        print("ERROR: detected invalid logical core count")
        sys.exit(1)

    return value


def get_current_power_limits():
    """Best-effort printout of active PPT limits if ryzenadj is available."""
    if shutil.which("ryzenadj") is None:
        return None, None, "ryzenadj not found in PATH (skipping power limit info)."

    rc, stdout, stderr = run_command(["sudo", "ryzenadj", "-i"], check=False)
    if rc != 0:
        message = "Failed to query ryzenadj -i."
        if stderr.strip():
            message += f" stderr: {stderr.strip()}"
        return None, None, message

    slow = None
    fast = None
    for line in stdout.splitlines():
        if "PPT LIMIT SLOW" in line:
            match = re.search(r"\|\s+([\d.]+)\s+\|", line)
            if match:
                slow = float(match.group(1))
        if "PPT LIMIT FAST" in line:
            match = re.search(r"\|\s+([\d.]+)\s+\|", line)
            if match:
                fast = float(match.group(1))

    if slow is None or fast is None:
        return None, None, "Could not parse PPT LIMIT SLOW/FAST from ryzenadj output."

    return slow, fast, None


def run_sysbench(core_count, duration):
    """Run sysbench CPU test for a given core count."""
    cmd = [
        "sysbench",
        "cpu",
        f"--threads={core_count}",
        f"--time={duration}",
        "run",
    ]
    rc, stdout, stderr = run_command(cmd, check=False)
    eps = parse_events_per_second(stdout)

    passed = rc == 0 and eps is not None
    return {
        "name": "sysbench",
        "passed": passed,
        "returncode": rc,
        "events_per_sec": eps,
        "stderr": stderr.strip(),
    }


def run_stressng_cpu(core_count, duration):
    """Run stress-ng CPU test for a given core count."""
    cmd = [
        "stress-ng",
        "--cpu",
        str(core_count),
        "--timeout",
        f"{duration}s",
        "--metrics-brief",
    ]

    rc, stdout, stderr = run_command(cmd, check=False)
    merged = "\n".join([stdout, stderr])
    bogo_ops = parse_stressng_bogo_ops(merged)

    passed = rc == 0
    return {
        "name": "stress-ng-cpu",
        "passed": passed,
        "returncode": rc,
        "bogo_ops_per_sec": bogo_ops,
        "stderr": stderr.strip(),
    }


def run_memory_stage(duration, vm_workers, vm_bytes):
    """Run memory-pressure stability stage with stress-ng VM workers."""
    cmd = [
        "stress-ng",
        "--vm",
        str(vm_workers),
        "--vm-bytes",
        vm_bytes,
        "--timeout",
        f"{duration}s",
        "--metrics-brief",
    ]

    rc, stdout, stderr = run_command(cmd, check=False)
    merged = "\n".join([stdout, stderr])
    bogo_ops = parse_stressng_bogo_ops(merged)

    return {
        "name": "stress-ng-memory",
        "passed": rc == 0,
        "returncode": rc,
        "bogo_ops_per_sec": bogo_ops,
        "stderr": stderr.strip(),
    }


def scan_logs(start_time):
    """Scan kernel/system logs since test start for relevant instability markers."""
    text = ""
    source = None

    # Try journalctl first (often more complete and may not need elevated dmesg access).
    journal_cmd = ["journalctl", "--since", start_time, "-k", "--no-pager"]
    rc, stdout, _ = run_command(journal_cmd, check=False)
    if rc == 0:
        text = stdout
        source = "journalctl -k"
    else:
        # Fallback to dmesg with since filter.
        dmesg_cmd = ["dmesg", "--since", start_time]
        rc, stdout, _ = run_command(dmesg_cmd, check=False)
        if rc == 0:
            text = stdout
            source = "dmesg"

    if source is None:
        return {
            "source": "none",
            "passed": True,
            "matches": [],
            "error": "Could not read journalctl or dmesg logs.",
        }

    matches = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(keyword in lowered for keyword in LOG_KEYWORDS):
            matches.append(line.strip())

    return {
        "source": source,
        "passed": len(matches) == 0,
        "matches": matches,
        "error": None,
    }


def print_cpu_step_result(core_count, sysbench_result, stressng_result):
    """Print one core-step result line."""
    status = "PASS" if (sysbench_result["passed"] and stressng_result["passed"]) else "FAIL"

    sysbench_eps = (
        f"{sysbench_result['events_per_sec']:.2f}"
        if sysbench_result["events_per_sec"] is not None
        else "n/a"
    )
    stressng_bogo = (
        f"{stressng_result['bogo_ops_per_sec']:.2f}"
        if stressng_result["bogo_ops_per_sec"] is not None
        else "n/a"
    )

    print(
        f"[{status}] cores={core_count:>2} | "
        f"sysbench_eps={sysbench_eps:>10} | "
        f"stressng_bogo_ops_s={stressng_bogo:>10}"
    )


def print_summary(cpu_results, memory_result, log_result, duration, start_cores, end_cores):
    """Print final run summary."""
    print("\n" + "=" * 72)
    print("Stability Test Summary")
    print("=" * 72)
    print(f"Core range: {start_cores}..{end_cores}")
    print(f"Duration per CPU step: {duration}s")

    total_steps = len(cpu_results)
    passed_steps = sum(1 for row in cpu_results if row["step_passed"])
    failed_steps = total_steps - passed_steps

    print(f"CPU scaling steps: total={total_steps}, passed={passed_steps}, failed={failed_steps}")

    first_failure = next((row for row in cpu_results if not row["step_passed"]), None)
    if first_failure:
        print(f"First CPU-scaling failure at cores={first_failure['core_count']}")
    else:
        print("CPU-scaling stage: all steps passed")

    if memory_result is not None:
        mem_status = "PASS" if memory_result["passed"] else "FAIL"
        mem_bogo = (
            f"{memory_result['bogo_ops_per_sec']:.2f}"
            if memory_result["bogo_ops_per_sec"] is not None
            else "n/a"
        )
        print(f"Memory stage: {mem_status} (bogo_ops/s={mem_bogo})")
    else:
        print("Memory stage: skipped")

    if log_result is not None:
        log_status = "PASS" if log_result["passed"] else "FAIL"
        print(f"Log scan: {log_status} (source={log_result['source']})")
        if log_result["error"]:
            print(f"  Note: {log_result['error']}")
        if log_result["matches"]:
            print("  Matched log lines (up to 10):")
            for line in log_result["matches"][:10]:
                print(f"    - {line}")
            if len(log_result["matches"]) > 10:
                print(f"    ... and {len(log_result['matches']) - 10} more")
    else:
        print("Log scan: skipped")

    overall_pass = failed_steps == 0
    if memory_result is not None:
        overall_pass = overall_pass and memory_result["passed"]
    if log_result is not None:
        overall_pass = overall_pass and log_result["passed"]

    print("-" * 72)
    print(f"Overall status: {'PASS' if overall_pass else 'FAIL'}")
    print("=" * 72)


def collect_args(total_cores):
    """Parse CLI args and resolve defaults/prompt fallbacks."""
    parser = argparse.ArgumentParser(
        description="CPU stability test over 1..N cores under current settings."
    )
    parser.add_argument("--duration", type=int, help="Duration per CPU step in seconds")
    parser.add_argument("--start-cores", type=int, help="Start core count")
    parser.add_argument("--end-cores", type=int, help="End core count")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt for missing values; use defaults",
    )
    parser.add_argument(
        "--skip-memory-stage",
        action="store_true",
        help="Skip stress-ng VM memory-pressure stage",
    )
    parser.add_argument(
        "--skip-log-scan",
        action="store_true",
        help="Skip post-run kernel/system log scan",
    )
    parser.add_argument(
        "--memory-workers",
        type=int,
        help="stress-ng --vm worker count for memory stage",
    )
    parser.add_argument(
        "--memory-bytes",
        default=None,
        help="stress-ng --vm-bytes value (default 70%%)",
    )

    args = parser.parse_args()

    default_duration = 360
    default_start = 1
    default_end = total_cores
    default_mem_workers = max(1, min(total_cores, 4))
    default_mem_bytes = "70%"

    if args.no_prompt:
        duration = args.duration if args.duration is not None else default_duration
        start_cores = args.start_cores if args.start_cores is not None else default_start
        end_cores = args.end_cores if args.end_cores is not None else default_end
        memory_workers = (
            args.memory_workers if args.memory_workers is not None else default_mem_workers
        )
    else:
        duration = (
            args.duration
            if args.duration is not None
            else prompt_int("Duration per core step in seconds", default_duration, minimum=1)
        )
        start_cores = (
            args.start_cores
            if args.start_cores is not None
            else prompt_int("Start core count", default_start, minimum=1, maximum=total_cores)
        )
        end_cores = (
            args.end_cores
            if args.end_cores is not None
            else prompt_int("End core count", default_end, minimum=1, maximum=total_cores)
        )
        memory_workers = (
            args.memory_workers
            if args.memory_workers is not None
            else prompt_int(
                "Memory stage VM workers",
                default_mem_workers,
                minimum=1,
                maximum=total_cores,
            )
        )

    memory_bytes = args.memory_bytes if args.memory_bytes else default_mem_bytes

    if duration < 1:
        print("ERROR: --duration must be >= 1")
        sys.exit(1)

    if start_cores < 1 or end_cores < 1:
        print("ERROR: core counts must be >= 1")
        sys.exit(1)

    if end_cores > total_cores:
        print(f"ERROR: --end-cores cannot exceed detected logical cores ({total_cores})")
        sys.exit(1)

    if start_cores > end_cores:
        print("ERROR: --start-cores cannot be greater than --end-cores")
        sys.exit(1)

    if memory_workers < 1 or memory_workers > total_cores:
        print(f"ERROR: --memory-workers must be in range 1..{total_cores}")
        sys.exit(1)

    run_memory_stage_flag = not args.skip_memory_stage
    run_log_scan_flag = not args.skip_log_scan

    if not args.no_prompt:
        # Prompt only when not explicitly disabled by CLI flags.
        if args.skip_memory_stage is False:
            run_memory_stage_flag = prompt_bool("Run memory-pressure stage", default=True)
        if args.skip_log_scan is False:
            run_log_scan_flag = prompt_bool("Run post-run kernel/system log scan", default=True)

    return {
        "duration": duration,
        "start_cores": start_cores,
        "end_cores": end_cores,
        "run_memory_stage": run_memory_stage_flag,
        "run_log_scan": run_log_scan_flag,
        "memory_workers": memory_workers,
        "memory_bytes": memory_bytes,
        "no_prompt": args.no_prompt,
    }


def main():
    check_required_tools()
    total_cores = get_logical_core_count()
    config = collect_args(total_cores)

    now = datetime.now()
    start_time = now.strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 72)
    print("CPU Stability Test")
    print("=" * 72)

    slow, fast, limit_msg = get_current_power_limits()
    if limit_msg:
        print(f"Power limits: {limit_msg}")
    else:
        print(f"Current power limits: slow={slow}W, fast={fast}W")

    print(f"Detected logical cores: {total_cores}")
    print(f"Core sweep: {config['start_cores']}..{config['end_cores']}")
    print(f"Duration per CPU step: {config['duration']}s")
    print(
        "Memory stage: "
        + (
            f"enabled (workers={config['memory_workers']}, vm-bytes={config['memory_bytes']})"
            if config["run_memory_stage"]
            else "disabled"
        )
    )
    print(f"Log scan: {'enabled' if config['run_log_scan'] else 'disabled'}")
    print("=" * 72)

    if not config["no_prompt"]:
        if not prompt_bool("Start stability test now", default=True):
            print("Aborted by user.")
            sys.exit(0)

    cpu_results = []
    memory_result = None
    log_result = None

    try:
        for core_count in range(config["start_cores"], config["end_cores"] + 1):
            sysbench_result = run_sysbench(core_count, config["duration"])
            stressng_result = run_stressng_cpu(core_count, config["duration"])

            step_passed = sysbench_result["passed"] and stressng_result["passed"]
            cpu_results.append(
                {
                    "core_count": core_count,
                    "step_passed": step_passed,
                    "sysbench": sysbench_result,
                    "stressng_cpu": stressng_result,
                }
            )

            print_cpu_step_result(core_count, sysbench_result, stressng_result)

        if config["run_memory_stage"]:
            print("\nRunning memory-pressure stage...")
            memory_result = run_memory_stage(
                duration=config["duration"],
                vm_workers=config["memory_workers"],
                vm_bytes=config["memory_bytes"],
            )
            mem_status = "PASS" if memory_result["passed"] else "FAIL"
            print(
                f"[{mem_status}] memory stage | "
                f"bogo_ops_s={memory_result['bogo_ops_per_sec'] if memory_result['bogo_ops_per_sec'] is not None else 'n/a'}"
            )

        if config["run_log_scan"]:
            print("\nScanning kernel/system logs for instability indicators...")
            log_result = scan_logs(start_time)
            log_status = "PASS" if log_result["passed"] else "FAIL"
            print(
                f"[{log_status}] log scan using {log_result['source']} "
                f"(matches={len(log_result['matches'])})"
            )

    except KeyboardInterrupt:
        print("\nInterrupted by user. Printing partial summary...")

    print_summary(
        cpu_results=cpu_results,
        memory_result=memory_result,
        log_result=log_result,
        duration=config["duration"],
        start_cores=config["start_cores"],
        end_cores=config["end_cores"],
    )


if __name__ == "__main__":
    main()
