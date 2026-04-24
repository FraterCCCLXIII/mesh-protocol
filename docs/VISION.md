# FABRIC 2.0 Vision: The Radical Ideas We're Not Yet Ready For

**Status:** Speculative research directions, not a specification.

---

## Honest Assessment of FABRIC 1.0

FABRIC 1.0 is a **well-engineered synthesis**. It takes the best ideas from Nostr, ActivityPub, SSB, AT Protocol, and Relay 2.0, fixes their problems, and creates something practical.

But it's not **radically innovative**. It's an evolution, not a paradigm shift.

This document explores the radical ideas we identified but chose not to include in v1.0 — because they're either too abstract, too complex, or need more research.

---

## The Assumptions All Protocols Share

Every decentralized social protocol (including FABRIC 1.0) shares these assumptions:

1. **Content is discrete objects** (posts, messages, reactions)
2. **Time is linear** (timestamps, sequences, HLC)
3. **Identity is singular** (one person = one keypair hierarchy)
4. **Trust is binary** (follow or don't, block or don't)
5. **Feeds are aggregations** (collect objects, sort, display)
6. **Types are fixed** (the protocol defines what a "post" is)

**The radical innovations come from challenging these assumptions.**

---

## Radical Idea #1: Programmable Social Primitives

### The Problem

Every protocol pre-defines object types:
- Nostr: events with kinds
- AT Protocol: Lexicon schemas
- FABRIC 1.0: Post, Edge, Reaction, etc.

When you want a new type, you need protocol changes or extensions.

### The Radical Alternative

What if the protocol didn't define posts, follows, or likes at all?

Instead, it defines only:
1. **Statements** — signed blobs with any structure
2. **References** — links between statements
3. **Computations** — pure functions over statements
4. **Capabilities** — who can execute what

Everything else is **emergent**:

```
Post = Statement where schema matches {author, content, timestamp, ...}
Follow = Statement where schema matches {source, target, type: "follow"}
Like = Statement where refs contains target and type = "reaction"
Feed = Computation that filters/sorts statements
```

### The Protocol as Virtual Machine

Think of it like Ethereum, but for social:
- Statements are transactions
- Computations are smart contracts
- Feeds are views over contract state
- No blockchain needed (just signatures + replication)

### Benefits

- **Infinitely extensible** without protocol changes
- **Community-defined semantics** — each group defines their types
- **Interop through computation** — share the function, not the schema
- **Innovation without coordination** — anyone can invent new social primitives

### Why Not in v1.0

Too abstract. Implementers need concrete types to build against. But this is the direction for v2.0.

---

## Radical Idea #2: Verifiable Computation as Core Primitive

### The Problem

