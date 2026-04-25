"""
§12 Multi-device fork + merge: two logical devices post independently (parallel heads), then MERGE.
Uses protocol.DAGStore / create_merge_event (spec-aligned reference implementation).
"""
import unittest
from datetime import datetime

from protocol import (
    DAGStore,
    LogEvent,
    ObjectType,
    OpType,
    SigningKeyPair,
    create_merge_event,
    generate_event_id,
)


def _content_event(
    actor: str, lamport: int, parents: list, object_id: str, body: str, dev: str, sk: SigningKeyPair
) -> LogEvent:
    e = LogEvent(
        id=generate_event_id(actor, lamport, parents),
        actor=actor,
        parents=parents,
        lamport=lamport,
        op=OpType.CREATE,
        object_type=ObjectType.CONTENT,
        object_id=object_id,
        payload={"body": body, "kind": "post"},
        ts=datetime.utcnow(),
        device_id=dev,
    )
    from protocol import canonical_json

    d = e.to_dict()
    to_sign = {k: v for k, v in d.items() if k != "sig"}
    e.sig = sk.sign(canonical_json(to_sign))
    return e


class TestMultideviceForkMerge(unittest.TestCase):
    """Simulates two devices (phone / laptop) with one root key + merge, per spec §12.3–12.4."""

    def setUp(self):
        self.root = SigningKeyPair.generate()
        self.actor = "ent:phonedevmerge"

    def test_two_parallel_heads_merge_to_single(self):
        store = DAGStore()
        d_phone = "dev:phone"
        d_lap = "dev:laptop"
        c1 = "cnt:post_phone"
        c2 = "cnt:post_laptop"

        e1 = _content_event(self.actor, 1, [], c1, "gm", d_phone, self.root)
        e2 = _content_event(self.actor, 2, [], c2, "coffee", d_lap, self.root)
        self.assertNotEqual(e1.id, e2.id)

        store.add_event(e1)
        store.add_event(e2)
        self.assertTrue(store.needs_merge(self.actor))
        self.assertEqual(len(store.get_heads(self.actor)), 2)

        heads = store.get_heads(self.actor)
        merge = create_merge_event(
            self.actor, heads, self.root, device_id="dev:merger"
        )
        self.assertEqual(merge.op.value, "merge")
        self.assertEqual(len(merge.parents), 2)

        store.add_event(merge)
        self.assertFalse(store.needs_merge(self.actor))
        self.assertEqual(len(store.get_heads(self.actor)), 1)
        self.assertEqual(store.get_heads(self.actor)[0].id, merge.id)

    def test_sync_replay_merges_remote(self):
        """One store receives events from "device A" then "device B" remote batch; merge."""
        s = DAGStore()
        a1 = "dev:a"
        a2 = "dev:b"
        p1 = _content_event(self.actor, 1, [], "c1", "a", a1, self.root)
        p2 = _content_event(self.actor, 2, [], "c2", "b", a2, self.root)
        s.add_event(p1)
        s.add_event(p2)
        m = create_merge_event(self.actor, s.get_heads(self.actor), self.root, device_id="dev:sync")
        s.add_event(m)
        self.assertEqual(len(s.get_heads(self.actor)), 1)


if __name__ == "__main__":
    unittest.main()
