"""
HOLON Protocol Simulator - Network Simulation

Simulates multiple relays with sync delays and network conditions.
"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable
from collections import defaultdict

from core import Storage, Entity, Content, Link


@dataclass
class NetworkConfig:
    """Configuration for network simulation."""
    # Latency settings (ms)
    min_latency_ms: float = 10.0
    max_latency_ms: float = 100.0
    latency_variance: float = 0.3  # Variance factor

    # Reliability
    packet_loss_rate: float = 0.01  # 1% packet loss
    relay_failure_rate: float = 0.001  # 0.1% chance of relay failure per tick

    # Bandwidth (objects per second per relay)
    max_sync_rate: int = 1000

    # Sync behavior
    sync_interval_seconds: float = 5.0  # How often clients sync
    full_sync_probability: float = 0.01  # Probability of full resync


@dataclass
class Relay:
    """Simulated relay server."""
    id: str
    storage: Storage
    is_online: bool = True
    objects_received: int = 0
    objects_sent: int = 0
    sync_requests: int = 0
    failed_syncs: int = 0

    # Network stats
    total_latency_ms: float = 0.0
    latency_samples: int = 0

    def get_stats(self) -> dict:
        return {
            "id": self.id,
            "is_online": self.is_online,
            "objects_received": self.objects_received,
            "objects_sent": self.objects_sent,
            "sync_requests": self.sync_requests,
            "failed_syncs": self.failed_syncs,
            "avg_latency_ms": self.total_latency_ms / max(1, self.latency_samples),
            "storage": self.storage.get_metrics(),
        }


@dataclass
class Client:
    """Simulated client that syncs with relays."""
    id: str
    entity_id: str
    connected_relays: list[str]
    sync_cursors: dict[str, int] = field(default_factory=dict)
    local_storage: Storage = field(default_factory=Storage)
    pending_writes: list = field(default_factory=list)
    last_sync: datetime = field(default_factory=datetime.utcnow)

    # Stats
    sync_attempts: int = 0
    sync_successes: int = 0
    objects_synced: int = 0


class NetworkSimulator:
    """Simulates network of relays and clients."""

    def __init__(self, config: NetworkConfig = None):
        self.config = config or NetworkConfig()
        self.relays: dict[str, Relay] = {}
        self.clients: dict[str, Client] = {}
        self.network_metrics: list[dict] = []

        # Primary relay (for writes)
        self.primary_relay_id: str | None = None

    def add_relay(self, relay_id: str, is_primary: bool = False) -> Relay:
        """Add a relay to the network."""
        relay = Relay(id=relay_id, storage=Storage())
        self.relays[relay_id] = relay
        if is_primary or self.primary_relay_id is None:
            self.primary_relay_id = relay_id
        return relay

    def add_client(self, client_id: str, entity_id: str, relay_ids: list[str] = None) -> Client:
        """Add a client to the network."""
        if relay_ids is None:
            relay_ids = list(self.relays.keys())

        client = Client(
            id=client_id,
            entity_id=entity_id,
            connected_relays=relay_ids,
        )
        self.clients[client_id] = client
        return client

    def get_primary_storage(self) -> Storage:
        """Get the primary relay's storage (for agent operations)."""
        if self.primary_relay_id and self.primary_relay_id in self.relays:
            return self.relays[self.primary_relay_id].storage
        raise RuntimeError("No primary relay configured")

    def simulate_latency(self) -> float:
        """Simulate network latency."""
        base = random.uniform(self.config.min_latency_ms, self.config.max_latency_ms)
        variance = base * self.config.latency_variance * random.uniform(-1, 1)
        return max(1.0, base + variance)

    def simulate_packet_loss(self) -> bool:
        """Returns True if packet is lost."""
        return random.random() < self.config.packet_loss_rate

    def write_to_primary(self, obj: Entity | Content | Link) -> bool:
        """Write an object to the primary relay."""
        if self.primary_relay_id is None:
            return False

        relay = self.relays[self.primary_relay_id]
        if not relay.is_online:
            return False

        # Simulate latency
        latency = self.simulate_latency()
        relay.total_latency_ms += latency
        relay.latency_samples += 1

        # Check for packet loss
        if self.simulate_packet_loss():
            return False

        # Write to storage
        if isinstance(obj, Entity):
            relay.storage.create_entity(obj)
        elif isinstance(obj, Content):
            relay.storage.create_content(obj)
        elif isinstance(obj, Link):
            relay.storage.create_link(obj)

        relay.objects_received += 1
        return True

    def replicate_to_relays(self, current_time: datetime):
        """Replicate data from primary to other relays."""
        if self.primary_relay_id is None:
            return

        primary = self.relays[self.primary_relay_id]
        primary_storage = primary.storage

        for relay_id, relay in self.relays.items():
            if relay_id == self.primary_relay_id:
                continue
            if not relay.is_online:
                continue

            # Simulate inter-relay sync
            latency = self.simulate_latency()
            relay.total_latency_ms += latency
            relay.latency_samples += 1

            if self.simulate_packet_loss():
                relay.failed_syncs += 1
                continue

            # Copy new entities
            for eid, entity in primary_storage.entities.items():
                if eid not in relay.storage.entities:
                    relay.storage.create_entity(entity)
                    relay.objects_received += 1

            # Copy new content
            for cid, content in primary_storage.content.items():
                if cid not in relay.storage.content:
                    relay.storage.create_content(content)
                    relay.objects_received += 1

            # Copy new links
            for lid, link in primary_storage.links.items():
                if lid not in relay.storage.links:
                    relay.storage.create_link(link)
                    relay.objects_received += 1

    def sync_client(self, client: Client, current_time: datetime) -> dict:
        """Sync a client with its connected relays."""
        client.sync_attempts += 1
        sync_result = {
            "client_id": client.id,
            "timestamp": current_time.isoformat(),
            "objects_synced": 0,
            "latency_ms": 0,
            "success": False,
            "relays_synced": [],
        }

        total_latency = 0
        total_objects = 0

        for relay_id in client.connected_relays:
            relay = self.relays.get(relay_id)
            if not relay or not relay.is_online:
                continue

            # Simulate latency
            latency = self.simulate_latency()
            total_latency += latency
            relay.total_latency_ms += latency
            relay.latency_samples += 1
            relay.sync_requests += 1

            # Check for packet loss
            if self.simulate_packet_loss():
                relay.failed_syncs += 1
                continue

            # Get cursor for this relay
            cursor = client.sync_cursors.get(relay_id, 0)

            # Sync entities
            for eid, entity in relay.storage.entities.items():
                if eid not in client.local_storage.entities:
                    client.local_storage.create_entity(entity)
                    total_objects += 1

            # Sync content
            for cid, content in relay.storage.content.items():
                if cid not in client.local_storage.content:
                    client.local_storage.create_content(content)
                    total_objects += 1

            # Sync links
            for lid, link in relay.storage.links.items():
                if lid not in client.local_storage.links:
                    client.local_storage.create_link(link)
                    total_objects += 1

            # Update cursor
            client.sync_cursors[relay_id] = relay.storage._seq
            relay.objects_sent += total_objects
            sync_result["relays_synced"].append(relay_id)

        sync_result["objects_synced"] = total_objects
        sync_result["latency_ms"] = total_latency
        sync_result["success"] = total_objects > 0 or len(sync_result["relays_synced"]) > 0

        if sync_result["success"]:
            client.sync_successes += 1
            client.objects_synced += total_objects

        client.last_sync = current_time
        return sync_result

    def simulate_tick(self, current_time: datetime, tick_duration: timedelta):
        """Simulate one tick of network activity."""
        # Random relay failures
        for relay in self.relays.values():
            if relay.is_online and random.random() < self.config.relay_failure_rate:
                relay.is_online = False
            elif not relay.is_online and random.random() > self.config.relay_failure_rate * 10:
                # Relays come back online eventually
                relay.is_online = True

        # Replicate between relays
        self.replicate_to_relays(current_time)

        # Sync clients that need it
        sync_interval = timedelta(seconds=self.config.sync_interval_seconds)
        for client in self.clients.values():
            if current_time - client.last_sync >= sync_interval:
                self.sync_client(client, current_time)

    def collect_metrics(self, current_time: datetime, elapsed_seconds: float) -> dict:
        """Collect network metrics."""
        online_relays = sum(1 for r in self.relays.values() if r.is_online)
        total_objects = sum(r.storage.get_metrics()["total_objects"] for r in self.relays.values())

        # Calculate sync success rate
        total_attempts = sum(c.sync_attempts for c in self.clients.values())
        total_successes = sum(c.sync_successes for c in self.clients.values())
        sync_success_rate = total_successes / max(1, total_attempts)

        # Average latency across relays
        total_latency = sum(r.total_latency_ms for r in self.relays.values())
        total_samples = sum(r.latency_samples for r in self.relays.values())
        avg_latency = total_latency / max(1, total_samples)

        # Bandwidth (rough estimate)
        total_synced = sum(c.objects_synced for c in self.clients.values())
        bandwidth_obj_per_sec = total_synced / max(1, elapsed_seconds)

        metrics = {
            "timestamp": current_time.isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "online_relays": online_relays,
            "total_relays": len(self.relays),
            "total_clients": len(self.clients),
            "total_objects_across_relays": total_objects,
            "sync_success_rate": sync_success_rate,
            "avg_latency_ms": avg_latency,
            "bandwidth_obj_per_sec": bandwidth_obj_per_sec,
        }
        self.network_metrics.append(metrics)
        return metrics

    def get_relay_stats(self) -> dict:
        """Get statistics for all relays."""
        return {
            "relays": [r.get_stats() for r in self.relays.values()],
            "relay_message_counts": {r.id: r.objects_received + r.objects_sent for r in self.relays.values()},
        }

    def get_client_stats(self) -> dict:
        """Get statistics for all clients."""
        return {
            "total_clients": len(self.clients),
            "total_sync_attempts": sum(c.sync_attempts for c in self.clients.values()),
            "total_sync_successes": sum(c.sync_successes for c in self.clients.values()),
            "total_objects_synced": sum(c.objects_synced for c in self.clients.values()),
        }


# Helper function for integration with main simulator
def create_network_simulation(
    num_relays: int = 3,
    num_clients: int = 100,
    config: NetworkConfig = None
) -> NetworkSimulator:
    """Create a network simulation with the specified number of relays and clients."""
    network = NetworkSimulator(config)

    # Add relays
    for i in range(num_relays):
        network.add_relay(f"relay-{i+1}", is_primary=(i == 0))

    # Add clients (will be linked to entities later)
    for i in range(num_clients):
        # Each client connects to 1-3 relays
        num_connected = random.randint(1, min(3, num_relays))
        connected = random.sample(list(network.relays.keys()), num_connected)
        network.add_client(f"client-{i+1}", f"ent:user-{i+1}", connected)

    return network
