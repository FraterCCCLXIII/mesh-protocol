# HOLON Protocol v4.0 Simulator

A simulation framework aligned with the HOLON v4.0 specification.

## Architecture

Based on the v4.0 two-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  ALGORITHM LAYER                                             │
│  Views │ Discovery │ Reputation │ Moderation │ Economics    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                  │
│  Entity │ Content │ Link                                    │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd simulator_v4

# List scenarios
python run_simulation.py --list

# Run simulation
python run_simulation.py --scenario small_network --seed 42
```

## Features Tested

### Data Layer
- Entity creation (users, groups, relays)
- Content creation (posts, articles)
- Links (follow, react, subscribe, member, tip, verify, label)
- Handle resolution
- Group nesting (holonic structure via parent field)

### Algorithm Layer

#### Views
- Transparent ranking formulas
- Formula evaluation (decay, log, cap)
- Boundary generation and verification
- View subscription

#### Discovery
- Handle resolution
- Full-text search
- Follows of follows
- Similar followers
- Mutuals
- Active in context
- Suggested contexts
- Rising stars

#### Reputation
- Account age scoring
- Follower count (capped, log-scaled)
- Content quality (avg reactions)
- Verification bonus
- Spam rate penalty

#### Moderation
- Content labeling
- Label-based filtering
- Moderator role checking

#### Economics
- Tips (sats)
- Creator subscriptions
- Paid content
- View subscriptions

## Agent Types

| Type | Behavior |
|------|----------|
| LURKER | Heavy searcher, light poster |
| CASUAL | Average activity |
| ACTIVE | High engagement, tips |
| CREATOR | Monetizes content, verifies identity |
| CURATOR | Creates views, high follow rate |
| SPAMMER | Malicious actor |
| MODERATOR | Labels content |

## Scenarios

### Basic
- `small_network` - 100 users, basic functionality
- `medium_network` - 10,000 users, scale test
- `large_network` - 100,000 users, stress test

### Discovery
- `discovery_test` - All discovery mechanisms
- `search_stress` - Heavy search load
- `handle_resolution` - Handle lookup + verification

### Algorithm
- `view_creation` - Curator view creation
- `view_verification` - View execution + verification
- `ranking_formulas` - Different ranking algorithms

### Economics
- `creator_economy` - Subscriptions, tips, paid content
- `view_economy` - Paid view subscriptions
- `tipping_culture` - Heavy tipping

### Moderation
- `spam_attack` - Spam with moderation response
- `moderation_test` - Labeling and filtering

### Full
- `full_ecosystem` - All v4.0 features together

## Output

```
======================================================================
HOLON v4.0 SIMULATION RESULTS: Small Network
======================================================================

📦 DATA LAYER
  Entities:     103
  Content:      245
  Links:        892
  Total:        1,240
  Size:         0.32 MB
  Handles:      100

  Link breakdown:
    react: 534
    follow: 189
    member: 87
    tip: 45
    subscribe: 23
    verify: 14

🔍 ALGORITHM LAYER - Views
  Executions:   25
  Avg time:     0.15 ms
  P50 time:     0.12 ms
  P95 time:     0.31 ms

🔎 ALGORITHM LAYER - Discovery
  Queries:      12
  Avg time:     0.08 ms

💰 ECONOMICS
  Tips:              45
  Tip amount:        27,500 sats
  Creator subs:      23
  View subs:         18

👥 AGENTS
  Total:             100
  Content created:   245
  Follows:           189
  Group memberships: 87
  Views created:     8
  Verifications:     14

======================================================================
```

## Comparison to v3 Simulator

| Feature | v3 Simulator | v4 Simulator |
|---------|--------------|--------------|
| Layers | 3 (Object/Structure/View) | 2 (Data/Algorithm) |
| Discovery | Not simulated | Full simulation |
| Economics | Not simulated | Tips, subscriptions |
| Verification | Not simulated | External identity proofs |
| Ranking formulas | Basic | Full expression language |
| Handle resolution | Not simulated | Full simulation |
| Agent types | 6 | 7 (added CURATOR) |

## Files

- `core.py` - Data Layer + Algorithm Layer implementation
- `agents.py` - Agent system with v4.0 behaviors
- `scenarios.py` - Test scenarios
- `run_simulation.py` - Main runner
