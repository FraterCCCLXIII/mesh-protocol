#!/usr/bin/env python3
"""
Relay 2.0 Simulator - Main Runner

Tests the two-layer architecture:
- Truth Layer: Identity, Event, State, Attestation
- View Layer: ViewDefinition, Boundary, Reducers
"""

import argparse
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from core import (
    RelayStorage, ViewDefinition, ReducerType, Boundary, EventRange,
    ReducerEngine, generate_view_id
)
from agents import ActorManager, ActorType


class ScenarioType(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    AGENT_HEAVY = "agent_heavy"
    CURATOR_HEAVY = "curator_heavy"
    FULL = "full"


@dataclass
class ScenarioConfig:
    name: str
    description: str
    duration: timedelta
    actors: dict[ActorType, int]
    tick_interval: timedelta = timedelta(minutes=1)


SCENARIOS = {
    ScenarioType.SMALL: ScenarioConfig(
        name="Small Relay",
        description="100 actors testing basic functionality",
        duration=timedelta(hours=1),
        actors={
            ActorType.USER: 80,
            ActorType.AGENT: 5,
            ActorType.CURATOR: 10,
            ActorType.INDEXER: 3,
            ActorType.MODERATOR: 2,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.MEDIUM: ScenarioConfig(
        name="Medium Relay",
        description="1,000 actors testing scale",
        duration=timedelta(hours=4),
        actors={
            ActorType.USER: 800,
            ActorType.AGENT: 50,
            ActorType.CURATOR: 100,
            ActorType.INDEXER: 30,
            ActorType.MODERATOR: 20,
        },
        tick_interval=timedelta(minutes=1),
    ),
    ScenarioType.LARGE: ScenarioConfig(
        name="Large Relay",
        description="10,000 actors stress test",
        duration=timedelta(hours=12),
        actors={
            ActorType.USER: 8000,
            ActorType.AGENT: 500,
            ActorType.CURATOR: 1000,
            ActorType.INDEXER: 300,
            ActorType.MODERATOR: 200,
        },
        tick_interval=timedelta(minutes=2),
    ),
    ScenarioType.AGENT_HEAVY: ScenarioConfig(
        name="Agent-Heavy Relay",
        description="Many AI agents doing action.* flows",
        duration=timedelta(hours=2),
        actors={
            ActorType.USER: 100,
            ActorType.AGENT: 200,
            ActorType.CURATOR: 20,
            ActorType.INDEXER: 10,
            ActorType.MODERATOR: 10,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.CURATOR_HEAVY: ScenarioConfig(
        name="Curator-Heavy Relay",
        description="Many curators creating views",
        duration=timedelta(hours=2),
        actors={
            ActorType.USER: 200,
            ActorType.AGENT: 20,
            ActorType.CURATOR: 150,
            ActorType.INDEXER: 20,
            ActorType.MODERATOR: 10,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.FULL: ScenarioConfig(
        name="Full Ecosystem",
        description="All actor types, all features",
        duration=timedelta(hours=6),
        actors={
            ActorType.USER: 500,
            ActorType.AGENT: 100,
            ActorType.CURATOR: 100,
            ActorType.INDEXER: 50,
            ActorType.MODERATOR: 50,
        },
        tick_interval=timedelta(minutes=1),
    ),
}


class Simulator:
    """Relay 2.0 simulation runner."""

    def __init__(self, scenario_type: ScenarioType, seed: int | None = None):
        self.scenario = SCENARIOS[scenario_type]
        self.storage = RelayStorage()
        self.actor_manager = ActorManager(self.storage)
        self.reducer_engine = ReducerEngine(self.storage)
        
        # Metrics
        self.metrics_history: list[dict] = []
        self.view_executions: list[dict] = []
        
        if seed is not None:
            random.seed(seed)
        
        self.current_time = datetime.now()
        self.start_time = self.current_time
        
        # System views
        self.system_views: list[ViewDefinition] = []

    def setup(self):
        """Set up the simulation."""
        print(f"Setting up scenario: {self.scenario.name}")
        print(f"  Duration: {self.scenario.duration}")
        print(f"  Tick interval: {self.scenario.tick_interval}")
        
        # Create actors
        print("\nCreating actors...")
        actor_count = 0
        for actor_type, count in self.scenario.actors.items():
            for i in range(count):
                name = f"{actor_type.value}_{i+1}"
                self.actor_manager.create_actor(name, actor_type)
                actor_count += 1
                if actor_count % 500 == 0:
                    print(f"  Created {actor_count} actors...")
        print(f"  Created {actor_count} total actors")
        
        # Create system views
        print("\nCreating system views...")
        self._create_system_views()
        print(f"  Created {len(self.system_views)} views")

    def _create_system_views(self):
        """Create default system views."""
        # Global timeline
        all_actors = list(self.actor_manager.actors.keys())[:50]  # Limit for perf
        
        view = ViewDefinition(
            id=generate_view_id("global-timeline"),
            actor="relay:system",
            version=1,
            sources=[{"kind": "actor_log", "actor_id": aid} for aid in all_actors],
            reduce=ReducerType.REVERSE_CHRONOLOGICAL,
            params={"limit": 100},
            created_at=self.current_time,
            updated_at=self.current_time,
        )
        self.storage.put_view_definition(view)
        self.system_views.append(view)
        self.actor_manager.all_view_ids.append(view.id)
        
        # Engagement-sorted view
        view2 = ViewDefinition(
            id=generate_view_id("top-posts"),
            actor="relay:system",
            version=1,
            sources=[{"kind": "actor_log", "actor_id": aid} for aid in all_actors[:20]],
            reduce=ReducerType.ENGAGEMENT,
            params={"limit": 50},
            created_at=self.current_time,
            updated_at=self.current_time,
        )
        self.storage.put_view_definition(view2)
        self.system_views.append(view2)
        self.actor_manager.all_view_ids.append(view2.id)

    def run(self, progress_interval: int = 10):
        """Run the simulation."""
        print(f"\nRunning simulation...")
        
        end_time = self.start_time + self.scenario.duration
        tick_count = 0
        last_progress = 0
        
        while self.current_time < end_time:
            # Actor activity
            self.actor_manager.simulate_tick(self.current_time, self.scenario.tick_interval)
            
            # Collect metrics
            if tick_count % 10 == 0:
                self._collect_metrics()
            
            # Execute views
            if tick_count % 20 == 0 and self.system_views:
                self._execute_views()
            
            # Advance time
            self.current_time += self.scenario.tick_interval
            tick_count += 1
            
            # Progress
            elapsed = self.current_time - self.start_time
            progress = int((elapsed.total_seconds() / self.scenario.duration.total_seconds()) * 100)
            if progress >= last_progress + progress_interval:
                metrics = self.storage.get_metrics()
                print(f"  {progress}% | Events: {metrics['event_count']:,} | "
                      f"States: {metrics['state_count']:,} | "
                      f"Attestations: {metrics['attestation_count']:,}")
                last_progress = progress
        
        print(f"\nSimulation complete!")

    def _collect_metrics(self):
        """Collect current metrics."""
        metrics = self.storage.get_metrics()
        metrics["timestamp"] = self.current_time.isoformat()
        metrics["elapsed_seconds"] = (self.current_time - self.start_time).total_seconds()
        metrics.update(self.actor_manager.get_stats())
        self.metrics_history.append(metrics)

    def _execute_views(self):
        """Execute views and measure performance."""
        for view in self.system_views[:3]:
            # Create a boundary for deterministic execution
            event_ranges = []
            for source in view.sources:
                if source.get("kind") == "actor_log":
                    actor_id = source.get("actor_id")
                    event_ranges.append(EventRange(
                        actor=actor_id,
                        to_ts=self.current_time,
                    ))
            
            boundary = Boundary(
                view_definition_version=view.version,
                event_ranges=event_ranges,
                as_of=self.current_time,
            )
            
            try:
                result = self.reducer_engine.execute(view, boundary)
                self.view_executions.append({
                    "view_id": view.id,
                    "timestamp": self.current_time.isoformat(),
                    "result_count": len(result.items),
                    "computation_time_ms": result.computation_time_ms,
                    "deterministic": result.deterministic,
                    "result_hash": result.result_hash[:16],
                })
            except Exception as e:
                print(f"    View execution failed: {e}")

    def get_results(self) -> dict:
        """Get simulation results."""
        final_metrics = self.storage.get_metrics()
        
        # View stats
        if self.view_executions:
            exec_times = [e["computation_time_ms"] for e in self.view_executions]
            exec_times.sort()
            view_stats = {
                "total_executions": len(self.view_executions),
                "avg_time_ms": sum(exec_times) / len(exec_times),
                "p50_time_ms": exec_times[len(exec_times) // 2],
                "p95_time_ms": exec_times[int(len(exec_times) * 0.95)],
                "deterministic_rate": sum(1 for e in self.view_executions if e["deterministic"]) / len(self.view_executions),
            }
        else:
            view_stats = {}
        
        return {
            "scenario": self.scenario.name,
            "duration": str(self.scenario.duration),
            "final_metrics": final_metrics,
            "view_stats": view_stats,
            "metrics_history": self.metrics_history,
            "view_executions": self.view_executions[-50:],
        }

    def print_summary(self):
        """Print summary."""
        results = self.get_results()
        
        print("\n" + "=" * 70)
        print(f"RELAY 2.0 SIMULATION RESULTS: {results['scenario']}")
        print("=" * 70)
        
        m = results["final_metrics"]
        
        print(f"\n📜 TRUTH LAYER")
        print(f"  Identities:    {m['identity_count']:,}")
        print(f"  Events:        {m['event_count']:,}")
        print(f"  States:        {m['state_count']:,}")
        print(f"  Attestations:  {m['attestation_count']:,}")
        print(f"  Total:         {m['total_objects']:,}")
        print(f"  Size:          {m['total_size_mb']:.2f} MB")
        
        print(f"\n  Event breakdown:")
        for etype, count in sorted(m.get("event_type_counts", {}).items(), key=lambda x: -x[1]):
            print(f"    {etype}: {count:,}")
        
        if results["view_stats"]:
            v = results["view_stats"]
            print(f"\n👁️ VIEW LAYER")
            print(f"  View definitions: {m['view_definition_count']:,}")
            print(f"  Executions:       {v['total_executions']:,}")
            print(f"  Avg time:         {v['avg_time_ms']:.2f} ms")
            print(f"  P50 time:         {v['p50_time_ms']:.2f} ms")
            print(f"  P95 time:         {v['p95_time_ms']:.2f} ms")
            print(f"  Deterministic:    {v['deterministic_rate']*100:.1f}%")
        
        actor_stats = self.actor_manager.get_stats()
        print(f"\n👥 ACTORS")
        print(f"  Total:             {actor_stats['total_actors']:,}")
        for atype, count in actor_stats.get("by_type", {}).items():
            print(f"    {atype}: {count:,}")
        print(f"  Follows:           {actor_stats['total_follows']:,}")
        print(f"  View subs:         {actor_stats['total_view_subscriptions']:,}")
        
        print("\n" + "=" * 70)

    def save_results(self, output_dir: str = "results"):
        """Save results."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scenario_name = self.scenario.name.lower().replace(" ", "_")
        
        results_file = output_path / f"relay2_{scenario_name}_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump(self.get_results(), f, indent=2, default=str)
        print(f"\nResults saved to: {results_file}")


def list_scenarios():
    print("\nRelay 2.0 Scenarios:")
    print("-" * 70)
    for s in ScenarioType:
        cfg = SCENARIOS[s]
        total = sum(cfg.actors.values())
        print(f"\n{s.value}")
        print(f"  {cfg.description}")
        print(f"  Actors: {total:,} | Duration: {cfg.duration}")


def main():
    parser = argparse.ArgumentParser(description="Relay 2.0 Simulator")
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default="small",
        choices=[s.value for s in ScenarioType],
        help="Scenario to run"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--output", "-o", type=str, default="results", help="Output directory")
    parser.add_argument("--list", action="store_true", help="List scenarios")
    
    args = parser.parse_args()
    
    if args.list:
        list_scenarios()
        return
    
    scenario_type = ScenarioType(args.scenario)
    simulator = Simulator(scenario_type, seed=args.seed)
    
    start = time.time()
    simulator.setup()
    simulator.run()
    elapsed = time.time() - start
    
    print(f"\nReal time: {elapsed:.1f}s")
    
    simulator.print_summary()
    simulator.save_results(args.output)


if __name__ == "__main__":
    main()
