"""
HOLON Protocol v4.0 Simulator - Scenarios

Test scenarios aligned with v4.0 features:
- Discovery mechanisms
- Transparent algorithms (views)
- Economics (tips, subscriptions)
- Moderation (labels)
"""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

from agents import AgentType


class ScenarioType(Enum):
    # Basic scenarios
    SMALL_NETWORK = "small_network"
    MEDIUM_NETWORK = "medium_network"
    LARGE_NETWORK = "large_network"

    # Discovery scenarios
    DISCOVERY_TEST = "discovery_test"
    SEARCH_STRESS = "search_stress"
    HANDLE_RESOLUTION = "handle_resolution"

    # Algorithm scenarios
    VIEW_CREATION = "view_creation"
    VIEW_VERIFICATION = "view_verification"
    RANKING_FORMULAS = "ranking_formulas"

    # Economics scenarios
    CREATOR_ECONOMY = "creator_economy"
    VIEW_ECONOMY = "view_economy"
    TIPPING_CULTURE = "tipping_culture"

    # Moderation scenarios
    SPAM_ATTACK = "spam_attack"
    MODERATION_TEST = "moderation_test"

    # Mixed scenarios
    FULL_ECOSYSTEM = "full_ecosystem"


@dataclass
class GroupConfig:
    name: str
    parent: str | None = None
    moderators: list[str] = field(default_factory=list)


@dataclass
class ScenarioConfig:
    name: str
    description: str
    duration: timedelta
    users: dict[AgentType, int]
    groups: list[GroupConfig]
    tick_interval: timedelta = timedelta(minutes=1)
    initial_views: int = 5
    # Special events
    spam_wave_at: timedelta | None = None
    viral_content_at: timedelta | None = None