Current protocols sync data, then clients compute views locally. But:
- Algorithms are hidden (what is "For You" actually doing?)
- Auditing is impossible (you can't prove a feed was computed correctly)
- Results can't be shared (your computation ≠ my computation)

### The Radical Alternative

Make **computation** a first-class, shareable, verifiable object.

```json
{
  "type": "computation",
  "id": "fabric:comp:sha256:...",
  "name": "Trending Tech Posts",
  "code": {
    "lang": "fabric-compute-v1",
    "source": "posts |> filter(topics.contains('tech')) |> sort(engagement_rate) |> limit(50)"
  },
  "input_schema": {"posts": "Post[]"},
  "output_schema": "Post[]",
  "deterministic": true,
  "sig": "ed25519:..."
}
```

### Properties

- **Source is public** — anyone can read the algorithm
- **Execution is reproducible** — same inputs = same outputs
- **Results are verifiable** — I can check if you computed correctly
- **Computations compose** — build complex from simple

### Algorithm Markets

People publish and share computations:
- "Best timeline algorithm for tech content"
- "Anti-engagement-bait filter"
- "Quality-weighted chronological"

You subscribe to computations like you subscribe to people.

### Why Not in v1.0

Requires a computation language/VM. Complex to specify correctly. But the direction is clear.

---

## Radical Idea #3: Spectrum Identity

### The Problem

Current identity model: one person = one keypair (with device keys).

But identity is contextual:
- Professional me vs personal me
- Public me vs anonymous me
- Individual me vs member-of-group me

### The Radical Alternative

Identity as a **spectrum with selective disclosure**:

```
Core Identity (master key, rarely used)
├── Professional Identity (work contexts)
│   └── "I am a verified engineer"
├── Personal Identity (social contexts)
│   └── "I am the same person as on Platform X"
├── Pseudonymous Identity (anonymous contexts)
│   └── "I have reputation > 100" (without revealing who)
└── Collective Identity (shared with group)
    └── "I am a member of Organization Y"
```

### Zero-Knowledge Properties

Prove things without revealing everything:
- "I am a member of Community X" (without revealing which member)
- "I have posted more than 1000 times" (without revealing posts)
- "I am over 18" (without revealing age)
- "I am the same person as Account Y" (linkable pseudonymity)

### Use Cases

- **Whistleblowing**: Prove you're an employee without revealing identity
- **Reputation portability**: Carry reputation without doxxing
- **Contextual personas**: Professional vs personal without correlation
- **Collective action**: Group speaks as one without individual exposure

### Why Not in v1.0

Requires ZK infrastructure (zkSNARKs, etc.). Complex cryptography. But this is where identity should go.

---

## Radical Idea #4: Multidimensional Trust

### The Problem

Trust is binary: follow or don't.

But I might trust someone for:
- Technical accuracy: 90%
- Political opinions: 10%
- Humor: 70%
- Breaking news: 50%

Binary follow mixes all dimensions.

### The Radical Alternative

Trust as a **vector, not a scalar**:

```json
{
  "type": "trust_allocation",
  "source": "ed25519:me...",
  "target": "ed25519:alice...",
  "dimensions": {
    "technical": 0.9,
    "political": 0.1,
    "humor": 0.7,
    "news": 0.5
  },
  "total_weight": 0.6
}
```

### Feed Computation

Your feed weights content by relevant trust dimension:

```
relevance(post, viewer) = 
  trust[post.author][post.topic_dimension] * 
  base_relevance(post)
```

### Emergent Expertise

The network naturally surfaces who's trusted for what:
- High technical trust → shown in technical contexts
- High news trust → shown for breaking news
- Low political trust → filtered in political contexts

### Why Not in v1.0

Requires topic classification. Complex trust computation. UX for setting trust vectors is hard. But the model is right.

---

## Radical Idea #5: Social as a Database

### The Insight

What if we treated social networks as **distributed databases**?

| Social Concept | Database Analog |
|----------------|-----------------|
| Post | Row in posts table |
| Follow | Row in edges table |
| Reaction | Row in reactions table |
| Feed | Query over tables |
| Thread | Recursive query |
| Trending | Aggregation query |

### The Protocol

Define:
1. **Schema primitives** — what tables can exist
2. **Write rules** — who can insert/update what
3. **Replication** — how tables sync across nodes
4. **Query language** — how to read across tables

Everything else is schema definition and queries.

### Benefits

- **Familiar model** — developers know databases
- **Powerful queries** — joins, aggregations, recursion
- **Optimization** — decades of database research applies
- **Flexibility** — any social feature is a query pattern

### Example Queries

```sql
-- Home feed
SELECT * FROM posts 
WHERE author IN (SELECT target FROM edges WHERE source = me AND type = 'follow')
ORDER BY timestamp DESC LIMIT 50;

-- Thread
WITH RECURSIVE thread AS (
  SELECT * FROM posts WHERE id = :root
  UNION ALL
  SELECT p.* FROM posts p JOIN thread t ON p.reply_to = t.id
)
SELECT * FROM thread ORDER BY timestamp;

-- Trending
SELECT topic, COUNT(*) as cnt 
FROM posts 
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY topic 
ORDER BY cnt DESC LIMIT 10;
```

### Why Not in v1.0

This is actually what FABRIC is, just not explicitly framed this way. The v2.0 framing should make this explicit.

---

## Radical Idea #6: Continuous Dataflow

### The Problem

Current model: Batch sync → local compute → display.

This creates latency and staleness.

### The Radical Alternative

Feeds as **continuous dataflow computations**:

```
feed_stream = 
  posts_stream
  |> filter(author_in_follows)
  |> filter(not_blocked)
  |> transform(add_engagement_scores)
  |> window(1_hour)
  |> sort(relevance)
  |> emit_top(50)
```

The feed is always running, always updating.

### Properties

- **Real-time**: New posts appear immediately
- **Reactive**: Changes propagate automatically
- **Composable**: Streams combine naturally
- **Distributed**: Computation can run anywhere

### Why Not in v1.0

Requires stream processing infrastructure. Complex operational model. But the direction is right for real-time social.

---

## Radical Idea #7: Proof-of-Attention Economy

### The Problem

Engagement is free, so spam is cheap.

### The Radical Alternative

Every action costs a scarce resource:

```json
{
  "type": "reaction",
  "cost": {
    "attention_tokens": 1,
    "proof_of_work": "0x00000f..."  // Optional: hashcash
  }
}
```

### Mechanics

- You get N attention tokens per day (or earn them)
- Reactions cost tokens
- Shares cost more tokens
- Quality content earns tokens back (others spend on you)

### Benefits

- **Spam is expensive**: Must spend real resource
- **Quality rises**: Attention goes to worthy content
- **Signal is meaningful**: A like actually costs something

### Why Not in v1.0

Creates friction. Excludes low-resource participants. Complex economics. But interesting for premium/quality contexts.

---

## The Synthesis: What FABRIC 2.0 Might Look Like

If we combined these ideas:

### Core Primitives

1. **Statements** — signed blobs (not typed objects)
2. **References** — content-addressed links
3. **Computations** — pure functions (verifiable, shareable)
4. **Capabilities** — delegation with constraints
5. **Identity Proofs** — ZK attestations about identity properties

### Derived Concepts

Everything else is defined by computations over statements:
- Types are schemas that statements match
- Feeds are computations that filter/sort
- Trust is a computation over relationship statements
- Reputation is a computation over reaction statements

### Key Properties

- **Programmable**: New social features = new computations
- **Verifiable**: All feeds can be audited
- **Private**: ZK proofs for selective disclosure
- **Contextual**: Trust varies by dimension
- **Efficient**: HLC + content-addressing + incremental computation

---

## Why We Stopped at FABRIC 1.0

FABRIC 1.0 is the **right choice for today** because:

1. **Implementable**: Clear types, clear operations
2. **Familiar**: Developers know posts, follows, feeds
3. **Practical**: No exotic cryptography required
4. **Proven patterns**: HLC, capabilities, content-addressing

The radical ideas need:
- More research (ZK identity)
- More infrastructure (computation VM)
- More UX work (multidimensional trust)
- More economic modeling (attention tokens)

FABRIC 1.0 ships. FABRIC 2.0 explores.

---

## Research Directions

If you want to push toward 2.0:

1. **Computation language**: Design a minimal, deterministic language for feed computations. Inspirations: Datalog, CQL, Differential Dataflow.

2. **ZK identity**: Implement spectrum identity using zkSNARKs or similar. Inspiration: Semaphore, Anon Aadhaar.

3. **Trust vectors**: Design UX for setting and using multidimensional trust. Inspiration: Netflix tags, Spotify taste profiles.

4. **Attention economics**: Model the economics of scarce engagement. Inspiration: Steem (but without blockchain), prediction markets.

5. **Stream processing**: Build incremental dataflow over social graphs. Inspiration: Materialize, Flink, Differential Dataflow.

---

## Conclusion

FABRIC 1.0 is a solid foundation: practical, implementable, better than alternatives.

FABRIC 2.0 is a vision: programmable, verifiable, contextual, multidimensional.

The gap between them is years of research and engineering. But knowing where we're going helps us make better decisions today.

---

*Status: Vision document*
*Not a specification*
*Ideas for exploration*
