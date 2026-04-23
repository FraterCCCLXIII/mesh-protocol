"""
HOLON Protocol Simulator - Scenarios

Pre-defined simulation scenarios for testing different aspects of the protocol.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from agents import AgentType


class ScenarioType(Enum):
    SMALL_NETWORK = "small_network"
    MEDIUM_NETWORK = "medium_network"
    LARGE_NETWORK = "large_network"
    SPAM_ATTACK = "spam_attack"
    VIRAL_CONTENT = "viral_content"
    NESTED_HOLONS = "nested_holons"
    VIEW_STRESS = "view_stress"


@dataclass
class HolonConfig:
    """Configuration for creating holons (groups)."""
    name: str
    parent: str | None = None
    children: int = 0  # Number of child holons to create


@dataclass
class ScenarioConfig:
    """Configuration for a simulation scenario."""
    name: str
    description: str
    duration: timedelta
    users: dict[AgentType, int]  # Number of each agent type
    holons: list[HolonConfig]
    tick_interval: timedelta = timedelta(minutes=1)
    views_to_create: int = 5
    viral_content_at: timedelta | None = None  # Inject viral content at this time
    spam_wave_at: timedelta | None = None  # Inject spam wave at this time


# =============================================================================
# PRE-DEFINED SCENARIOS
# =============================================================================

SCENARIOS = {
    ScenarioType.SMALL_NETWORK: ScenarioConfig(
        name="Small Network",
        description="A small network of 100 users with 5 groups. Tests basic functionality.",
        duration=timedelta(hours=1),
        tick_interval=timedelta(seconds=30),
        users={
            AgentType.LURKER: 50,
            AgentType.CASUAL: 35,
            AgentType.ACTIVE: 10,
            AgentType.POWER_USER: 4,
            AgentType.MODERATOR: 1,
        },
        holons=[
            HolonConfig(name="General"),
            HolonConfig(name="Tech"),
            HolonConfig(name="Random"),
            HolonConfig(name="Rust", parent="Tech"),
            HolonConfig(name="Python", parent="Tech"),
        ],
    ),

    ScenarioType.MEDIUM_NETWORK: ScenarioConfig(
        name="Medium Network",
        description="A medium network of 10,000 users. Tests storage growth and query performance.",
        duration=timedelta(hours=24),
        tick_interval=timedelta(minutes=1),
        users={
            AgentType.LURKER: 5000,
            AgentType.CASUAL: 3500,
            AgentType.ACTIVE: 1000,
            AgentType.POWER_USER: 450,
            AgentType.MODERATOR: 50,
        },
        holons=[
            HolonConfig(name="General", children=5),
            HolonConfig(name="Tech", children=10),
            HolonConfig(name="Creative", children=5),
            HolonConfig(name="Gaming", children=5),
            HolonConfig(name="Science", children=5),
        ],
    ),

    ScenarioType.LARGE_NETWORK: ScenarioConfig(
        name="Large Network",
        description="A large network of 100,000 users. Tests scalability limits.",
        duration=timedelta(days=7),
        tick_interval=timedelta(minutes=5),
        users={
            AgentType.LURKER: 50000,
            AgentType.CASUAL: 35000,
            AgentType.ACTIVE: 10000,
            AgentType.POWER_USER: 4500,
            AgentType.MODERATOR: 500,
        },
        holons=[
            HolonConfig(name=f"Category{i}", children=10) for i in range(50)
        ],
    ),

    ScenarioType.SPAM_ATTACK: ScenarioConfig(
        name="Spam Attack",
        description="Simulates a spam attack to test moderation and filtering.",
        duration=timedelta(hours=1),
        tick_interval=timedelta(seconds=10),
        users={
            AgentType.CASUAL: 500,
            AgentType.ACTIVE: 200,
            AgentType.SPAMMER: 50,  # 10% spammers
            AgentType.MODERATOR: 10,
        },
        holons=[
            HolonConfig(name="Main"),
            HolonConfig(name="Verified", parent="Main"),
        ],
        spam_wave_at=timedelta(minutes=20),
    ),

    ScenarioType.VIRAL_CONTENT: ScenarioConfig(
        name="Viral Content",
        description="Tests behavior when content goes viral (many reactions to one post).",
        duration=timedelta(hours=1),
        tick_interval=timedelta(seconds=15),
        users={
            AgentType.LURKER: 5000,
            AgentType.CASUAL: 3000,
            AgentType.ACTIVE: 1500,
            AgentType.POWER_USER: 500,
        },
        holons=[
            HolonConfig(name="Main"),
        ],
        viral_content_at=timedelta(minutes=10),
    ),

    ScenarioType.NESTED_HOLONS: ScenarioConfig(
        name="Nested Holons",
        description="Tests deep nesting of holons (Structure Layer stress test).",
        duration=timedelta(hours=6),
        tick_interval=timedelta(minutes=1),
        users={
            AgentType.CASUAL: 500,
            AgentType.ACTIVE: 300,
            AgentType.POWER_USER: 100,
            AgentType.MODERATOR: 20,
        },
        holons=[
            # Create a deep hierarchy
            HolonConfig(name="Level1"),
            HolonConfig(name="Level1-A", parent="Level1"),
            HolonConfig(name="Level1-B", parent="Level1"),
            HolonConfig(name="Level2-A1", parent="Level1-A"),
            HolonConfig(name="Level2-A2", parent="Level1-A"),
            HolonConfig(name="Level2-B1", parent="Level1-B"),
            HolonConfig(name="Level3-A1a", parent="Level2-A1"),
            HolonConfig(name="Level3-A1b", parent="Level2-A1"),
            HolonConfig(name="Level4-Deep", parent="Level3-A1a"),
            HolonConfig(name="Level5-Deepest", parent="Level4-Deep"),
        ],
    ),

    ScenarioType.VIEW_STRESS: ScenarioConfig(
        name="View Stress Test",
        description="Tests View Layer with many complex views and verifications.",
        duration=timedelta(hours=1),
        tick_interval=timedelta(seconds=30),
        users={
            AgentType.CASUAL: 5000,
            AgentType.ACTIVE: 3000,
            AgentType.POWER_USER: 1000,
        },
        holons=[
            HolonConfig(name="Main", children=10),
        ],
        views_to_create=50,  # Create 50 different views
    ),
}


def get_scenario(scenario_type: ScenarioType) -> ScenarioConfig:
    """Get a scenario configuration by type."""
    return SCENARIOS[scenario_type]


def list_scenarios() -> list[dict]:
    """List all available scenarios."""
    return [
        {
            "type": s.value,
            "name": SCENARIOS[s].name,
            "description": SCENARIOS[s].description,
            "users": sum(SCENARIOS[s].users.values()),
            "duration": str(SCENARIOS[s].duration),
        }
        for s in ScenarioType
    ]
