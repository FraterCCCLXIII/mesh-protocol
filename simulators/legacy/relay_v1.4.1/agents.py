"""
Relay v1.4-1 Simulator - Agent System

Actors that interact with the relay via Log events and State objects.
Supports action.* flows (v1.4).
"""

import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from core import (
    Identity, LogEvent, LogEventType, StateObject, StateType,
    FeedDefinition, ReducerType, ChannelGenesis,
    RelayStorage, ActionVerifier, compute_commitment_hash,
    generate_actor_id, generate_event_id, generate_object_id
)


class ActorType(Enum):
    USER = "user"
    AGENT = "agent"  # AI/bot agents that handle action.*
    CURATOR = "curator"  # Creates feed definitions
    CHANNEL_OWNER = "channel_owner"


@dataclass
class ActorConfig:
    # Log event rates
    posts_per_day: float = 1.0
    follows_per_day: float = 0.5
    reactions_per_day: float = 5.0
    
    # State updates
    profile_updates_per_week: float = 0.5
    
    # Action flows (v1.4)
    action_requests_per_day: float = 0.0
    
    # Feed definitions
    feed_creates_per_day: float = 0.0
    
    # Channel activity
    channel_creates_per_week: float = 0.0
    memberships_per_day: float = 0.0


ACTOR_CONFIGS = {
    ActorType.USER: ActorConfig(
        posts_per_day=1.0,
        follows_per_day=0.5,
        reactions_per_day=5.0,
        memberships_per_day=0.1,
    ),
    ActorType.AGENT: ActorConfig(
        posts_per_day=0.5,
        action_requests_per_day=0.0,  # Agents receive requests, not create them
    ),
    ActorType.CURATOR: ActorConfig(
        posts_per_day=0.5,
        follows_per_day=2.0,
        feed_creates_per_day=0.3,
    ),
    ActorType.CHANNEL_OWNER: ActorConfig(
        posts_per_day=0.5,
        channel_creates_per_week=0.5,
        memberships_per_day=0.2,
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
    channels_owned: list[str] = field(default_factory=list)
    channels_joined: list[str] = field(default_factory=list)
    feeds_created: list[str] = field(default_factory=list)
    pending_action_requests: list[str] = field(default_factory=list)
    
    # Tracking
    events_today: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

    @property
    def actor_id(self) -> str:
        return self.identity.actor_id


class ActorManager:
    """Manages all actors in the simulation."""

    def __init__(self, storage: RelayStorage):
        self.storage = storage
        self.actors: dict[str, Actor] = {}
        self.agents: dict[str, Actor] = {}  # Subset that are agents
        self.all_event_ids: list[str] = []
        self.action_verifier = ActionVerifier(storage)

    def create_actor(self, name: str, actor_type: ActorType) -> Actor:
        """Create a new actor with identity."""
        # Generate keys (simulated)
        public_key = os.urandom(32)
        actor_id = generate_actor_id(public_key)
        
        identity = Identity(
            actor_id=actor_id,
            public_key=public_key,
            display_name=name.replace("_", " ").title(),
            bio=f"A {actor_type.value} on the relay",
            origins={
                "log": [f"{self.storage.origin_url}/actors/{actor_id}/log/"],
                "state": [f"{self.storage.origin_url}/actors/{actor_id}/state/"],
            },
        )
        self.storage.put_identity(identity)
        
        # Create profile state
        profile = StateObject(
            object_id=generate_object_id(),
            actor=actor_id,
            type=StateType.PROFILE,
            version=1,
            payload={
                "display_name": identity.display_name,
                "bio": identity.bio,
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
        
        if actor_type == ActorType.AGENT:
            self.agents[actor_id] = actor
        
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
            
            # Action requests (users request from agents)
            if (actor.actor_type == ActorType.USER and 
                self._should_act(1.0, ticks_per_day) and  # 1 per day
                self.agents):
                self._do_action_request(actor, current_time)
            
            # Process pending action requests (agents)
            if actor.actor_type == ActorType.AGENT:
                self._process_action_requests(actor, current_time)
            
            # Feed creation (curators)
            if self._should_act(actor.config.feed_creates_per_day, ticks_per_day):
                self._do_create_feed(actor, current_time)
            
            # Channel creation
            if self._should_act(actor.config.channel_creates_per_week / 7, ticks_per_day):
                self._do_create_channel(actor, current_time)
            
            # Join channels
            if self._should_act(actor.config.memberships_per_day, ticks_per_day):
                self._do_join_channel(actor, current_time)

    def _should_act(self, rate_per_day: float, ticks_per_day: float) -> bool:
        if rate_per_day <= 0:
            return False
        probability = rate_per_day / ticks_per_day
        return random.random() < probability

    def _get_prev(self, actor: Actor) -> str | None:
        """Get prev event for chain."""
        return self.storage.get_log_head(actor.actor_id)

    def _do_post(self, actor: Actor, current_time: datetime):
        """Actor creates a post event."""
        topics = ["programming", "ai", "design", "music", "travel", "food"]
        
        event = LogEvent(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=LogEventType.POST,
            data={
                "text": f"Thoughts on {random.choice(topics)}...",
                "created_at": current_time.isoformat() + "Z",
            },
            ts=current_time,
            prev=self._get_prev(actor),
        )
        self.storage.append_log(event)
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
        
        event = LogEvent(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=LogEventType.FOLLOW_ADD,
            data={},
            ts=current_time,
            prev=self._get_prev(actor),
            target=target.actor_id,
        )
        self.storage.append_log(event)
        actor.following.append(target.actor_id)

    def _do_reaction(self, actor: Actor, current_time: datetime):
        """Actor reacts to an event."""
        if not self.all_event_ids:
            return
        
        target_id = random.choice(self.all_event_ids)
        
        event = LogEvent(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=LogEventType.REACTION,
            data={
                "emoji": random.choice(["👍", "❤️", "🔥", "🎉", "💯"]),
                "target_event_id": target_id,
            },
            ts=current_time,
            prev=self._get_prev(actor),
            target=target_id,
        )
        self.storage.append_log(event)

    def _do_action_request(self, actor: Actor, current_time: datetime):
        """Actor requests an action from an agent (§13.4)."""
        if not self.all_event_ids or not self.agents:
            return
        
        agent = random.choice(list(self.agents.values()))
        input_ref = random.choice(self.all_event_ids)
        
        action_ids = [
            "relay.basic.summarize.v1",
            "relay.basic.translate.v1",
            "relay.basic.analyze.v1",
        ]
        
        event = LogEvent(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=LogEventType.ACTION_REQUEST,
            data={
                "action_id": random.choice(action_ids),
                "action": "Summarize",
                "input_refs": [input_ref],
            },
            ts=current_time,
            prev=self._get_prev(actor),
            target=agent.actor_id,
        )
        self.storage.append_log(event)
        self.all_event_ids.append(event.id)
        
        # Add to agent's pending requests
        agent.pending_action_requests.append(event.id)

    def _process_action_requests(self, agent: Actor, current_time: datetime):
        """Agent processes pending action requests (§13.4)."""
        if not agent.pending_action_requests:
            return
        
        # Process one request at a time
        request_id = agent.pending_action_requests.pop(0)
        request_event = self.storage.get_event(request_id)
        if not request_event:
            return
        
        # Create action.commit
        agent_params = {"max_words": random.choice([50, 100, 150])}
        commitment_hash = compute_commitment_hash(
            request_event_id=request_id,
            action_id=request_event.data.get("action_id", ""),
            input_refs=request_event.data.get("input_refs", []),
            agent_params=agent_params,
        )
        
        commit_event = LogEvent(
            id=generate_event_id(),
            actor=agent.actor_id,
            type=LogEventType.ACTION_COMMIT,
            data={
                "request_event_id": request_id,
                "commitment_hash": commitment_hash,
                "agent_params": agent_params,
            },
            ts=current_time,
            prev=self._get_prev(agent),
        )
        self.storage.append_log(commit_event)
        
        # Create output (a post with the "summary")
        output_event = LogEvent(
            id=generate_event_id(),
            actor=agent.actor_id,
            type=LogEventType.POST,
            data={
                "text": "Here is the summary you requested...",
                "is_action_output": True,
            },
            ts=current_time + timedelta(milliseconds=1),
            prev=commit_event.id,
        )
        self.storage.append_log(output_event)
        self.all_event_ids.append(output_event.id)
        
        # Create action.result
        result_event = LogEvent(
            id=generate_event_id(),
            actor=agent.actor_id,
            type=LogEventType.ACTION_RESULT,
            data={
                "commitment_hash": commitment_hash,
                "output_refs": [output_event.id],
            },
            ts=current_time + timedelta(milliseconds=2),
            prev=output_event.id,
        )
        self.storage.append_log(result_event)
        self.all_event_ids.append(result_event.id)

    def _do_create_feed(self, actor: Actor, current_time: datetime):
        """Actor (curator) creates a feed definition (§11.1)."""
        # Pick some actors to include
        source_actors = random.sample(
            list(self.actors.keys()),
            min(5, len(self.actors))
        )
        
        feed_def = FeedDefinition(
            object_id=generate_object_id(),
            actor=actor.actor_id,
            version=1,
            sources=[
                {"kind": "actor_log", "actor_id": aid}
                for aid in source_actors
            ],
            reduce=random.choice([ReducerType.CHRONOLOGICAL, ReducerType.REVERSE_CHRONOLOGICAL]),
            params={"limit": 100},
            created_at=current_time,
            updated_at=current_time,
        )
        self.storage.put_feed_definition(feed_def)
        actor.feeds_created.append(feed_def.object_id)

    def _do_create_channel(self, actor: Actor, current_time: datetime):
        """Actor creates a channel (§4.3.1, §13)."""
        channel_names = ["general", "tech", "random", "announcements", "help"]
        
        genesis = ChannelGenesis(
            owner_actor_id=actor.actor_id,
            name=f"{random.choice(channel_names)}_{len(actor.channels_owned)}",
            created_at=current_time,
        )
        
        channel = self.storage.create_channel(genesis)
        actor.channels_owned.append(channel.channel_id)
        actor.channels_joined.append(channel.channel_id)
        
        # Log membership.add event
        event = LogEvent(
            id=generate_event_id(),
            actor=actor.actor_id,
            type=LogEventType.MEMBERSHIP_ADD,
            data={
                "channel_id": channel.channel_id,
                "role": "owner",
            },
            ts=current_time,
            prev=self._get_prev(actor),
            target=channel.channel_id,
        )
        self.storage.append_log(event)

    def _do_join_channel(self, actor: Actor, current_time: datetime):
        """Actor joins a channel."""
        available = [
            cid for cid in self.storage.channels.keys()
            if cid not in actor.channels_joined
        ]
        if not available:
            return
        
        channel_id = random.choice(available)
        
        if self.storage.add_member(channel_id, actor.actor_id):
            actor.channels_joined.append(channel_id)
            
            event = LogEvent(
                id=generate_event_id(),
                actor=actor.actor_id,
                type=LogEventType.MEMBERSHIP_ADD,
                data={
                    "channel_id": channel_id,
                    "role": "member",
                },
                ts=current_time,
                prev=self._get_prev(actor),
                target=channel_id,
            )
            self.storage.append_log(event)

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
            "total_feeds": sum(len(a.feeds_created) for a in self.actors.values()),
            "total_channels": len(self.storage.channels),
            "total_memberships": sum(len(a.channels_joined) for a in self.actors.values()),
        }
