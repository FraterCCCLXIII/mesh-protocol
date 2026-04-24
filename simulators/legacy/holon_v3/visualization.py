"""
HOLON Protocol Simulator - Visualization

Generate charts and graphs from simulation results.
"""

import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


def load_results(results_file: str) -> dict:
    """Load simulation results from JSON file."""
    with open(results_file) as f:
        return json.load(f)


def plot_storage_growth(results: dict, output_dir: Path):
    """Plot storage growth over time."""
    history = results.get("metrics_history", [])
    if not history:
        return

    df = pd.DataFrame(history)
    df["elapsed_minutes"] = df["elapsed_seconds"] / 60

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Storage Growth: {results['scenario']}", fontsize=14)

    # Total objects over time
    ax1 = axes[0, 0]
    ax1.plot(df["elapsed_minutes"], df["total_objects"], "b-", linewidth=2)
    ax1.set_xlabel("Time (minutes)")
    ax1.set_ylabel("Total Objects")
    ax1.set_title("Total Objects Over Time")
    ax1.grid(True, alpha=0.3)

    # Storage size over time
    ax2 = axes[0, 1]
    ax2.plot(df["elapsed_minutes"], df["total_size_mb"], "g-", linewidth=2)
    ax2.set_xlabel("Time (minutes)")
    ax2.set_ylabel("Size (MB)")
    ax2.set_title("Storage Size Over Time")
    ax2.grid(True, alpha=0.3)

    # Object breakdown over time
    ax3 = axes[1, 0]
    ax3.stackplot(
        df["elapsed_minutes"],
        df["entity_count"],
        df["content_count"],
        df["link_count"],
        labels=["Entities", "Content", "Links"],
        alpha=0.7
    )
    ax3.set_xlabel("Time (minutes)")
    ax3.set_ylabel("Count")
    ax3.set_title("Object Breakdown Over Time")
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3)

    # Link breakdown (final state)
    ax4 = axes[1, 1]
    final_metrics = results.get("final_metrics", {})
    link_breakdown = final_metrics.get("link_breakdown", {})
    if link_breakdown:
        labels = list(link_breakdown.keys())
        values = list(link_breakdown.values())
        colors = plt.cm.Set3(range(len(labels)))
        ax4.pie(values, labels=labels, autopct="%1.1f%%", colors=colors)
        ax4.set_title("Link Breakdown (Final)")
    else:
        ax4.text(0.5, 0.5, "No link data", ha="center", va="center")
        ax4.set_title("Link Breakdown")

    plt.tight_layout()
    output_file = output_dir / "storage_growth.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"  Saved: {output_file}")


def plot_view_performance(results: dict, output_dir: Path):
    """Plot view execution performance."""
    executions = results.get("view_executions", [])
    if not executions:
        return

    df = pd.DataFrame(executions)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f"View Performance: {results['scenario']}", fontsize=14)

    # Execution time distribution
    ax1 = axes[0]
    ax1.hist(df["computation_time_ms"], bins=50, edgecolor="black", alpha=0.7)
    ax1.set_xlabel("Computation Time (ms)")
    ax1.set_ylabel("Frequency")
    ax1.set_title("Execution Time Distribution")
    ax1.axvline(df["computation_time_ms"].median(), color="r", linestyle="--", label=f"Median: {df['computation_time_ms'].median():.2f}ms")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Execution time over simulation
    ax2 = axes[1]
    ax2.scatter(range(len(df)), df["computation_time_ms"], alpha=0.5, s=10)
    ax2.set_xlabel("Execution Number")
    ax2.set_ylabel("Computation Time (ms)")
    ax2.set_title("Execution Time Over Simulation")
    ax2.grid(True, alpha=0.3)

    # Result count distribution
    ax3 = axes[2]
    ax3.hist(df["result_count"], bins=20, edgecolor="black", alpha=0.7, color="orange")
    ax3.set_xlabel("Result Count")
    ax3.set_ylabel("Frequency")
    ax3.set_title("Results Per View Execution")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = output_dir / "view_performance.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"  Saved: {output_file}")