SCENARIOS = {
    # ==========================================================================
    # BASIC SCENARIOS
    # ==========================================================================

    ScenarioType.SMALL_NETWORK: ScenarioConfig(
        name="Small Network",
        description="100 users testing basic functionality",
        duration=timedelta(hours=1),
        users={
            AgentType.LURKER: 40,
            AgentType.CASUAL: 35,
            AgentType.ACTIVE: 15,
            AgentType.CREATOR: 5,
            AgentType.CURATOR: 3,
            AgentType.MODERATOR: 2,
        },
        groups=[
            GroupConfig(name="General"),
            GroupConfig(name="Tech"),
            GroupConfig(name="Random"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    ScenarioType.MEDIUM_NETWORK: ScenarioConfig(
        name="Medium Network",
        description="10,000 users testing scale",
        duration=timedelta(hours=6),
        users={
            AgentType.LURKER: 4000,
            AgentType.CASUAL: 3500,
            AgentType.ACTIVE: 1500,
            AgentType.CREATOR: 500,
            AgentType.CURATOR: 300,
            AgentType.MODERATOR: 200,
        },
        groups=[
            GroupConfig(name="General"),
            GroupConfig(name="Tech"),
            GroupConfig(name="Creative"),
            GroupConfig(name="Gaming"),
            GroupConfig(name="AI", parent="Tech"),
            GroupConfig(name="Web", parent="Tech"),
            GroupConfig(name="Rust", parent="Tech"),
        ],
        tick_interval=timedelta(minutes=1),
    ),

    ScenarioType.LARGE_NETWORK: ScenarioConfig(
        name="Large Network",
        description="100,000 users stress test",
        duration=timedelta(hours=24),
        users={
            AgentType.LURKER: 40000,
            AgentType.CASUAL: 35000,
            AgentType.ACTIVE: 15000,
            AgentType.CREATOR: 5000,
            AgentType.CURATOR: 3000,
            AgentType.MODERATOR: 2000,
        },
        groups=[
            GroupConfig(name=f"Category{i}") for i in range(20)
        ],
        tick_interval=timedelta(minutes=5),
    ),

    # ==========================================================================
    # DISCOVERY SCENARIOS
    # ==========================================================================

    ScenarioType.DISCOVERY_TEST: ScenarioConfig(
        name="Discovery Test",
        description="Tests all discovery mechanisms: search, suggestions, verification",
        duration=timedelta(hours=2),
        users={
            AgentType.LURKER: 200,  # Heavy searchers
            AgentType.CASUAL: 150,
            AgentType.ACTIVE: 100,
            AgentType.CREATOR: 30,
            AgentType.CURATOR: 20,
        },
        groups=[
            GroupConfig(name="Programming"),
            GroupConfig(name="Design"),
            GroupConfig(name="AI"),
            GroupConfig(name="Rust", parent="Programming"),
            GroupConfig(name="Python", parent="Programming"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    ScenarioType.SEARCH_STRESS: ScenarioConfig(
        name="Search Stress",
        description="Heavy search and discovery load",
        duration=timedelta(hours=1),
        users={
            AgentType.LURKER: 500,  # All searching heavily
            AgentType.CASUAL: 300,
            AgentType.ACTIVE: 200,
        },
        groups=[
            GroupConfig(name="Main"),
        ],
        tick_interval=timedelta(seconds=15),
    ),

    ScenarioType.HANDLE_RESOLUTION: ScenarioConfig(
        name="Handle Resolution",
        description="Tests handle lookup and external verification",
        duration=timedelta(hours=1),
        users={
            AgentType.CASUAL: 100,
            AgentType.CREATOR: 50,  # Many verifying external identities
        },
        groups=[
            GroupConfig(name="Verified"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    # ==========================================================================
    # ALGORITHM SCENARIOS
    # ==========================================================================

    ScenarioType.VIEW_CREATION: ScenarioConfig(
        name="View Creation",
        description="Tests view creation and subscription by curators",
        duration=timedelta(hours=2),
        users={
            AgentType.CASUAL: 200,
            AgentType.ACTIVE: 150,
            AgentType.CREATOR: 50,
            AgentType.CURATOR: 100,  # Many curators creating views
        },
        groups=[
            GroupConfig(name="General"),
            GroupConfig(name="Curated"),
        ],
        tick_interval=timedelta(seconds=30),
        initial_views=3,
    ),

    ScenarioType.VIEW_VERIFICATION: ScenarioConfig(
        name="View Verification",
        description="Tests view execution and verification",
        duration=timedelta(hours=1),
        users={
            AgentType.ACTIVE: 500,
            AgentType.CREATOR: 100,
            AgentType.CURATOR: 50,
        },
        groups=[
            GroupConfig(name="Main"),
        ],
        tick_interval=timedelta(seconds=20),
        initial_views=20,  # Many views to verify
    ),

    ScenarioType.RANKING_FORMULAS: ScenarioConfig(
        name="Ranking Formula Test",
        description="Tests different ranking formulas (decay, log, etc.)",
        duration=timedelta(hours=2),
        users={
            AgentType.CASUAL: 300,
            AgentType.ACTIVE: 200,
            AgentType.CREATOR: 100,
        },
        groups=[
            GroupConfig(name="Main"),
        ],
        tick_interval=timedelta(seconds=30),
        initial_views=10,
    ),

    # ==========================================================================
    # ECONOMICS SCENARIOS
    # ==========================================================================

    ScenarioType.CREATOR_ECONOMY: ScenarioConfig(
        name="Creator Economy",
        description="Tests subscriptions, paid content, tips",
        duration=timedelta(hours=3),
        users={
            AgentType.LURKER: 100,
            AgentType.CASUAL: 200,  # Subscribers
            AgentType.ACTIVE: 150,  # Tippers
            AgentType.CREATOR: 50,  # Monetizing creators
        },
        groups=[
            GroupConfig(name="Creators"),
            GroupConfig(name="Premium"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    ScenarioType.VIEW_ECONOMY: ScenarioConfig(
        name="View Economy",
        description="Tests paid view subscriptions",
        duration=timedelta(hours=2),
        users={
            AgentType.CASUAL: 300,
            AgentType.ACTIVE: 200,
            AgentType.CURATOR: 100,  # Creating paid views
        },
        groups=[
            GroupConfig(name="Main"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    ScenarioType.TIPPING_CULTURE: ScenarioConfig(
        name="Tipping Culture",
        description="Heavy tipping activity",
        duration=timedelta(hours=1),
        users={
            AgentType.ACTIVE: 500,  # Active tippers
            AgentType.CREATOR: 100,
        },
        groups=[
            GroupConfig(name="Main"),
        ],
        tick_interval=timedelta(seconds=20),
    ),

    # ==========================================================================
    # MODERATION SCENARIOS
    # ==========================================================================

    ScenarioType.SPAM_ATTACK: ScenarioConfig(
        name="Spam Attack",
        description="Spam attack with moderation response",
        duration=timedelta(hours=1),
        users={
            AgentType.CASUAL: 300,
            AgentType.ACTIVE: 150,
            AgentType.SPAMMER: 50,
            AgentType.MODERATOR: 20,
        },
        groups=[
            GroupConfig(name="Main"),
            GroupConfig(name="Moderated"),
        ],
        tick_interval=timedelta(seconds=10),
        spam_wave_at=timedelta(minutes=15),
    ),

    ScenarioType.MODERATION_TEST: ScenarioConfig(
        name="Moderation Test",
        description="Tests labeling and content filtering",
        duration=timedelta(hours=2),
        users={
            AgentType.CASUAL: 200,
            AgentType.ACTIVE: 150,
            AgentType.CREATOR: 50,
            AgentType.SPAMMER: 20,
            AgentType.MODERATOR: 30,
        },
        groups=[
            GroupConfig(name="Strict", moderators=["mod_1", "mod_2"]),
            GroupConfig(name="Relaxed"),
        ],
        tick_interval=timedelta(seconds=30),
    ),

    # ==========================================================================
    # FULL ECOSYSTEM
    # ==========================================================================

    ScenarioType.FULL_ECOSYSTEM: ScenarioConfig(
        name="Full Ecosystem",
        description="All v4.0 features: discovery, algorithms, economics, moderation",
        duration=timedelta(hours=4),
        users={
            AgentType.LURKER: 200,
            AgentType.CASUAL: 300,
            AgentType.ACTIVE: 200,
            AgentType.CREATOR: 100,
            AgentType.CURATOR: 50,
            AgentType.SPAMMER: 20,
            AgentType.MODERATOR: 30,
        },
        groups=[
            GroupConfig(name="General"),
            GroupConfig(name="Tech"),
            GroupConfig(name="Creative"),
            GroupConfig(name="Premium"),
            GroupConfig(name="AI", parent="Tech"),
            GroupConfig(name="Design", parent="Creative"),
        ],
        tick_interval=timedelta(seconds=30),
        initial_views=10,
        spam_wave_at=timedelta(hours=1),
        viral_content_at=timedelta(hours=2),
    ),
}


def get_scenario(scenario_type: ScenarioType) -> ScenarioConfig:
    return SCENARIOS[scenario_type]


def list_scenarios() -> list[dict]:
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
