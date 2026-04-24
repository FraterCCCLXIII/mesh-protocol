#!/usr/bin/env python3
"""
HOLON Protocol v4.0 Simulator - Main Runner

Tests the two-layer architecture:
- Data Layer: Entity, Content, Link
- Algorithm Layer: Views, Discovery, Reputation, Moderation
"""

import argparse
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from core import (
    Storage, View, ViewEngine, ReputationEngine, DiscoveryEngine, ModerationEngine,
    Content, ContentKind, Link, LinkKind, AccessType,
    generate_content_id, generate_link_id, generate_view_id
)
from agents import AgentManager, AgentType
from scenarios import ScenarioType, get_scenario, list_scenarios


class Simulator:
    """Main v4.0 simulation runner."""

    def __init__(self, scenario_type: ScenarioType, seed: int | None = None):
        self.scenario = get_scenario(scenario_type)
        self.storage = Storage()
        self.agent_manager = AgentManager(self.storage)

        # Algorithm layer engines
        self.view_engine = ViewEngine(self.storage)
        self.reputation_engine = ReputationEngine(self.storage)
        self.discovery_engine = DiscoveryEngine(self.storage, self.reputation_engine)
        self.moderation_engine = ModerationEngine(self.storage)

        # Metrics
        self.metrics_history: list[dict] = []
        self.view_executions: list[dict] = []
        self.discovery_metrics: list[dict] = []
        self.economics_metrics: list[dict] = []

        # Random seed
        if seed is not None:
            random.seed(seed)

        # Time
        self.current_time = datetime.now()
        self.start_time = self.current_time

        # Views
        self.views: list[View] = []

    def setup(self):
        """Set up the simulation."""
        print(f"Setting up scenario: {self.scenario.name}")
        print(f"  Duration: {self.scenario.duration}")
        print(f"  Tick interval: {self.scenario.tick_interval}")

        # Create groups
        print("\nCreating groups...")
        group_ids = {}
        for group_config in self.scenario.groups:
            parent_id = group_ids.get(group_config.parent) if group_config.parent else None
            entity = self.agent_manager.create_group(
                group_config.name,
                parent=parent_id,
                moderators=group_config.moderators,
            )
            group_ids[group_config.name] = entity.id
        print(f"  Created {len(group_ids)} groups")

        # Create agents
        print("\nCreating agents...")
        agent_count = 0
        for agent_type, count in self.scenario.users.items():
            for i in range(count):
                name = f"{agent_type.value}_{i+1}"
                self.agent_manager.create_agent(name, agent_type)
                agent_count += 1
                if agent_count % 1000 == 0:
                    print(f"  Created {agent_count} agents...")
        print(f"  Created {agent_count} total agents")

        # Create initial views
        print("\nCreating initial views...")
        self._create_initial_views()
        print(f"  Created {len(self.views)} views")

    def _create_initial_views(self):
        """Create initial views for testing."""
        groups = [
            e for e in self.agent_manager.all_entity_ids
            if self.storage.get_entity(e) and
            self.storage.get_entity(e).kind.value == "group"
        ]

        view_templates = [
            {
                "name": "Trending",
                "source": {"type": "all"},
                "filter": [
                    {"field": "kind", "op": "eq", "value": "post"},
                    {"field": "created", "op": "gt", "value": "-24h"},
                ],
                "rank": {"formula": "reactions * 2 + replies"},
            },
            {
                "name": "Latest",
                "source": {"type": "all"},
                "filter": [{"field": "kind", "op": "eq", "value": "post"}],
                "rank": None,  # Chronological
            },
            {
                "name": "Best Articles",
                "source": {"type": "all"},
                "filter": [{"field": "kind", "op": "eq", "value": "article"}],
                "rank": {"formula": "reactions + replies * 2"},
            },
            {
                "name": "Hot (HN-style)",
                "source": {"type": "all"},
                "filter": [{"field": "created", "op": "gt", "value": "-48h"}],
                "rank": {"formula": "(reactions - 1) / decay(age_hours, 2.5)"},
            },
        ]

        for i, template in enumerate(view_templates[:self.scenario.initial_views]):
            view = View(
                id=generate_view_id(f"system-{template['name'].lower().replace(' ', '-')}"),
                author="ent:system",
                name=template["name"],
                source=template["source"],
                filter=template["filter"],
                rank=template["rank"],
                limit=50,
            )
            self.storage.create_view(view)
            self.views.append(view)
            self.agent_manager.all_view_ids.append(view.id)

        # Add group-specific views
        for group_id in groups[:3]:
            group = self.storage.get_entity(group_id)
            view = View(
                id=generate_view_id(f"hot-{group.handle}"),
                author="ent:system",
                name=f"Hot in {group.profile.get('name', 'Group')}",
                source={"context": group_id, "include_children": True},
                filter=[{"field": "created", "op": "gt", "value": "-24h"}],
                rank={"formula": "reactions + replies"},
                limit=50,
            )
            self.storage.create_view(view)
            self.views.append(view)
            self.agent_manager.all_view_ids.append(view.id)

    def run(self, progress_interval: int = 10):
        """Run the simulation."""
        print(f"\nRunning simulation...")

        end_time = self.start_time + self.scenario.duration
        tick_count = 0
        last_progress = 0

        while self.current_time < end_time:
            # Agent activity
            self.agent_manager.simulate_tick(self.current_time, self.scenario.tick_interval)

            elapsed = self.current_time - self.start_time

            # Special events
            if self.scenario.viral_content_at and elapsed >= self.scenario.viral_content_at:
                if not hasattr(self, '_viral_injected'):
                    self._inject_viral_content()
                    self._viral_injected = True

            if self.scenario.spam_wave_at and elapsed >= self.scenario.spam_wave_at:
                if not hasattr(self, '_spam_injected'):
                    self._inject_spam_wave()
                    self._spam_injected = True

            # Collect metrics
            if tick_count % 10 == 0:
                self._collect_metrics()

            # Execute views
            if tick_count % 20 == 0 and self.views:
                self._execute_views()

            # Test discovery
            if tick_count % 30 == 0:
                self._test_discovery()

            # Advance time
            self.current_time += self.scenario.tick_interval
            tick_count += 1

            # Progress
            progress = int((elapsed.total_seconds() / self.scenario.duration.total_seconds()) * 100)
            if progress >= last_progress + progress_interval:
                metrics = self.storage.get_metrics()
                agent_stats = self.agent_manager.get_agent_stats()
                print(f"  {progress}% | Objects: {metrics['total_objects']:,} | "
                      f"Views: {agent_stats['total_views_created']} | "
                      f"Verifications: {agent_stats['total_verifications']}")
                last_progress = progress

        print(f"\nSimulation complete!")

    def _inject_viral_content(self):
        """Inject viral content."""
        print("  [EVENT] Injecting viral content...")
        author = random.choice(list(self.agent_manager.agents.keys()))

        content = Content(
            id=generate_content_id(),
            kind=ContentKind.POST,
            author=author,
            created=self.current_time,
            body={"text": "🚀 This is going viral! Everyone is talking about this! 🔥"},
        )
        self.storage.create_content(content)
        self.agent_manager.all_content_ids.append(content.id)

        # Many reactions
        for agent_id in list(self.agent_manager.agents.keys())[:500]:
            link = Link(
                id=generate_link_id(),
                kind=LinkKind.REACT,
                source=agent_id,
                target=content.id,
                created=self.current_time,
                data={"emoji": random.choice(["🔥", "🚀", "💯", "❤️"])},
            )
            self.storage.create_link(link)

    def _inject_spam_wave(self):
        """Inject spam wave."""
        print("  [EVENT] Injecting spam wave...")
        spammers = [
            a for a in self.agent_manager.agents.values()
            if a.agent_type == AgentType.SPAMMER
        ]

        for spammer in spammers:
            for _ in range(10):
                content = Content(
                    id=generate_content_id(),
                    kind=ContentKind.POST,
                    author=spammer.entity_id,
                    created=self.current_time,
                    body={"text": "🚨 SPAM! BUY NOW! http://spam.example.com 🚨"},
                )
                self.storage.create_content(content)
                self.agent_manager.all_content_ids.append(content.id)

    def _collect_metrics(self):
        """Collect current metrics."""
        metrics = self.storage.get_metrics()
        metrics["timestamp"] = self.current_time.isoformat()
        metrics["elapsed_seconds"] = (self.current_time - self.start_time).total_seconds()
        metrics.update(self.agent_manager.get_agent_stats())
        self.metrics_history.append(metrics)

    def _execute_views(self):
        """Execute views and collect timing."""
        for view in self.views[:5]:
            try:
                boundary = self.view_engine.execute(view, self.current_time)
                self.view_executions.append({
                    "view_id": view.id,
                    "view_name": view.name,
                    "timestamp": self.current_time.isoformat(),
                    "result_count": len(boundary.result_ids),
                    "computation_time_ms": boundary.computation_time_ms,
                    "input_hash": boundary.input_hash[:16],
                    "result_hash": boundary.result_hash[:16],
                })
            except Exception as e:
                print(f"    View execution failed: {e}")

    def _test_discovery(self):
        """Test discovery mechanisms."""
        if not self.agent_manager.agents:
            return

        agent = random.choice(list(self.agent_manager.agents.values()))

        start = time.time()

        # Test follows_of_follows
        fof = self.discovery_engine.follows_of_follows(agent.entity_id, limit=10)

        # Test search
        results = self.discovery_engine.search("rust", limit=10)

        # Test rising stars
        rising = self.discovery_engine.rising_stars(limit=10)

        elapsed_ms = (time.time() - start) * 1000

        self.discovery_metrics.append({
            "timestamp": self.current_time.isoformat(),
            "follows_of_follows_count": len(fof),
            "search_results": len(results),
            "rising_stars": len(rising),
            "total_time_ms": elapsed_ms,
        })

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
            }
        else:
            view_stats = {}

        # Discovery stats
        if self.discovery_metrics:
            discovery_times = [d["total_time_ms"] for d in self.discovery_metrics]
            discovery_stats = {
                "total_queries": len(self.discovery_metrics),
                "avg_time_ms": sum(discovery_times) / len(discovery_times),
            }
        else:
            discovery_stats = {}

        # Economics stats
        tips = [l for l in self.storage.links.values() if l.kind == LinkKind.TIP]
        subscriptions = [l for l in self.storage.links.values()
                        if l.kind == LinkKind.SUBSCRIBE and "tier" in l.data]
        view_subs = [l for l in self.storage.links.values()
                    if l.kind == LinkKind.SUBSCRIBE and l.target.startswith("view:")]

        economics_stats = {
            "total_tips": len(tips),
            "total_tip_amount": sum(l.data.get("amount_sats", 0) for l in tips),
            "creator_subscriptions": len(subscriptions),
            "view_subscriptions": len(view_subs),
        }

        return {
            "scenario": self.scenario.name,
            "duration": str(self.scenario.duration),
            "final_metrics": final_metrics,
            "view_stats": view_stats,
            "discovery_stats": discovery_stats,
            "economics_stats": economics_stats,
            "metrics_history": self.metrics_history,
            "view_executions": self.view_executions[-50:],
            "discovery_metrics": self.discovery_metrics[-50:],
        }

    def print_summary(self):
        """Print summary."""
        results = self.get_results()

        print("\n" + "=" * 70)
        print(f"HOLON v4.0 SIMULATION RESULTS: {results['scenario']}")
        print("=" * 70)

        # Data Layer
        m = results["final_metrics"]
        print(f"\n📦 DATA LAYER")
        print(f"  Entities:     {m['entity_count']:,}")
        print(f"  Content:      {m['content_count']:,}")
        print(f"  Links:        {m['link_count']:,}")
        print(f"  Total:        {m['total_objects']:,}")
        print(f"  Size:         {m['total_size_mb']:.2f} MB")
        print(f"  Handles:      {m['handle_count']:,}")

        print(f"\n  Link breakdown:")
        for kind, count in sorted(m.get("link_breakdown", {}).items(), key=lambda x: -x[1]):
            print(f"    {kind}: {count:,}")

        # Algorithm Layer - Views
        if results["view_stats"]:
            v = results["view_stats"]
            print(f"\n🔍 ALGORITHM LAYER - Views")
            print(f"  Executions:   {v['total_executions']:,}")
            print(f"  Avg time:     {v['avg_time_ms']:.2f} ms")
            print(f"  P50 time:     {v['p50_time_ms']:.2f} ms")
            print(f"  P95 time:     {v['p95_time_ms']:.2f} ms")

        # Algorithm Layer - Discovery
        if results["discovery_stats"]:
            d = results["discovery_stats"]
            print(f"\n🔎 ALGORITHM LAYER - Discovery")
            print(f"  Queries:      {d['total_queries']:,}")
            print(f"  Avg time:     {d['avg_time_ms']:.2f} ms")

        # Economics
        e = results["economics_stats"]
        print(f"\n💰 ECONOMICS")
        print(f"  Tips:              {e['total_tips']:,}")
        print(f"  Tip amount:        {e['total_tip_amount']:,} sats")
        print(f"  Creator subs:      {e['creator_subscriptions']:,}")
        print(f"  View subs:         {e['view_subscriptions']:,}")

        # Agent stats
        agent_stats = self.agent_manager.get_agent_stats()
        print(f"\n👥 AGENTS")
        print(f"  Total:             {agent_stats['total_agents']:,}")
        print(f"  Content created:   {agent_stats['total_content']:,}")
        print(f"  Follows:           {agent_stats['total_follows']:,}")
        print(f"  Group memberships: {agent_stats['total_group_memberships']:,}")
        print(f"  Views created:     {agent_stats['total_views_created']:,}")
        print(f"  Verifications:     {agent_stats['total_verifications']:,}")

        print("\n" + "=" * 70)

    def save_results(self, output_dir: str = "results"):
        """Save results to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scenario_name = self.scenario.name.lower().replace(" ", "_")

        results_file = output_path / f"{scenario_name}_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump(self.get_results(), f, indent=2, default=str)
        print(f"\nResults saved to: {results_file}")


def main():
    parser = argparse.ArgumentParser(description="HOLON v4.0 Protocol Simulator")
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default="small_network",
        choices=[s.value for s in ScenarioType],
        help="Scenario to run"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--output", "-o", type=str, default="results", help="Output directory")
    parser.add_argument("--list", action="store_true", help="List scenarios")

    args = parser.parse_args()

    if args.list:
        print("\nHOLON v4.0 Scenarios:")
        print("-" * 70)
        for scenario in list_scenarios():
            print(f"\n{scenario['type']}")
            print(f"  {scenario['description']}")
            print(f"  Users: {scenario['users']:,} | Duration: {scenario['duration']}")
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
