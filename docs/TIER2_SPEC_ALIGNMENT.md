# Tier 2 — Spec alignment (MESH v1.1)

## §12 Multi-device (reference implementation + CI)

- **Code:** `protocol.DAGStore`, `create_merge_event`, `LogEvent` (parents + Lamport + MERGE op).
- **Tests:** `app/server/test_multidevice_dag.py` — two parallel `CREATE` heads (device A / B), `needs_merge` true, `create_merge_event` + single head after merge; plus sync replay.
- **Run:** `cd app/server && python -m unittest test_multidevice_dag -v`

The demo **FastAPI** relay still uses a simpler SQLite `content` model for posts; the **§12** behavior is **proven on the reference DAG** in the same repo (the “why not Nostr/SSB” story: explicit fork + merge, not a single linear chain per device).

## §9 / Appendix C — `home_timeline` view

- **Endpoint:** `GET /api/users/{entity_id}/feed?view=home_timeline` (default).
- **Validation / cost object:** `app/server/mesh_views.py` — caps `limit` (200), `offset` (20k), follow count (10k), and estimates `estimated_events_scanned` + `attestation_lookups` when `labels=1`.
- **Rejections:** `400` / `413` with `detail` (pathological pagination, too many follows, disallowed `limit`, etc.).
- **Response:** JSON includes `view`, `view_cost` (per §9.3 style), `labels_status` (`ok` | `off` | `disabled`), `items`, `total`.
- **Headers:** `X-Mesh-View`, `X-Mesh-View-Est-Events-Scanned`, `X-Mesh-View-Attestation-Lookups`.
- **Tests:** `app/server/test_mesh_views.py`

## Attestations on the home feed (moderation service)

- **Service:** `services/moderation` — `GET /api/subjects/{content_id}/labels`.
- **Relay env (optional):**
  - `MESH_MODERATION_URL` — base URL, e.g. `http://localhost:12004`
  - `MESH_ATTESTATION_ISSUER_ALLOWLIST` — comma-separated MESH `entity` ids; **only** these issuers’ labels are returned to the client
- **Query:** `labels=1` on the feed. If allowlist is empty or URL missing, `labels_status=disabled` and `moderation_labels` are empty arrays.
- **Client:** `Home` requests `labels=1`; `PostCard` shows small `spam` / `harassment` / … chips when present.

**Run tests:** `cd app/server && python -m unittest test_mesh_views test_multidevice_dag -v`
