
# Ryzen mobile power optimizer requirements


## Project goals

Build a python harness test script that finds the optimal power settings for mobile ryzen processor.

The goal is to find the best performance vs power spot and consequently configure this as default power profule in Ubuntu 26.04 LTS Linux system.

The project implements python scripts that iterate incrementally over power CPU power configurations, measures the performance and produces report that allows to select optimal powersetting for the CPU.

## Requirements

The solution is implemented by python script that orchestrates calls to Lunux tools intalled on the ubuntu system.

Create `prerequisites.md` file with instructions on how to install the required script dependencies.

The script will do the following:

1. Read the current CPU power limits and show it and store it as max power limits
2. Ask for starting slow power limit (slow-limit start) in W to start the tests. Default to 15W.
3. Ask for fast power limit offset (fast-limit-offset) in W to be added on top of the slow power limit. Default to 5W. This offset applies to all iterations.
4. Show confirmation promt to start the test
5. Start iterating over the starting power (start-slow-limit) 
    * Set CPU power limits to slow-limit=slow-limit-start, fast-limit=slow-limit-start+fast-limit-add
    * Get current power limits and check they are set correctly
    * Run performance benchmark 5 times to measure the performance and collect the performance result
    * Get the average performance result of 3 results with less deviation and output a line with the CPU Power settings and measured performance.
    * Collect the results
    * Check the power setting again against the expected set values    
    * Increase both slow-limit and fast-limit with 1W and execute the tests again
    * Stop the test until the max slow power limit is reached
6. Create and output the report of the relative performance increase for each 1W power increment. The report should help find sweet spot when increase of power usafe does not increase the performance proportionally.

## Implementation details

### Set CPU power limits
To set processor power limits use `ryzenadj` command line tool.
Use:
- 'slow-limit' to set long term power envelope
- 'fast-limit' to set short term power envelope (configured as offset from slow-limit)
- limit is set in milliwatts: 28000=28W
Example:
```
sudo ryzenadj --slow-limit=15000 --fast-limit=20000
```

The fast-limit is configured by the user as an offset added to the slow-limit. Both are incremented equally in each iteration.

### Get current CPU power limits
* Get currently configured power limits
To get current power limits use `ryzenadj -i` command line tool.
```
>sudo ryzenadj -i | grep -E 'PPT LIMIT FAST|PPT LIMIT SLOW'
detected compatible ryzen_smu kernel module
| PPT LIMIT FAST      |    20.000 | fast-limit         |
| PPT LIMIT SLOW      |    15.000 | slow-limit  
```

### Measure performence

Use sysbench to measure the performance. Use `events per second` as performance indicator. And extract that as performance measurement.

Warmup benchmark
```
sysbench cpu --threads=$(nproc) --time=15 run > /dev/null
```

Benchmark (30 seconds per iteration)
```
sysbench cpu --threads=$(nproc) --time=30 run
```


