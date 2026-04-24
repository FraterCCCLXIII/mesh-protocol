# Relay 2.0 Simulator

A simulation framework for testing the Relay 2.0 protocol specification.

## Architecture

Based on the Relay 2.0 two-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  VIEW LAYER                                                  │
│  ViewDefinition │ Boundary │ Reducers │ Determinism         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  TRUTH LAYER                                                 │
│  Identity │ Event │ State │ Attestation │ Snapshot          │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd simulator_relay_v2

# List scenarios
python run_simulation.py --list

# Run simulation
python run_simulation.py --scenario small --seed 42
```

## Truth Layer Primitives

### Identity (§8)
- Public keys and actor_id
- `id = multihash(SHA-256(public_key))`

### Event (§10)
- Immutable, append-only, content-addressed
- Types: follow.add, follow.remove, post, reaction, action.*

### State (§11)
- Versioned, authoritative, mutable objects
- Types: profile, channel, feed_definition

### Attestation (§6)
- Claims that MUST NOT override Event/State facts
- Categories: trust, content, view

### Snapshot
- Verifiable checkpoints
- Comparable only with same scope, as_of, ordering

## View Layer

### ViewDefinition (§11.1)
- Signed State with type: relay.feed.definition.v1
- Fields: sources, reduce, params

### Boundary (§0.6)
- Defines dataset over which View is evaluated
- Valid for deterministic claims only with finite inputs

### Reducers (§17.10)
- relay.reduce.chronological.v1
- relay.reduce.reverse_chronological.v1
- relay.reduce.engagement.v1

## Actor Types

| Type | Behavior |
|------|----------|
| USER | Posts, follows, reactions |
| AGENT | AI agents doing action.* flows |
| CURATOR | Creates view definitions |
| INDEXER | Creates attestations for indexing |
| MODERATOR | Creates content labels |

## Scenarios

| Scenario | Actors | Focus |
|----------|--------|-------|
| small | 100 | Basic functionality |
| medium | 1,000 | Scale testing |
| large | 10,000 | Stress testing |
| agent_heavy | 340 | AI agent action.* flows |
| curator_heavy | 400 | View creation |
| full | 800 | All features |

## Example Output

```
======================================================================
RELAY 2.0 SIMULATION RESULTS: Full Ecosystem
======================================================================

📜 TRUTH LAYER
  Identities:    800
  Events:        1,453
  States:        800
  Attestations:  221
  Total:         3,288
  Size:          0.97 MB

  Event breakdown:
    reaction: 1,127
    post: 168
    follow.add: 116
    action.request: 42

👁️ VIEW LAYER
  View definitions: 14
  Executions:       36
  Avg time:         0.15 ms
  P50 time:         0.16 ms
  P95 time:         0.28 ms
  Deterministic:    100.0%
```

## Key Concepts Tested

1. **Content-addressed Events** - IDs derived from content hash
2. **Append-only Logs** - Events with parents (prev in v1 wire)
3. **State Versioning** - Version must increment
4. **View Boundaries** - Finite inputs for determinism
5. **Reducer Execution** - Chronological, engagement sorting
6. **Determinism Verification** - Same inputs = same output hash

## Files

- `core.py` - Truth Layer + View Layer implementation
- `agents.py` - Actor system
- `run_simulation.py` - Main runner