def plot_agent_activity(results: dict, output_dir: Path):
    """Plot agent activity statistics."""
    history = results.get("metrics_history", [])
    if not history:
        return

    df = pd.DataFrame(history)
    df["elapsed_minutes"] = df["elapsed_seconds"] / 60

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Agent Activity: {results['scenario']}", fontsize=14)

    # Content and follows over time
    ax1 = axes[0]
    ax1.plot(df["elapsed_minutes"], df["total_content"], "b-", label="Content", linewidth=2)
    ax1.plot(df["elapsed_minutes"], df["total_follows"], "g-", label="Follows", linewidth=2)
    if "total_group_memberships" in df.columns:
        ax1.plot(df["elapsed_minutes"], df["total_group_memberships"], "r-", label="Memberships", linewidth=2)
    ax1.set_xlabel("Time (minutes)")
    ax1.set_ylabel("Count")
    ax1.set_title("Activity Over Time")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Agent type distribution (if available)
    ax2 = axes[1]
    if history and "by_type" in history[-1]:
        by_type = history[-1]["by_type"]
        labels = list(by_type.keys())
        values = list(by_type.values())
        colors = plt.cm.Paired(range(len(labels)))
        bars = ax2.bar(labels, values, color=colors, edgecolor="black")
        ax2.set_xlabel("Agent Type")
        ax2.set_ylabel("Count")
        ax2.set_title("Agent Distribution")
        ax2.tick_params(axis="x", rotation=45)
        for bar, val in zip(bars, values):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    str(val), ha="center", va="bottom", fontsize=9)
    else:
        ax2.text(0.5, 0.5, "No agent data", ha="center", va="center")

    plt.tight_layout()
    output_file = output_dir / "agent_activity.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"  Saved: {output_file}")


def plot_network_simulation(results: dict, output_dir: Path):
    """Plot network simulation metrics (relay sync, etc.)."""
    network_metrics = results.get("network_metrics", [])
    if not network_metrics:
        return

    df = pd.DataFrame(network_metrics)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Network Simulation: {results['scenario']}", fontsize=14)

    # Sync latency over time
    ax1 = axes[0, 0]
    if "sync_latency_ms" in df.columns:
        ax1.plot(df["elapsed_seconds"] / 60, df["sync_latency_ms"], "b-", alpha=0.7)
        ax1.set_xlabel("Time (minutes)")
        ax1.set_ylabel("Sync Latency (ms)")
        ax1.set_title("Sync Latency Over Time")
        ax1.grid(True, alpha=0.3)

    # Messages per relay
    ax2 = axes[0, 1]
    if "relay_message_counts" in results:
        relay_counts = results["relay_message_counts"]
        ax2.bar(relay_counts.keys(), relay_counts.values(), edgecolor="black")
        ax2.set_xlabel("Relay")
        ax2.set_ylabel("Messages")
        ax2.set_title("Messages Per Relay")
        ax2.tick_params(axis="x", rotation=45)

    # Sync success rate
    ax3 = axes[1, 0]
    if "sync_success_rate" in df.columns:
        ax3.plot(df["elapsed_seconds"] / 60, df["sync_success_rate"] * 100, "g-", linewidth=2)
        ax3.set_xlabel("Time (minutes)")
        ax3.set_ylabel("Success Rate (%)")
        ax3.set_title("Sync Success Rate")
        ax3.set_ylim(0, 105)
        ax3.grid(True, alpha=0.3)

    # Bandwidth usage
    ax4 = axes[1, 1]
    if "bandwidth_mbps" in df.columns:
        ax4.fill_between(df["elapsed_seconds"] / 60, df["bandwidth_mbps"], alpha=0.5)
        ax4.plot(df["elapsed_seconds"] / 60, df["bandwidth_mbps"], "r-", linewidth=1)
        ax4.set_xlabel("Time (minutes)")
        ax4.set_ylabel("Bandwidth (Mbps)")
        ax4.set_title("Network Bandwidth")
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = output_dir / "network_simulation.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"  Saved: {output_file}")


