#!/usr/bin/env python3
"""
Ryzen Mobile Power Optimizer
Finds optimal CPU power settings by testing performance across different power limits.
"""

import subprocess
import re
import csv
import sys
import os
from datetime import datetime
from statistics import mean, stdev
from pathlib import Path


class PowerOptimizer:
    """Main power optimization harness."""
    
    def __init__(self):
        self.max_slow_limit = None
        self.slow_limit_start = None
        self.fast_limit_offset = None
        self.results = []
        self.prev_performance = None
        
    def run_command(self, cmd, check=True, sudo=False):
        """
        Run a shell command and return output.
        
        Args:
            cmd: Command to run (list or string)
            check: Raise exception on non-zero exit
            sudo: Prepend 'sudo' to command
            
        Returns:
            (returncode, stdout, stderr)
        """
        if sudo and isinstance(cmd, list):
            cmd = ['sudo'] + cmd
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                shell=isinstance(cmd, str)
            )
            
            if check and result.returncode != 0:
                print(f"❌ Command failed: {cmd}")
                print(f"stderr: {result.stderr}")
                sys.exit(1)
            
            return result.returncode, result.stdout, result.stderr
        
        except Exception as e:
            print(f"❌ Error running command: {e}")
            sys.exit(1)
    
    def check_prerequisites(self):
        """Verify all required tools are installed."""
        print("\n📋 Checking prerequisites...")
        
        tools = ['ryzenadj', 'sysbench', 'python3']
        
        for tool in tools:
            returncode, _, _ = self.run_command(['which', tool], check=False)
            if returncode == 0:
                print(f"  ✓ {tool} found")
            else:
                print(f"  ✗ {tool} NOT FOUND")
                print(f"    Install with: sudo apt install {tool}")
                sys.exit(1)
        
        # Check ryzen_smu kernel module
        returncode, output, _ = self.run_command(['lsmod'], check=False)
        if 'ryzen_smu' in output:
            print(f"  ✓ ryzen_smu kernel module loaded")
        else:
            print(f"  ⚠ ryzen_smu kernel module NOT loaded")
            print(f"    Load with: sudo modprobe ryzen_smu")
            print(f"    Or add 'ryzen_smu' to /etc/modules for auto-load")
            response = input("\n  Continue anyway? (y/n): ").strip().lower()
            if response != 'y':
                sys.exit(1)
        
        print("  ✓ All prerequisites OK\n")
    
    def get_current_power_limits(self):
        """
        Query current CPU power limits from ryzenadj.
        
        Returns:
            (slow_limit_W, fast_limit_W) or (None, None) on error
        """
        returncode, output, _ = self.run_command(['ryzenadj', '-i'], 
                                                   check=False, sudo=True)
        
        if returncode != 0:
            print("❌ Failed to query power limits")
            return None, None
        
        slow_limit = None
        fast_limit = None
        
        # Parse output: | PPT LIMIT SLOW      |    15.000 | slow-limit
        for line in output.split('\n'):
            if 'PPT LIMIT SLOW' in line:
                match = re.search(r'\|\s+([\d.]+)\s+\|', line)
                if match:
                    slow_limit = float(match.group(1))
            elif 'PPT LIMIT FAST' in line:
                match = re.search(r'\|\s+([\d.]+)\s+\|', line)
                if match:
                    fast_limit = float(match.group(1))
        
        return slow_limit, fast_limit
    
    def discover_max_power_limit(self):
        """Discover system's maximum slow power limit."""
        print("🔍 Discovering system maximum power limit...")
        
        slow_limit, _ = self.get_current_power_limits()
        
        if slow_limit is None:
            print("❌ Could not read current power limits from ryzenadj")
            sys.exit(1)
        
        self.max_slow_limit = slow_limit
        print(f"  System max slow limit: {self.max_slow_limit}W\n")
    
    def get_user_inputs(self):
        """Collect user configuration inputs."""
        print("⚙️  Configuration")
        print(f"  System max power limit: {self.max_slow_limit}W\n")
        
        # Slow limit start
        while True:
            try:
                user_input = input(f"  Enter starting slow limit in W (default 15): ").strip()
                self.slow_limit_start = float(user_input) if user_input else 15.0
                
                if self.slow_limit_start < 1 or self.slow_limit_start > self.max_slow_limit:
                    print(f"    ❌ Must be between 1W and {self.max_slow_limit}W")
                    continue
                break
            except ValueError:
                print("    ❌ Invalid input, enter a number")
        
        # Fast limit offset
        while True:
            try:
                user_input = input(f"  Enter fast limit offset in W (default 5): ").strip()
                self.fast_limit_offset = float(user_input) if user_input else 5.0
                
                if self.fast_limit_offset < 0:
                    print(f"    ❌ Must be >= 0W")
                    continue
                break
            except ValueError:
                print("    ❌ Invalid input, enter a number")
        
        print(f"\n  Configuration:")
        print(f"    Starting slow limit: {self.slow_limit_start}W")
        print(f"    Fast limit offset: {self.fast_limit_offset}W")
        print(f"    Power range: {self.slow_limit_start}W - {self.max_slow_limit}W")
        print(f"    Benchmark duration: 30 seconds × 5 runs per power level")
        print(f"    Estimated total time: ~{int((self.max_slow_limit - self.slow_limit_start + 1) * 2.5)} minutes\n")
        
        # Confirmation
        while True:
            response = input("  Ready to start tests? (y/n): ").strip().lower()
            if response in ('y', 'yes'):
                break
            elif response in ('n', 'no'):
                print("Aborting.")
                sys.exit(0)
    
    def run_warmup(self):
        """Run CPU warmup to stabilize thermal state."""
        print("🔥 Running warmup (15 seconds)...\n")
        
        returncode, _, _ = self.run_command(
            f'sysbench cpu --threads=$(nproc) --time=15 run > /dev/null 2>&1',
            check=False,
            sudo=False
        )
        
        if returncode != 0:
            print("❌ Warmup failed. Continuing anyway...\n")
        else:
            print("✓ Warmup complete\n")
    
    def set_power_limits(self, slow_limit_W, fast_limit_W):
        """
        Set CPU power limits.
        
        Args:
            slow_limit_W: Slow (long-term) limit in watts
            fast_limit_W: Fast (short-term) limit in watts
        """
        slow_mW = int(slow_limit_W * 1000)
        fast_mW = int(fast_limit_W * 1000)
        
        cmd = ['ryzenadj', f'--slow-limit={slow_mW}', f'--fast-limit={fast_mW}']
        
        returncode, stdout, stderr = self.run_command(cmd, check=False, sudo=True)
        
        if returncode != 0:
            print(f"❌ Failed to set power limits to {slow_limit_W}W / {fast_limit_W}W")
            print(f"   stderr: {stderr}")
            sys.exit(1)
    
    def verify_power_limits(self, expected_slow_W, expected_fast_W, tolerance_pct=1.0):
        """
        Verify that power limits were applied correctly.
        
        Args:
            expected_slow_W: Expected slow limit in watts
            expected_fast_W: Expected fast limit in watts
            tolerance_pct: Tolerance in percent
            
        Returns:
            True if within tolerance, False otherwise
        """
        actual_slow, actual_fast = self.get_current_power_limits()
        
        if actual_slow is None or actual_fast is None:
            print(f"❌ Could not read power limits after setting")
            return False
        
        slow_error_pct = abs(actual_slow - expected_slow_W) / expected_slow_W * 100
        fast_error_pct = abs(actual_fast - expected_fast_W) / expected_fast_W * 100
        
        if slow_error_pct > tolerance_pct or fast_error_pct > tolerance_pct:
            print(f"❌ Power limits not applied correctly:")
            print(f"   Expected: {expected_slow_W}W / {expected_fast_W}W")
            print(f"   Actual:   {actual_slow}W / {actual_fast}W")
            print(f"   Error: {slow_error_pct:.1f}% / {fast_error_pct:.1f}%")
            return False
        
        return True
    
    def run_benchmark(self, duration=30):
        """
        Run CPU benchmark and extract performance metric.
        
        Args:
            duration: Benchmark duration in seconds
            
        Returns:
            Events per second (float) or None on error
        """
        cmd = f'sysbench cpu --threads=$(nproc) --time={duration} run'
        
        returncode, output, _ = self.run_command(cmd, check=False, sudo=False)
        
        if returncode != 0:
            return None
        
        # Extract "events per second:" from output
        match = re.search(r'events per second:\s+([\d.]+)', output)
        if match:
            return float(match.group(1))
        
        return None
    
    def select_best_3_results(self, results, deviation_threshold_pct=2.0):
        """
        Select 3 results with lowest deviation, or fallback to middle 3.
        
        Args:
            results: List of 5 benchmark results
            deviation_threshold_pct: Max acceptable deviation in percent
            
        Returns:
            List of 3 selected results
        """
        if len(results) < 3:
            return results
        
        # Try all 3-sample combinations
        best_group = None
        best_deviation = float('inf')
        
        for i in range(len(results) - 2):
            for j in range(i + 1, len(results) - 1):
                for k in range(j + 1, len(results)):
                    group = [results[i], results[j], results[k]]
                    group_mean = mean(group)
                    group_stdev = stdev(group)
                    group_cv = (group_stdev / group_mean) * 100  # Coefficient of variation
                    
                    if group_cv < best_deviation:
                        best_deviation = group_cv
                        best_group = group
        
        # If best found group is within threshold, use it
        if best_deviation <= deviation_threshold_pct:
            return best_group
        
        # Fallback: remove highest and lowest
        sorted_results = sorted(results)
        return sorted_results[1:4]
    
    def calculate_incremental_change(self, current_performance):
        """
        Calculate incremental performance change.
        
        Args:
            current_performance: Current benchmark result
            
        Returns:
            Percentage change from previous, or 0.0 for first run
        """
        if self.prev_performance is None:
            return 0.0
        
        change = ((current_performance - self.prev_performance) / self.prev_performance) * 100
        return change
    
    def run_iteration(self, slow_limit_W, fast_limit_W):
        """
        Run one complete test iteration at given power limits.
        
        Returns:
            Tuple: (avg_performance, incremental_pct_change) or (None, None) on error
        """
        print(f"\n📊 Testing: {slow_limit_W}W slow / {fast_limit_W}W fast")
        
        # Set limits
        self.set_power_limits(slow_limit_W, fast_limit_W)
        
        # Verify limits
        if not self.verify_power_limits(slow_limit_W, fast_limit_W):
            print(f"   ⚠️ Power limits verification failed. Aborting test.")
            sys.exit(1)
        
        # Run 5 benchmarks
        print(f"   Running 5 benchmarks (30s each)...")
        benchmark_results = []
        
        for i in range(5):
            result = self.run_benchmark(duration=30)
            if result is None:
                print(f"   ❌ Benchmark {i+1}/5 failed")
                sys.exit(1)
            
            benchmark_results.append(result)
            print(f"     Run {i+1}/5: {result:.1f} events/sec")
        
        # Select best 3
        best_3 = self.select_best_3_results(benchmark_results)
        avg_performance = mean(best_3)
        
        print(f"   Selected 3 best results: {[f'{x:.1f}' for x in best_3]}")
        print(f"   Average: {avg_performance:.1f} events/sec")
        
        # Calculate incremental change
        incremental_pct = self.calculate_incremental_change(avg_performance)
        print(f"   Change from previous: {incremental_pct:+.2f}%")
        
        # Verify power limits again
        if not self.verify_power_limits(slow_limit_W, fast_limit_W):
            print(f"   ⚠️ Power limits drifted! Proceeding anyway...")
        
        # Update for next iteration
        self.prev_performance = avg_performance
        
        return avg_performance, incremental_pct
    
    def run_test_suite(self):
        """Run the complete test suite across all power levels."""
        print("\n" + "="*60)
        print("🚀 STARTING TEST SUITE")
        print("="*60)
        
        current_slow_limit = self.slow_limit_start
        current_fast_limit = self.slow_limit_start + self.fast_limit_offset
        
        while current_slow_limit <= self.max_slow_limit:
            avg_perf, incremental_pct = self.run_iteration(
                current_slow_limit,
                current_fast_limit
            )
            
            self.results.append({
                'slow_limit_W': current_slow_limit,
                'fast_limit_W': current_fast_limit,
                'avg_performance_events_per_sec': avg_perf,
                'incremental_percent_change': incremental_pct
            })
            
            # Increment for next iteration
            current_slow_limit += 1.0
            current_fast_limit += 1.0
        
        print("\n" + "="*60)
        print("✅ TEST SUITE COMPLETE")
        print("="*60)
    
    def save_report(self):
        """Save results to CSV file."""
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"power-test-report-{timestamp}.csv"
        
        print(f"\n💾 Saving report to: {filename}\n")
        
        try:
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = [
                    'slow_limit_W',
                    'fast_limit_W',
                    'avg_performance_events_per_sec',
                    'incremental_percent_change'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
            
            print(f"✓ Report saved: {filename}\n")
            return filename
        
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
            sys.exit(1)
    
    def display_report(self):
        """Display results in human-readable format."""
        print("📈 RESULTS SUMMARY")
        print("-" * 80)
        print(f"{'Slow Limit':>12} | {'Fast Limit':>12} | {'Performance':>18} | {'Change':>10}")
        print("-" * 80)
        
        for result in self.results:
            slow = result['slow_limit_W']
            fast = result['fast_limit_W']
            perf = result['avg_performance_events_per_sec']
            change = result['incremental_percent_change']
            
            print(f"{slow:>12.1f}W | {fast:>12.1f}W | {perf:>18.1f} | {change:>+9.2f}%")
        
        print("-" * 80)
        
        # Find sweet spot (max performance with diminishing returns)
        print("\n💡 SWEET SPOT ANALYSIS")
        diminishing_threshold = 0.2  # Performance gain < 0.2% per 1W
        
        for i, result in enumerate(self.results):
            if result['incremental_percent_change'] < diminishing_threshold and i > 0:
                prev = self.results[i - 1]
                print(f"  Diminishing returns after: {prev['slow_limit_W']}W / {prev['fast_limit_W']}W")
                print(f"    (Gain drops to {result['incremental_percent_change']:.3f}% at {result['slow_limit_W']}W)")
                break
    
    def run(self):
        """Main execution flow."""
        try:
            self.check_prerequisites()
            self.discover_max_power_limit()
            self.get_user_inputs()
            self.run_warmup()
            self.run_test_suite()
            report_file = self.save_report()
            self.display_report()
            
            print("\n✅ Power optimization testing complete!")
            print(f"   Report saved: {report_file}")
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Test interrupted by user")
            if self.results:
                report_file = self.save_report()
                print(f"   Partial results saved: {report_file}")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            sys.exit(1)


def main():
    optimizer = PowerOptimizer()
    optimizer.run()


if __name__ == '__main__':
    main()
