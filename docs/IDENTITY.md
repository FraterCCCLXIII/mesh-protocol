# MESH web client identity

The React client uses **one relay session** shape in `localStorage` (`mesh_session`): a relay `token` (opaque session id) obtained after an **Ed25519 challenge/response** with the MESH node, plus a small `user` object for UI.

## Recommended: Identity Vault (default)

- **Mode:** set `VITE_IDENTITY_MODE` unset or to `vault` (default in code).
- **Flow:** email + password → Identity Vault (see `services/identity-vault/`) stores **encrypted** key blobs. Private keys are derived/decrypted in the browser; the relay only sees the public key and a valid signature on each login challenge.
- **Recovery:** re-enter the **same email and password** used at registration. The Vault never holds your password in the clear; protect your account with a strong password and a safe backup strategy (the Vault service may support account recovery if you configure it there—refer to that service’s documentation).

## Development only: local keys

- **Mode:** `VITE_IDENTITY_MODE=local` in the client env.
- **Flow:** an Ed25519 keypair is generated in the browser and stored in `localStorage` (`mesh_local_key_material`) together with a `mesh_session` after registering against the relay. **No email recovery.**
- **Recovery:** if you clear site data, local keys are gone—create a new local account. Do not use for production or valuable identities.

## Migration between modes

- **Local → Vault:** not automated. Create a new Vault account and treat it as a new identity, or re-register by generating new keys in Vault and updating follows manually.
- **Vault → Local:** not supported; local mode is a dev convenience.

## Code map

- `src/lib/relayAuth.ts` — challenge/response to obtain relay token.
- `src/contexts/AuthContext.tsx` — Vault registration/login; writes `mesh_session`.
- `src/lib/localIdentity.ts` — local dev register/login; writes `mesh_session` and key material.
- `src/lib/mesh.ts` — API helpers; reads `mesh_session` for `?token=`. **Entity id** for all relay APIs is `user.entityId` (never a distinct “account id” from the Vault for MESH HTTP routes).
