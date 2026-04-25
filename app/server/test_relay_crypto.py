"""Tests for relay Ed25519 verification and ID helpers (spec-aligned vectors)."""
import unittest

from protocol import SigningKeyPair
from relay_crypto import (
    generate_content_id,
    generate_entity_id,
    generate_log_event_id,
    verify_signature,
)


class TestVerifySignature(unittest.TestCase):
    def test_valid_signature_round_trip(self):
        pair = SigningKeyPair.generate()
        msg = b"mesh-auth-challenge"
        sig = pair.sign(msg)
        pub = pair.public_key_bytes()
        self.assertTrue(verify_signature(pub, msg, sig))

    def test_rejects_wrong_message(self):
        pair = SigningKeyPair.generate()
        sig = pair.sign(b"original")
        pub = pair.public_key_bytes()
        self.assertFalse(verify_signature(pub, b"tampered", sig))

    def test_rejects_short_signature(self):
        pair = SigningKeyPair.generate()
        pub = pair.public_key_bytes()
        self.assertFalse(verify_signature(pub, b"x", b"\x00" * 31))

    def test_spec_style_signing_keypair_vector(self):
        # Appendix A sample private key (hex) — 32-byte seed
        seed_hex = (
            "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
        )
        seed = bytes.fromhex(seed_hex)
        pair = SigningKeyPair.from_seed(seed)
        message = b"mesh-challenge-test"
        sig = pair.sign(message)
        self.assertTrue(verify_signature(pair.public_key_bytes(), message, sig))


class TestDeterministicIds(unittest.TestCase):
    def test_entity_id_stable(self):
        pub = bytes.fromhex(
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
        )
        eid = generate_entity_id(pub)
        self.assertTrue(eid.startswith("ent:"))
        self.assertEqual(len(eid), 36)  # ent: + 32 hex chars

    def test_content_id_deterministic(self):
        d = {"author": "ent:ab", "kind": "post", "body": "hi"}
        self.assertEqual(generate_content_id(d), generate_content_id(d))

    def test_log_event_id_shape(self):
        lid = generate_log_event_id("ent:abc", 1)
        self.assertEqual(len(lid), 48)


if __name__ == "__main__":
    unittest.main()
