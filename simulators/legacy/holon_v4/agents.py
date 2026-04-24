"""
HOLON Protocol v4.0 Simulator - Agent System

User agents with behaviors aligned to v4.0 spec:
- Discovery (search, follow suggestions)
- Algorithm interaction (subscribing to views)
- Economics (tipping, subscribing)
- Verification (external identity proofs)
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from core import (
    Content, ContentKind, Entity, EntityKind, Link, LinkKind, AccessType,
    Storage, View, DiscoveryEngine, ReputationEngine,
    generate_content_id, generate_entity_id, generate_link_id, generate_view_id
)


class AgentType(Enum):
    LURKER = "lurker"           # Mostly reads, uses discovery
    CASUAL = "casual"           # Average activity
    ACTIVE = "active"           # High engagement
    CREATOR = "creator"         # Creates content, monetizes
    CURATOR = "curator"         # Creates views, curates
    SPAMMER = "spammer"         # Malicious actor
    MODERATOR = "moderator"     # Labels content


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    # Content creation
    posts_per_day: float = 1.0
    article_probability: float = 0.1  # Chance of article vs post
    paid_content_probability: float = 0.0

    # Engagement
    reactions_per_day: float = 5.0
    follows_per_day: float = 0.5
    reply_probability: float = 0.3

    # Discovery
    search_per_day: float = 1.0
    use_follow_suggestions: float = 0.3
    join_group_probability: float = 0.1

    # Economics
    tip_probability: float = 0.05
    subscribe_probability: float = 0.02

    # Views
    create_view_probability: float = 0.0
    subscribe_view_probability: float = 0.1

    # Verification
    verification_probability: float = 0.0

    # Moderation
    label_probability: float = 0.0

    # Anti-patterns
    spam_probability: float = 0.0
    unfollow_probability: float = 0.01


AGENT_CONFIGS = {
    AgentType.LURKER: AgentConfig(
        posts_per_day=0.1,
        reactions_per_day=2.0,
        follows_per_day=0.2,
        reply_probability=0.05,
        search_per_day=3.0,
        use_follow_suggestions=0.5,
    ),
    AgentType.CASUAL: AgentConfig(
        posts_per_day=0.5,
        reactions_per_day=5.0,
        follows_per_day=0.3,
        reply_probability=0.2,
        search_per_day=1.0,
        tip_probability=0.02,
    ),
    AgentType.ACTIVE: AgentConfig(
        posts_per_day=2.0,
        reactions_per_day=15.0,
        follows_per_day=1.0,
        reply_probability=0.4,
        tip_probability=0.05,
        subscribe_probability=0.05,
        subscribe_view_probability=0.2,
    ),
    AgentType.CREATOR: AgentConfig(
        posts_per_day=3.0,
        article_probability=0.3,
        paid_content_probability=0.1,
        reactions_per_day=10.0,
        follows_per_day=0.5,
        reply_probability=0.3,
        verification_probability=0.5,
    ),
    AgentType.CURATOR: AgentConfig(
        posts_per_day=1.0,
        reactions_per_day=20.0,
        follows_per_day=2.0,
        reply_probability=0.2,
        create_view_probability=0.3,
        subscribe_view_probability=0.5,
    ),
    AgentType.SPAMMER: AgentConfig(
        posts_per_day=50.0,
        reactions_per_day=0.0,
        follows_per_day=10.0,
        reply_probability=0.8,
        spam_probability=1.0,
    ),
    AgentType.MODERATOR: AgentConfig(
        posts_per_day=1.0,
        reactions_per_day=10.0,
        follows_per_day=0.5,
        reply_probability=0.3,
        label_probability=0.5,
    ),
}


@dataclass
class Agent:
    """A simulated user agent."""
    entity_id: str
    agent_type: AgentType
    config: AgentConfig
    handle: str

    # Social state
    following: list[str] = field(default_factory=list)
    joined_groups: list[str] = field(default_factory=list)
    subscribed_to: list[str] = field(default_factory=list)  # Creators
    subscribed_views: list[str] = field(default_factory=list)
    verified_externals: list[str] = field(default_factory=list)

    # Activity tracking
    posts_today: int = 0
    reactions_today: int = 0
    follows_today: int = 0
    searches_today: int = 0
    last_activity_reset: datetime = field(default_factory=datetime.now)

    # Created content/views
    created_views: list[str] = field(default_factory=list)


class AgentManager:
    """Manages all agents in the simulation."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self.agents: dict[str, Agent] = {}
        self.all_content_ids: list[str] = []
        self.all_entity_ids: list[str] = []
        self.all_view_ids: list[str] = []

        # Engines
        self.reputation = ReputationEngine(storage)
        self.discovery = DiscoveryEngine(storage, self.reputation)

    def create_agent(self, name: str, agent_type: AgentType) -> Agent:
        """Create a new agent with an entity."""
        entity_id = generate_entity_id(name)
        handle = name.lower().replace("_", "")

        # Create entity in storage
        entity = Entity(
            id=entity_id,
            kind=EntityKind.USER,
            handle=handle,
            profile={
                "name": name.replace("_", " ").title(),
                "bio": f"A {agent_type.value} user",
            },
            discoverable=agent_type != AgentType.SPAMMER,
        )
        self.storage.create_entity(entity)

        # Create agent
        config = AGENT_CONFIGS[agent_type]
        agent = Agent(
            entity_id=entity_id,
            agent_type=agent_type,
            config=config,
            handle=handle,
        )
        self.agents[entity_id] = agent
        self.all_entity_ids.append(entity_id)

        return agent

    def create_group(self, name: str, parent: str | None = None, moderators: list[str] = None) -> Entity:
        """Create a group with governance."""
        entity_id = generate_entity_id(name)

        governance = {
            "moderators": moderators or [],
            "rules_url": f"https://example.com/{name.lower()}/rules",
        }

        entity = Entity(
            id=entity_id,
            kind=EntityKind.GROUP,
            handle=name.lower().replace(" ", "-"),
            profile={
                "name": name,
                "description": f"A community for {name}",
            },
            parent=parent,
            governance=governance,
        )
        self.storage.create_entity(entity)
        self.all_entity_ids.append(entity_id)
        return entity

    def simulate_tick(self, current_time: datetime, tick_duration: timedelta):
        """Simulate one tick of agent activity."""
        # Reset daily counters
        for agent in self.agents.values():
            if current_time.date() != agent.last_activity_reset.date():
                agent.posts_today = 0
                agent.reactions_today = 0
                agent.follows_today = 0
                agent.searches_today = 0
                agent.last_activity_reset = current_time

        ticks_per_day = 86400 / tick_duration.total_seconds()

        for agent in self.agents.values():
            # Content creation
            if self._should_act(agent.config.posts_per_day, ticks_per_day):
                self._do_post(agent, current_time)
                agent.posts_today += 1

            # Reactions
            if self._should_act(agent.config.reactions_per_day, ticks_per_day):
                self._do_react(agent, current_time)
                agent.reactions_today += 1

            # Following
            if self._should_act(agent.config.follows_per_day, ticks_per_day):
                self._do_follow(agent, current_time)
                agent.follows_today += 1

            # Discovery/search
            if self._should_act(agent.config.search_per_day, ticks_per_day):
                self._do_search(agent, current_time)
                agent.searches_today += 1

            # Group joining
            if random.random() < agent.config.join_group_probability / ticks_per_day:
                self._do_join_group(agent, current_time)

            # Tipping
            if random.random() < agent.config.tip_probability / ticks_per_day:
                self._do_tip(agent, current_time)

            # Creator subscriptions
            if random.random() < agent.config.subscribe_probability / ticks_per_day:
                self._do_subscribe(agent, current_time)

            # View creation
            if random.random() < agent.config.create_view_probability / ticks_per_day:
                self._do_create_view(agent, current_time)

            # View subscription
            if random.random() < agent.config.subscribe_view_probability / ticks_per_day:
                self._do_subscribe_view(agent, current_time)

            # Verification
            if random.random() < agent.config.verification_probability / ticks_per_day:
                self._do_verify(agent, current_time)

            # Labeling (moderation)
            if random.random() < agent.config.label_probability / ticks_per_day:
                self._do_label(agent, current_time)

    def _should_act(self, rate_per_day: float, ticks_per_day: float) -> bool:
        probability = rate_per_day / ticks_per_day
        return random.random() < probability

    def _do_post(self, agent: Agent, current_time: datetime):
        """Agent creates content."""
        # Decide content type
        if random.random() < agent.config.article_probability:
            kind = ContentKind.ARTICLE
            body = {
                "title": f"Article by {agent.handle}",
                "body": self._generate_text(agent.config.spam_probability > 0, long=True),
            }
        else:
            kind = ContentKind.POST
            body = {
                "text": self._generate_text(agent.config.spam_probability > 0),
            }

        # Decide if reply
        reply_to = None
        thread_root = None
        if self.all_content_ids and random.random() < agent.config.reply_probability:
            reply_to = random.choice(self.all_content_ids)
            original = self.storage.get_content(reply_to)
            if original:
                thread_root = original.thread_root or reply_to

        # Decide access
        if random.random() < agent.config.paid_content_probability:
            access = AccessType.PAID
            price = random.choice([100, 500, 1000, 5000])
        else:
            access = AccessType.PUBLIC
            price = None

        # Choose context
        context = random.choice(agent.joined_groups) if agent.joined_groups else None

        content = Content(
            id=generate_content_id(),
            kind=kind,
            author=agent.entity_id,
            created=current_time,
            context=context,
            body=body,
            reply_to=reply_to,
            thread_root=thread_root,
            access=access,
            price=price,
        )
        self.storage.create_content(content)
        self.all_content_ids.append(content.id)

    def _do_react(self, agent: Agent, current_time: datetime):
        """Agent reacts to content."""
        if not self.all_content_ids:
            return

        target = random.choice(self.all_content_ids)
        emoji = random.choice(["❤️", "🔥", "👀", "👍", "😂", "🎉", "🚀", "💯"])

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.REACT,
            source=agent.entity_id,
            target=target,
            created=current_time,
            data={"emoji": emoji},
        )
        self.storage.create_link(link)

    def _do_follow(self, agent: Agent, current_time: datetime):
        """Agent follows another entity, using discovery."""
        # Use follow suggestions sometimes
        if random.random() < agent.config.use_follow_suggestions:
            suggestions = self.discovery.follows_of_follows(agent.entity_id, limit=10)
            if suggestions:
                target = random.choice(suggestions)
            else:
                target = self._random_entity_to_follow(agent)
        else:
            target = self._random_entity_to_follow(agent)

        if not target:
            return

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.FOLLOW,
            source=agent.entity_id,
            target=target,
            created=current_time,
        )
        self.storage.create_link(link)
        agent.following.append(target)

    def _random_entity_to_follow(self, agent: Agent) -> str | None:
        candidates = [
            e for e in self.all_entity_ids
            if e != agent.entity_id and e not in agent.following
        ]
        if not candidates:
            return None
        return random.choice(candidates)

    def _do_search(self, agent: Agent, current_time: datetime):
        """Agent uses search/discovery."""
        topics = ["programming", "rust", "python", "ai", "web", "design"]
        query = random.choice(topics)
        results = self.discovery.search(query, limit=10)

        # Maybe follow someone from results
        entity_results = [r for r in results if r["type"] == "entity"]
        if entity_results and random.random() < 0.2:
            target = random.choice(entity_results)["id"]
            if target not in agent.following and target != agent.entity_id:
                link = Link(
                    id=generate_link_id(),
                    kind=LinkKind.FOLLOW,
                    source=agent.entity_id,
                    target=target,
                    created=current_time,
                )
                self.storage.create_link(link)
                agent.following.append(target)

    def _do_join_group(self, agent: Agent, current_time: datetime):
        """Agent joins a group."""
        groups = [
            e for e in self.all_entity_ids
            if self.storage.get_entity(e) and
            self.storage.get_entity(e).kind == EntityKind.GROUP and
            e not in agent.joined_groups
        ]
        if not groups:
            return

        # Use suggested groups or random
        if random.random() < 0.5:
            suggested = self.discovery.suggested_contexts(agent.entity_id, limit=5)
            if suggested:
                group = random.choice(suggested)
            else:
                group = random.choice(groups)
        else:
            group = random.choice(groups)

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.MEMBER,
            source=agent.entity_id,
            target=group,
            created=current_time,
            data={"role": "member"},
        )
        self.storage.create_link(link)
        agent.joined_groups.append(group)

    def _do_tip(self, agent: Agent, current_time: datetime):
        """Agent tips content."""
        if not self.all_content_ids:
            return

        target = random.choice(self.all_content_ids)
        amount = random.choice([100, 500, 1000])

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.TIP,
            source=agent.entity_id,
            target=target,
            created=current_time,
            data={"amount_sats": amount},
        )
        self.storage.create_link(link)

    def _do_subscribe(self, agent: Agent, current_time: datetime):
        """Agent subscribes to a creator."""
        creators = [
            a for a in self.agents.values()
            if a.agent_type == AgentType.CREATOR and
            a.entity_id not in agent.subscribed_to and
            a.entity_id != agent.entity_id
        ]
        if not creators:
            return

        target = random.choice(creators)

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.SUBSCRIBE,
            source=agent.entity_id,
            target=target.entity_id,
            created=current_time,
            data={"tier": "supporter"},
        )
        self.storage.create_link(link)
        agent.subscribed_to.append(target.entity_id)

    def _do_create_view(self, agent: Agent, current_time: datetime):
        """Agent (curator) creates a view."""
        view_types = [
            {
                "name": f"Best of {random.choice(['AI', 'Rust', 'Web', 'Design'])}",
                "source": {"type": "all"},
                "filter": [{"field": "kind", "op": "eq", "value": "post"}],
                "rank": {"formula": "reactions * 2 + replies"},
            },
            {
                "name": f"Hot in {random.choice(agent.joined_groups) if agent.joined_groups else 'General'}",
                "source": {"context": random.choice(agent.joined_groups) if agent.joined_groups else None},
                "filter": [{"field": "created", "op": "gt", "value": "-24h"}],
                "rank": {"formula": "reactions / decay(age_hours, 3)"},
            },
            {
                "name": "Quality Long-form",
                "source": {"type": "all"},
                "filter": [{"field": "kind", "op": "eq", "value": "article"}],
                "rank": {"formula": "reactions + replies * 3"},
            },
        ]

        template = random.choice(view_types)
        view = View(
            id=generate_view_id(f"{agent.handle}-{len(agent.created_views)}"),
            author=agent.entity_id,
            name=template["name"],
            source=template["source"],
            filter=template["filter"],
            rank=template["rank"],
            limit=50,
        )
        self.storage.create_view(view)
        agent.created_views.append(view.id)
        self.all_view_ids.append(view.id)

    def _do_subscribe_view(self, agent: Agent, current_time: datetime):
        """Agent subscribes to a view."""
        available = [
            v for v in self.all_view_ids
            if v not in agent.subscribed_views
        ]
        if not available:
            return

        view_id = random.choice(available)

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.SUBSCRIBE,
            source=agent.entity_id,
            target=view_id,
            created=current_time,
        )
        self.storage.create_link(link)
        agent.subscribed_views.append(view_id)

    def _do_verify(self, agent: Agent, current_time: datetime):
        """Agent verifies external identity."""
        platforms = ["dns", "twitter", "github", "mastodon"]
        platform = random.choice([p for p in platforms if p not in agent.verified_externals])

        if platform in agent.verified_externals:
            return

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.VERIFY,
            source=agent.entity_id,
            target=f"{platform}:{agent.handle}",
            created=current_time,
            data={"proof": f"https://{platform}.com/{agent.handle}/verification"},
        )
        self.storage.create_link(link)
        agent.verified_externals.append(platform)

    def _do_label(self, agent: Agent, current_time: datetime):
        """Agent (moderator) labels content."""
        if not self.all_content_ids:
            return

        target_id = random.choice(self.all_content_ids)
        content = self.storage.get_content(target_id)
        if not content:
            return

        # Detect spam
        is_spam = "SPAM" in content.body.get("text", "").upper() or \
                  "BUY NOW" in content.body.get("text", "").upper()

        if is_spam:
            labels = ["spam"]
        else:
            labels = random.choice([["quality"], ["off-topic"], ["nsfw"], []])

        if not labels:
            return

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.LABEL,
            source=agent.entity_id,
            target=target_id,
            created=current_time,
            data={
                "labels": labels,
                "confidence": random.uniform(0.7, 1.0),
            },
        )
        self.storage.create_link(link)

    def _generate_text(self, is_spam: bool, long: bool = False) -> str:
        if is_spam:
            return "🚨 BUY NOW! Limited offer! Click here: http://spam.example.com 🚨"

        templates = [
            "Just discovered something interesting about {topic}.",
            "Anyone have thoughts on {topic}?",
            "Working on a project related to {topic}.",
            "Great discussion about {topic} today!",
            "Learning more about {topic} every day.",
            "Here's my take on {topic}...",
            "Exploring new ideas in {topic}.",
            "Can't stop thinking about {topic}.",
        ]
        topics = ["Rust", "Python", "AI", "web development", "distributed systems",
                  "cryptography", "design", "startups", "open source"]

        text = random.choice(templates).format(topic=random.choice(topics))

        if long:
            paragraphs = [text]
            for _ in range(random.randint(2, 5)):
                paragraphs.append(random.choice(templates).format(topic=random.choice(topics)))
            text = "\n\n".join(paragraphs)

        return text

    def get_agent_stats(self) -> dict:
        by_type = {}
        for agent in self.agents.values():
            t = agent.agent_type.value
            by_type[t] = by_type.get(t, 0) + 1

        total_subscriptions = sum(len(a.subscribed_to) for a in self.agents.values())
        total_view_subs = sum(len(a.subscribed_views) for a in self.agents.values())
        total_verifications = sum(len(a.verified_externals) for a in self.agents.values())

        return {
            "total_agents": len(self.agents),
            "by_type": by_type,
            "total_content": len(self.all_content_ids),
            "total_follows": sum(len(a.following) for a in self.agents.values()),
            "total_group_memberships": sum(len(a.joined_groups) for a in self.agents.values()),
            "total_creator_subscriptions": total_subscriptions,
            "total_view_subscriptions": total_view_subs,
            "total_verifications": total_verifications,
            "total_views_created": len(self.all_view_ids),
        }
