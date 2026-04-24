"""
Relay 2.0 Simulator - Agent System

Actors that interact with the relay via Events, States, and Attestations.
"""

import random
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from core import (
    Identity, Event, EventType, State, StateType, Attestation, ClaimCategory,
    ViewDefinition, ReducerType, RelayStorage,
    generate_actor_id, generate_event_id, generate_state_id,
    generate_attestation_id, generate_view_id
)


class ActorType(Enum):
    USER = "user"
    AGENT = "agent"  # AI/bot agents
    CURATOR = "curator"  # Creates feeds
    INDEXER = "indexer"  # Aggregates/indexes
    MODERATOR = "moderator"


@dataclass
class ActorConfig:
    # Event rates
    posts_per_day: float = 1.0
    follows_per_day: float = 0.5
    reactions_per_day: float = 5.0
    
    # State updates
    profile_updates_per_week: float = 0.5
    
    # Actions (for agents)
    action_requests_per_day: float = 0.0
    action_commits_per_day: float = 0.0
    
    # Attestations
    attestations_per_day: float = 0.0
    
    # Views
    view_creates_per_day: float = 0.0
    view_subscribes_per_day: float = 0.1


ACTOR_CONFIGS = {
    ActorType.USER: ActorConfig(
        posts_per_day=1.0,
        follows_per_day=0.5,
        reactions_per_day=5.0,
    ),
    ActorType.AGENT: ActorConfig(
        posts_per_day=0.5,
        action_requests_per_day=2.0,
        action_commits_per_day=2.0,
    ),
    ActorType.CURATOR: ActorConfig(
        posts_per_day=0.5,
        follows_per_day=2.0,
        reactions_per_day=10.0,
        view_creates_per_day=0.5,
    ),
    ActorType.INDEXER: ActorConfig(
        attestations_per_day=10.0,
    ),
    ActorType.MODERATOR: ActorConfig(
        attestations_per_day=5.0,
    ),
}


@dataclass
class Actor:
    """A simulated actor."""
    identity: Identity
    actor_type: ActorType
    config: ActorConfig
    name: str
    
    # State
    following: list[str] = field(default_factory=list)
    created_views: list[str] = field(default_factory=list)
    subscribed_views: list[str] = field(default_factory=list)
    
    # Tracking
    events_today: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

    @property
    def actor_id(self) -> str:
        return self.identity.id


