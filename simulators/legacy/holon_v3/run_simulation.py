#!/usr/bin/env python3
"""
HOLON Protocol Simulator - Main Runner

Run simulations and collect metrics.
"""

import argparse
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from core import (
    Storage, View, ViewEngine, Link, LinkKind,
    generate_entity_id, generate_view_id, generate_link_id
)
from agents import AgentManager, AgentType
from scenarios import ScenarioType, get_scenario, list_scenarios, HolonConfig

# Try to import network simulation (optional)
try:
    from network import NetworkSimulator, NetworkConfig, create_network_simulation
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False


class Simulator:
    """Main simulation runner."""

    def __init__(self, scenario_type: ScenarioType, seed: int | None = None):
        self.scenario = get_scenario(scenario_type)

        # Network simulation (if configured)
        self.network: NetworkSimulator | None = None
        if NETWORK_AVAILABLE and self.scenario.num_relays > 1:
            config = NetworkConfig(
                min_latency_ms=max(5, self.scenario.network_latency_ms * 0.5),
                max_latency_ms=max(20, self.scenario.network_latency_ms * 1.5),
                packet_loss_rate=self.scenario.packet_loss_rate,
                relay_failure_rate=self.scenario.relay_failure_rate,
            )
            self.network = NetworkSimulator(config)
            for i in range(self.scenario.num_relays):
                self.network.add_relay(f"relay-{i+1}", is_primary=(i == 0))
            self.storage = self.network.get_primary_storage()
        else:
            self.storage = Storage()

        self.agent_manager = AgentManager(self.storage)
        self.view_engine = ViewEngine(self.storage)

        # Metrics collection
        self.metrics_history: list[dict] = []
        self.view_executions: list[dict] = []
        self.network_metrics: list[dict] = []
        self.key_rotation_events: list[dict] = []
        self.group_key_events: list[dict] = []

        # Random seed for reproducibility
        if seed is not None:
            random.seed(seed)

        # Simulation time
        self.current_time = datetime.utcnow()
        self.start_time = self.current_time

        # Views created
        self.views: list[View] = []

        # Key rotation tracking
        self.last_key_rotation = self.current_time
        self.key_versions: dict[str, int] = {}  # entity_id -> version

    def setup(self):
        """Set up the simulation environment."""
        print(f"Setting up scenario: {self.scenario.name}")
        print(f"  Duration: {self.scenario.duration}")
        print(f"  Tick interval: {self.scenario.tick_interval}")

        # Create holons
        print("\nCreating holons...")
        holon_ids = {}
        for holon_config in self.scenario.holons:
            parent_id = holon_ids.get(holon_config.parent) if holon_config.parent else None
            entity = self.agent_manager.create_group(holon_config.name, parent_id)
            holon_ids[holon_config.name] = entity.id

            # Create children if specified
            for i in range(holon_config.children):
                child_name = f"{holon_config.name}-Sub{i+1}"
                child = self.agent_manager.create_group(child_name, entity.id)
                holon_ids[child_name] = child.id

        print(f"  Created {len(holon_ids)} holons")

        # Create agents
        print("\nCreating agents...")
        agent_count = 0
        for agent_type, count in self.scenario.users.items():
            for i in range(count):
                name = f"{agent_type.value}_{i+1}"
                self.agent_manager.create_agent(name, agent_type)
                agent_count += 1

                # Progress indicator for large numbers
                if agent_count % 1000 == 0:
                    print(f"  Created {agent_count} agents...")

        print(f"  Created {agent_count} total agents")

        # Create views
        print("\nCreating views...")
        self._create_views()
        print(f"  Created {len(self.views)} views")

    def _create_views(self):
        """Create test views based on scenario configuration."""
        groups = [
            e for e in self.agent_manager.all_entity_ids
            if self.storage.get_entity(e) and
            self.storage.get_entity(e).kind.value == "group"
        ]

        for i in range(self.scenario.views_to_create):
            if groups:
                group = random.choice(groups)
            else:
                group = None

            view = View(
                id=generate_view_id(f"test-view-{i+1}"),
                author="ent:system",
                name=f"Test View {i+1}",
                source={"type": "context", "holon": group} if group else {"type": "follows", "of": "ent:system"},
                filters=[
                    {"field": "kind", "op": "eq", "value": "post"},
                    {"field": "created", "op": "gt", "value": {"relative": "-24h"}},
                ],
                sort=[
                    {"field": "reaction_count", "order": "desc"},
                    {"field": "created", "order": "desc"},
                    {"field": "id", "order": "asc"},
                ],
                limit=50,
            )
            self.storage.create_view(view)
            self.views.append(view)

    def run(self, progress_interval: int = 10):
        """Run the simulation."""
        print(f"\nRunning simulation...")

        end_time = self.start_time + self.scenario.duration
        tick_count = 0
        last_progress = 0

        while self.current_time < end_time:
            # Simulate one tick
            self.agent_manager.simulate_tick(self.current_time, self.scenario.tick_interval)

            # Handle special events
            elapsed = self.current_time - self.start_time

            if self.scenario.viral_content_at and elapsed >= self.scenario.viral_content_at:
                if not hasattr(self, '_viral_injected'):
                    self._inject_viral_content()
                    self._viral_injected = True

            if self.scenario.spam_wave_at and elapsed >= self.scenario.spam_wave_at:
                if not hasattr(self, '_spam_injected'):
                    self._inject_spam_wave()
                    self._spam_injected = True

            # Key rotation (if configured)
            if self.scenario.key_rotation_interval:
                if self.current_time - self.last_key_rotation >= self.scenario.key_rotation_interval:
                    self._perform_key_rotations()
                    self.last_key_rotation = self.current_time

            # Member churn (for group encryption testing)
            if self.scenario.member_churn_rate > 0:
                self._simulate_member_churn()

            # Network simulation
            if self.network:
                self.network.simulate_tick(self.current_time, self.scenario.tick_interval)
                if tick_count % 10 == 0:
                    net_metrics = self.network.collect_metrics(
                        self.current_time,
                        (self.current_time - self.start_time).total_seconds()
                    )
                    self.network_metrics.append(net_metrics)

            # Collect metrics periodically
            if tick_count % 10 == 0:
                self._collect_metrics()

            # Execute and time views periodically
            if tick_count % 50 == 0 and self.views:
                self._execute_views()

            # Advance time
            self.current_time += self.scenario.tick_interval
            tick_count += 1

            # Progress reporting
            progress = int((elapsed.total_seconds() / self.scenario.duration.total_seconds()) * 100)
            if progress >= last_progress + progress_interval:
                metrics = self.storage.get_metrics()
                extra_info = ""
                if self.network:
                    online = sum(1 for r in self.network.relays.values() if r.is_online)
                    extra_info = f" | Relays: {online}/{len(self.network.relays)}"
                print(f"  {progress}% complete | Objects: {metrics['total_objects']:,} | "
                      f"Size: {metrics['total_size_mb']:.2f} MB{extra_info}")
                last_progress = progress

        print(f"\nSimulation complete!")

    def _perform_key_rotations(self):
        """Perform key rotations for a subset of users."""
        # Rotate keys for 5% of users each interval
        users = list(self.agent_manager.agents.keys())
        to_rotate = random.sample(users, max(1, len(users) // 20))

        for user_id in to_rotate:
            version = self.key_versions.get(user_id, 1)
            new_version = version + 1
            self.key_versions[user_id] = new_version

            # Create key rotation link
            link = Link(
                id=generate_link_id(),
                kind=LinkKind.CREDENTIAL,
                source=user_id,
                target=user_id,
                created=self.current_time,
                data={
                    "subkind": "key_rotation",
                    "old_version": version,
                    "new_version": new_version,
                },
            )
            self.storage.create_link(link)

            self.key_rotation_events.append({
                "timestamp": self.current_time.isoformat(),
                "user": user_id,
                "old_version": version,
                "new_version": new_version,
            })

    def _simulate_member_churn(self):
        """Simulate members joining and leaving groups."""
        groups = [
            e for e in self.agent_manager.all_entity_ids
            if self.storage.get_entity(e) and
            self.storage.get_entity(e).kind.value == "group"
        ]

        if not groups:
            return

        for group in groups:
            # Get current members
            members = [
                a for a in self.agent_manager.agents.values()
                if group in a.joined_groups
            ]

            # Some members leave
            num_leave = int(len(members) * self.scenario.member_churn_rate * random.random())
            for agent in random.sample(members, min(num_leave, len(members))):
                if group in agent.joined_groups:
                    agent.joined_groups.remove(group)
                    # Create leave link
                    link = Link(
                        id=generate_link_id(),
                        kind=LinkKind.CREDENTIAL,
                        source=agent.entity_id,
                        target=group,
                        created=self.current_time,
                        data={"subkind": "membership", "tombstone": True},
                        tombstone=True,
                    )
                    self.storage.create_link(link)

                    self.group_key_events.append({
                        "timestamp": self.current_time.isoformat(),
                        "action": "leave",
                        "group": group,
                        "member": agent.entity_id,
                    })

            # Some new members join
            non_members = [
                a for a in self.agent_manager.agents.values()
                if group not in a.joined_groups
            ]
            num_join = int(len(non_members) * self.scenario.member_churn_rate * random.random())
            for agent in random.sample(non_members, min(num_join, len(non_members))):
                agent.joined_groups.append(group)
                link = Link(
                    id=generate_link_id(),
                    kind=LinkKind.CREDENTIAL,
                    source=agent.entity_id,
                    target=group,
                    created=self.current_time,
                    data={"subkind": "membership", "role": "member"},
                )
                self.storage.create_link(link)

                self.group_key_events.append({
                    "timestamp": self.current_time.isoformat(),
                    "action": "join",
                    "group": group,
                    "member": agent.entity_id,
                })

    def _inject_viral_content(self):
        """Inject a piece of viral content that everyone reacts to."""
        print("  [EVENT] Injecting viral content...")
        from core import Content, ContentKind, Link, LinkKind, generate_content_id, generate_link_id

        # Create viral post
        author = random.choice(list(self.agent_manager.agents.keys()))
        content = Content(
            id=generate_content_id(author, "post"),
            kind=ContentKind.POST,
            author=author,
            created=self.current_time,
            data={"text": "🚀 This is the viral post everyone is talking about! 🔥", "viral": True},
        )
        self.storage.create_content(content)
        self.agent_manager.all_content_ids.append(content.id)

        # Have many users react
        for agent_id in list(self.agent_manager.agents.keys())[:1000]:  # First 1000 agents
            link = Link(
                id=generate_link_id(),
                kind=LinkKind.INTERACTION,
                source=agent_id,
                target=content.id,
                created=self.current_time,
                data={"subkind": "react", "emoji": "🔥"},
            )
            self.storage.create_link(link)

    def _inject_spam_wave(self):
        """Inject a wave of spam content."""
        print("  [EVENT] Injecting spam wave...")
        from core import Content, ContentKind, generate_content_id

        # Find or create spammers
        spammers = [
            a for a in self.agent_manager.agents.values()
            if a.agent_type == AgentType.SPAMMER
        ]

        if not spammers:
            # Create temporary spammers
            for i in range(20):
                self.agent_manager.create_agent(f"spammer_wave_{i}", AgentType.SPAMMER)
            spammers = [
                a for a in self.agent_manager.agents.values()
                if a.agent_type == AgentType.SPAMMER
            ]

        # Each spammer posts 10 spam messages
        for spammer in spammers:
            for _ in range(10):
                content = Content(
                    id=generate_content_id(spammer.entity_id, "post"),
                    kind=ContentKind.POST,
                    author=spammer.entity_id,
                    created=self.current_time,
                    data={"text": "SPAM! Buy now! http://spam.example.com", "is_spam": True},
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
        for view in self.views[:5]:  # Only test first 5 views each time
            execution = self.view_engine.execute(view, self.current_time)
            self.view_executions.append({
                "view_id": view.id,
                "timestamp": self.current_time.isoformat(),
                "result_count": len(execution.results),
                "computation_time_ms": execution.computation_time_ms,
            })

    def get_results(self) -> dict:
        """Get simulation results."""
        final_metrics = self.storage.get_metrics()

        # View execution stats
        if self.view_executions:
            exec_times = [e["computation_time_ms"] for e in self.view_executions]
            exec_times.sort()
            view_stats = {
                "total_executions": len(self.view_executions),
                "avg_time_ms": sum(exec_times) / len(exec_times),
                "p50_time_ms": exec_times[len(exec_times) // 2],
                "p95_time_ms": exec_times[int(len(exec_times) * 0.95)],
                "p99_time_ms": exec_times[int(len(exec_times) * 0.99)] if len(exec_times) > 100 else exec_times[-1],
            }
        else:
            view_stats = {}

        results = {
            "scenario": self.scenario.name,
            "duration": str(self.scenario.duration),
            "final_metrics": final_metrics,
            "view_stats": view_stats,
            "metrics_history": self.metrics_history,
            "view_executions": self.view_executions[-100:],
        }

        # Add network metrics if available
        if self.network:
            results["network_metrics"] = self.network_metrics
            results["relay_stats"] = self.network.get_relay_stats()
            results["client_stats"] = self.network.get_client_stats()

        # Add key rotation stats if available
        if self.key_rotation_events:
            results["key_rotation_events"] = self.key_rotation_events[-100:]
            results["key_rotation_stats"] = {
                "total_rotations": len(self.key_rotation_events),
                "unique_users_rotated": len(set(e["user"] for e in self.key_rotation_events)),
            }

        # Add group encryption stats if available
        if self.group_key_events:
            results["group_key_events"] = self.group_key_events[-100:]
            joins = len([e for e in self.group_key_events if e["action"] == "join"])
            leaves = len([e for e in self.group_key_events if e["action"] == "leave"])
            results["group_churn_stats"] = {
                "total_joins": joins,
                "total_leaves": leaves,
                "net_change": joins - leaves,
            }

        return results

    def print_summary(self):
        """Print a summary of results."""
        results = self.get_results()

        print("\n" + "=" * 60)
        print(f"SIMULATION RESULTS: {results['scenario']}")
        print("=" * 60)

        m = results["final_metrics"]
        print(f"\nStorage:")
        print(f"  Entities:     {m['entity_count']:,}")
        print(f"  Content:      {m['content_count']:,}")
        print(f"  Links:        {m['link_count']:,}")
        print(f"  Total:        {m['total_objects']:,}")
        print(f"  Size:         {m['total_size_mb']:.2f} MB")

        print(f"\nLink breakdown:")
        for subkind, count in sorted(m.get("link_breakdown", {}).items(), key=lambda x: -x[1]):
            print(f"  {subkind}: {count:,}")

        if results["view_stats"]:
            v = results["view_stats"]
            print(f"\nView execution:")
            print(f"  Total executions: {v['total_executions']:,}")
            print(f"  Avg time:         {v['avg_time_ms']:.2f} ms")
            print(f"  P50 time:         {v['p50_time_ms']:.2f} ms")
            print(f"  P95 time:         {v['p95_time_ms']:.2f} ms")

        # Network stats
        if "relay_stats" in results:
            r = results["relay_stats"]
            print(f"\nNetwork (Multi-Relay):")
            print(f"  Relays:           {len(r['relays'])}")
            for relay in r["relays"]:
                status = "✓" if relay["is_online"] else "✗"
                print(f"    {relay['id']}: {status} | "
                      f"recv: {relay['objects_received']:,} | "
                      f"sent: {relay['objects_sent']:,} | "
                      f"avg latency: {relay['avg_latency_ms']:.1f}ms")

        # Key rotation stats
        if "key_rotation_stats" in results:
            k = results["key_rotation_stats"]
            print(f"\nKey Rotation:")
            print(f"  Total rotations:  {k['total_rotations']:,}")
            print(f"  Users rotated:    {k['unique_users_rotated']:,}")

        # Group churn stats
        if "group_churn_stats" in results:
            g = results["group_churn_stats"]
            print(f"\nGroup Membership Churn:")
            print(f"  Total joins:      {g['total_joins']:,}")
            print(f"  Total leaves:     {g['total_leaves']:,}")
            print(f"  Net change:       {g['net_change']:+,}")

        print("\n" + "=" * 60)

    def save_results(self, output_dir: str = "results"):
        """Save results to files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        scenario_name = self.scenario.name.lower().replace(" ", "_")

        # Save full results
        results_file = output_path / f"{scenario_name}_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump(self.get_results(), f, indent=2, default=str)
        print(f"\nResults saved to: {results_file}")

        # Save summary
        summary_file = output_path / f"{scenario_name}_{timestamp}_summary.txt"
        with open(summary_file, "w") as f:
            import sys
            old_stdout = sys.stdout
            sys.stdout = f
            self.print_summary()
            sys.stdout = old_stdout
        print(f"Summary saved to: {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="HOLON Protocol Simulator")
    parser.add_argument(
        "--scenario", "-s",
        type=str,
        default="small_network",
        choices=[s.value for s in ScenarioType],
        help="Scenario to run"
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
        default="results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios"
    )

    args = parser.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        print("-" * 60)
        for scenario in list_scenarios():
            print(f"\n{scenario['type']}")
            print(f"  {scenario['description']}")
            print(f"  Users: {scenario['users']:,} | Duration: {scenario['duration']}")
        return

    # Run simulation
    scenario_type = ScenarioType(args.scenario)
    simulator = Simulator(scenario_type, seed=args.seed)

    start = time.time()
    simulator.setup()
    simulator.run()
    elapsed = time.time() - start

    print(f"\nReal time elapsed: {elapsed:.1f} seconds")

    simulator.print_summary()
    simulator.save_results(args.output)


if __name__ == "__main__":
    main()
