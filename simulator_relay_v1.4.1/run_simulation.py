#!/usr/bin/env python3
"""
Relay v1.4-1 / v1.5 Simulator - Main Runner

Tests the wire protocol:
- Identity (§8) with actor_id
- Log events (§10) with prev chain
- State objects (§11) with versioning
- Channels (§13) with genesis
- Feed definitions (§11.1, v1.4)
- Action events (§13.4, v1.4)
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
    RelayStorage, FeedReducer, ActionVerifier,
    generate_object_id
)
from agents import ActorManager, ActorType


class ScenarioType(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ACTION_HEAVY = "action_heavy"
    FEED_HEAVY = "feed_heavy"
    CHANNEL_HEAVY = "channel_heavy"
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
        description="100 actors testing basic v1.4-1 functionality",
        duration=timedelta(hours=1),
        actors={
            ActorType.USER: 80,
            ActorType.AGENT: 10,
            ActorType.CURATOR: 8,
            ActorType.CHANNEL_OWNER: 2,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.MEDIUM: ScenarioConfig(
        name="Medium Relay",
        description="500 actors testing scale",
        duration=timedelta(hours=4),
        actors={
            ActorType.USER: 400,
            ActorType.AGENT: 50,
            ActorType.CURATOR: 40,
            ActorType.CHANNEL_OWNER: 10,
        },
        tick_interval=timedelta(minutes=1),
    ),
    ScenarioType.LARGE: ScenarioConfig(
        name="Large Relay",
        description="2,000 actors stress test",
        duration=timedelta(hours=8),
        actors={
            ActorType.USER: 1600,
            ActorType.AGENT: 200,
            ActorType.CURATOR: 150,
            ActorType.CHANNEL_OWNER: 50,
        },
        tick_interval=timedelta(minutes=2),
    ),
    ScenarioType.ACTION_HEAVY: ScenarioConfig(
        name="Action-Heavy",
        description="Many action.* flows (§13.4)",
        duration=timedelta(hours=2),
        actors={
            ActorType.USER: 200,  # Request actions
            ActorType.AGENT: 100,  # Handle actions
            ActorType.CURATOR: 10,
            ActorType.CHANNEL_OWNER: 5,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.FEED_HEAVY: ScenarioConfig(
        name="Feed-Heavy",
        description="Many feed definitions (§11.1)",
        duration=timedelta(hours=2),
        actors={
            ActorType.USER: 150,
            ActorType.AGENT: 20,
            ActorType.CURATOR: 100,  # Create feeds
            ActorType.CHANNEL_OWNER: 10,
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.CHANNEL_HEAVY: ScenarioConfig(
        name="Channel-Heavy",
        description="Many channels and memberships (§13)",
        duration=timedelta(hours=2),
        actors={
            ActorType.USER: 200,
            ActorType.AGENT: 20,
            ActorType.CURATOR: 20,
            ActorType.CHANNEL_OWNER: 60,  # Create channels
        },
        tick_interval=timedelta(seconds=30),
    ),
    ScenarioType.FULL: ScenarioConfig(
        name="Full v1.4-1",
        description="All v1.4-1 features",
        duration=timedelta(hours=6),
        actors={
            ActorType.USER: 400,
            ActorType.AGENT: 80,
            ActorType.CURATOR: 60,
            ActorType.CHANNEL_OWNER: 60,
        },
        tick_interval=timedelta(minutes=1),
    ),
}


class Simulator:
    """Relay v1.4-1 simulation runner."""

    def __init__(self, scenario_type: ScenarioType, seed: int | None = None):
        self.scenario = SCENARIOS[scenario_type]
        self.storage = RelayStorage()
        self.actor_manager = ActorManager(self.storage)
        self.feed_reducer = FeedReducer(self.storage)
        self.action_verifier = ActionVerifier(self.storage)
        
        # Metrics
        self.metrics_history: list[dict] = []
        self.feed_reductions: list[dict] = []
        self.action_verifications: list[dict] = []
        
        if seed is not None:
            random.seed(seed)
        
        self.current_time = datetime.now()
        self.start_time = self.current_time

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
            
            # Test feed reduction
            if tick_count % 20 == 0:
                self._test_feed_reduction()
            
            # Verify actions
            if tick_count % 30 == 0:
                self._verify_actions()
            
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
                      f"Feeds: {metrics['feed_definition_count']:,}")
                last_progress = progress
        
        print(f"\nSimulation complete!")

    def _collect_metrics(self):
        """Collect current metrics."""
        metrics = self.storage.get_metrics()
        metrics["timestamp"] = self.current_time.isoformat()
        metrics["elapsed_seconds"] = (self.current_time - self.start_time).total_seconds()
        metrics.update(self.actor_manager.get_stats())
        self.metrics_history.append(metrics)

    def _test_feed_reduction(self):
        """Test feed reduction (§17.10, §17.11)."""
        feed_defs = list(self.storage.feed_definitions.values())
        if not feed_defs:
            return
        
        feed_def = random.choice(feed_defs)
        
        try:
            result = self.feed_reducer.reduce(feed_def)
            
            # Test verification
            verified = self.feed_reducer.recompute_and_verify(feed_def, result)
            
            self.feed_reductions.append({
                "feed_id": feed_def.object_id,
                "timestamp": self.current_time.isoformat(),
                "event_count": len(result.event_ids),
                "computation_time_ms": result.computation_time_ms,
                "result_hash": result.result_hash[:16],
                "verified": verified,
            })
        except Exception as e:
            print(f"    Feed reduction failed: {e}")

    def _verify_actions(self):
        """Verify action chains (§13.4)."""
        # Find action.result events
        result_events = [
            eid for eid in self.actor_manager.all_event_ids
            if self.storage.get_event(eid) and 
            self.storage.get_event(eid).type.value == "action.result"
        ]
        
        if not result_events:
            return
        
        result_id = random.choice(result_events[-10:])  # Recent ones
        
        verification = self.action_verifier.verify_action_chain(result_id)
        
        self.action_verifications.append({
            "result_event_id": result_id,
            "timestamp": self.current_time.isoformat(),
            "valid": verification.get("valid", False),
            "action_id": verification.get("action_id"),
            "error": verification.get("error"),
        })

    def get_results(self) -> dict:
        """Get simulation results."""
        final_metrics = self.storage.get_metrics()
        
        # Feed stats
        if self.feed_reductions:
            times = [f["computation_time_ms"] for f in self.feed_reductions]
            times.sort()
            verified = sum(1 for f in self.feed_reductions if f["verified"])
            feed_stats = {
                "total_reductions": len(self.feed_reductions),
                "avg_time_ms": sum(times) / len(times),
                "p50_time_ms": times[len(times) // 2],
                "p95_time_ms": times[int(len(times) * 0.95)] if len(times) > 1 else times[0],
                "verification_rate": verified / len(self.feed_reductions),
            }
        else:
            feed_stats = {}
        
        # Action stats
        if self.action_verifications:
            valid = sum(1 for a in self.action_verifications if a["valid"])
            action_stats = {
                "total_verifications": len(self.action_verifications),
                "valid_rate": valid / len(self.action_verifications),
            }
        else:
            action_stats = {}
        
        return {
            "scenario": self.scenario.name,
            "duration": str(self.scenario.duration),
            "final_metrics": final_metrics,
            "feed_stats": feed_stats,
            "action_stats": action_stats,
            "metrics_history": self.metrics_history,
            "feed_reductions": self.feed_reductions[-50:],
            "action_verifications": self.action_verifications[-50:],
        }

    def print_summary(self):
        """Print summary."""
        results = self.get_results()
        
        print("\n" + "=" * 70)
        print(f"RELAY v1.4-1 SIMULATION RESULTS: {results['scenario']}")
        print("=" * 70)
        
        m = results["final_metrics"]
        
        print(f"\n📜 WIRE PROTOCOL")
        print(f"  Identities:        {m['identity_count']:,}")
        print(f"  Actors:            {m['actor_count']:,}")
        print(f"  Log events:        {m['event_count']:,}")
        print(f"  State objects:     {m['state_count']:,}")
        print(f"  Channels:          {m['channel_count']:,}")
        print(f"  Feed definitions:  {m['feed_definition_count']:,}")
        print(f"  Size:              {m['total_size_mb']:.2f} MB")
        
        print(f"\n  Event breakdown:")
        for etype, count in sorted(m.get("event_type_counts", {}).items(), key=lambda x: -x[1]):
            print(f"    {etype}: {count:,}")
        
        if results["feed_stats"]:
            f = results["feed_stats"]
            print(f"\n📊 FEED REDUCTION (§17.10-11)")
            print(f"  Reductions:        {f['total_reductions']:,}")
            print(f"  Avg time:          {f['avg_time_ms']:.2f} ms")
            print(f"  P50 time:          {f['p50_time_ms']:.2f} ms")
            print(f"  P95 time:          {f['p95_time_ms']:.2f} ms")
            print(f"  Verified:          {f['verification_rate']*100:.1f}%")
        
        if results["action_stats"]:
            a = results["action_stats"]
            print(f"\n🤖 ACTION FLOWS (§13.4)")
            print(f"  Verifications:     {a['total_verifications']:,}")
            print(f"  Valid:             {a['valid_rate']*100:.1f}%")
        
        actor_stats = self.actor_manager.get_stats()
        print(f"\n👥 ACTORS")
        print(f"  Total:             {actor_stats['total_actors']:,}")
        for atype, count in actor_stats.get("by_type", {}).items():
            print(f"    {atype}: {count:,}")
        print(f"  Follows:           {actor_stats['total_follows']:,}")
        print(f"  Channels:          {actor_stats['total_channels']:,}")
        print(f"  Memberships:       {actor_stats['total_memberships']:,}")
        print(f"  Feeds:             {actor_stats['total_feeds']:,}")
        
        print("\n" + "=" * 70)

    def save_results(self, output_dir: str = "results"):
        """Save results."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scenario_name = self.scenario.name.lower().replace(" ", "_").replace("-", "_")
        
        results_file = output_path / f"relay141_{scenario_name}_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump(self.get_results(), f, indent=2, default=str)
        print(f"\nResults saved to: {results_file}")


def list_scenarios():
    print("\nRelay v1.4-1 Scenarios:")
    print("-" * 70)
    for s in ScenarioType:
        cfg = SCENARIOS[s]
        total = sum(cfg.actors.values())
        print(f"\n{s.value}")
        print(f"  {cfg.description}")
        print(f"  Actors: {total:,} | Duration: {cfg.duration}")


def main():
    parser = argparse.ArgumentParser(description="Relay v1.4-1 Simulator")
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