class ActorManager:
    """Manages all actors in the simulation."""

    def __init__(self, storage: RelayStorage):
        self.storage = storage
        self.actors: dict[str, Actor] = {}
        self.all_event_ids: list[str] = []
        self.all_view_ids: list[str] = []

    def create_actor(self, name: str, actor_type: ActorType) -> Actor:
        """Create a new actor with identity."""
        # Generate keys (simulated)
        public_key = os.urandom(32)
        actor_id = Identity.generate_actor_id(public_key)
        
        identity = Identity(
            id=actor_id,
            public_key=public_key,
            created_at=datetime.now(),
        )
        self.storage.create_identity(identity)
        
        # Create profile state
        profile = State(
            id=generate_state_id(actor_id, "profile"),
            actor=actor_id,
            type=StateType.PROFILE,
            version=1,
            payload={
                "name": name.replace("_", " ").title(),
                "bio": f"A {actor_type.value} on the relay",
            },
        )
        self.storage.put_state(profile)
        
        config = ACTOR_CONFIGS[actor_type]
        actor = Actor(
            identity=identity,
            actor_type=actor_type,
            config=config,
            name=name,
        )
        self.actors[actor_id] = actor
        
        return actor

    def simulate_tick(self, current_time: datetime, tick_duration: timedelta):
        """Simulate one tick of actor activity."""
        # Reset daily counters
        for actor in self.actors.values():
            if current_time.date() != actor.last_reset.date():
                actor.events_today = 0
                actor.last_reset = current_time
        
        ticks_per_day = 86400 / tick_duration.total_seconds()
        
        for actor in self.actors.values():
            # Posts
            if self._should_act(actor.config.posts_per_day, ticks_per_day):
                self._do_post(actor, current_time)
            
            # Follows
            if self._should_act(actor.config.follows_per_day, ticks_per_day):
                self._do_follow(actor, current_time)
            
            # Reactions
            if self._should_act(actor.config.reactions_per_day, ticks_per_day):
                self._do_reaction(actor, current_time)
            
            # Action requests (agents)
            if self._should_act(actor.config.action_requests_per_day, ticks_per_day):
                self._do_action_request(actor, current_time)
            
            # Attestations (indexers, moderators)
            if self._should_act(actor.config.attestations_per_day, ticks_per_day):
                self._do_attestation(actor, current_time)
            
            # View creation (curators)
            if self._should_act(actor.config.view_creates_per_day, ticks_per_day):
                self._do_create_view(actor, current_time)
            
            # View subscription
            if self._should_act(actor.config.view_subscribes_per_day, ticks_per_day):
                self._do_subscribe_view(actor, current_time)

    def _should_act(self, rate_per_day: float, ticks_per_day: float) -> bool:
        probability = rate_per_day / ticks_per_day
        return random.random() < probability

    def _get_prev(self, actor: Actor) -> list[str]:
        """Get parent event(s) for new event."""
        head = self.storage.get_actor_head(actor.actor_id)
        return [head] if head else []

    def _do_post(self, actor: Actor, current_time: datetime):
        """Actor creates a post event."""
        topics = ["programming", "ai", "design", "music", "travel"]
        
        event = Event(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=EventType.POST,
            data={
                "text": f"Thoughts on {random.choice(topics)}...",
                "created_at": current_time.isoformat(),
            },
            parents=self._get_prev(actor),
            timestamp=current_time,
        )
        self.storage.append_event(event)
        self.all_event_ids.append(event.id)

    def _do_follow(self, actor: Actor, current_time: datetime):
        """Actor follows another actor."""
        candidates = [
            a for a in self.actors.values()
            if a.actor_id != actor.actor_id and a.actor_id not in actor.following
        ]
        if not candidates:
            return
        
        target = random.choice(candidates)
        
        event = Event(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=EventType.FOLLOW_ADD,
            data={},
            parents=self._get_prev(actor),
            timestamp=current_time,
            target=target.actor_id,
        )
        self.storage.append_event(event)
        actor.following.append(target.actor_id)

    def _do_reaction(self, actor: Actor, current_time: datetime):
        """Actor reacts to an event."""
        if not self.all_event_ids:
            return
        
        target_id = random.choice(self.all_event_ids)
        
        event = Event(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=EventType.REACTION,
            data={
                "emoji": random.choice(["👍", "❤️", "🔥", "🎉", "💯"]),
            },
            parents=self._get_prev(actor),
            timestamp=current_time,
            target=target_id,
        )
        self.storage.append_event(event)

    def _do_action_request(self, actor: Actor, current_time: datetime):
        """Actor (agent) requests an action."""
        if not self.all_event_ids:
            return
        
        # Find another agent to handle the request
        agents = [a for a in self.actors.values() if a.actor_type == ActorType.AGENT and a.actor_id != actor.actor_id]
        if not agents:
            return
        
        target_agent = random.choice(agents)
        
        event = Event(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=EventType.ACTION_REQUEST,
            data={
                "action_id": "relay.basic.summarize.v1",
                "action": "Summarize",
                "input_refs": [random.choice(self.all_event_ids)],
            },
            parents=self._get_prev(actor),
            timestamp=current_time,
            target=target_agent.actor_id,
        )
        self.storage.append_event(event)
        self.all_event_ids.append(event.id)

    def _do_attestation(self, actor: Actor, current_time: datetime):
        """Actor creates an attestation."""
        if not self.all_event_ids:
            return
        
        target_id = random.choice(self.all_event_ids)
        
        # Different attestation types based on actor type
        if actor.actor_type == ActorType.MODERATOR:
            claim = {
                "category": ClaimCategory.CONTENT.value,
                "type": random.choice(["label.quality", "label.spam", "label.nsfw"]),
                "confidence": random.uniform(0.7, 1.0),
            }
        else:  # Indexer
            claim = {
                "category": ClaimCategory.VIEW.value,
                "type": "indexed",
                "indexed_at": current_time.isoformat(),
            }
        
        attestation = Attestation(
            id=generate_attestation_id(),
            actor=actor.actor_id,
            claim=claim,
            target=target_id,
            created_at=current_time,
        )
        self.storage.create_attestation(attestation)

    def _do_create_view(self, actor: Actor, current_time: datetime):
        """Actor (curator) creates a view definition."""
        # Pick some actors to include in the feed
        source_actors = random.sample(
            list(self.actors.keys()),
            min(5, len(self.actors))
        )
        
        view_def = ViewDefinition(
            id=generate_view_id(f"{actor.name}-feed-{len(actor.created_views)}"),
            actor=actor.actor_id,
            version=1,
            sources=[
                {"kind": "actor_log", "actor_id": aid}
                for aid in source_actors
            ],
            reduce=random.choice([ReducerType.CHRONOLOGICAL, ReducerType.REVERSE_CHRONOLOGICAL]),
            params={},
            created_at=current_time,
            updated_at=current_time,
        )
        self.storage.put_view_definition(view_def)
        actor.created_views.append(view_def.id)
        self.all_view_ids.append(view_def.id)

    def _do_subscribe_view(self, actor: Actor, current_time: datetime):
        """Actor subscribes to a view."""
        available = [v for v in self.all_view_ids if v not in actor.subscribed_views]
        if not available:
            return
        
        view_id = random.choice(available)
        actor.subscribed_views.append(view_id)
        
        # Record subscription as attestation
        attestation = Attestation(
            id=generate_attestation_id(),
            actor=actor.actor_id,
            claim={
                "category": ClaimCategory.VIEW.value,
                "type": "subscribed",
                "subscribed_at": current_time.isoformat(),
            },
            target=view_id,
            created_at=current_time,
        )
        self.storage.create_attestation(attestation)

    def get_stats(self) -> dict:
        by_type = {}
        for actor in self.actors.values():
            t = actor.actor_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        return {
            "total_actors": len(self.actors),
            "by_type": by_type,
            "total_events": len(self.all_event_ids),
            "total_follows": sum(len(a.following) for a in self.actors.values()),
            "total_views": len(self.all_view_ids),
            "total_view_subscriptions": sum(len(a.subscribed_views) for a in self.actors.values()),
        }