def plot_comparison(results_list: list[dict], output_dir: Path):
    """Plot comparison of multiple simulation runs."""
    if len(results_list) < 2:
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Simulation Comparison", fontsize=14)

    labels = [r.get("scenario", f"Run {i}") for i, r in enumerate(results_list)]
    colors = plt.cm.Set2(range(len(results_list)))

    # Final object counts
    ax1 = axes[0, 0]
    x = range(len(results_list))
    entity_counts = [r["final_metrics"]["entity_count"] for r in results_list]
    content_counts = [r["final_metrics"]["content_count"] for r in results_list]
    link_counts = [r["final_metrics"]["link_count"] for r in results_list]

    width = 0.25
    ax1.bar([i - width for i in x], entity_counts, width, label="Entities", color="blue", alpha=0.7)
    ax1.bar(x, content_counts, width, label="Content", color="green", alpha=0.7)
    ax1.bar([i + width for i in x], link_counts, width, label="Links", color="red", alpha=0.7)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.set_ylabel("Count")
    ax1.set_title("Final Object Counts")
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis="y")

    # Storage size comparison
    ax2 = axes[0, 1]
    sizes = [r["final_metrics"]["total_size_mb"] for r in results_list]
    bars = ax2.bar(labels, sizes, color=colors, edgecolor="black")
    ax2.set_ylabel("Size (MB)")
    ax2.set_title("Final Storage Size")
    ax2.tick_params(axis="x", rotation=45)
    for bar, size in zip(bars, sizes):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f"{size:.2f}", ha="center", va="bottom", fontsize=9)

    # View performance comparison
    ax3 = axes[1, 0]
    view_stats = [r.get("view_stats", {}) for r in results_list]
    if all("avg_time_ms" in v for v in view_stats):
        avg_times = [v["avg_time_ms"] for v in view_stats]
        p95_times = [v.get("p95_time_ms", 0) for v in view_stats]

        x = range(len(results_list))
        ax3.bar([i - 0.2 for i in x], avg_times, 0.4, label="Avg", color="blue", alpha=0.7)
        ax3.bar([i + 0.2 for i in x], p95_times, 0.4, label="P95", color="orange", alpha=0.7)
        ax3.set_xticks(x)
        ax3.set_xticklabels(labels, rotation=45, ha="right")
        ax3.set_ylabel("Time (ms)")
        ax3.set_title("View Execution Time")
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis="y")

    # Growth rate comparison (storage over time)
    ax4 = axes[1, 1]
    for i, r in enumerate(results_list):
        history = r.get("metrics_history", [])
        if history:
            df = pd.DataFrame(history)
            df["elapsed_minutes"] = df["elapsed_seconds"] / 60
            ax4.plot(df["elapsed_minutes"], df["total_objects"],
                    label=labels[i], color=colors[i], linewidth=2)
    ax4.set_xlabel("Time (minutes)")
    ax4.set_ylabel("Total Objects")
    ax4.set_title("Storage Growth Comparison")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = output_dir / "comparison.png"
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"  Saved: {output_file}")


def generate_all_charts(results_file: str, output_dir: str = None):
    """Generate all charts for a simulation result."""
    results = load_results(results_file)

    if output_dir is None:
        output_dir = Path(results_file).parent / "charts"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating charts for: {results['scenario']}")
    plot_storage_growth(results, output_dir)
    plot_view_performance(results, output_dir)
    plot_agent_activity(results, output_dir)
    plot_network_simulation(results, output_dir)

    print(f"\nAll charts saved to: {output_dir}")


def generate_comparison_charts(results_files: list[str], output_dir: str):
    """Generate comparison charts for multiple simulation results."""
    results_list = [load_results(f) for f in results_files]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating comparison charts...")
    plot_comparison(results_list, output_path)

    # Also generate individual charts
    for results_file in results_files:
        generate_all_charts(results_file, output_path / Path(results_file).stem)

    print(f"\nAll charts saved to: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate visualization charts")
    parser.add_argument("results_files", nargs="+", help="Results JSON files")
    parser.add_argument("--output", "-o", default="charts", help="Output directory")
    parser.add_argument("--compare", "-c", action="store_true", help="Generate comparison charts")

    args = parser.parse_args()

    if args.compare and len(args.results_files) > 1:
        generate_comparison_charts(args.results_files, args.output)
    else:
        for f in args.results_files:
            generate_all_charts(f, args.output)
