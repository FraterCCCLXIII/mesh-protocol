"""
HOLON Protocol Simulator - Agent System

Defines user agents with configurable behaviors for simulation.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from core import (
    Content, ContentKind, Entity, EntityKind, Link, LinkKind,
    Storage, generate_content_id, generate_entity_id, generate_link_id
)


class AgentType(Enum):
    """Types of user agents with different behavior profiles."""
    LURKER = "lurker"           # Mostly reads, rarely posts
    CASUAL = "casual"           # Average activity
    ACTIVE = "active"           # High engagement
    POWER_USER = "power_user"   # Very high activity, creates content
    SPAMMER = "spammer"         # Malicious actor
    MODERATOR = "moderator"     # Moderates content


@dataclass
class AgentConfig:
    """Configuration for agent behavior."""
    posts_per_day: float = 1.0
    reactions_per_day: float = 5.0
    follows_per_day: float = 0.5
    reply_probability: float = 0.3
    join_group_probability: float = 0.1
    unfollow_probability: float = 0.01
    spam_probability: float = 0.0
    label_probability: float = 0.0  # For moderators


# Default configs for each agent type
AGENT_CONFIGS = {
    AgentType.LURKER: AgentConfig(
        posts_per_day=0.1,
        reactions_per_day=2.0,
        follows_per_day=0.2,
        reply_probability=0.05,
    ),
    AgentType.CASUAL: AgentConfig(
        posts_per_day=0.5,
        reactions_per_day=5.0,
        follows_per_day=0.3,
        reply_probability=0.2,
    ),
    AgentType.ACTIVE: AgentConfig(
        posts_per_day=2.0,
        reactions_per_day=15.0,
        follows_per_day=1.0,
        reply_probability=0.4,
    ),
    AgentType.POWER_USER: AgentConfig(
        posts_per_day=5.0,
        reactions_per_day=30.0,
        follows_per_day=2.0,
        reply_probability=0.5,
        join_group_probability=0.3,
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
        label_probability=0.3,
    ),
}


@dataclass
class Agent:
    """A simulated user agent."""
    entity_id: str
    agent_type: AgentType
    config: AgentConfig
    joined_groups: list[str] = field(default_factory=list)
    following: list[str] = field(default_factory=list)

    # Activity tracking
    posts_today: int = 0
    reactions_today: int = 0
    follows_today: int = 0
    last_activity_reset: datetime = field(default_factory=datetime.utcnow)


class AgentManager:
    """Manages all agents in the simulation."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self.agents: dict[str, Agent] = {}
        self.all_content_ids: list[str] = []  # Track for reactions
        self.all_entity_ids: list[str] = []  # Track for follows

    def create_agent(self, name: str, agent_type: AgentType) -> Agent:
        """Create a new agent with an entity."""
        entity_id = generate_entity_id(name)

        # Create entity in storage
        entity = Entity(
            id=entity_id,
            kind=EntityKind.USER,
            data={"name": name, "agent_type": agent_type.value}
        )
        self.storage.create_entity(entity)

        # Create agent
        config = AGENT_CONFIGS[agent_type]
        agent = Agent(
            entity_id=entity_id,
            agent_type=agent_type,
            config=config,
        )
        self.agents[entity_id] = agent
        self.all_entity_ids.append(entity_id)

        return agent

    def create_group(self, name: str, parent: str | None = None) -> Entity:
        """Create a group holon."""
        entity_id = generate_entity_id(name)
        entity = Entity(
            id=entity_id,
            kind=EntityKind.GROUP,
            data={
                "name": name,
                "visibility": "public",
                "join_policy": "open",
                "posting_policy": "members",
            },
            parent=parent,
        )
        self.storage.create_entity(entity)
        self.all_entity_ids.append(entity_id)
        return entity

    def simulate_tick(self, current_time: datetime, tick_duration: timedelta):
        """Simulate one tick of agent activity."""
        # Reset daily counters if needed
        for agent in self.agents.values():
            if current_time.date() != agent.last_activity_reset.date():
                agent.posts_today = 0
                agent.reactions_today = 0
                agent.follows_today = 0
                agent.last_activity_reset = current_time

        # Calculate action probabilities for this tick
        ticks_per_day = 86400 / tick_duration.total_seconds()

        for agent in self.agents.values():
            # Post
            if self._should_act(agent.config.posts_per_day, ticks_per_day, agent.posts_today):
                self._do_post(agent, current_time)
                agent.posts_today += 1

            # React
            if self._should_act(agent.config.reactions_per_day, ticks_per_day, agent.reactions_today):
                self._do_react(agent, current_time)
                agent.reactions_today += 1

            # Follow
            if self._should_act(agent.config.follows_per_day, ticks_per_day, agent.follows_today):
                self._do_follow(agent, current_time)
                agent.follows_today += 1

            # Join group
            if random.random() < agent.config.join_group_probability / ticks_per_day:
                self._do_join_group(agent, current_time)

            # Label (for moderators)
            if random.random() < agent.config.label_probability / ticks_per_day:
                self._do_label(agent, current_time)

    def _should_act(self, rate_per_day: float, ticks_per_day: float, done_today: int) -> bool:
        """Determine if an action should occur this tick."""
        probability = rate_per_day / ticks_per_day
        return random.random() < probability

    def _do_post(self, agent: Agent, current_time: datetime):
        """Agent creates a post."""
        # Decide if reply or new post
        reply_to = None
        thread_root = None
        if self.all_content_ids and random.random() < agent.config.reply_probability:
            reply_to = random.choice(self.all_content_ids)
            original = self.storage.get_content(reply_to)
            thread_root = original.thread_root or reply_to if original else reply_to

        # Choose context (group)
        context = None
        if agent.joined_groups:
            context = random.choice(agent.joined_groups)

        # Generate content
        is_spam = random.random() < agent.config.spam_probability
        text = self._generate_text(is_spam)

        content_id = generate_content_id(agent.entity_id, "post")
        content = Content(
            id=content_id,
            kind=ContentKind.POST,
            author=agent.entity_id,
            created=current_time,
            context=context,
            reply_to=reply_to,
            thread_root=thread_root,
            data={
                "text": text,
                "is_spam": is_spam,
            },
        )
        self.storage.create_content(content)
        self.all_content_ids.append(content_id)

    def _do_react(self, agent: Agent, current_time: datetime):
        """Agent reacts to content."""
        if not self.all_content_ids:
            return

        target = random.choice(self.all_content_ids)
        emoji = random.choice(["❤️", "🔥", "👀", "👍", "😂", "🎉"])

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.INTERACTION,
            source=agent.entity_id,
            target=target,
            created=current_time,
            data={"subkind": "react", "emoji": emoji},
        )
        self.storage.create_link(link)

    def _do_follow(self, agent: Agent, current_time: datetime):
        """Agent follows another entity."""
        # Find someone to follow (not already following, not self)
        candidates = [
            e for e in self.all_entity_ids
            if e != agent.entity_id and e not in agent.following
        ]
        if not candidates:
            return

        target = random.choice(candidates)

        # Maybe unfollow first?
        if agent.following and random.random() < agent.config.unfollow_probability:
            unfollow_target = random.choice(agent.following)
            unfollow_link = Link(
                id=generate_link_id(),
                kind=LinkKind.RELATIONSHIP,
                source=agent.entity_id,
                target=unfollow_target,
                created=current_time,
                data={"subkind": "follow", "tombstone": True},
                tombstone=True,
            )
            self.storage.create_link(unfollow_link)
            agent.following.remove(unfollow_target)

        # Follow
        link = Link(
            id=generate_link_id(),
            kind=LinkKind.RELATIONSHIP,
            source=agent.entity_id,
            target=target,
            created=current_time,
            data={"subkind": "follow"},
        )
        self.storage.create_link(link)
        agent.following.append(target)

    def _do_join_group(self, agent: Agent, current_time: datetime):
        """Agent joins a group."""
        # Find groups not already joined
        groups = [
            e for e in self.all_entity_ids
            if self.storage.get_entity(e) and
            self.storage.get_entity(e).kind == EntityKind.GROUP and
            e not in agent.joined_groups
        ]
        if not groups:
            return

        group = random.choice(groups)

        # Create membership link (simplified - no request/approval)
        link = Link(
            id=generate_link_id(),
            kind=LinkKind.CREDENTIAL,
            source=agent.entity_id,
            target=group,
            created=current_time,
            data={"subkind": "membership", "role": "member"},
        )
        self.storage.create_link(link)
        agent.joined_groups.append(group)

    def _do_label(self, agent: Agent, current_time: datetime):
        """Agent (moderator) labels content."""
        if not self.all_content_ids:
            return

        # Find recent unlabeled content
        target = random.choice(self.all_content_ids)
        content = self.storage.get_content(target)
        if not content:
            return

        # Label spam content
        if content.data.get("is_spam"):
            label = "spam"
            confidence = 0.9
        else:
            label = random.choice(["quality", "off-topic", "nsfw"])
            confidence = random.uniform(0.5, 0.9)

        link = Link(
            id=generate_link_id(),
            kind=LinkKind.INTERACTION,
            source=agent.entity_id,
            target=target,
            created=current_time,
            data={
                "subkind": "label",
                "labels": [{"name": label, "confidence": confidence}],
                "scope": content.context,
            },
        )
        self.storage.create_link(link)

    def _generate_text(self, is_spam: bool) -> str:
        """Generate random post text."""
        if is_spam:
            return "BUY NOW! Limited offer! Click here: http://spam.example.com"

        templates = [
            "Just discovered something interesting about {topic}.",
            "Anyone have thoughts on {topic}?",
            "Working on a project related to {topic}.",
            "Great discussion about {topic} today!",
            "Learning more about {topic} every day.",
            "Here's my take on {topic}...",
        ]
        topics = ["Rust", "Python", "AI", "web3", "programming", "design", "startups"]

        template = random.choice(templates)
        topic = random.choice(topics)
        return template.format(topic=topic)

    def get_agent_stats(self) -> dict:
        """Get statistics about agents."""
        by_type = {}
        for agent in self.agents.values():
            t = agent.agent_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_agents": len(self.agents),
            "by_type": by_type,
            "total_content": len(self.all_content_ids),
            "total_follows": sum(len(a.following) for a in self.agents.values()),
            "total_group_memberships": sum(len(a.joined_groups) for a in self.agents.values()),
        }
