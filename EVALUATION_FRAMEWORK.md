# Protocol Evaluation Framework

## The Problem with Raw Benchmarks

The numbers we have (0.23ms for Ed25519, 12ms for storage writes) are **necessary but insufficient**. They tell us:

- ✓ Crypto works and is fast
- ✓ Storage works and is I/O bound
- ✗ Nothing about correctness under adversarial conditions
- ✗ Nothing about real-world usage patterns
- ✗ Nothing about developer/user experience

## Evaluation Dimensions

### 1. Correctness (Does it work?)

| Test | What it validates | Priority |
|------|-------------------|----------|
| **Unit tests** | Individual primitives work | P0 |
| **Signature verification** | Rejects invalid sigs | P0 |
| **Prev chain validation** | Rejects out-of-order events | P0 |
| **Version increment** | Rejects stale state updates | P0 |
| **Content addressing** | Same content → same ID | P0 |
| **Boundary determinism** | Same inputs → same output | P1 |
| **Action chain verification** | request→commit→result validates | P1 |

**Current status:**
- HOLON v4: Basic correctness ✓
- Relay v1.4.1: Prev chain ✓, commitment_hash ✓
- Relay v2: Boundary determinism ✓, view verification ✓

### 2. Security (Does it resist attacks?)

| Attack | Test method | Expected behavior |
|--------|-------------|-------------------|
| **Signature forgery** | Submit event with wrong sig | Reject |
| **Replay attack** | Resubmit old signed event | Detect duplicate |
| **Sybil attack** | Create 10k identities | Rate limit / PoW |
| **Spam attack** | Flood content | Moderation / filtering |
| **Eclipse attack** | Isolate node from peers | Detect divergence |
| **State rollback** | Submit old version | Reject (version check) |

**What we should test:**
```python
async def test_signature_forgery():
    """Relay MUST reject events with invalid signatures."""
    event = create_valid_event()
    event['sig'] = random_bytes(64)  # Forge signature
    response = await relay.submit(event)
    assert response.status == 400
    assert "Invalid signature" in response.error

async def test_sybil_resistance():
    """Measure cost of creating many identities."""
    start = time.time()
    for i in range(1000):
        identity = create_identity()
        await relay.register(identity)
    elapsed = time.time() - start
    # Should take meaningful time/resources
    assert elapsed > 10  # At least 10ms per identity
```

### 3. Scalability (Does it grow?)

| Metric | 1 user | 1K users | 1M users | Test method |
|--------|--------|----------|----------|-------------|
| **Storage size** | ~1KB | ~10MB | ~10TB | Measure DB |
| **Query latency** | <1ms | <10ms | <100ms | Load test |
| **Sync time** | instant | <1s | <1min | Federation test |
| **Memory usage** | <10MB | <100MB | <10GB | Profile |

**Current benchmark extrapolation:**
```
Storage writes: ~80/sec (SQLite limit)
At 1M users with 10 posts/day each:
  - 10M posts/day = 115 posts/sec
  - Need: ~2 relay nodes to handle writes
  - Reads scale horizontally (replicas)
```

### 4. Usability (Is it practical?)

| Aspect | Question | How to evaluate |
|--------|----------|-----------------|
| **Developer UX** | How hard to build a client? | Build a minimal client, count LOC |
| **User UX** | How fast does feed load? | Measure time to first content |
| **Ops UX** | How hard to run a relay? | Document setup, count steps |
| **Recovery** | What happens after crash? | Kill process, restart, verify |

### 5. Interoperability (Does federation work?)

| Test | What it validates |
|------|-------------------|
| **Two-relay sync** | Events propagate correctly |
| **Partial sync** | Resume from sequence number |
| **Conflicting events** | Deterministic resolution |
| **Cross-relay query** | Find user on another relay |

## Proposed Test Suite

### Level 1: Smoke Tests (run in CI)
```bash
# All must pass
pytest test_crypto.py          # Signatures, encryption
pytest test_storage.py         # CRUD operations
pytest test_verification.py    # Signature/version checks
```

### Level 2: Integration Tests
```bash
# Social features work end-to-end
pytest test_follow_flow.py     # Follow, unfollow, followers list
pytest test_post_flow.py       # Create, read, reply, react
pytest test_group_flow.py      # Create group, join, post
pytest test_dm_flow.py         # Encrypted DMs
```

### Level 3: Adversarial Tests
```bash
# Security properties hold
pytest test_forgery.py         # Reject bad signatures
pytest test_replay.py          # Detect duplicates
pytest test_spam.py            # Rate limiting works
pytest test_version_rollback.py  # Reject old versions
```

### Level 4: Load Tests
```bash
# Performance at scale
pytest test_1k_users.py        # 1000 users, 10k posts
pytest test_concurrent.py      # 100 concurrent connections
pytest test_large_feed.py      # User following 1000 accounts
```

### Level 5: Federation Tests
```bash
# Multi-relay scenarios
pytest test_two_relay_sync.py  # Events propagate
pytest test_partition.py       # Recovery after network split
pytest test_cross_relay.py     # Query across relays
```

## Evaluation Scorecard

| Criterion | Weight | HOLON v4 | Relay v1.4.1 | Relay v2 |
|-----------|--------|----------|--------------|----------|
| **Correctness** | 30% | | | |
| - Crypto works | | ✓ | ✓ | ✓ |
| - Storage works | | ✓ | ✓ | ✓ |
| - Verification works | | partial | ✓ | ✓ |
| **Security** | 25% | | | |
| - Sig verification | | ✓ | ✓ | ✓ |
| - Replay protection | | ? | ✓ (prev) | ? |
| - Spam resistance | | ? | ? | ? |
| **Scalability** | 20% | | | |
| - Write throughput | | ~80/s | ~80/s | ~80/s |
| - Query latency | | 0.1ms | 0.44ms | 6.45ms |
| - Horizontal scaling | | ? | ? | ? |
| **Usability** | 15% | | | |
| - Client simplicity | | simpler | medium | complex |
| - Feature richness | | groups | channels | views |
| **Interop** | 10% | | | |
| - Federation | | code exists | code exists | code exists |
| - Tested | | no | no | no |

## What We Should Do Next

### Immediate (validate correctness)
1. Write adversarial tests for signature rejection
2. Test prev chain validation under concurrent writes
3. Test version increment rejection
4. Verify boundary determinism in Relay v2

### Short-term (validate security)
1. Implement and test spam resistance
2. Test replay attack detection
3. Measure Sybil attack cost

### Medium-term (validate scale)
1. Load test with 10k simulated users
2. Test federation between 2-3 relays
3. Measure sync convergence time

### Long-term (validate usability)
1. Build minimal client for each protocol
2. Measure time-to-first-post for new user
3. Document operational runbook

## Key Questions to Answer

1. **Which protocol is simplest for client developers?**
   - Count lines of code for equivalent client
   - Survey developer experience

2. **Which protocol handles spam best?**
   - Simulate spam attack
   - Measure filtering effectiveness

3. **Which protocol scales most efficiently?**
   - Extrapolate storage/compute for 1M users
   - Estimate operational cost

4. **Which protocol recovers fastest from failure?**
   - Simulate node crash
   - Measure recovery time

5. **Which protocol has best UX latency?**
   - Measure time to load feed
   - Measure time for post to appear on follower's feed

## The Real Test

Ultimately, the best evaluation is: **Can someone build a usable social app on this protocol?**

That means:
- A working mobile/web client
- Real users posting content
- Federation between at least 2 relays
- Handling of spam/abuse
- Recovery from failures

Everything else is proxy metrics.
