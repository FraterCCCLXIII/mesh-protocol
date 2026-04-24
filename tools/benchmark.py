#!/usr/bin/env python3
"""Benchmark all four simulators."""

import subprocess
import time
import re

SIMULATORS = [
    {
        "name": "HOLON v3",
        "dir": "simulator",
        "scenarios": [
            ("small_network", "100 users, 1hr"),
            ("spam_attack", "760 users, 1hr"),
        ]
    },
    {
        "name": "HOLON v4", 
        "dir": "simulator_v4",
        "scenarios": [
            ("small_network", "100 users, 1hr"),
            ("full_ecosystem", "900 users, 4hr"),
        ]
    },
    {
        "name": "Relay v2",
        "dir": "simulator_relay_v2", 
        "scenarios": [
            ("small", "100 users, 1hr"),
            ("full", "800 users, 6hr"),
        ]
    },
    {
        "name": "Relay v1.4-1",
        "dir": "simulator_relay_v1.4.1",
        "scenarios": [
            ("small", "100 users, 1hr"),
            ("full", "600 users, 6hr"),
        ]
    },
]

def run_benchmark(sim_dir, scenario, runs=3):
    """Run a scenario multiple times and return avg time."""
    times = []
    for i in range(runs):
        start = time.time()
        result = subprocess.run(
            ["python", "run_simulation.py", "--scenario", scenario, "--seed", str(i+1)],
            cwd=sim_dir,
            capture_output=True,
            text=True
        )
        elapsed = time.time() - start
        times.append(elapsed)
    return sum(times) / len(times), min(times), max(times)

def extract_metrics(sim_dir, scenario):
    """Run once and extract key metrics from output."""
    result = subprocess.run(
        ["python", "run_simulation.py", "--scenario", scenario, "--seed", "42"],
        cwd=sim_dir,
        capture_output=True,
        text=True
    )
    output = result.stdout
    
    metrics = {}
    
    # Try to extract common metrics
    patterns = [
        (r"Entities:\s*(\d+)", "entities"),
        (r"Events?:\s*(\d+)", "events"),
        (r"Content:\s*(\d+)", "content"),
        (r"Links?:\s*(\d+)", "links"),
        (r"States?:\s*(\d+)", "states"),
        (r"Total:\s*(\d+)", "total_objects"),
        (r"Size:\s*([\d.]+)\s*MB", "size_mb"),
        (r"Avg time:\s*([\d.]+)\s*ms", "view_avg_ms"),
        (r"P95 time:\s*([\d.]+)\s*ms", "view_p95_ms"),
    ]
    
    for pattern, key in patterns:
        match = re.search(pattern, output)
        if match:
            val = match.group(1)
            metrics[key] = float(val) if '.' in val else int(val)
    
    return metrics

print("=" * 80)
print("SIMULATOR BENCHMARK COMPARISON")
print("=" * 80)
print()

# Run small scenarios (comparable ~100 users)
print("SMALL SCENARIOS (~100 users, 1hr simulation)")
print("-" * 80)
print(f"{'Simulator':<20} {'Scenario':<20} {'Avg Time':<12} {'Min':<10} {'Max':<10}")
print("-" * 80)

for sim in SIMULATORS:
    scenario, desc = sim["scenarios"][0]
    avg, mn, mx = run_benchmark(sim["dir"], scenario)
    print(f"{sim['name']:<20} {scenario:<20} {avg:.3f}s       {mn:.3f}s     {mx:.3f}s")

print()

# Run full scenarios
print("FULL SCENARIOS (600-900 users, 4-6hr simulation)")
print("-" * 80)
print(f"{'Simulator':<20} {'Scenario':<20} {'Avg Time':<12} {'Min':<10} {'Max':<10}")
print("-" * 80)

for sim in SIMULATORS:
    scenario, desc = sim["scenarios"][1]
    avg, mn, mx = run_benchmark(sim["dir"], scenario)
    print(f"{sim['name']:<20} {scenario:<20} {avg:.3f}s       {mn:.3f}s     {mx:.3f}s")

print()

# Extract metrics from full runs
print("METRICS FROM FULL SCENARIOS")
print("-" * 80)

all_metrics = {}
for sim in SIMULATORS:
    scenario, desc = sim["scenarios"][1]
    metrics = extract_metrics(sim["dir"], scenario)
    all_metrics[sim["name"]] = metrics

# Print comparison table
print(f"{'Metric':<25} {'HOLON v3':<15} {'HOLON v4':<15} {'Relay v2':<15} {'Relay v1.4-1':<15}")
print("-" * 80)

metric_names = [
    ("total_objects", "Total Objects"),
    ("events", "Events"),
    ("content", "Content"),
    ("links", "Links"),
    ("states", "States"),
    ("size_mb", "Size (MB)"),
    ("view_avg_ms", "View Avg (ms)"),
    ("view_p95_ms", "View P95 (ms)"),
]

for key, label in metric_names:
    row = f"{label:<25}"
    for sim in SIMULATORS:
        val = all_metrics.get(sim["name"], {}).get(key, "-")
        if isinstance(val, float):
            row += f"{val:<15.2f}"
        elif isinstance(val, int):
            row += f"{val:<15,}"
        else:
            row += f"{val:<15}"
    print(row)

print()
print("=" * 80)
