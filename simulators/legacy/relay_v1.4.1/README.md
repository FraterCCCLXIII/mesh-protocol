# Relay v1.4-1 / v1.5 Simulator

A simulation framework for testing the Relay v1.4-1 wire protocol.

## What This Tests

Based on `Relay_v1.4.1.md`:

- **Identity (§8)** with `actor_id = relay:actor: + multihash(SHA-256(pubkey))`
- **Log events (§10)** with `prev` chain
- **State objects (§11)** with version increment
- **Channels (§13)** with `channel_id` from genesis (§4.3.1)
- **Feed definitions (§11.1)** with reducers (§17.10) — v1.4 feature
- **Action events (§13.4)**: request → commit → result — v1.4 feature

## Quick Start

```bash
cd simulator_relay_v1.4.1

# List scenarios
python run_simulation.py --list

# Run simulation
python run_simulation.py --scenario small --seed 42
```

## Wire Protocol (Part I)

### Identifiers (§4.2, §4.3)

```python
actor_id = "relay:actor:" + multihash(SHA-256(public_key))
channel_id = "relay:channel:" + multihash(SHA-256(canonical_json(genesis)))
```

### Log Events (§10)

```json
{
  "id": "relay:event:...",
  "actor": "relay:actor:...",
  "type": "post",
  "data": {...},
  "ts": "2026-04-24T00:00:00Z",
  "prev": "relay:event:...",
  "sig": "base64..."
}
```

Event types:
- MVP (Appendix B): `follow.add`, `follow.remove`, `state.commit`, `state.delete`, `key.rotate`
- v1.3 (Appendix C): `membership.add`, `membership.remove`, `trust.revoke`, `state.revoke`
- v1.4 (§13.4): `action.request`, `action.commit`, `action.result`

### State Objects (§11)

```json
{
  "object_id": "relay:obj:...",
  "actor": "relay:actor:...",
  "type": "relay.profile.v1",
  "version": 1,
  "payload": {...},
  "created_at": "2026-04-24T00:00:00Z",
  "updated_at": "2026-04-24T00:00:00Z"
}
```

Version MUST increment on each update.

### Feed Definitions (§11.1, v1.4)

```json
{
  "type": "relay.feed.definition.v1",
  "sources": [
    {"kind": "actor_log", "actor_id": "relay:actor:..."}
  ],
  "reduce": "relay.reduce.chronological.v1",
  "params": {"limit": 100}
}
```

Required reducers (§17.10):
- `relay.reduce.chronological.v1` — Sort by (ts, event_id)
- `relay.reduce.reverse_chronological.v1`

### Action Events (§13.4, v1.4)

```
action.request → action.commit → action.result
```

The `commitment_hash` binds request to commit:
```python
commitment_hash = SHA256(canonical_json({
  "kind": "relay.action.commitment.v1",
  "request_event_id": "...",
  "action_id": "relay.basic.summarize.v1",
  "input_refs": [...],
  "agent_params": {...}
}))
```

## Actor Types

| Type | Behavior |
|------|----------|
| USER | Posts, follows, reactions, action requests |
| AGENT | Handles action.* flows |
| CURATOR | Creates feed definitions |
| CHANNEL_OWNER | Creates channels |

## Scenarios

| Scenario | Actors | Focus |
|----------|--------|-------|
| small | 100 | Basic v1.4-1 |
| medium | 500 | Scale |
| large | 2,000 | Stress |
| action_heavy | 315 | action.* flows (§13.4) |
| feed_heavy | 280 | Feed definitions (§11.1) |
| channel_heavy | 300 | Channels (§13) |
| full | 600 | All features |

## Example Output

```
======================================================================
RELAY v1.4-1 SIMULATION RESULTS: Full v1.4-1
======================================================================

📜 WIRE PROTOCOL
  Identities:        600
  Actors:            505
  Log events:        1,243
  State objects:     600
  Channels:          0
  Feed definitions:  6
  Size:              0.88 MB

  Event breakdown:
    reaction: 694
    post: 224
    follow.add: 85
    action.request: 80
    action.commit: 80
    action.result: 80

📊 FEED REDUCTION (§17.10-11)
  Reductions:        17
  Avg time:          0.04 ms
  Verified:          100.0%

🤖 ACTION FLOWS (§13.4)
  Verifications:     11
  Valid:             100.0%
```

## Key Differences from Relay 2.0 Simulator

| Aspect | v1.4-1 | v2.0 |
|--------|--------|------|
| Architecture | Wire protocol | Two-layer (Truth/View) |
| Events | Log with `prev` chain | Events with `parents` |
| Views | Feed definitions | ViewDefinition + Boundary |
| Determinism | Reducer-based | Boundary-based |
| Attestation | Not in core | First-class primitive |
| Snapshot | Not simulated | Simulated |

## Files

- `core.py` - Wire protocol implementation
- `agents.py` - Actor system with action flows
- `run_simulation.py` - Main runner
