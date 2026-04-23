#!/usr/bin/env python3
"""
HOLON Protocol Simulator - Comparison Mode

Run the same scenario with different configurations and compare results.
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any

from run_simulation import Simulator
from scenarios import ScenarioType, ScenarioConfig, get_scenario
from visualization import generate_comparison_charts, load_results


@dataclass
class ComparisonConfig:
    """Configuration for a comparison run."""
    name: str
    description: str
    base_scenario: ScenarioType
    variations: list[dict]  # List of parameter overrides


# Pre-defined comparisons
COMPARISONS = {
    "scale_comparison": ComparisonConfig(
        name="Scale Comparison",
        description="Compare behavior at different network sizes",
        base_scenario=ScenarioType.SMALL_NETWORK,
        variations=[
            {"name": "100 users", "users_multiplier": 1},
            {"name": "500 users", "users_multiplier": 5},
            {"name": "1000 users", "users_multiplier": 10},
        ],
    ),
    "relay_comparison": ComparisonConfig(
        name="Relay Configuration Comparison",
        description="Compare single vs multi-relay setups",
        base_scenario=ScenarioType.SMALL_NETWORK,
        variations=[
            {"name": "1 Relay", "num_relays": 1},
            {"name": "3 Relays", "num_relays": 3},
            {"name": "5 Relays", "num_relays": 5},
        ],
    ),
    "latency_comparison": ComparisonConfig(
        name="Network Latency Comparison",
        description="Compare behavior under different latency conditions",
        base_scenario=ScenarioType.MULTI_RELAY,
        variations=[
            {"name": "Low Latency (10ms)", "network_latency_ms": 10},
            {"name": "Medium Latency (50ms)", "network_latency_ms": 50},
            {"name": "High Latency (200ms)", "network_latency_ms": 200},
        ],
    ),
    "churn_comparison": ComparisonConfig(
        name="Member Churn Comparison",
        description="Compare group key management under different churn rates",
        base_scenario=ScenarioType.GROUP_ENCRYPTION,
        variations=[
            {"name": "Low Churn (1%)", "member_churn_rate": 0.01},
            {"name": "Medium Churn (5%)", "member_churn_rate": 0.05},
            {"name": "High Churn (10%)", "member_churn_rate": 0.10},
        ],
    ),
    "view_complexity": ComparisonConfig(
        name="View Complexity Comparison",
        description="Compare view execution with different numbers of views",
        base_scenario=ScenarioType.VIEW_STRESS,
        variations=[
            {"name": "10 Views", "views_to_create": 10},
            {"name": "50 Views", "views_to_create": 50},
            {"name": "100 Views", "views_to_create": 100},
        ],
    ),
}


def apply_variation(base_scenario: ScenarioConfig, variation: dict) -> ScenarioConfig:
    """Apply a variation to a base scenario configuration."""
    # Create a copy of the scenario
    import copy
    scenario = copy.deepcopy(base_scenario)

    # Apply user multiplier if present
    if "users_multiplier" in variation:
        multiplier = variation["users_multiplier"]
        scenario.users = {k: int(v * multiplier) for k, v in scenario.users.items()}

    # Apply direct overrides
    for key, value in variation.items():
        if key in ("name", "users_multiplier"):
            continue
        if hasattr(scenario, key):
            setattr(scenario, key, value)

    # Update name
    scenario.name = f"{scenario.name} - {variation.get('name', 'Variation')}"

    return scenario


def run_comparison(comparison_name: str, seed: int = None, output_dir: str = "results/comparisons"):
    """Run a comparison and collect results."""
    if comparison_name not in COMPARISONS:
        print(f"Unknown comparison: {comparison_name}")
        print(f"Available: {list(COMPARISONS.keys())}")
        return

    config = COMPARISONS[comparison_name]
    base_scenario = get_scenario(config.base_scenario)

    print(f"\n{'='*60}")
    print(f"COMPARISON: {config.name}")
    print(f"{'='*60}")
    print(f"Description: {config.description}")
    print(f"Base scenario: {config.base_scenario.value}")
    print(f"Variations: {len(config.variations)}")

    results_files = []
    all_results = []

    output_path = Path(output_dir) / comparison_name
    output_path.mkdir(parents=True, exist_ok=True)

    for i, variation in enumerate(config.variations):
        var_name = variation.get("name", f"Variation {i+1}")
        print(f"\n--- Running: {var_name} ---")

        # Apply variation
        scenario = apply_variation(base_scenario, variation)

        # Run simulation - create a minimal simulator with the modified scenario
        import random
        from core import Storage, ViewEngine
        from agents import AgentManager

        if seed is not None:
            random.seed(seed + i)  # Different seed for each variation

        # Create simulator manually with modified scenario
        simulator = Simulator.__new__(Simulator)
        simulator.scenario = scenario
        simulator.network = None  # No network sim for comparison mode
        simulator.storage = Storage()
        simulator.agent_manager = AgentManager(simulator.storage)
        simulator.view_engine = ViewEngine(simulator.storage)
        simulator.metrics_history = []
        simulator.view_executions = []
        simulator.network_metrics = []
        simulator.key_rotation_events = []
        simulator.group_key_events = []
        simulator.current_time = datetime.utcnow()
        simulator.start_time = simulator.current_time
        simulator.views = []
        simulator.last_key_rotation = simulator.current_time
        simulator.key_versions = {}

        start = time.time()
        simulator.setup()
        simulator.run(progress_interval=25)
        elapsed = time.time() - start

        print(f"  Completed in {elapsed:.1f}s")

        # Save results
        results = simulator.get_results()
        results["variation"] = variation
        all_results.append(results)

        # Save individual result
        safe_name = var_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        results_file = output_path / f"{safe_name}.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        results_files.append(str(results_file))

    # Generate comparison summary
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    # Print comparison table
    print(f"\n{'Variation':<25} {'Objects':>10} {'Size (MB)':>12} {'View P95':>12}")
    print("-" * 60)

    for results in all_results:
        var_name = results["variation"].get("name", "Unknown")
        metrics = results["final_metrics"]
        view_stats = results.get("view_stats", {})

        print(f"{var_name:<25} {metrics['total_objects']:>10,} {metrics['total_size_mb']:>12.2f} "
              f"{view_stats.get('p95_time_ms', 0):>12.2f}")

    # Save comparison summary
    summary_file = output_path / "comparison_summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "comparison": config.name,
            "description": config.description,
            "results": all_results,
        }, f, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")

    # Generate charts
    try:
        print("\nGenerating comparison charts...")
        generate_comparison_charts(results_files, str(output_path / "charts"))
    except Exception as e:
        print(f"Chart generation failed: {e}")

    return all_results


def list_comparisons():
    """List available comparisons."""
    print("\nAvailable comparisons:")
    print("-" * 60)
    for name, config in COMPARISONS.items():
        print(f"\n{name}")
        print(f"  {config.description}")
        print(f"  Base: {config.base_scenario.value}")
        print(f"  Variations: {len(config.variations)}")


def main():
    parser = argparse.ArgumentParser(description="HOLON Protocol Simulator - Comparison Mode")
    parser.add_argument(
        "comparison",
        nargs="?",
        help="Comparison to run"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="results/comparisons",
        help="Output directory"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available comparisons"
    )

    args = parser.parse_args()

    if args.list or not args.comparison:
        list_comparisons()
        return

    run_comparison(args.comparison, seed=args.seed, output_dir=args.output)


if __name__ == "__main__":
    main()
