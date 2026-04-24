# MESH Protocol

**Modular Extensible Social Hybrid Protocol**

A next-generation decentralized social network protocol combining the best of Nostr, ActivityPub, SSB, and AT Protocol.

## Quick Links

| Resource | Description |
|----------|-------------|
| [**Specification v1.1**](specs/MESH_PROTOCOL_v1.1.md) | Complete protocol specification |
| [**Implementation**](implementations/mesh/) | Production-ready Python implementation |
| [**Benchmarks**](docs/LEARNINGS.md) | Performance analysis and comparisons |

---

## What is MESH?

MESH is a layered protocol for decentralized social networking:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    APPLICATION (mobile, web, bots)                  │
├─────────────────────────────────────────────────────────────────────┤
│                    NETWORK (HTTP, WebSocket, federation)            │
├─────────────────────────────────────────────────────────────────────┤
│                    VIEW (feeds, algorithms, caching)                │
├─────────────────────────────────────────────────────────────────────┤
│                    MODERATION (attestations, trust networks)        │
├─────────────────────────────────────────────────────────────────────┤
│                    SOCIAL (Entity, Content, Link)                   │
├─────────────────────────────────────────────────────────────────────┤
│                    INTEGRITY (DAG, merge, verification)             │
├─────────────────────────────────────────────────────────────────────┤
│                    STORAGE (SQLite, PostgreSQL)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    PRIVACY (Ed25519, X25519, AES-GCM)               │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Self-sovereign identity** | Ed25519 keys are your identity |
| **Multi-device support** | Device keys with automatic merge |
| **End-to-end encryption** | X25519 + AES-256-GCM for DMs/groups |
| **Verifiable feeds** | Deterministic computation |
| **Composable moderation** | Third-party attestations |
| **Optional recovery** | Social, custodial, or hardware backup |
| **High performance** | 6,000+ writes/sec, 37M+ DAU per node |

## Performance

| Operation | Time | Throughput |
|-----------|:----:|:----------:|
| Ed25519 sign+verify | 0.15ms | 6,700/sec |
| Storage write | 0.17ms | 6,000/sec |
| Simple query | 0.19ms | 5,300/sec |
| View execution | 2.76ms | 360/sec |

## Getting Started

### Install Dependencies

```bash
pip install cryptography aiosqlite
```

### Basic Usage

```python
from implementations.mesh import (
    SigningKeyPair, Storage, Entity, Content, LogEvent,
    generate_entity_id, EntityKind, ContentKind
)

# Create identity
keys = SigningKeyPair.generate()
entity_id = generate_entity_id(keys.public_key_bytes())

# Initialize storage
storage = Storage("mesh.db")
await storage.initialize()

# Create a post
content = Content(
    id=generate_content_id({...}),
    author=entity_id,
    kind=ContentKind.POST,
    body={"text": "Hello MESH!"},
    ...
)
```

## Repository Structure

```
mesh-protocol/
├── README.md                 # This file
├── specs/
│   ├── MESH_PROTOCOL_v1.1.md # Current specification
│   ├── drafts/               # Work in progress
│   └── archive/              # Historical versions
├── implementations/
│   ├── mesh/                 # Production implementation
│   │   ├── crypto.py         # Ed25519, X25519, AES-GCM
│   │   ├── primitives.py     # Entity, Content, Link
│   │   ├── integrity.py      # LogEvent, DAG, merge
│   │   ├── storage.py        # SQLite with WAL
│   │   ├── views.py          # ViewDefinitions, reducers
│   │   ├── attestations.py   # Moderation layer
│   │   └── benchmark.py      # Performance tests
│   └── legacy/               # Previous protocol versions
├── simulators/
│   └── legacy/               # Historical simulators
├── tools/
│   ├── compare_all.py        # Cross-implementation tests
│   ├── benchmark_all.py      # Performance comparison
│   └── tests/                # Adversarial tests
└── docs/
    ├── LEARNINGS.md          # What we learned
    ├── EVALUATION_FRAMEWORK.md
    └── results/              # Benchmark results
```

## Comparison with Other Protocols

| Feature | MESH | Nostr | ActivityPub | SSB | AT Protocol |
|---------|:----:|:-----:|:-----------:|:---:|:-----------:|
| Self-sovereign ID | ✓ | ✓ | ✗ | ✓ | ✗ |
| Multi-device | ✓ | ✗ | ✓ | ✗ | ✓ |
| E2EE | ✓ | ✗ | ✗ | ✓ | ✗ |
| Fork handling | ✓ Auto | N/A | N/A | ✗ Manual | ✓ |
| Identity recovery | ✓ Optional | ✗ | ✓ | ✗ | ✓ |
| Custom algorithms | ✓ | ✗ | ✗ | ✗ | ✓ |

## Development

### Run Tests

```bash
cd tools && python -m pytest tests/ -v
```

### Run Benchmarks

```bash
python implementations/mesh/benchmark.py
```

## License

This project is released under CC0 1.0 Universal (Public Domain).

## Contributing

Contributions welcome! See the [specification](specs/MESH_PROTOCOL_v1.1.md) for protocol details.
