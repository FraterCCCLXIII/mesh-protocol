

# Relay 2.0 stack specification (v1.4-1 / v1.5 wire encoding)

**Status:** Draft 0.4 (Relay 2.0 architecture + v1.4-1/1.5 normative HTTP and object encoding; **MUST**/**MUST NOT** in this document are as stated unless an erratum supersedes them).

**Conventions (normative keywords):** In **narrative** text, **MUST**, **MUST NOT**, and **SHOULD** are **bold** when used as **normative** keywords. In **markdown** **tables**, those words are **unbolded** for readability (same meaning).

**Relay 2.0** organizes the protocol in **two** **layers** of **meaning**:

1. **Truth layer** — cryptographically **signed**, **content-addressed** **facts**: **Identity**, **Event** (append-only log), **State** (authoritative mutable object), **Attestation** (claims), and snapshot-style checkpoints where used.
2. **View layer** — **deterministic** **projections** over the Truth layer: feeds, ordered lists, reducers (**§17.10**), recompute (**§17.11**). The **ViewDefinition** is concretely **`relay.feed.definition.v1`** state (**§11.1**) with **`sources`** + **`reduce`** + **`params`**. **Optional** **view** **execution** over HTTP (**`GET` `/view/.../run` **, ** **§0.3** **) ** may ** be ** **advertised** ** in ** **`/.well-known/relay-capabilities.json` ** as **`endpoints.view_run` **( ** **§8.1** **) **; ** **when** ** **absent** **, ** **verifiers** ** **recompute** ** from ** **§17** ** **fetches** **. **

The **body** of this document uses the same **three-part** *organization* as v1.4-1 for editing continuity:

1. **Part I** — Wire protocol + APIs (Truth + View wiring)
2. **Part II** — Reference server + relay implementation (non-normative reference)
3. **Part III** — Client architecture (non-normative reference)

## 0. Relay 2.0 model (read this first)

**Status (this section):** Draft 0.4 — two-layer **architecture** (Truth Layer + View Layer), **5** truth-facing primitives + **1** view entry point (**ViewDefinition**), with **v1.4-1** as the **normative** **HTTP** and **envelope** **encoding** in Parts I+ below.

**Design rule:** Relay 2.0 defines **what is true** and **what can be derived**, not how UIs are styled. Presentation, ranking, and most product behavior are **Views** (deterministic over explicit **boundaries**).

### 0.1 Migration (from v1.4 naming)

| v1.4 / v1.5 in this spec | Relay 2.0 concept |
| --- | --- |
| **Log** event | **Event** (`relay.event.v1` **role**; **wire** in **§10** uses **`ts`**, **`prev`**, not a top-level **`kind`:**) |
| **State** object | **State** (`relay.state.v1` **role**; **wire** in **§11**) |
| **Channel** config / metadata | **State** with a channel `type` (see **§13**) |
| **membership.*** on log | **Event** types (same `type` **strings**) |
| **action.*** (request, commit, result) | **Event** types (Appendix C) |
| **`relay.feed.definition.v1`** | **ViewDefinition** — **signed** **State** that names **inputs** and a **versioned** **reduce** **function** |
| v1 **`prev`** | **2.0** **parents** (often **one** **parent**); **v1.4-1** **wire** **unchanged** |

**Terminology (non-normative):** On the **v1** **wire** (**§10**), the **event** **predecessor** is the **single** field **`prev`**. In **Relay** **2.0** **sketches** (**§0.5**), the **abstract** **form** is **`parents`** (a **list**). The **mapping** **row** **in** **the** **table** **above** **covers** **this:** for **a** **linear** **chain,** **`prev`** **( **or** **`null`** **for** **the** **genesis** **head** **) **is** **the** **v1** **encoding** **of** **a** **single** **parent;** **`parents`** **generalizes** **to** **one** **or** **more** **parents** **( **forks** **or** **future** **DAG** **semantics** **) **without** **changing** **v1** **envelopes** **on** **existing** **deployments** **. **

### 0.2 Truth primitives (2.0)

* **Identity** — **§8**; **public** **keys** and **`actor_id`** (**§4.3**).
* **Event** — **immutable** **append** **per** **actor**; **§10**, **POST** **§16.3**, **GET** **§17.3**–**§17.4**.
* **State** — **versioned** **authoritative** **object**; **§11**, **§16.1**, **§17.5**.
* **Snapshot** (where offered) — **verifiable** **checkpoints**; `relay.snapshot.v1` **`scope`** is a **composable** **filter** object (**§0.5**); **compare** only with **same** **`scope`**, **`as_of`**, and **ordering**; **MUST** **not** be **treated** as **interchangeable** with **arbitrary** **non-snapshot** **boundaries** (**§0.7**).
* **Attestation** — **§6**; **MUST** **not** **override** **Event** / **State** **facts**; **Relay 2.0** **`claim`** **classification** (**§6.2.0**).
* **Verifiability profile** — **§0.8**; implementations **MUST** **declare** **`relay.profile.minimal`** or **`relay.profile.auditable`** (or both if multiple surfaces exist).

### 0.3 View layer (2.0)

* **ViewDefinition (normative mapping)** — **MUST** be **implemented** **only** as **signed** **State** with **`type`:** **`relay.feed.definition.v1`** (**§11.1**). **No** **alternate** **protocol-level** **representation** **permitted**; **wire** **fields** are **`sources`**, **`reduce`**, optional **`params`**.
* **Boundary** — **Single** **normative** **definition** is **§0.6**; **v1.4-1** **recompute** / **audit** **advice** in **§17.11** **MUST** be **read** in **light** of **§0.6**–**§0.7** for **2.0** **determinism** **claims**.
* **Target** **REST** (2.0 **sketch**, **not** **required** **on** **the** **wire** **today**): **`GET` `/view/{id}/run?boundary=…`**; **deployed** **origins** use **`/actors/...`** **paths** in **§16**–**§17**. ** **Discovery** **: ** **optional** **`endpoints.view_run` ** in **`/.well-known/relay-capabilities.json` **( **§8.1** **) ** **MAY** ** advertise ** a ** **template** ** URL ** for ** this ** **shape** **; ** when ** **absent** **, ** **clients** **MUST** ** **not** ** **assume** ** the ** **origin** ** **implements** ** **`GET` `/view/.../run` ** and ** **MUST** ** **fall** ** **back** ** to ** **recompute** ** from ** **§17.10** **–** **§17.11** **. **

### 0.4 API mapping (2.0 target vs this document’s HTTP)

| 2.0 **target** | **Normative** **v1.4-1** **surface** (this spec) |
| --- | --- |
| `POST /event` | `POST /actors/{actor_id}/log` (append **Event** **envelope**) |
| `GET /event/{id}` | `GET /actors/.../log/events/{event_id}` |
| `PUT` / `GET` `/state/...` | `PUT` / `GET` `/actors/.../state/...` |
| `GET /view/.../run` | **Not** a **separate** **MUST**; use **recompute** from **§17.10** + **fetches** (**§17.11**). |

### 0.5 Canonical JSON sketches (2.0 target; **not** v1.4-1 on-the-wire)

*Normative machine rules for `relay.snapshot.v1` **scope** and for **Boundary** are **§0.5** (scope shape in sketches below), **§0.6**, and **§0.7**.*

The **objects** **below** are **reference** **shapes** for **new** **implementations** and **for** **mapping** **mental** **models** **to** **§8**, **§10**, **§11** **( **v1** **envelopes** **)**. **Field** **names** **and** **required** **keys** **on** **the** **wire** **remain** **exactly** **as** in **the** **numbered** **sections** **(Part** **I) **.

#### Identity (2.0 sketch)

```json
{
  "kind": "relay.identity.v1",
  "id": "relay:actor:multihash(public_key)",
  "public_key": "base64(ed25519 public key)",
  "created_at": "2026-04-22T00:00:00Z",
  "sig": "base64(signature)"
}
```

**Rules (2.0):** `id` = **multihash**(**SHA-256**(**public_key**)) **(see** **§4.3) **; ** no **economic** **/ ** **reputation** at **this** **layer**; **`sig` **MUST** **verify**.

#### Event (2.0 sketch; v1 **§10** uses `prev`, `ts`, …)

```json
{
  "kind": "relay.event.v1",
  "id": "relay:event:multihash(content)",
  "actor": "relay:actor:abc",
  "type": "string",
  "data": {},
  "parents": ["relay:event:..."],
  "timestamp": "2026-04-22T00:00:00Z",
  "sig": "base64(signature)"
}
```

**Rules (2.0):** **content-addressed**; **immutable**; **`parents` **MAY** be **unresolved** at **append**; **verifiers** **MUST** treat **unresolved** **parents** as **unverified** **until** **fetched**.

**Unresolved** **parents** **( ** **orphan** ** **state** **) **: ** if **, ** after ** **reasonable** ** **fetch** ** **attempts** **( ** **client** **/ **indexer** **/ ** **origin** ** **policy** **; ** the ** **protocol** ** does ** **not** ** **require** ** **global** ** **liveness** ** or ** a ** **single** ** **global** ** **registry** ** of ** **events** ** ) **, ** a ** **listed** ** **parent** ** **id** ** **cannot** ** **be** ** **resolved** **, ** the ** **event** ** is ** **orphaned** ** in ** that ** **verifier'**s** ** **view** **. ** An ** **orphan** ** **MUST** **not** be ** **treated** ** as ** **cryptographically** ** **linked** ** to ** a ** **full** ** **parent** ** **chain** **. ** **Orphaned** ** **events** **MAY** be ** **shown** ** with ** a ** **warning** **, ** **stored** ** **for** ** **audit** **, ** or ** **excluded** ** from ** **deterministic** ** **Views** **( ** **§0.6** ** ) **. ** **Two** ** **recomputes** ** **that** ** **resolve** ** **or** ** **exclude** ** **different** ** **subsets** ** **as** ** **orphans** ** **MUST** ** **not** ** **be** ** **claimed** ** **as** ** **deterministically** ** **equivalent** ** **( ** **§0.6** ** **Determinism** ** **rule** **) **. ** **Absence** ** of ** a ** **parent** ** is ** **not** ** by ** **itself** ** **proof** ** the ** **child** ** **is** ** **invalid** **( **it** ** may ** be ** **un-** **replicated** **, ** **retained** ** **only** ** **elsewhere** **, ** or ** **temporarily** ** **unavailable** ** ) **. **

#### State (2.0 sketch; v1 **§11** `created_at` / `updated_at`, …)

```json
{
  "kind": "relay.state.v1",
  "id": "relay:state:user-defined",
  "actor": "relay:actor:abc",
  "type": "string",
  "version": 4,
  "data": {},
  "parents": ["relay:event:..."],
  "timestamp": "2026-04-22T00:00:00Z",
  "sig": "base64(signature)"
}
```

| Concept | Meaning |
| --- | --- |
| **Event** | What happened (audit) |
| **State** | What is true now (read path) |

**Rules (2.0):** **`version` **MUST** **increment**; **State** **is** **authoritative** for **reads**; **Event** **chain** **is** **authoritative** for **audit**; where **both** **exist, ** **State** **SHOULD** be **derivable** from **Event** **history** **( **profiles** **MAY** **require** **stricter** **rules** **)**.

#### Snapshot (2.0 sketch)

`relay.snapshot.v1` **MUST** carry **`scope`** as a **closed**, **composable** **filter** object (not a free-form `scope.kind` / `value` pair). **Removed:** **`actor_prefix`** (ambiguous).

```json
{
  "kind": "relay.snapshot.v1",
  "id": "relay:snapshot:multihash(root_hash)",
  "actor": "relay:actor:origin",
  "root_hash": "hex",
  "state_count": 15234,
  "as_of": "2026-04-22T00:00:00Z",
  "partial": false,
  "scope": {
    "actors": ["relay:actor:abc"],
    "types": ["post"],
    "id_range": {
      "from": "relay:state:...",
      "to": "relay:state:..."
    }
  },
  "sig": "base64(signature)"
}
```

**Top-level `relay.snapshot.v1` (sketch) — `actor` (normative):**

| Field | Type | Semantics |
| --- | --- | --- |
| `actor` | string | MUST be `relay:actor:…` for the **signer** (entity that **created** the snapshot and whose key verifies `sig`). **Origin** snapshots: the origin’s actor. **Mirror** / **indexer**: that service’s actor. Authority to trust the cut comes from `sig` and `scope` / `as_of`, not from `actor` matching every included state row’s `actor_id`. |

**`scope` subobject** (and **the** **same** **keys** **when** ** used ** **in** ** **Boundary** **`state_scope` **) **: **

| Field | Type | Semantics |
| --- | --- | --- |
| `actors` | array of string | **Exact** **match** on `actor_id` (state owner / publisher as defined for the state object). |
| `types` | array of string | **Exact** **match** on state **`type`**. MUST NOT use partial or prefix matching. |
| `id_range` | object | Inclusive interval over `state.id`: compare endpoints in UTF-8 **byte** lexicographic order (byte-by-byte), not Unicode scalar order, unless a profile says otherwise. For ASCII-only ids this matches JSON key ordering in §4.1; for non-ASCII, byte order remains normative. `from` and `to` MUST define a closed interval (both ends included). If `from` is after `to` in that order, the interval is empty and `id_range` MUST be rejected as invalid. |

**Examples (non-normative):** **In** **ASCII,** `relay:state:aaa` ** **precedes** **`relay:state:aab` **in** **UTF-** **8** **byte** **order. ** Comparing **`state:e`** **and** **`state:é`**: ** the ** **first** ** **differing** ** **bytes** ** are **`0x65`** **vs** **`0xC3`**, **so** ** **order** ** **follows** ** **raw** ** **UTF-** **8** ** **bytes** ** of ** the ** full **`id`**,** **not** ** **Unicode** ** **scalar** ** **value** ** of** ** a** ** **suffix** ** **code** ** point** ** alone. **

**Scope evaluation (normative):**

* **Conjunction (AND):** `scope` **MUST** be **interpreted** as the **conjunction** of **all** **present** **filters**; a **key** **absent** **or** an **empty** **array** **for** **`actors` **/ ** `types` **imposes** **no** **constraint** **in** **that** **dimension** **( **except** **as** **required** **by** **`partial` **, ** **below** **). **
* **When** **`partial` **is** **`true`**, **`scope` **MUST** **not** be **`{}` **; **it** **MUST** **contain** **at** **least** **one** **constraining** **field** ( **non-empty** **`actors` **or** **`types` **, ** **or** **valid** **`id_range` **with** **`from` **≤** **`to` **).**
* **When** **`partial` **is** **`false`**, the **snapshot** is **a** **“** **full** **”** **cut** **within** **a** **defined** **authority** **domain** ( **not** **unbounded** **“** **entire** **network** **”** ) **. ** A **“** **full** **”** **snapshot** **MUST** **name** that ** domain **: **( **1** ) ** an ** **origin** **( **e.g. ** the ** **signing** ** **`actor`** **on** ** the **`relay.snapshot.v1` ** object ** or ** a ** **profile-** **defined ** **`origin` **/ **`authority` ** field ** ) **, ** and ** ( **2** ) ** a ** **declared** ** membership** ** universe **: ** e.g. ** **all** ** **state** ** **objects** ** **that** ** **origin** ** **authorizes** ** **for** ** that ** **snapshot** ** at **`as_of`**, ** **optionally** ** **narrowed** ** by ** **`scope` **( **`scope` **MAY** be **`{}` **( **no** **additional** **AND** **filters** ) **, ** or ** **list** ** explicit** ** `actors` ** / **`types` ** / **`id_range` ** ). ** “** **Full** **” ** is ** **always** ** **relative** ** to ** that ** **authority** ** + **`as_of` ** + ** **`scope` **; ** it ** is ** **not** ** an ** **absolute** ** “** **every** ** **object** ** **in** ** **the** ** **federation** **. **

**Canonical evaluation:** Implementations **MUST** **apply** **filters** in **any** **order** (**order-independent**). **Identical** **`scope` **+ **`as_of` **+ **same** **state** **set** **MUST** **yield** **identical** **membership** for **the** **snapshot** **( **before** **Merkle** **)**. **

**Comparability:** Two **snapshots** are **portably** **comparable** **for** **deterministic** **View** **use** **iff** **they** have **the** **same** **canonical** **`scope` **object, **the** **same** **`as_of`**, and **the** **same** **membership** **set** **and** **Merkle** **construction** **per** **§0.5.1** — **in** **particular** **the** **same** **leaf** **ordering** **( **sort** **by** **`id`** **) ** and **the** **same** **leaf** **/ ** **internal** **/ ** **root** **hash** **rules**. **MUST** **not** **assume** **equivalence** **otherwise**. **

**Proof** (sketch object; **normative** **merkle** **/ ** **proof** **bytes** in **§0.5.1** ) **:**

```json
{
  "kind": "relay.snapshot.proof.v1",
  "snapshot_id": "...",
  "state_id": "...",
  "leaf_index": 42,
  "merkle_path": ["hex64 of 32 bytes", "..."],
  "path_bits": [0, 1, 0],
  "root_hash": "hex64 of 32 bytes"
}
```

#### 0.5.1 Snapshot Merkle tree and membership proof (normative)

**Alignment** with **§4.1** **( **and** **the** **exclusion** **of** **signature** **fields** **from** **signed** **/ ** **hashed** **material** **) **: ** a ** **leaf** **hash** **MUST** ** be ** **SHA-256**(**UTF-8** **bytes** **of** **the** **canonical** **state** **JSON** **( **per ** **§4.1** **) ** for ** the ** **state** ** object **, ** with ** the ** same ** **outer** ** **`sig`** ** ( **and** ** any** ** other ** **field** ** **excluded** ** for ** **signing** ** / **`object_id`** ** per ** **§4.1** ** and ** **§4.2** **) ** as ** for ** **that** ** object’s** ** **normal** ** **hash** ** / ** **sign** ** **pipeline** **. ** **MUST** ** **not** ** **mix** ** in ** a ** **different** ** **canonical** ** **subset** ** ( **e.g. ** **including** ** **`sig`**) ** for ** **Merkle** ** **leaves** ** **only** **. **

**Domain-separated** **padding** **hash** ( **synthetic** **sibling** **) **: **

`H_pad` **=** **SHA-256**(**UTF-8** **bytes** **of** ** the ** **literal** ** string **`relay.merkle.pad.v1`**) ** ( **32** ** **bytes** ** output ** ). **

**Tree** **construction** ( **binary** **Merkle** **) **: **

1. ** **Collect** ** **N** ** **state** ** **objects** ** **in** ** the ** **snapshot** ** **membership** ** **after** ** **§0.5** ** **scope** ** / ** **`as_of` ** **( **the** ** **same** ** **set** ** ** used** ** for ** **comparability** ** above **). **
2. ** **Sort** ** them ** **by** **`state.id` ** string ** in ** **UTF-8** ** **byte** ** **lexicographic** ** **ascending** ** **order** ** ( **same** ** order ** as ** **§0.5** ** **`id_range` ** and ** **§0.5.1** ** **table** ** in ** **§0.5** ** ) **. **
3. ** **For** ** each ** **object** **, ** **compute** ** the ** **leaf** ** **hash** **`L[i]`** ** as ** **above** ** for ** **i** ** = ** **0** ** .. ** **N** **−** **1** **. **
4. ** **Build** ** **a** ** **level** ** **list** ** **starting** ** with **`[L[0], …, L[N-1]]`**. ** **While** ** **the** ** **list** ** **length** ** **M** ** **>** ** **1** **: ** if ** **M** ** is ** **odd** **, ** **append** **`H_pad` ** as ** the ** **last** ** **element** **( **synthetic** ** **right** ** **sibling** ** in ** the ** **pairing** **order **) **. ** **Then** ** **pair** ** **adjacent** ** **elements** ** **( **0**-**1** **, ** **2**-**3** **, ** **…** **) **: ** for ** each ** **pair** **(left,** **right)** **, ** **parent** **=** **SHA-256**(**left** **`||`** **right** **) ** where ** **left** ** and ** **right** ** are ** the ** **raw** ** **32**-** **byte** ** **digests** **. ** **Replace** ** the ** **level** ** with ** the ** **list** ** of ** **parents** **. **
5. ** **The** ** **single** ** **remaining** ** **32**-** **byte** ** **value** ** is ** the ** **Merkle** ** **root** **. ** The **`root_hash` ** field ** in **`relay.snapshot.v1` ** ( **and** **` relay.snapshot.proof.v1` **) **MUST** ** **equal** ** that ** **root** ** ( **e.g. ** **lower**-** **hex** ** **encoding** ** in ** **JSON** ** as ** **elsewhere** **) **. **

**`relay.snapshot.proof.v1` ** **fields** **( **in ** **addition** ** to **`kind` **, **`snapshot_id` **, **`state_id` **) **: **

| Field | Semantics |
| --- | --- |
| `leaf_index` | **0**-** **based** ** **index** ** of **`state_id` ** in ** the ** **§0.5.1** ** **sorted** ** **`id` ** list ** **( **the** ** **same** ** **order** ** as ** **tree** ** **construction** **). ** |
| `merkle_path` | **JSON** ** **array** ** of ** **length** ** **=** ** **tree** ** **depth** **( **not** ** **counting** ** **the** ** **leaf** **) **. ** The **`i` **-** **th** ** **element** ** is ** the ** **32**-** **byte** ** **sibling** ** **hash** ** at ** **level** ** **`i` **( **sibling** ** of ** the ** **node** ** **containing** ** the ** **current** ** **hash** ** on ** the ** **path** ** to ** the ** **root** **) **, ** **encoded** ** as ** **64**-** **character** ** **lowercase** ** **hex** **( **or** ** **a** ** **profile**-** **defined** ** **base64** ** if ** **documented** **) **. ** |
| `path_bits` | Same length as `merkle_path`. Bit `i` MUST be 0 if the path node at that level was the left child (parent = SHA-256 of path-node hash concatenated with sibling), and 1 if it was the right child (parent = SHA-256 of sibling concatenated with path-node hash), when walking from leaf to root. |
| `root_hash` | ** **Expected** ** **Merkle** ** **root** **( **e.g. ** **hex ** **as ** in ** the ** **parent** ** **snapshot** **) **; ** **verifier** ** **MUST** ** **compare** ** after ** **recompute** **. ** |

**Verify** ( **normative** **) **: ** **Given** ** a ** **fetched** ** **state** ** object ** **, ** **recompute** **`H_leaf` ** per ** **the** ** **leaf** ** **rule** ** above **; ** if ** the ** **object’s** **`id` ** string ** **does** ** **not** ** **equal** **`state_id` **( **after** ** **the** ** **same** ** **id** ** **conventions** ** as ** **the** ** **deployment** **) **, ** **reject** **. ** **Let** **`h` **= **`H_leaf` **. ** **For** ** **i** ** = ** **0** ** .. ** **len**(**`merkle_path`**) **−** **1** **: ** **decode** **`s` ** as ** **32** ** **raw** ** **bytes** ** from **`merkle_path[i]`** **; ** if **`path_bits[i]`** ** = ** **0** **, ** set **`h` ** **←** ** **SHA-256**(**`h` ** `||` **`s` **) **; ** else **`h` ** **←** ** **SHA-256**(**`s` ** `||` **`h`**) **. ** **MUST** ** **require** **`h` ** **equals** ** the ** **snapshot** ** **root** **( **e.g. ** **compare** ** to ** **`root_hash` ** in ** the ** **proof** ** and ** **the** **`relay.snapshot.v1` ** **object** **) **. **

**Pseudocode (non-normative,** **equivalent** **to** **the** **verify** **steps** ** above **) **: **

```text
function verify_merkle_membership(state, state_id, merkle_path, path_bits, root_expected):
  if state.id != state_id: fail  // same string conventions as snapshot / deployment
  h = H_leaf(state)                // per leaf rule above; 32 bytes
  assert len(merkle_path) == len(path_bits)
  for i from 0 to len(merkle_path) - 1:
    s = decode_32_bytes(merkle_path[i])
    if path_bits[i] == 0:  // current node was left child: parent = H(left || s)
      h = SHA256(h || s)
    else:                    // current node was right child: parent = H(s || h)
      h = SHA256(s || h)
  if h != decode_root_bytes(root_expected): fail
  ok
```

#### Attestation (2.0 sketch) — **normative** **`claim`** **shape** **aligns** **§6.2.0**; **§6.2** **shows** **v1.2** **trust** **wire** (flat **`type`**).

```json
{
  "kind": "relay.attestation.v1",
  "id": "...",
  "issuer": "relay:actor:abc",
  "claim": {
    "category": "trust | snapshot | view",
    "type": "string",
    "payload": {}
  },
  "expires_at": "...",
  "supersedes": "...",
  "sig": "..."
}
```

| Category | Purpose |
| --- | --- |
| `trust` | Identity or reputation claims ( **includes** **wire** **types** in **§6.3** **when** **normalized** **per** **§6.2.0** **). |
| `snapshot` | Claims about **snapshot** **correctness** / **membership** **/ ** **root**. |
| `view` | Claims about **computed** **View** **outputs** **( **e.g. ** **attested** **hashes** **)** . ** |

**Rules (2.0):** **`claim.category` **MUST** **be** **present** **on** **Relay 2.0** **general** **attestations** **( **§6.2.0** **)** . ** **MUST** **not** **override** **Truth** **primitives**; **unknown** **`claim.type` **values** **within** **a** **known** **`category` **MUST** be **ignored** **safely** **( **extension** **policy** **)** . **

#### ViewDefinition (2.0 sketch) — **wire** **MUST** **use** **`relay.feed.definition.v1`** (**§11.1**); **no** **`relay.view.definition.v1`** **or** **other** **parallel** **`type`**.

```json
{
  "kind": "relay.state.v1",
  "id": "relay:view:my_view",
  "type": "relay.feed.definition.v1",
  "version": 3,
  "data": {
    "sources": [],
    "reduce": "relay.reduce.reverse_chronological.v1",
    "params": {}
  },
  "sig": "..."
}
```

**Determinism (2.0):** **Formal** **definition** **—** **§0.6** **( **pure** **View** **function** **)** . ** **At** **minimum** **a** **View** **evaluation** **is** **deterministically** **equivalent** **iff** **same** **top-level** **ViewDefinition** **`version`**, **same** ** **explicit** ** **versions** **( **or** ** **ids** **)** ** for** **all** ** **nested** ** **referenced** ** ** `kind: "feed"` ** **ViewDefinitions** **( ** **§0.6** ** ) **, ** **same** ** **Boundary** **( ** **§0.6** ** ) **, ** and** **same** ** **resolved** ** **input** ** **data** **( ** see ** **§0.6** ** ) **. **

**Boundary** ( **normative** **object** **—** **full** **rules** **§0.6** **); **illustration** **only** **:**

```json
{
  "snapshot": "relay:snapshot:...",
  "event_ranges": [
    {
      "actor": "relay:actor:abc",
      "from": "relay:event:…",
      "to": "relay:event:…"
    }
  ],
  "state_scope": { "actors": ["relay:actor:abc"], "types": ["post"] }
}
```

**`event_ranges`** **( **when** **present** **) ** **MUST** **be** **a** **JSON** ** **array** ** **of** ** **one** ** **or** ** **more** ** **objects** **, ** **each** ** **with** ** **the** ** **same** ** **shape** ** **as** ** **this** ** **paragraph** ** **requires** ** **for** ** **a** ** **single** ** **range** **. ** **Each** ** **element** ** **MUST** ** **name** ** an **`actor`** **( **or** ** **equivalent** ** **per-** **source** ** **key** ** in ** **a** ** **profile** **) **; **`from`** **and** **`to`** **MUST** ** **delimit** ** **inclusive** ** **endpoints** ** **in** ** **that** ** **`actor`’s** ** **append-** ** **only** ** **log** ** **order** **( ** **the** ** **order** ** **induced** ** **by** ** **that** ** **`actor`’s** **`prev`** ** **chain** ** **/** ** **origin-** ** **stated** ** **log** ** **sequence** **) **, ** **not** ** **a** ** **global** ** **order** ** **on** ** **event** ** **id** ** **strings** **( ** **id** ** **hashes** ** **are** ** **not** ** **a** ** **causal** ** **total** ** **order** ** **across** ** **the** ** **network** **) **. ** **Option** ** **B** ** **( ** **if** ** **used** ** **by** ** **a** ** **profile** **, ** **not** ** **mixed** ** **with** ** **A** ** **on** ** **the** ** **same** ** **range** ** **object** **) **: ** **a** ** **defined** ** **total** ** **order** ** **( ** **e.g. ** **`(ts, event_id)`** ** **lexicographic** ** **tie-** ** **break** **) ** **MUST** ** **be** ** **stated** ** **in** ** **that** ** **profile** **. ** **Multiple** ** **`actor`** ** **values** ** **in** ** **`event_ranges`** ** **name** ** **a** ** **product** ** **of** ** **per-** **`actor`** ** **windows** **, ** **not** ** **one** ** **interval** ** **in** ** **a** ** **global** ** **event-** ** **id** ** **order** **( ** **§0.6.1** **) **. **

Without a **valid** **Boundary** (**§0.6**), a **stated** **result** **is** **“** **latest** **available** **”** **/ ** **best-effort** **—** **not** **reproducible** **/ ** **not** **audited** **( **§0.3** **, ** **§17.11** **)**. **

**View run** (response **sketch**):

```json
{
  "view_id": "...",
  "definition_version": 3,
  "boundary": {},
  "result": [],
  "result_count": 100,
  "attestation": { "root_hash": "...", "proof_available": true }
}
```

**Input kinds** and **core** **reduce** **families** **( **2.0** **naming** **— ** **see** **§17.10** **for** **normative** **ids** **)**:

| Input kind (2.0) | Meaning |
| --- | --- |
| `actor_log` | Events from an actor |
| `snapshot` | State set (bounded) |
| `event_type` | Filtered events |
| `view` | Nested view |

| Function family | Description |
| --- | --- |
| chronological / reverse_chronological | Order |
| union / intersection | Set ops |

#### Key guarantees (summary)

* **Truth:** **Signed**, **addressable**; **State** **for** **reads**; **Events** **for** **audit** (**Part** **I**).
* **View:** **Deterministic** **only** **with** **Boundary** **§0.6**; **ViewDefinition** **only** **`relay.feed.definition.v1`** (**§0.3**); **recomputable** (**§17.11**).
* **Snapshot:** **Merkle**-**verifiable** **root**; **`scope`** **filter** **object** **§0.5**; **not** **interchangeable** **with** **arbitrary** **non-snapshot** **boundaries** (**§0.7**).

### 0.6 Boundary definition (normative)

A **Boundary** **defines** **the** **dataset** ** over **which** a **View** **is** **evaluated** **and** **over** **which** **determinism** **and** **audit** **claims** **MUST** **be** **scoped** **. **

**Finite** **input** **for** **determinism** **( **replaces** **unqualified** **“** **sufficient** **constraint** **”** **):** A **Boundary** **is** **valid** **for** **deterministic** **/** **reproducible** **/** **fully** **verifiable** **claims** **only** **if** **it** **describes** **a** **finite** **set** **of** **inputs** **( **a** **verifier** **with** **unbounded** **resources** **could** **enumerate** **the** **set** **and** **finish** **)**. **

**MUST** **include** **at** **least** **one** **of** **the** **following** **finite** **pins** ( **unbounded** **filter-only** **boundaries** **are** **invalid** **for** **deterministic** **claims** **). ** **Each** ** **pin** ** **is** ** **finite** ** **by** ** **definition** ** **for** ** **this** ** **spec** **( ** **no** ** **separate** ** **“** **finiteness** ** **proof** **” ** **step** ** **at** ** **evaluation** ** **time** **) **: **

1. **`snapshot` **— **a** **`relay.snapshot.v1` ** **id** **( ** **or** ** **profile-** **defined** ** **snapshot** ** **ref** **) ** **that** ** **fixes** ** **a** ** **well-** ** **defined** ** **state** ** **membership** ** **set** ** **per** ** **§0.5** ** **/** ** **§0.7** **( ** **finite** ** **by** ** **construction** ** **: ** **the** ** **snapshot** ** **object** ** **+ **`scope` ** **+ **`as_of` **) **;** **or**
2. **`event_ranges` **— **a** ** **non-** ** **empty** ** **JSON** ** **array** ** **of** ** **per-** **`actor` ** **inclusive** ** **ranges** ** **( ** **§0.6.1** **) **( ** **finite** ** **per-** **`actor` **: ** **each** ** **`from` ** **..** **`to` ** **is** ** **a** ** **closed,** ** **enumerable** ** **window** ** **in** ** **log** ** **order** **) **;** **or**
3. **`id_range` **— **a** ** **closed** ** **lexicographic** ** **interval** ** over **`state.id` ** **( ** **in** **`state_scope` ** **or** ** **where** ** **the** ** **profile** ** **places** ** **it; ** **§0.5** **) **( ** **finite** **: ** **the** ** **set** ** **of** **`state.id` ** **values** ** **between** **`from` ** **and** **`to` ** **inclusive** ** **in** ** **UTF-** **8** ** **byte** ** **order** **) **. **

**`state_scope` **( **or** **filters** **alone** **)** **without** **( **1** ) **–** **( **3** ) ** ( **e.g. ** ** `{ "state_scope": { "types": ["post"] } }` ** with ** no ** **time** **, ** **snapshot** **, ** **or** ** **bounded** ** **range** **)** ** does ** **not** ** **define** ** a ** **finite** ** **dataset** **: ** it ** is ** **not** ** **valid** ** for ** **stated** ** **determinism** **( **it** **MAY** ** still ** be ** **used** ** for ** **best-effort** ** **/** ** heuristics** **; ** see ** **§0.3** ** ) **. **

**Static** ** **Boundary** ** **validation** ** **( ** **normative, ** **deterministic** ** **/ ** **audited** ** **evaluation** **) **: ** **Before** ** **invoking** ** **a** ** **reducer** ** **for** ** **a** ** **result** ** **that** ** **is** ** **claimed** ** **deterministic** ** **/ ** **fully** ** **verifiable, ** **an** ** **implementation** ** **MUST** ** **check** ** **that** ** **the** ** **Boundary** ** **satisfies** ** **( **1** ) ** **–** **( **3** ) ** **above** ** **( ** **or** ** **a** ** **profile-** ** **defined** ** **equivalent** ** **pin** **) **. ** **If** ** **the** ** **check** ** **fails, ** **the** ** **implementation** ** **MUST** ** **not** ** **run** ** **the** ** **reducer** ** **; ** **it** ** **MUST** ** **fail** ** **the** ** **evaluation** ** **( ** **or** ** **treat** ** **the** ** **outcome** ** **as** ** **non-** ** **deterministic** ** **/** ** **best-** ** **effort** ** **only** ** **per** ** **§0.3** **) **. **

**Boundary object** ( **all** **top-level** **keys** **optional** **unless** **a** **profile** **requires** **a** **specific** **pin** **, ** **subject** **to** **the** **finite-input** ** rules ** **above** ** ) **: **

```json
{
  "snapshot": "relay:snapshot:...",
  "event_ranges": [
    {
      "actor": "relay:actor:...",
      "from": "relay:event:...",
      "to": "relay:event:..."
    }
  ],
  "state_scope": {
    "actors": ["relay:actor:abc"],
    "types": ["post"],
    "id_range": { "from": "relay:state:...", "to": "relay:state:..." }
  }
}
```

**`state_scope`** **uses** **the** **same** **filter** **semantics** **as** **snapshot** **`scope`** **( **AND** **of** **present** **filters** **; ** **§0.5** **table** **)** . **

**`snapshot`** ** **and** **`state_scope`** ** **together** ** **( ** **normative** **) **: ** **If** ** **both** **`snapshot`** ** **and** **`state_scope`** ** **are** ** **present** **, ** **the** ** **effective** ** **state** ** **set** ** **for** ** **the** ** **Boundary** ** **is** ** **the** ** **intersection** ** **of** ** **( ** **a** **) ** **the** ** **membership** ** **fixed** ** **by** ** **the** ** **`relay.snapshot.v1`** ** **object** ** **( **`scope`** **+ **`as_of` **) ** **and** ** **( ** **b** **) ** **the** ** **set** ** **selected** ** **by** ** **applying** **`state_scope`** ** **as** ** **an** ** **AND** ** **filter** ** **with** ** **the** ** **same** ** **semantics** ** **as** ** **`scope`** ** **in** ** **§0.5** ** **( ** **types** **, **`actors`**, **`id_range`**, ** **etc.** **) **. **

**Rules:**

* A **valid** **Boundary** **( ** for ** **determinism** ** ) **MUST** **fully** **constrain** **all** **inputs** **required** ** **by** ** **the** ** **`reduce` ** **identifier’s** ** **declared** ** **input** ** **domains** **( ** **§17.10** **) ** **for** ** **that** ** **ViewDefinition** **, ** **including** ** **per-** **source** ** **log** ** **windows** **, ** **state** ** **heads** **, ** **the** ** **top-level** ** **`relay.feed.definition.v1`** **`version` **, ** **and** ** **explicit** ** **`version`s** ** **for** ** **every** ** **referenced** ** **`kind: "feed"`** ** **/** ** **nested** ** **ViewDefinition** ** **( ** **so** ** **recompute** ** **does** ** **not** ** **drift** ** **on** ** **silent** ** **definition** ** **upgrades** **; ** **see** ** **below** **) **, ** **or** ** **a** ** **pinning** ** **snapshot** **. **
* A **Boundary** **MAY** **include** **a** **snapshot** **reference**, **`event_ranges`** ** **( ** **one** ** **or** ** **more** ** **per-** **`actor`** ** **windows** **; ** **§0.6.1** **) **, ** **and/or** ** **`state_scope`**. **
* A **Boundary** **is** **syntactically** **well-formed** **iff** **all** **referenced** **data** **is** **resolvable** **and** **all** **declared** **ranges** **are** **finite** **( **no** **unbounded** **“** **to** **” ** **=** ** infinity** **; ** no ** **open** **- ** **ended** ** **log** ** **windows** ** in ** a ** **determinism** ** **claim** ** ) **. **

**ViewDefinition** **version** **pinning** **( ** **nested** ** **views** ** ) **: ** All ** **referenced** ** **ViewDefinition** ** **State** ** objects ** **( **e.g. ** ** **`kind: "feed"`** ** **sources** **)** **MUST** ** be ** **resolved** ** at ** **explicit** ** **state** ** **`version` **s ** **( **or** ** **content** ** **ids** ** **under** ** **a** ** **profile** ** ) ** **named** ** in ** ** the ** **Boundary** ** or ** an ** **accompanying** ** **pin** ** list **: ** the ** **outer** ** **definition** ** **`version` ** **alone** ** is ** **not** ** **sufficient** ** if ** **nested** ** **definitions** ** **can** ** **mutate** ** **independently** **( ** see ** also ** **§0.1** ** commentary ** on ** **nested** ** **feeds** ** ) **. **

**Resource** **limits** ** and ** **honest** ** **claims** **: ** **Implementations** **MAY** ** impose ** **implementation** ** **limits** ** ( **e.g. ** ** **maximum** ** **snapshot** ** **object** ** **count** **, ** **truncation** ** **of** ** **fetched** ** **logs** ** ) **, ** but ** **MUST** ** **not** ** **assert** ** **a** ** **deterministic** ** **/ ** **fully** ** **verified** ** **result** ** for ** a ** **Boundary** ** they ** **cannot** ** ( **or** ** will ** not ** ) ** **fully** ** **verify** **; ** they ** **MUST** ** **reject** ** or ** **downgrade** ** the ** **claim** **( **e.g. ** ** to ** **best-effort** **, ** **§0.3** ** ) **. **

**Determinism rule (Views):** Two **View** **evaluations** **MUST** be **treated** as **deterministically** **equivalent** **iff** **all** of **the** **following** **hold** **: ** the **same** **top-level** **ViewDefinition** **`version`**, the **same** **pinned** **versions** **( **or** ** **ids** **)** ** for ** **all** ** **nested** ** **ViewDefinitions** **, ** the **same** **Boundary** **value** ( **after** **canonicalization** **, ** **§0.6.1** **), ** **the** ** **same** ** **underlying** ** **resolved** ** **input** ** **bytes** ** **( ** **log** ** **events** **, ** **state** ** **objects** **) **, ** **and** ** **the** ** **same** ** **resolution** ** **status** ** **for** ** **every** ** **event** ** **referenced** ** **in** ** **the** ** **reduction** ** **( ** **including** ** **whether** ** **each** **`parents` ** **/** **`prev` ** **target** ** **is** ** **resolved** ** **or** ** **orphaned** ** per ** **§0.5** ** **Event** ** **rules** ** **and** ** **the** ** **verifier’s** ** **fetch** ** **policy** **) **. ** **Two** ** **recomputes** ** **that** ** **classify** ** **different** ** **subsets** ** **as** ** **orphans** ** **or** ** **resolve** ** **different** ** **parents** ** **MUST** ** **not** ** **be** ** **treated** ** **as** ** **deterministically** ** **equivalent** ** **for** ** **the** ** **same** ** **Boundary** ** **claim** **. **

### 0.6.1 Boundary object canonical form and `event_ranges` (normative)

**`event_ranges`:** when present, **MUST** be a **JSON** **array** of **one** **or** **more** **objects**. **Each** **object** **( **a ** **single** ** **per-** **`actor` ** **range** **) ** **MUST** ** **be** ** **interpreted** ** **in** ** **per-** **`actor` ** **log** ** **order** **( ** **§0.1** **, **`prev` ** **/** ** **origin** ** **order** **) **; ** **each** ** **MUST** ** **include** **`actor` ** **( ** **or** ** **profile** **-** **equivalent** **) **. **`from`** **and** **`to`** **are** ** **as** ** **in** ** **the** **`event_ranges`** ** **sketch** ** **§0.5** **. **

**Note** **( ** **multi-** **actor** ** **boundaries** **) **: ** **Pins** ** **in** **`event_ranges`** ** **are** ** **per-** **`actor` ** **and** ** **are** ** **not** ** **globally** ** **comparable** ** **as** ** **a** ** **single** ** **interval** ** **in** ** **a** ** **global** ** **event-** ** **id** ** **order** **. ** **An** ** **array** ** **with** ** **more** ** **than** ** **one** **`actor`** ** **( ** **or** ** **multiple** ** **windows** ** **for** ** **one** **`actor` ** **if** ** **a** ** **profile** ** **allows** **) ** **names** ** **a** ** **product** ** **of** ** **windows** **, ** **not** ** **one** ** **global** ** **timeline** **. **

**Cross-** **`actor` ** **ordering** ** **( ** **normative** ** **for** ** **applicable** **`reduce` ** **ids** **) **: ** A ** **reducer** ** **that** ** **merges** ** **or** ** **totally** ** **orders** ** **items** ** **from** ** **more** ** **than** ** **one** **`actor`** ** **( ** **or** ** **from** ** **more** ** **than** ** **one** **`event_ranges` ** **element** **) ** **MUST** ** **define** ** **in** ** **its** ** **§17.10** ** **/** ** **registry** ** **specification** ** **( ** **§22.7** **) ** **a** ** **deterministic** ** **cross-** **`actor` ** **total** ** **order** ** **( ** **e.g. ** **`(ts, event_id)`** ** **lexicographic** ** **as** ** **in** ** **§17.10** ** **chronological** ** **reducer** **, ** **or** ** **another** ** **documented** ** **tie-** ** **break** **) **. ** **If** ** **such** ** **a** ** **reducer** ** **would** ** **combine** ** **multiple** ** **`actor` ** **streams** ** **but** ** **its** ** **specification** ** **does** ** **not** ** **define** ** **that** ** **order,** ** **evaluation** ** **MUST** ** **fail** ** **( ** **no** ** **implementation-** ** **defined** ** **fallback, ** **no** ** **silent** ** **nondeterminism** **) **. ** **Per-** **`actor` **`event_ranges` ** **remain** ** **in** ** **that** **`actor`’s** ** **log** ** **order** **; ** **the** ** **cross-** **`actor` ** **rule** ** **applies** ** **when** ** **the** **`reduce` ** **combines** ** **those** ** **streams** **. **

**Boundary** **canonical** **form** ** for ** **comparing** ** or ** **hashing** ** **Boundary** ** **values** **( **e.g. ** **attestations** **, ** **caches** ** ) **: **

| Concern | Rule |
| --- | --- |
| Object key order | Object keys sorted in Unicode code point lexicographic order (same as §4.1). |
| Arrays | Arrays whose order is not semantically significant (e.g. `actors`, `types` in filters) MUST be sorted lexicographically as JSON string values (NFC, §4.1.2) before comparison or hashing. Order-sensitive arrays, if any, MUST be defined by profile. |
| `event_ranges` | Each element is an object `{ "actor", "from", "to" }` (and profile-defined keys only as documented). The array’s order is not semantically significant (product of per-actor windows). MUST be sorted in canonical order: ascending UTF-8 byte order of `actor` string, then `from` string, then `to` string (NFC per §4.1.2 on each string). |
| `null` vs omitted | Optional keys with no value MUST be omitted. MUST NOT use JSON `null` in place of omission for canonical Boundaries. |

**Boundary** ** **equality** **( **caching, ** **attestations** **, ** **fingerprints** ** ) **: ** two ** **semantically** ** **equivalent** ** **Boundary** ** **values** **MUST** ** have ** the ** same ** **bytes** ** after ** this ** **canonical** ** **form** ** and ** the ** **shared** ** **JSON** ** **rules** ** in ** **§4.1** **( ** **numbers** **, ** **strings** **, ** **NFC** **, ** **etc. ** ) **. **( ** The ** **Determinism** ** **rule** **( ** **Views** ** ) ** in ** **§0.6** ** is ** **unchanged; ** this ** **paragraph** ** is ** only ** the ** **hashing** ** **/ ** **compare** ** **spec** **. **)

**View function purity (normative):** A **reducer** / **View** **function** **MUST** **not** **depend** **on**: **(1)** **current** **wall** **clock**, **`Date.now`**, or **any** **unspecified** **“** **now** **”** **( **time** **MAY** **appear** **only** **as** **part** **of** the **Boundary** **or** **input** **objects** **); ** **(2)** **non-deterministic** **randomness** **; ** **(3)** **external** **network** **calls** **; ** **(4)** **non-specified** **host** **or** **process** **state** **( **e.g. ** **unordered** **map** **iteration** **without** **canonical** **order** **). ** It **MUST** **operate** **only** **on** the **ViewDefinition** **and** **Boundary**-**defined** **inputs** and **MUST** **yield** **identical** **output** **for** **identical** **inputs** **. **

**Forked** **actor** **logs** **( ** **normative, ** **ties** ** to ** **§17.10** **) **: ** If ** a ** **View** ** **input** ** **is** ** an ** **actor** ** **append-** ** **only** ** **log** ** **and** ** **the** ** **fetched** ** **events** ** **admit** ** **more** ** than ** one ** **head** ** **( **a ** **fork** **) **, ** the ** **deterministic** ** **reducer** ** **MUST** ** **follow** ** **§17.10** **( ** **Multiple** ** **heads** ** / ** **forks** **) **: ** **reject** ** **as** ** **ambiguous** ** **or** ** **apply** ** a ** **documented** ** **head** **-** ** **choice** ** **policy** **. **

**Enforcement:** Implementations **MUST** **treat** **any** **violation** **as** **non-deterministic** **output** **. ** They **MUST** **not** **claim** **bit-for-bit** **equivalence** **or** **universal** **audit** **parity** **across** **deployments** **for** **non-deterministic** **outputs** **. **

### 0.7 Snapshot and boundary (normative relationship)

* A **Snapshot** is **a** **specialized** **form** of **constraint** **that** **can** **serve** as **( **or** **contribute** **to** **)** a **Boundary**, **but** **is** **not** **the** **only** **way** **to** **define** one **. **
* A **Boundary** **MAY** **reference** a **snapshot** **`snapshot` **; **MAY** **define** **raw** **event** **windows** **with** **`event_ranges` **; **MAY** **define** **state** **filters** **with** **`state_scope` **( **independent** **of** **a** **snapshot** **or** **with** **it** **)**. **
* A **Snapshot** **object** **implicitly** **fixes** a **state** **membership** **set** **( **constrained** **by** **`scope` **+ **`as_of` **) **. ** A **Boundary** **that** **sets** **`snapshot` ** **inherits** those **membership** **and** **temporal** **commitments** **( **`as_of` **, ** **filter** **semantics** **)** **. **
* A **Boundary** **without** **`snapshot` ** **MUST** **define** **all** **required** **constraints** **explicitly** **( **e.g. ** **per-source** **heads** **+ ** **state** **filters** **)** in **a** **manner** **verifiable** **for** **the** **claim** **. **

**Constraint:** Implementations **MUST** **not** **assume** **snapshot-** **pinned** **boundaries** and **unpinned** **range** / **state_scope**- **only** **boundaries** are **interchangeable** **for** **the** **same** **View** **without** **a** **proof** **( **e.g. ** **showing** **the** **same** **state** **set** **and** **event** **windows** **)**. **

### 0.8 State and event verifiability profiles (normative)

*These **verifiability** **profiles** (**minimal** / **auditable** **state** **wrt** **events**) are **orthogonal** **to** **Part** **I** **capability** **profiles** **( **e.g. ** **`relay.profile.social` **, ** **§2.1** **). ** A **single** **deployment** **MUST** **declare** **both** **when** **both** **axes** **apply** **. **

Implementations **MUST** **declare** **at** **least** **one** **verifiability** **profile** **( **e.g. ** on **identity** **, ** **capabilities** **, ** or **a** **well-known** **document** **)** **. **

| Profile | Requirement |
| --- | --- |
| **`relay.profile.minimal`** | **State** **MAY** **exist** without **a** **complete** **verifiable** **event** **history** on **that** **actor** ( **e.g. ** **migrated** **or** **origin**- **sourced** **only** **)**. ** |
| **`relay.profile.auditable`** | **State** **MUST** be **derivable** **( **reconstructable** **)** from **a** **finite** **set** of **Event** **objects** **the** **client** **can** **fetch** and **the** **protocol** **rules** **allow** for **the** **state** **type** **. ** |

**`relay.profile.auditable` (additional rules):**

* **State** **MUST** **include** **parent** **( **e.g. ** **`prev` **- ** **linked** **or** **schema-specific** **)** **or** **equivalent** **references** such **that** **verifiers** **MAY** **reconstruct** **or** **verify** **derivation** **from** **events** **( **as** **defined** for **the** **state** **type** **)**. **
* **Verifiers** **MUST** be **able** **to** **reconstruct** **the** **state** **or** **reject** **as** **non-auditable** when **reconstruction** **fails** **( **per** **local** **policy** **)**. **

**Clients** **MUST** **respect** **the** **declared** **profile** when **deciding** **whether** **to** **show** **“** **verified** **”** **derivation** **vs** **“** **origin**- **attested** **only** **”** **. **

**v1.4** extends **v1.3** (`Relay-Stack-Spec-v1-3.md`) with **additive** normative material for two protocol capabilities—**action events** (agent request/commit/result) and **deterministic feed definitions** (portable, verifiable views)—and **non-normative** ecosystem notes. Unless this document **explicitly** changes a rule, **v1.3** (and, where not superseded, **v1.2**) semantics **remain in force**. v1.4 **MUST** be read as a **superset** of the v1.3 body: **unchanged** sections (markings below) are **inherited** verbatim in intent; **new** or **replaced** paragraphs are **normative** where they use **MUST** / **MUST NOT**. Implementations that claim **v1.4** interop **MUST** support the **MUST** rules in **§4.3.1**, **§8.1**, **§13.1 (v1.3)**, **§13.4 (v1.4)**, **§11.1 (v1.4)**, **§17.10–§17.11 (v1.4)**, and **Appendix C (including v1.4 rows)**. Implementations that do **not** implement action or feed features **MUST** still **treat** unknown log `type` / state `type` as **optional** and **MUST** preserve **signed** data without corruption (**§10.2**, **§22.4**).

## Status, versioning, and normative scope (v1.4, v1.5 optional)

* **v1.1 → v1.2** (unchanged): interoperability and correctness upgrade; v1.2 is **backward compatible** with v1.1.
* **v1.2 → v1.3** (inherited): **additive**; **`channel_id` minting** (§4.3.1) is **normative** for v1.3-minted channels; **legacy** opaque ids **MAY** coexist. See **v1-3** spec for full delta.
* **v1.3 → v1.4** (this revision): **additive** for the wire and state. **Action events** and **feed definitions** introduce **new** log `type` values and a **new** state `type` (`relay.feed.definition.v1`) with **registry-backed** **reduction functions** (§17.10). No change to **§4.3** `actor_id` model, **dual** log/state model, or **§10.4** (no global consensus). Clients that **do not** implement v1.4 features **MUST** **degrade** per **§22.4** (no silent corruption) and **MUST** **not** be required to trust indexers for feed **correctness**—**§17.11** is **recompute-from-sources** for verifiers.
* **Normative (required for interoperability):** Part I in this document — v1.3 rules **plus** the **§13.4**, **§11.1**, **§17.10–§17.11**, and **Appendix C (v1.4 rows)** **MUST**s where a deployment claims **v1.4**.
* **Non-normative (reference only):** Part II and Part III, except that **new** v1.4 normative **checklist** rows in **Appendix A** apply to **Part I** claims. Implementations **MAY** deviate in Parts II–III.
* **v1.4 → v1.5 (this document, additive only):** additive; three optional extensions: private action addressing (§13.5), envelope expiry for ephemeral/revocable log events (§10.5), routing hint in capabilities (§8.1 amendment). **No** **new** **profile** **identifier** **is** **required**—these are **optional** **extensions,** not **new** **relay** **profiles. **Deployments** **that** **enable** a **v1.5** **optional** **extension** **MUST** **satisfy** the **MUST/SHOULD** **language** **in** the **cited** **§** **for** **that** **extension** **. **

### Addressed in v1.3 (inherited; unchanged here)

| Topic | v1.3 deliverable | Where |
| --- | --- | --- |
| **Global channel identity** | **`relay.channel.genesis.v1`**: canonical **genesis** document; `channel_id` = `relay:channel:` + **multihash(SHA-256)** over **UTF-8** bytes of **canonical JSON** of genesis. | **§4.3.1** |
| **Capability advertisement** | **Origin capabilities document** — **`GET /.well-known/relay-capabilities.json`** and optional `origins.capabilities` in the identity document. | **§8.1** |
| **Portable membership** | **`relay.membership.witness.signed_v1`:** channel-**owner**–signed **witness**; **§13.1** defines verification. | **§13.1** |
| **Registry / log `data` (v1.3 types)** | **Appendix C (normative):** `data` shapes for **`membership.add`**, **`membership.remove`**, **`trust.revoke`**, **`state.revoke`**. | **Appendix C**, **§10.2** |

### Addressed in v1.4 (new in this revision)

| Topic | v1.4 deliverable | Where |
| --- | --- | --- |
| **Agent interaction (signed steps)** | Log types **`action.request`**, **`action.commit`**, **`action.result`**: requester → **commit** → **result** on defined logs; **commitment_hash** (SHA-256) binds **request** to **commit**; all steps **verifiable** with **Ed25519** per **§7** / log rules **§10**. | **§13.4**, **Appendix C (v1.4 rows)** |
| **Portable deterministic feeds / ViewDefinition** | **State** type **`relay.feed.definition.v1`** (2.0 **ViewDefinition**): `sources` + `reduce` + optional `params`. **Reducers** are **versioned** identifiers, **pure** and **deterministic**; v1.4 **requires** **`relay.reduce.chronological.v1`** and **`relay.reduce.reverse_chronological.v1`**; others **§22** / extension registry. | **§11.1**, **§17.10** |
| **Verifiable feed output** | **Clients (and any honest mirror)** **MUST** be able to **recompute** the feed output from **definition + fetched** logs/state; origin/indexer is **not** a trust root for “correct order” of a feed—**recompute** is **§17.11**. **§11.1** / **§17.10**–**§17.11** **define** a **logical** **recompute** **/** **audit** **boundary** **(advisory** **envelope) ** for **strong** **cross-deployment** **audit** **vs** **“** **latest** **fetched** **”** **local** **UIs. **| **§11.1,** **§17.10,** **§17.11** |
| **Ecosystem notes (non-normative)** | **Why** these primitives exist (agents, indexer accountability, composability) — **not** a behavioral **MUST**. | **§23.3** |

### Addressed in v1.5 (additive in this document)

| Topic | v1.5 deliverable | Where |
| --- | --- | --- |
| **Private** **action** **addressing** | **Optional** **extension** **`relay.ext.private_action.v1`**: **tag** (SHA-256 of **§4.1** **canonical** **`relay.action.tag.v1`**) + **`encrypted_payload` **;** **plaintext** **`target`** **omitted** **;** **§13.4** **commitment** on **decrypted** **payload** **per** **§13.5** **. ** **Optional,** **advisory** **UX** **discovery** **( `GET …/private-actions` **, **§8.1** **`private_action_hints` **, **§18** **`PRIVATE_ACTION_HINT` **) **is** **not** **a** **trust** **root** **(§13.5) **. **| **§13.5,** **§8.1,** **§17,** **§18** |
| **Envelope** **expiry** **for** **ephemeral**/**revocable** **log** **events** | **Optional** **`expires_at` **(RFC** **3339,** **§4.1.1.1) **;** **fetch/relay/append** **rules** **(§9** **exception,** **§10.5) **. | **§9,** **§10.5,** **§16.3,** **§17.3–§17.4,** **§18.3** |
| **Routing** **hint** **in** **capabilities** **(§8.1** **amendment) **| **Optional** **`routing_hint`** on **`relay.origin.capabilities.v1` **( **`region`**, **`relay_profiles`**, **`priority` **) **. | **§8.1** |

### Deferred to a future core revision (v1.5+)

| Topic | Notes |
| --- | --- |
| **Additional normative** `data` / reducer rows promoted from **`registry/`** | Continues **§22** process; v1.4 adds **core** **Appendix C** **action.***  **and** **two** **required** **reducers** only. |
| **Stricter** separation of **identity** vs **capability** validation | v1.3 / v1.4 **unchanged** here. |
| **Canonical channel policies as signed documents** (optional) | e.g. normative `policy` hash; not in v1.4. |
| **Closed** **enumeration** of **`data.action` **/ **`action_id` **(purely** **convenience) **| **v1.4** **§13.4** **adds** **`data.action_id` **as** the **default** **canonical** **interoperable** **action** **identifier;** **a** **global** **“** **all** **valid** **action_id** **values** **”** **list** **remains** **optional;** **Relay** **core** **MUST** **not** require **a** **centrally** **curated** **registry** to **use** an **`action_id` **(see** **§8.1,** **§22) **. ** |
| **Nested feed `reduce` + outer `reduce` composition** (edge cases) | v1.4 **clarifies** the **default** in **§17.10**; **further** **registry** work may **tighten** **merge** when **reducers** **differ** **in** **subtle** **ways**. |
| **Materialized feed outputs; cross-deployment feed audit** | **v1.4** **§11.1** / **§17.11** **document** a **logical** **recompute** / **audit** **boundary** ( **`definition_object_id`**, **`definition_version`**, **`as_of`**, **`source_heads` **) **as** **advisory,** **plus** a **SHOULD-** level **tag** for **exports**; **no** **MUST-** level **on-the-wire** **envelope** for **every** **cache** (that **would** **overconstrain** **sharing**). **A** **v1.5+** or **profile-** **gated** **normative** **wire** **format** **MAY** **pin** a **subset** of **fields**; **strict** **cross-deployment** **tooling** **may** still **need** **OOB** **agreement** on **head** / **snapshot** **encoding** **where** **origins** **differ**. |

### Deferred to a future core revision (v1.6+)

| Topic | Notes |
| --- | --- |
| **ECIES** key **derivation** **details** **for** **private** **action** ( **`registry/relay.ext.private_action.v1`**) | **Ciphertext** **format,** **X25519** **or** **successor** **agreement-key** **derivation** **from** **Ed25519,** KDF, **AEAD. **v1.5** **§13.5** **defines** **tag** and **`encrypted_payload` **;** **full** **wire** **and** **crypto** **details** **deferred** **(see** **§13.5) **. |
| **Merkle-** **or** **SNARK-** **batched** **membership** **witnesses** (channels) | v1.3 **§13.1** **signed** **witness** **+** **O(n)** log **walk;** very **large** **channels** **may** **need** **compact** **proofs. |
| **Merkle-** **provable** **expiry** **receipts** | **Proving** **to** a **third** **party** **that** **an** **event** **was** **validly** **expired** **(or** **omitted** **as** **expired** **per** **§10.5) ** **rather** **than** **withheld;** **v1.5** **enforces** **operational** **expiry** **only** **. **|
| **Normative** **`routing_hint` **. **`region` **string** **taxonomy** | **Standardizing** **region** **slug** **values** **for** **cross-** **deployment** **interoperability** **;** **deferred** to **v1.6+** or **a** **companion** **registry** **entry. **§8.1** **v1.5** **is** **advisory** **only** **(operator-** **defined** **slugs) **. ** |

### Deferred notes (v1.4 → v1.5+, non-normative)

*Implementation and ecosystem expectations tied to **deferred** rows. **MUST** **not** be cited **instead of** normative **§** for the same behavior.*

* **`data.action` **/ **`data.action_id` **fragmentation: **v1.4** **normatively** **adds** **`data.action_id` **(§13.4) **as** the **wire**-**level** **canonical** **action** **identifier** **for** **interoperable** **classification** **when** **present. **`data.action` **alone** (no **`action_id` **) **remains** **ecosystem-****local** **/ ** **legacy** **per** **§13.4. ** The **deferred** **row** on **a** **closed,** **curated** **global** **enumeration** **(optional) ** and **further** **registry-**backed** **names** **(§22) ** **is** about **convenience** **and** **inter-**ecosystem** **catalogs,** **not** **a** **prerequisite** **to** **using** an **`action_id` **. **Verifiers** **MUST** **treat** **differing** **signed** **bytes** as **differing** **commitment** **inputs** **(§4.1,** **§13.4) **. **

* **Outer feed nesting a mutable `kind: "feed"` source:** A **nested** **`relay.feed.definition.v1`** **can** **gain** a **new** **`version`** **between** **two** **recomputes** of an **enclosing** **feed** while **the** **enclosing** **definition** **`version`** **(and** **`reduce` / `params`**) **and** **all** **non-**`feed` **sources** **(e.g.** **`actor_log`**) **are** **unchanged** **. **The** **outer** **feed**’s **output** **can** **still** **change**—**correct** **per** **§11.1** / **§17.10** **(nested** **state** **is** **fetched** **at** **recompute** **time**)** **. **That** **is** **neither** **reducer** **non-determinism** **nor** a **bug** **in** the **outer** **definition** **;** **it** **is** **independent** **mutation** of **nested** **state. ** *Non-normative:* **feeds** **that** **nest** **mutable** **`kind: "feed"`** **sources** **should** **expect** **materialized** **output** to **vary** when **only** a **nested** **definition** **revision** **changes** **.

* **SHOULD-level export tagging and cross-deployment feed-audit / timeline-diff tooling:** v1.4 **adds** the **recompute** **/** **audit** **boundary** **shape** in **§11.1** (with **§17.10**–**§17.11) ** and **keeps** **SHOULD-** level **tagging** **(not** **MUST) **; **deferred** **row** *Materialized feed outputs; cross-deployment feed audit* **remains** **for** a **possible** **future** **normative** **wire** **envelope** **or** **strict** **head** / **snapshot** **taxonomies. ** **Tooling** **across** **heterogeneous** **deployments** **may** still **require** **out-of-band** **agreement** **on** **which** **boundary** **fields** **are** **exchanged,** even **with** the **v1.4** **advisory** **object** **(flexible** **caching** **/** **sharing** **vs** **universal** **on-wire** **MUST) **. **

* **Private** **action** **addressing,** **ECIES,** **and** **the** **registry** **(v1.5,** **deferred** **to** **v1.6+** **for** **full** **normative** **crypto) **: **v1.5** **§13.5** **normatively** **requires** the **`relay.action.tag.v1` **object** **,** the **`tag` **hex,** and **an** **`encrypted_payload` **string** **,** and **deferred** **ECIES** **(or** **successor) **envelope** **/ **KDF** **/ **AAD** **to** **registry/relay.ext.private_action.v1` **(see** **v1.6+** **deferred** **table) **. **Core** **interop** **assumes** **Ed25519** **identity** **keys** **per** **§7.1** **and** **SHA-256** **/ **§4.1** **as** **cited** **in** **§13.5** **. **

### Open interop questions and known limitations (v1.4, non-normative)

*Ecosystem and historical commentary only. It **MUST** **not** be cited **instead of** the normative **§** for the same topic. If one paragraph here appears “softer” than a **MUST** elsewhere, the **MUST** **wins**.*

* **`data.action` / `data.action_id` interop (normative: §10.2, §13.4, §22; status deferred).** *Commentary only:* with **`data.action_id` **present,** **v1.4** **gives** **a** **single** **normative** **string** for **“** **which** **action** **”** for **receipt-** and **conformance-****class** **questions;** **`data.action` **(without **`action_id` **) **is** **ecosystem-local** / **legacy** and **is** **not** a **portable** **interoperable** **id **(see ** §13.4 **) **. ** This **does** **not** **relax** **§13.4** **(parse,** **sign,** **and** **hash) **. **

* **Nested `kind: "feed"` / outer `reduce` (normative: §17.10, §11.1 table).** *Commentary only:* v1.4 **requires** **nested** **feeds** **to** **be** **fully** **reduced** **before** **outer** **merge** **(§17.10) **. **Tighter** **(outer,** **inner) ** **pair** **merge** **rules** for **all** **reducer** **combinations** **may** still **land** in **the** **registry** **or** a **future** **revision** **. **

* **Async / incomplete fetches (normative: §13.4, “Partial fetch and visibility”).** *Normative anchors:* a **verifier** **MUST** **fetch** **`action.request`**, **`action.commit`**, and **`action.result`** per **§13.4**. *Summary, not a substitute:* **§13.4** **is** **authoritative**; incomplete fetches ⇒ **not yet** verifiable for receipt-class claims; do **not** conflate **“pending fetch”** with **invalid** signatures.

* **Feed recompute / audit boundary (normative: §11.1, §17.10–§17.11; advisory envelope).** *Commentary only:* **v1.4** **names** a **minimal** **logical** **envelope** **( `definition_object_id`**, **`definition_version`**, **`as_of`**, **`source_heads` **)** **and** **the** **rule** “** **same** **definition** **+** **same** **boundaries** **” ** **⇒** ** **same** **reducer** **output** **for** **correct** **implementations**; **omitting** **boundaries** **does** **not** **break** **local** **UIs** **but** **limits** **strong** **cross-deployment** **audit** **claims** **(see** **deferred** **row;** **normative** **text** **§11.1,** **§17.10,** **§17.11) **. **

* **Feed definition as mutable state; “feed audit” tooling (normative: §11.1, §16 `version`, §17.11; SHOULD in §11.1; deferred table).** *Commentary only:* **a** **single** **MUST-** level **on-the-wire** **envelope** for **every** **export** **remains** **out** **of** **scope;** see **recompute** **boundary** **bullet** **above** and **deferred** **row** for **v1.5+** **candidates** **(a** **normative** **envelope) **. **

* **`agent_params` trust and size (normative: §4.1, Appendix C, §13.4 SHOULD, §23.2).** *Commentary only:* the commitment **binds** `agent_params` bytes, not their reasonableness or off-protocol use. **See** **§13.4** for **SHOULD-** level guidance on **compact** objects; **origins** **MAY** **reject** abnormally **large** `agent_params` (or over-deep nesting) before applying the commit event.

* **Recompute cost (normative: §17.11, including “Scalability and what the MUST does not require”).** *Commentary only:* the **MUST** is **possession** of a **correct recompute** **procedure** when **auditing**; not **per-frame** full recompute. **§17.11** **states** that **caching** / **spot-checks** make assurance **probabilistic** in practice. **Strong** **audit** **claims** **use** the **recompute** **/** **audit** **boundary** **(§11.1) ** **when** **peers** **compare** **outputs. **

* **Unsolicited `action.request` (normative: §13.4, §23.2).** *Commentary only:* lone `action.request` does not imply target consent; see **§23.2** and **§13.4** for verifier **MUST** **not** **infer** relationships from an unanswered request.

---

## Part I — Truth and View: wire protocol + HTTP APIs (normative, v1.4; v1.5 optional: **§8.1** `routing_hint`, **§10.5** `expires_at`, **§13.5** private `action.request`; **body** carries v1.2 / v1.3 except where amended)

*Relay 2.0* **Part I** specifies how **Identity**, **Event**, **State**, and **ViewDefinition** objects are **signed**, **hashed**, **classed** (**§9**), **transported** over **HTTP** (**§16**–**§17**), and **verified**. The v1-era field names (`prev`, `ts`, state `version`) remain the interoperable **wire**; map them to **Event**/**State** as in **§0.1**.

### 1. Protocol roles

Relay defines five interoperable roles:

* **Actor Origin**: authoritative publisher for an actor's mutable state and identity snapshots
* **Feed Host**: serves signed log segments and state snapshots over HTTP
* **Fast Relay**: low-state WebSocket service for live distribution
* **Mirror Node**: caches signed public artifacts for resilience
* **Indexer**: builds search, channel, and discovery views from public artifacts. Indexers can become **power centers** for discovery; deployments that expose an Indexer role **SHOULD** also expose the **transparency** endpoints in **§17.9** so clients can see **policy** and **sources** (ranking inputs) without scraping HTML.

A single deployment may implement one or more roles.

### 2. Relay profiles and interoperability (v1.2, normative)

Relay defines **conformance profiles** so that partial implementations can claim interoperable support without implementing the entire Part I at once. Implementations **MUST** declare which profiles they support (see **§2.1** and the **`relay_profiles`** field on the **identity** document, **§8**). Claiming “Relay v1.2 interop” in marketing or security contexts **MUST** be consistent with the declared profiles and the **interoperability baseline** (**§2.5**).

#### 2.1 Profile identifiers

Implementations **MUST** list supported profile URIs. Example on the **identity** document (see **§8**):

```json
"relay_profiles": [
  "relay.profile.minimal",
  "relay.profile.social"
]
```

* **`relay.profile.minimal`:** smallest wire subset for basic social following and state (**§2.2**).
* **`relay.profile.social`:** **minimal** + labels, channels, WebSocket relay, trust attestation objects (**§2.3**).
* **`relay.profile.full`:** **social** + revocable, ephemeral, guardian recovery UX, and **`ext_required`** processing (**§2.4**).

#### 2.2 `relay.profile.minimal`

An implementation that claims **`relay.profile.minimal` MUST** support **all** of the following (normative; ties to this document are cited):

* Identity document resolution (**§8**)
* Canonical JSON, hashing, and signatures: **§4**, **§4.1**–**§4.1.2**, **§4.2**, **§4.3**, **§7.1** (Ed25519)
* **SHA-256** for content-addressed ids (**§4.2**)
* **RFC 9421** HTTP message signatures for origin APIs (**§19**)
* **State** publish and fetch APIs (**§16**; **PUT/GET** state paths in **§16**)
* **Log** append and fetch APIs (**§16**; **POST** log, **GET** log head/range)
* **Conflict** detection and **§5** (including `conflict_detected`, **§21**)
* **Snapshot** fetch (**§17.6**; **GET** `.../snapshots/latest` and snapshot semantics, **Part II §29**)
* **MVP** log `data` and **`target` rules** for required event **types** (**Appendix B**, **§10.2**, **§10.2.1**)
* **Required** log **event** `type` values (must be accepted for append, fetch, and correct `data` / `target` handling): **`follow.add`**, **`follow.remove`**, **`state.commit`**, **`state.delete`**, **`key.rotate`**

#### 2.3 `relay.profile.social`

An implementation with **`relay.profile.social` MUST** support **all** of **`relay.profile.minimal`**, and **additionally**:

* **Label** objects and APIs (**§12**, **§17.8**)
* **Channel** objects and channel views (**§13**, **§17.7**)
* **WebSocket** relay protocol (**§18**, including **security** in **§18.4**)
* **Trust attestation** objects and **§6**

#### 2.4 `relay.profile.full`

An implementation with **`relay.profile.full` MUST** support **all** of **`relay.profile.social`**, and **additionally**:

* **Revocable** and **ephemeral** content and APIs where exposed (**§20**)
* **Guardian recovery** workflows on the **origin** (reference: **Part II §34**; client UX in **Part III**)
* **Extension** model including **`ext_required`**: **§22.3**–**§22.5**

#### 2.5 Interoperability baseline (practical)

Two independent implementations can claim **practical** Relay v1.2 interoperability with each other **if and only if** both **declare** and **implement** **`relay.profile.minimal`**; the full requirement set is **§2.2** (single source of truth—do not duplicate that list here). Profile strings **MUST** be declared in **`relay_profiles`** on the identity document (**§8**) for discoverability.

### 3. Transport model

Relay uses:

* **HTTPS/HTTP** for durable fetch, publication, snapshots, and object retrieval
* **WebSocket** for live sync, notifications, and low-latency fan-out
* **Optional P2P transport** as a compatible mirror/fetch layer, not a required core transport

HTTP is the source-of-truth access layer. WebSocket is acceleration only.

### 4. Serialization, canonicalization, and hashing

All protocol objects MUST use canonical JSON for hashing and signing.

#### 4.1 Canonicalization (normative, unchanged in substance from v1.1)

The following are **REQUIRED** for a canonical serialization:

* UTF-8 encoding
* object keys sorted **lexicographically** (per Unicode code point, byte-wise where applicable for JSON)
* **Boundary** **( ** `boundary` ** **objects, ** **§0.6** ** ) **: ** in ** **addition, ** ** follow ** the ** **normative** ** **array** ** and ** **key** ** **conventions** ** in ** **§0.6.1** ** so ** that ** two ** ** semantically** ** **equal** ** **boundaries** ** **hash** ** the ** same **( **on ** **top** ** of ** **this** ** **list** ** ) **. **
* no insignificant **whitespace** (no variable pretty-printing)
* **numbers** per **§4.1.1**; **string** text values per **§4.1.2** where they participate in signed/hashed objects
* the **signature** field (and other designated outer signature fields) **excluded** from the input to `object_id` and signing transforms as specified in this document

#### 4.1.1 JSON numbers and precision (v1.2, normative)

To avoid cross-language hash/signature drift (`1` vs `1.0`, exponent forms, float rounding), the following apply to **all** bytes fed to signing and to **object_id** computation:

1. **No exponent notation:** a JSON `number` **MUST NOT** be serialized with `e` or `E` (e.g. `1e3` and `1E-3` are **invalid** in canonical form).
2. **Integers only for JSON `number`:** any numeric value that is a whole number **MUST** be a JSON `number` with **no** `.` in the text (e.g. `42`, not `42.0` or `1.0`). Lexically, the entire token (optional leading `-`, then digits) **MUST** match:  
   `-?(0|[1-9][0-9]*)`  
   (This implies **no** leading zeros on multi-digit values except a lone `0`.)
3. **No JSON `number` for true fractions or irrationals** in protocol fields: values that are not **mathematical integers** (money, ratios, “1.5”, IEEE floats) **MUST** be carried as:
   * a **JSON string** holding a **decimal** with no exponent (e.g. `"0.1"`, `"3.14159"`) and **no** redundant leading zeros in the **integer** part, **or**
   * a **JSON integer** in a **defined smallest unit** in the object schema (e.g. “nanocoins” as a `uint64`), **or**
   * an **extension-registered** encoding.
4. **Strings for precision-sensitive** amounts in core objects **MUST** use the decimal string pattern above; implementations **MUST NOT** round-trip them through a binary float before hashing.
5. **max precision** for string decimals is not capped in v1.2, but a given object schema **MUST** document allowed scale; extensions **MUST** reject out-of-scale values for interop.

If an implementation cannot represent a value without violating these rules, it **MUST** reject the object (or use an allowed string/integer form) before signing or hashing.

#### 4.1.1.1 Instants and timestamps (v1.2, normative)

* **This is not a “fraction” issue:** all **time instants** in **protocol** objects (including log **`ts`**, state **`created_at` / `updated_at`**, attestation **`ts` / `expires_at`**, identity **`updated_at`**, and any other core- or registry-defined field whose name ends in **`_at`**, **`_ts`**, or is explicitly documented as an instant) **MUST** be **RFC 3339** **strings** (e.g. `2026-04-21T00:00:00Z` or with a numeric offset). **Unix epoch in a JSON `number` (seconds or milliseconds)** and **stringified epoch digits** are **invalid** for these fields in v1.2 interop—using them will **not** match peers’ canonical objects.
* **Calendar dates** (no time of day) **MUST** still use an RFC 3339 **full** instant at **00:00:00Z** for that day unless an extension defines a `date` string pattern.

#### 4.1.2 JSON strings, Unicode, and escaping (v1.2, normative)

* **Encoding:** the outer document **MUST** be **UTF-8** (as required of JSON in interchange).
* **Unicode normalization:** for **all string values** that are part of a **signed** or **hashed** object, implementations **MUST** apply **[Unicode NFC](https://www.unicode.org/reports/tr15/)** (Canonical Composition) **before** computing **digests**, **before** **signing**, and **before** **signature verification** that recomputes canonical signed material, so that **visually** identical user text in different NFD vs NFC **does not** yield different **`object_id`**s or broken cross-implementation verification. (This is **not** optional at the base layer: two compliant implementations **MUST** agree on the bytes hashed.) UI **MAY** still apply locale rules for **display** only; the **wire and crypto** canonical form for those strings is **NFC**.
* **JSON escaping** (on the wire, after NFC where applied): string contents **MUST** be serialized with **[RFC 8259](https://www.rfc-editor.org/rfc/rfc8259)-compatible** escaping (`\"`, `\\`, `\u` where required) as produced by a conforming JSON generator; the **byte sequence** fed to a digest is the **minimally** escaped UTF-8 JSON for that value **after** the rules above, without optional pretty-printing.
* If two different NFC strings are **semantically** equal under another Unicode rule (e.g. compatibility), v1.2 does **not** collapse them; **NFC** is the defined canonicalization for protocol strings.

#### 4.2 Hashing and content addressing (v1.2, required)

* Relay v1.2 **MUST** use **SHA-256** for all **content-addressed** identifiers in the base protocol:  
  `object_id = "relay:obj:" + lower_hex(SHA-256(UTF-8 bytes of canonical JSON(object payload without signature fields)))`  
  (Implementations that use a logical `object_id` such as `post:<uuid>` for some objects are unchanged; this requirement applies to `relay:obj:…` and any operation defined as "content addressed".)
* **Rationale:** wide support, cross-language stability, ecosystem familiarity.
* **Future algorithms:** implementations **MAY** support additional digests (e.g. BLAKE3) via a documented **extension** that carries, for example:  
  `{ "hash_alg": "blake3", "id": "relay:obj:blake3:…" }`  
  Conforming v1.2 clients **MUST** implement and accept **SHA-256**; other algorithms are optional.

**Identifiers (including logical ids where specified):**

* `actor_id`: stable actor identifier, `relay:actor:` + **multihash** (see **§4.3**)
* `object_id`: either logical (e.g. `post:<uuid>`) or content-addressed per §4.2
* `channel_id`: `relay:channel:` + **multihash** (SHA-256, **§4.3**). **v1.3:** new channels **MUST** be minted per **§4.3.1**; **legacy** opaque ids without a verifiable genesis **MAY** persist per deployment policy.
* `label_id`: `relay:label:<hash>`
* `event_id`: `relay:event:<hash>`

#### 4.3 `actor_id` and `channel_id` (multihash) — v1.2, normative for `actor_id` naming; v1.3 `channel_id` minting: **§4.3.1**

A [multihash](https://github.com/multiformats/multihash) value encodes which digest algorithm was used. For interoperability, **independent implementations must agree on the byte string being hashed and on SHA-256** when minting a new `actor_id`.

* **`actor_id` (MUST):** `actor_id` **MUST** be `relay:actor:` + a multihash with **SHA-256** (code `0x12`, 32-byte digest) over the **32-byte raw Ed25519 public key** bytes of the primary active key (the same key material that appears, base64-encoded, in the identity document’s `keys.active` entry; implementations **MUST** decode to raw 32 bytes before hashing). Implementations **MUST NOT** hash alternate encodings (PEM, JWK, base64 string, etc.) for `actor_id` unless a future spec defines a different canonical public-key byte form.

#### 4.3.1 `channel_id` from canonical genesis (v1.3, normative for new channels)

* **`channel_id` (MUST for v1.3-minted channels):** `channel_id` **MUST** be `relay:channel:` + a multihash with **SHA-256** (code `0x12`, 32-byte digest) over the **UTF-8** bytes of **canonical JSON** (per **§4.1** including **NFC** on all string values) of a **`relay.channel.genesis.v1` object** (defined below). Implementations that claim **v1.3** **MUST** use this construction when **creating** a new channel. Any `channel_id` that cannot be **matched** to a **published** genesis object **SHOULD** be treated as a **legacy** (pre-v1.3) identifier for **interop only**.

**`relay.channel.genesis.v1` (required keys):**

| Field | Type | Rule |
| --- | --- | --- |
| `kind` | string | **MUST** be the literal `relay.channel.genesis.v1`. |
| `owner_actor_id` | string | **MUST** be the `relay:actor:…` of the **creating** **owner** (NFC the string). |
| `salt` | string | **MUST** be **base64url** (unpadded) encoding of **≥ 16** **cryptographically random** bytes, unique per **creation** attempt. |
| `title` | string or omitted | If present, **MUST** be **NFC**; **MAY** be omitted. |
| `namespace` | string or omitted | Optional human slug; **MUST** be NFC if present. |
| `created_at` | string (RFC 3339) or omitted | Optional; if present, **MUST** be a **§4.1.1.1** **instant** string. |

* **MUST NOT:** extra keys in the genesis object are **forbidden** for **normative** `channel_id` computation unless the **`kind` string is versioned** (e.g. `relay.channel.genesis.v2` in a future spec). Unrecognized `kind` for minting = **invalid** for v1.3 interop.
* **Uniqueness:** the **`salt` guarantees** distinct ids even when `title` and `owner` match another deployment.
* **Cross-origin:** any two parties that **share the same** **`relay.channel.genesis.v1` JSON** (byte-for-byte after canonicalization) **MUST** compute the same `channel_id`—enabling **mirrors and aliases (§13.3)** to point at a **logically** identical channel key **without** a global registry, provided they agree on the genesis **out of band** (URL, message, or signed distribution).

* **`channel_id` (legacy, pre-v1.3):** deployments **MAY** continue to use **opaque** server-assigned multihash inputs not derived from `relay.channel.genesis.v1` until they rotate channels; v1.3 **does not** assign those ids a second global meaning. See **§23.2** for discovery implications.

### 5. Conflict resolution (v1.2, normative)

#### 5.1 State object conflicts

**Conflict** when: same `object_id` **and** same `version` **and** different payload.

**REQUIRED** client behavior when a state conflict is detected (including on mirror/replica):

* mark the object as **conflicted** in local UI and sync state
* **fetch the authoritative** version from the **origin**; **origin** is **authoritative**
* **replace** local state with the origin’s version
* **retain** optional conflict **metadata** (expected version, local snapshot id, timestamps) for **diagnostics**

#### 5.2 Mirror behavior

* mirrors **MAY** temporarily store multiple conflicting state versions
* mirrors **MUST NOT** present a non-authoritative version as the **authoritative** current state
* mirrors **SHOULD** refetch from **origin** when a conflict is detected

#### 5.3 Log conflicts (forks)

* log forks (divergent `prev` chains) **MUST NOT** be collapsed or merged **silently**
* divergent branches **MUST** be **preserved**; clients and servers that surface history **MAY** show multiple heads or fork metadata

**Client requirements:**

* **MAY** display a fork **warning** and require user choice
* **MAY** prefer the **longest** valid signed chain (policy-dependent)
* **MUST NOT** **discard** signed events that are **valid** under the object’s verification rules (unless overridden by a higher-layer policy, e.g. legal hold, which is out of band to this spec)

#### 5.4 Identity fork resolution (recovery)

If a **recovery key** (or an equivalent recovery path defined in the identity document) signs a **new** identity document that supersedes a prior one:

* the new identity document **supersedes** the previous chain for protocol purposes where recovery authority applies
* clients **MUST** **prefer** the **recovery-signed** valid chain per local validation policy when both appear

#### 5.5 Multi-device versioning (v1.2, non-normative pattern)

The wire rule stays: each successful state write **MUST** use `version = previous + 1` for the same `object_id` (**§16.1**). Two devices that are **offline** can each produce a write they believe is “next,” colliding at the same integer **version** when they come online—**§5.1** applies (origin wins, client reconciles). That behavior is **correct** but can produce **frequent conflict churn** for hot objects.

**Optional** (not required for v1.2 interop): implementations **MAY** attach a stable **`device_id`** (string, e.g. UUID) and a monotonic per-device **`write_seq`** (integer) in **`ext_payload`** or a documented profile for **diagnostics** and **UI** (show “edited on phone vs laptop”). A future core or **extension** **MAY** define a **composite** logical clock (e.g. `(version, device_id)` or Lamport time). This document does **not** replace the integer **`version`** field for **authoritative** ordering at the origin.

#### 5.6 Conflict handling — client guidance (v1.2, non-normative; strongly recommended)

When a state **conflict** is detected (**§5.1**), **clients** **SHOULD**:

* mark the local object as **conflicted** in UI and sync state
* show a **user-visible** notice (e.g. “updated elsewhere”)
* offer **resolution** paths such as: **overwrite** with the **origin** version; **copy** local edits to a **new draft**; show a **diff** when the client can compute one

**Diagnostic metadata:** clients **MAY** store **`device_id`** / **`write_seq`** (as in **§5.5**) alongside conflict records for support and debugging. This is **not** a substitute for **origin** authority.

### 6. Trust attestation model (v1.2, normative)

**Relay 2.0** **Truth** **layer** **Attestation** (claim objects) — **MUST** **not** **override** **signed** **Event** / **State** (**§0.2**).


#### 6.1 Trust signals are not self-validating

Any **trust signal** (including those embedded in an identity or profile surface) **MUST** be backed by a **verifiable** **Trust Attestation Object** (or a normatively equivalent signed record) when “trust” is asserted in any interoperable way. Bare strings in a profile without a corresponding attestation object are **advisory** only.

#### 6.2 Trust attestation object schema

##### 6.2.0 Relay 2.0 `claim` classification (normative, additive)

For **Relay 2.0** general attestation objects (not limited to the **§6.2** v1.2 example), **`claim` MUST** be structured as:

```json
"claim": {
  "category": "trust | snapshot | view",
  "type": "string",
  "payload": {}
}
```

* **`category` MUST** be present and **MUST** be one of `trust`, `snapshot`, or `view` (see the **Attestation (2.0 sketch)** table in **§0.5**).
* **Unknown** `type` string values **within** a **known** `category` **MUST** be handled per **extension** policy; **MUST** default to **ignoring** them **safely** (no false verification).
* **Attestations** **MUST** **not** **override** or **replace** signed **Truth** primitives (**Event**, **State**, **Identity**).

**Mapping from v1.2 (example below):** a verifier **MAY** treat a **v1.2** attestation with top-level `type`, `subject`, and `evidence` as **`claim: { "category": "trust", "type": "<same as type>", "payload": { "subject", "evidence", ... } }`** for 2.0 processing.

A trust attestation is a signed, addressable object. Example:

```json
{
  "id": "relay:attestation:hash",
  "issuer": "relay:actor:issuer",
  "subject": "relay:actor:target",
  "type": "domain_verified|social_vouch|org_verified|continuity_proven|proof_of_personhood",
  "evidence": {},
  "ts": "2026-04-21T00:00:00Z",
  "expires_at": "optional RFC3339 Z",
  "supersedes": "optional relay:attestation:…",
  "sig": "…"
}
```

* **`expires_at` (optional):** if present and in the **past**, the attestation **MUST** be treated as **invalid** for new trust decisions (existing UIs **MAY** show “expired”).
* **`supersedes` (optional):** if present, this attestation **explicitly** replaces the earlier id for display and policy; if absent, newer attestations with the same `(issuer, subject, type)` and a **later** `ts` (and still valid / unrevoked) **SHOULD** be preferred over older ones for the same trust claim.

The protocol does **not** require a **global** trust hierarchy: verifiers **MUST** apply **local** policy to whether an issuer is accepted.

#### 6.3 Verification rules (by type)

| Type | Typical issuer | Verification expectation |
| --- | --- | --- |
| `continuity_proven` | self / origin | consistent timestamps + account/history evidence per implementer |
| `domain_verified` | domain / DNS controller | DNS (or supported) **challenge** bound to the actor or origin |
| `social_vouch` | another actor | **issuer** signature over subject; optional external proof in `evidence` |
| `org_verified` | org actor | org signature + (optional) **trusted org** list in client policy |
| `proof_of_personhood` | external system | **extension-specific** validation rules |

`proof_of_personhood` and other non-core types are **extensible**; clients **MUST** treat unknown `type` values as **unverified** unless the extension is understood.

#### 6.4 Client responsibility

Clients **MUST**:

* verify the **attestation** signature
* verify the **issuer** identity (per normal identity rules)
* apply **local** trust **policy** for allow/deny (this document does not define a global trust hierarchy)

#### 6.5 Revocation and supersession

* **Revocation:** an issuer **MAY** publish a **`trust.revoke`** log event (see **§10**) that references an attestation `id` (and optionally reason). Verifiers **MUST** treat that attestation as **revoked** for new trust decisions after the revoke is accepted (ordering by log). **Compromised issuers** or **withdrawn** social vouches are handled by **revoke** + local policy.
* **Expiration:** see **`expires_at`** on the attestation object; no separate log event is required for time-only expiry.
* **Supersession:** a **new** attestation with a **later** `ts` (and valid signature, not revoked, not expired) **supersedes** a prior one for the same **claim** when verifiers would otherwise show duplicate lines; `supersedes` **MAY** make the link explicit.

#### 6.6 Trust display (v1.2, non-normative)

**Clients** **SHOULD** visually distinguish **verified** attestations, **self-asserted** or **unverified** signals, **expired** attestations, and **revoked** attestations.

**Clients** **SHOULD NOT** give **unverified** signals the **same** prominence (placement, copy, or trust chrome) as **cryptographically verified** attestations when both appear together.

### 7. Envelope

All transmitted signed objects SHOULD be wrapped in a common envelope.

```json
{
  "kind": "identity|log|state|label|channel|snapshot|revocation",
  "schema": "relay/v1.2/<kind>",
  "object": {},
  "sig": {
    "alg": "ed25519",
    "key_id": "key:active:1",
    "value": "base64..."
  }
}
```

#### 7.1 Signature algorithms (v1.2, normative)

* **Interoperable core** signing for envelopes and for identity `keys` entries **MUST** use **Ed25519** (`"alg": "ed25519"` in `sig` and in key records). The **`value`** field **MUST** be the **signature** bytes under that algorithm (encoding per deployment profile, e.g. base64), verifiable with the **raw** public key in the same actor’s identity document.
* **Other algorithms** (e.g. P-256, post-quantum) **MUST NOT** be used as a silent substitute for `ed25519` on the wire. They **MAY** be added only via a **documented `relay.ext.*`** (or a future **core** revision) that defines: wire encoding, how `sig` and keys are extended, and verification for that profile. A consumer that does not support that extension **MUST** treat the object as **unverified** (or **reject** the operation) rather than assert a false positive.
* **Agility / downgrade:** a bare change of `"alg": "…"` without a versioned, registered extension (or a **schema** version bump) **MUST** be **rejected** as invalid for v1.2 interop.

### 8. Identity document schema

**Relay 2.0** **Identity** **primitive** — this section is the **deployed** **HTTP** **/** **JSON** **shape** for **actor** **keys** and **metadata** (**§0.1**).


Endpoint:

* `GET /.well-known/relay.json`
* `GET /actors/{actor_id}/identity`

Schema:

```json
{
  "id": "relay:actor:abc",
  "kind": "user|group|organization|bot",
  "handles": ["@alice.example"],
  "keys": {
    "active": [
      {"id": "key:active:1", "alg": "ed25519", "public": "base64..."}
    ],
    "recovery": [
      {"id": "key:recovery:1", "alg": "ed25519", "public": "base64..."}
    ]
  },
  "recovery": {
    "mode": "guardian_threshold|recovery_key|org_admin",
    "threshold": 3,
    "guardians": ["relay:actor:g1", "relay:actor:g2", "relay:actor:g3"]
  },
  "origins": {
    "identity": ["https://alice.example/actors/relay:actor:abc/identity"],
    "log": ["https://alice.example/actors/relay:actor:abc/log/"],
    "state": ["https://alice.example/actors/relay:actor:abc/state/"],
    "relay_hint": ["wss://live.example/ws"],
    "capabilities": ["https://alice.example/.well-known/relay-capabilities.json"]
  },
  "trust_signals": [
    {
      "type": "continuity_proven",
      "issuer": "self",
      "since": "2026-01-01T00:00:00Z",
      "attestation": "relay:attestation:…"
    }
  ],
  "mailbox": {
    "profile": "optional",
    "endpoints": ["https://alice.example/mailbox"]
  },
  "relay_profiles": [
    "relay.profile.minimal",
    "relay.profile.social"
  ],
  "updated_at": "2026-04-21T00:00:00Z"
}
```

* **`relay_profiles`:** an array of **profile identifier** strings the implementation claims (**§2**). It **MUST** be present for **new** v1.2 interop; empty array means "no claim" (not recommended for public services). **v1.3:** if **`origins.capabilities`** (below) is present, clients **MAY** prefer **capabilities**-advertised **profiles** and limits when they **differ** from `relay_profiles` on a **ticker** cadence, but **MUST** still accept the identity document as a **v1.2**-valid surface.

* **`origins.capabilities` (v1.3, optional):** an array of **absolute HTTPS URLs** pointing at **origin capability** documents (see **§8.1**). The **first** `GET` that returns `200` with a valid `application/json` document **MUST** be used as **authoritative** for **server offers**; later URLs are **fallback** for redundancy.

**Note (largely addressed in v1.3, §8.1):** `relay_profiles` on the identity document **remains** **required** for v1.2 compatibility, but v1.3 **splits** **repeatable, automatable** **server** metadata into **`/.well-known/relay-capabilities.json`** (or URLs under **`origins.capabilities`**) so **capability** documents can **version** independently of **display name** / **bio** changes.

`trust_signals` entries **SHOULD** include an `attestation` (or `attestations`) reference to a **Trust Attestation object** (see §6) when the signal is claimed for interoperability. Legacy inline-only hints (without a resolvable attestation) remain **advisory**.

### 8.1 Origin capabilities document (v1.3, normative)

**Purpose:** publish **server** features, **rate limits**, **supported** `relay_profiles`, and **HTTP/WebSocket** bases without editing the **human** identity document on every deploy.

**Discovery (in order):**

1. **`GET` each URL** in `origins.capabilities` until one returns **200** + valid JSON (first wins), **or**
2. **`GET` `https://{actor_host}/.well-known/relay-capabilities.json`** when `origins.capabilities` is absent (impl **MAY** derive `actor_host` from the **identity** URL or `handles`).

**Document shape (minimum keys):**

```json
{
  "kind": "relay.origin.capabilities.v1",
  "updated_at": "2026-04-21T00:00:00Z",
  "relay_profiles": ["relay.profile.minimal", "relay.profile.social"],
  "endpoints": {
    "identity_base": "https://alice.example/actors/relay:actor:abc/",
    "log_base": "https://alice.example/actors/relay:actor:abc/log/",
    "state_base": "https://alice.example/actors/relay:actor:abc/state/",
    "relay_ws": ["wss://live.example/ws"],
    "view_run": "https://alice.example/view/{id}/run"
  },
  "limits": {
    "max_publishes_per_minute_per_actor": 60,
    "max_ws_subscriptions": 100
  },
  "policy_url": "https://alice.example/terms",
  "routing_hint": {
    "region": "us-east",
    "relay_profiles": ["relay.profile.minimal"],
    "priority": 1
  },
  "supported_action_ids": ["relay.basic.summarize.v1", "acme.agent.extract_entities.v2"],
  "private_action_hints": true
}
```

* **`kind`:** **MUST** be `relay.origin.capabilities.v1` for this revision.
* **`relay_profiles`:** **MUST** be a **superset or exact match** of the **behavior** claimed in the **identity** document’s `relay_profiles` (the identity document is still the **social** source of truth for what the **user** believes they enabled; capabilities **MUST NOT** silently **remove** a profile the identity still claims—use **lower** transport limits only).
* **`endpoints`:** **MAY** **override** path bases if the operator uses a **CDN** or **split** deployment; clients **MUST** use these bases for **fetch** when present.
* **`endpoints.view_run` (Relay 2.0, optional):** when **present**, **MUST** be an **HTTPS** **URL** ** **template** ** for ** the ** **2.0** ** **sketch** ** **`GET` `/view/{id}/run`** ** **surface** **( ** **§0.3** **) **. ** The **`{id}` ** **placeholder** **MUST** **denote ** the **`object_id` ** of ** the ** **`relay.feed.definition.v1` ** ** **ViewDefinition** ** **state** ** ( **same ** **`id` ** as ** **§17.5** ** **fetches** **) **. ** **When** **`endpoints.view_run` ** is ** **omitted** **, ** **clients** **MUST** ** **not** ** **assume** ** a ** **server-** **side** ** **view** ** **runner** ** exists** **; ** **use** ** **recompute** **( ** **§17.10** **–** **§17.11** **) ** **only** **. **
* **`limits` / `policy_url`:** **advisory**; **real** enforcement remains on the origin (`GET /relay/policy`, **Part II**).

* **`supported_action_ids` (v1.4, optional):** **`supported_action_ids` **MAY** be a **JSON** **array** of **zero** **or** **more** **strings,** each **a** **declared **`action_id` **(§13.4) ** the **operator ** ** advertises ** as ** ** supported ** ** on ** this ** ** origin ** or ** ** deployment **. ** Absence ** ** means ** ** no ** ** published ** ** list **; ** it ** ** does ** ** not ** ** imply ** ** the ** ** origin ** ** rejects ** ** other **`action_id` ** values **. ** Relay ** ** core ** ** does ** ** not ** ** require ** a ** ** global ** ** registry ** to ** ** use ** an **`action_id` ** in ** **`action.request` **(see ** ** status ** ** deferred ** ** row) **. ** Profile ** ** documents ** **(§2) ** ** and ** ** extension ** ** specs ** **(§22) ** ** MAY ** ** also ** ** list **`action_id` ** values **; ** ** those ** ** lists ** ** are ** ** likewise ** ** advisory ** ** for ** ** discovery **. **

* **`private_action_hints` (v1.5, optional):** when **`true` **, the **operator ** ** advertises ** the **advisory** **`GET /actors/{actor_id}/private-actions` ** **convenience** **index** for **`relay.ext.private_action.v1` **(§13.5) ** on ** this ** ** deployment **. ** When ** ** absent ** ** or **`false` **, ** ** clients ** ** MUST ** ** not ** ** assume ** ** that ** ** route ** ** exists** **(§17) **. ** The ** ** index ** ** remains ** ** non-** **authoritative; ** see ** **§13.5 **. **

* **`routing_hint` (v1.5, optional):** when **present,** **`routing_hint` **MUST** be a **JSON** **object** with **exactly** these **optional** **keys,** all **as** **defined** **here** **(additional** **keys** **MUST** **be** **ignored** **per** **§22.4** **unless** **a** **later** **version** **of** this **document** **names** them) **: **`region`**,** **`relay_profiles`**,** **`priority` **. **

  * **`region` (optional, string):** an **operator-** **defined** **region** **slug** **(e.g. **`us-east`**,** **`eu-west`**) **. **v1.5** **does** **not** **define** a **normative** **taxonomy;** **see** the **v1.6+** **deferred** **table.
  * **`relay_profiles` (optional, array of strings):** **same** **form** as **the** **top-** **level** **`relay_profiles` **in** this **document** **;** **MUST** **be** a **JSON** **array** of **zero** **or** **more** **profile** **identifiers** when **present** **(e.g. **[`"relay.profile.minimal"`]**) **. **Omission** **or** **empty** **array** **means** **no** **profile**-**specific** **hint** **beyond** the **accompanying** **`region` **(if** **any) **. **
  * **`priority` (optional, non**-**negative** **integer):** **lower** **values** **indicate** **higher** **preference** when **a** **client** **ranks** **multiple** **capability** **documents;** when **present,** **`priority` **MUST** **be** a **JSON** **number** **with** **no** **fractional** **part** and **MUST** be **≥** 0** **(see** **§4.1.1) **;** if **`routing_hint` **is** **present** **and** **`priority` **is** **omitted,** **clients** **MUST** **treat** **priority** as **0** after **JSON** **parsing** **. **

* **`routing_hint` (normative, behavioral):** **`routing_hint` **MUST** **be** **treated** **as** **advisory** **only** **. **Clients** **MUST** **not** **use** **`routing_hint` **(including **`region`**) as **the** **sole** or **definitive** **basis** **for** **identity** **binding,** **key** **trust,** or **any** **security** **decision;** the **identity** **document** **(§8) ** and **the** **rest** **of** **this** **capabilities** **document** **remain** **authoritative** **. **Clients** **MAY** **use** the **`region` **string** from **`routing_hint` **(when** **present) ** to **make** **optimistic** **initial** **routing** **or** **WebSocket** **selection** **decisions** **(e.g. **prefer** **a** **relay** **endpoint** **in** **the** **same** **region) ** before **full** **identity** **/ **log** **resolution** **. **Absence** **of** **`routing_hint` **means** **no** **v1.5** **published** **hint**—**it** **MUST** **not** be **read** **as** **“** **no** **region** **”** **in** **any** **strong** **sense** **(operators** **may** **publish** **region** **only** **in** **DNS** or **other** **OOB** **channels) **. **

**Caching:** clients **SHOULD** cache capabilities with **`ETag`** / **`updated_at`**; **MUST** refresh after **401/403/429** storms or when **identity** `updated_at` advances. **v1.5:** clients **SHOULD** **cache** **`routing_hint` **alongside** the **rest** **of** **the** **capabilities** **document** using **the** **same** **`ETag` **/ **`updated_at` **/ **cache** **invalidation** **rules** **(§8.1) **. **

### 9. Object classes and storage classes

**Relay 2.0** adds a **classification** **discipline** (`content_class` / `storage_class`) on top of **Event** / **State** (**§10**–**§11**).


Every user-visible content object MUST declare both:

* `content_class`
* `storage_class`

Allowed values:

* `content_class`: `durable_public|mutable_public|revocable|ephemeral`
* `storage_class`: `log|state|dual`

Rules:

* `durable_public` MAY be `log` or `dual`
* `mutable_public` MUST be `state` or `dual`
* `revocable` MUST be `state`
* `ephemeral` MUST be `state`

* **v1.5 exception (§10.5, log events only):** a **log** event **(§10) ** with **`storage_class`:** **`log` **MAY** **use** **`content_class`:** **`ephemeral`** or **`revocable` **only** when **`expires_at` **(§10.5) **is** **present** on **that** **event** **;** **all** **§10.5** **MUST**s **MUST** **be** **satisfied** **. **(Without **`expires_at`**, the **row**s **above** **apply** **unchanged: **`ephemeral`** **/ **`revocable` **MUST** **use** **`storage_class`:** **`state` **as** **before** **. **) ** **Envelope** **expiry** **(§10.5) ** **regulates** **what** **is** **“** **active** **” ** **for** **relay,** **listings,** **and** **serving, ** **not** a **claim** that **a** **time-** **expired** **or** **garbage-** **collected** **event** **“** **never** **existed** **” ** as **a** **signed** **log** **fact** **(see** **phases** **(B)–(C) **, ** **§17.4) **. **

`dual` means:

* current renderable version exists as state
* audit/history references exist as log events

#### 9.1 Log/state integration (dual, v1.2)

If an object needs **both**:

* a **current renderable** authoritative state, and  
* a durable **audit** trail on the log,

then `storage_class` **MUST** be `dual`. The system **MUST**:

* keep the **latest** accepted version in **state** storage
* emit a matching **log** event for each state transition that matters for audit, at minimum:

  * **create** → `state.commit`
  * **edit** → `state.commit`
  * **delete** (tombstone / soft delete) → `state.delete`
  * **revoke** (revocable content / key grant) → `state.revoke`

### 10. Event primitive — log event schema (v1.4-1 / v1.5 wire; `relay.event.v1` role)

In **Relay 2.0** an **Event** is an **immutable** **signed** **fact** on an actor log. This section is the normative v1 **envelope** (log event); **`prev`** is the v1 spine (often a single parent).


A log event is immutable and append-only.

For `dual` objects, the **required** interaction between state and log is specified in **§9.1** (e.g. `state.commit` / `state.delete` / `state.revoke` as applicable).

#### 10.1 Genesis and `prev` (v1.2, normative)

* **`prev` type:** the field **`prev`** is either a **string** event id (`"relay:event:…"`) or JSON **`null`**. It is **not** the string `"null"`.
* **Genesis:** the **first** event in an actor’s log chain (the **head** of a new chain) **MUST** use **`"prev": null`**. A receiver **MUST** treat `prev === null` (after JSON parsing) as “no logical predecessor in this chain.”
* **Detection:** clients **MUST** accept well-formed genesis events (`prev: null`). When walking **backward** along `prev`, the walk **stops** at that genesis event. If an actor has **multiple** heads or multiple incompatible genesis chains, apply **§5.3** (forks), not silent merge.

#### 10.2 The `data` object (v1.2 baseline; v1.3 / v1.4 add **Appendix C**)

The `data` object carries event-type–specific fields. v1.2 **normatively** defines the **envelope** (including `type`, `prev`, signatures) and, where referenced elsewhere, a few **cross-links** (e.g. `state.*` in **§9.1**). v1.3 **adds** **Appendix C** (first batch) for **four** additional **`type`** **normative** `data` shapes. v1.4 **adds** **Appendix C** (second batch) for **`action.request`**, **`action.commit`**, **`action.result`**. Types **not** in **Appendix B** or **Appendix C** still **SHOULD** be registered under **§22** and documented before broad interop.

* **MVP (v1.2) — Appendix B:** **`follow.add`**, **`follow.remove`**, **`state.commit`**, **`state.delete`**, **`key.rotate`** as in v1.2.
* **v1.3 — Appendix C:** **`membership.add`**, **`membership.remove`**, **`trust.revoke`**, **`state.revoke`**; implementations that claim **v1.3** interop for these `type` values **MUST** use `data` shapes compatible with **Appendix C** (allow extra keys).
* **v1.4 — Appendix C (action events):** **`action.request`**, **`action.commit`**, **`action.result`**; see **§13.4** and **Appendix C** (v1.4). Implementations that claim **v1.4** for these `type` values **MUST** use compatible `data` and verification rules (**allow extra keys** in `data` only where this document says so).
* **v1.5 —** **`ext` **/ **`ext_payload` **(§22.3) **on** **log** **envelopes** **(optional) **: **a** **log** **event** **MAY** **include** **`ext` **and** **`ext_payload` **in** the **signed** **envelope** **(append** **and** **fetch** **shapes) ** to **carry** **optional** **extensions;** **`relay.ext.private_action.v1` **(§13.5) ** **uses** **this** **path** **. **Unknown** **keys** in **`ext_payload` **follow** **§22.4** **. **
* **Honest general stance:** a conforming implementation **MAY** treat `data` as an open object and validate only what it understands; for unknown `type`+`data` pairs it **MUST** still store and forward the **signed** bytes if it stores the event at all.
* **Divergence risk (remaining):** other event types not covered by **B**+**C** can still **diverge** until registered.

**Types not in Appendices B or C:** there is no **fully specified** `data` schema in the core for those types beyond “JSON object, event-dependent, register before claiming interop.” (See **`registry/`** and **§22**.)

```json
{
  "id": "relay:event:hash",
  "actor": "relay:actor:abc",
  "prev": null,
  "ts": "2026-04-21T00:00:00Z",
  "type": "follow.add|follow.remove|membership.add|membership.remove|label.issue|key.rotate|state.commit|state.delete|state.revoke|channel.accept|channel.remove|trust.attest|trust.revoke",
  "target": "object id; required for some type values (see §10.2.1)",
  "data": {},
  "content_class": "durable_public",
  "storage_class": "log"
}
```

`prev` is `null` for genesis (as above) or, for a non-genesis event, a string `relay:event:…` pointing at the previous event. Non-JSON uses of a literal `"null"` string are **invalid** for v1.2.

* **`expires_at` (v1.5, optional, §10.5):** an **optional** **top-** **level** **field** on **any** **log** **event** **envelope;** **MUST** **satisfy** **§10.5** **when** **present** **(RFC** **3339** **;** **pairing** **with** **`content_class` **;** **fetch/relay) **. **Omit** **the** **key** when **envelope** **expiry** **is** **not** **in** **use** **. **

#### 10.2.1 `target` on log events (v1.2, normative)

* **`follow.add` and `follow.remove`:** `target` **MUST** be present and **MUST** be the `actor_id` (`relay:actor:…`) of the **followed** account. The top-level event **`actor`** is the **follower**; **`target`** is the **followee**. Omitting `target` for these `type` values is **invalid** for v1.2 interop. **`data` remains `{}`** per **Appendix B**—the followed identity is **not** duplicated inside `data`.
* **`key.rotate`:** `target` **MAY** be absent. If present, it **SHOULD** be the `actor_id` of the **identity** being updated (almost always the same as the event **`actor`**). Receivers **MUST** determine which keys are valid from the **signed** log plus the **identity** document **head**, not from `target` alone. Optional **`data.previous_key_id`** (Appendix B) and the published **`keys` list** in identity are the **audit** trail; the **superseded** key **MUST NOT** be used for new signatures once the origin has applied the update (**§7.1**).
* **`action.request` (v1.4):** `target` **MUST** be present and **MUST** be the `actor_id` of the **agent** (responder) the requester is asking to act. The event’s **`actor`** is the **requester**. Omission or wrong `target` is **invalid** for v1.4 interop. **`data` shape:** **Appendix C**, **§13.4**.
* **`action.request` (v1.5, optional** **`relay.ext.private_action.v1`**, **§13.5) **: when **this** **extension** is **in** **use,** **§13.5** **MUST** **be** **satisfied,** including **omission** of **top-** **level** **`target` **(replacing** **the** **v1.4** **`target` **requirement** **for** **that** **envelope) **. **With** **the** **extension** **absent,** the **v1.4** **bullet** **immediately** **above** **applies** **. **
* **`action.commit` (v1.4):** `target` **MAY** be absent; if present, it **SHOULD** equal the **`actor`**, which is the **agent** that commits. The **`data.request_event_id` MUST** identify the **request** event. Signature **MUST** verify under the **agent**’s key (**§7**).
* **`action.result` (v1.4):** `target` **MAY** be absent. **`actor` MUST** be the **agent** that produced the result. **`data.commitment_hash` MUST** match the **commit** step (**§13.4**).
* **Other `type` values:** `target` is **optional** unless **Appendix B**, **Appendix C**, or a **registered** profile says otherwise.

#### 10.3 Time ordering, clocks, and monotonicity (v1.2)

* **`ts` fields** **MUST** be **RFC 3339 strings** (see **§4.1.1.1**; **not** Unix epoch integers). They are used for **replay** windows (**§19.4**), attestation order (**§6**), and **UX**; they are **not** a guaranteed **global** total order.
* **Wrong or skewed clocks** on **clients** are partially bounded by **§19.4** (±5 minutes) for **HTTP** requests; for **log** `ts`, a malicious or bad clock can place events in surprising order. **Remedy (optional but useful):** an **origin** or **verifier** **MAY** treat the **append order** of accepted events on the actor’s log as a **monotonic** secondary ordering when `ts` ties or is suspect, as long as that does **not** **silently** drop valid signatures (**§5.3**). Clients **SHOULD** use **`prev` chain** and origin **head** as the source of truth for history, with **`ts`** as a hint.
* **Recommended ordering strategy (non-authoritative, for implementers):** when presenting or merging a **single** actor log view, **(1)** build the event graph from **`prev`** links and the origin-asserted **head**; **(2)** within one branch, sort by **`prev`** traversal order (append order as returned by the origin is a practical proxy when the API exposes it); **(3)** use **`ts`** only as a **tie-break** or **UX** hint where **`prev`** does not impose an order; **(4)** when **forks** exist, **do not** silently merge—surface branches or follow **§5.3** / client policy. This reduces inconsistent heuristics across clients without pretending **`ts`** is a global total order.
* **Not required:** a server **MUST NOT** be assumed to NTP-synchronize the world; only **local** policy and **§19.4** skew checks apply to HTTP; log times remain **advisory** for ordering when forks exist.

#### 10.4 Log consensus model (v1.2, normative)

Relay defines **no** global **consensus** mechanism for logs.

* Log **chains** are **per-actor** **append-only** histories.
* **Divergent** **valid** log branches (forks) **MUST** be **preserved**; no protocol node **MUST** **delete** a branch solely because another branch exists.
* The **protocol** **MUST NOT** require or **enforce** a **single** “canonical” chain selection for the world—**resolution** is by **origin** authority, **recovery-key** supersession where identity rules apply (**§5.4**), and **client** or **indexer** **policy**.

See also **§5.3** (fork behavior).

#### 10.5 Envelope `expires_at` for log events (v1.5, normative)

**Applies to:** top-**level** log **event** **objects** **(§10) ** when **`expires_at` **is **present** **. **Omission** of **`expires_at` **(or** **JSON** **`null` **where** **a** **string** is **expected,** **treated** **as** **absent) ** means **this** **section** **imposes** **no** **additional** **rules** **(see** **§4.1.1.1) **. **

**`expires_at` **(when **present) ** is **a** **single** **instant** on **the** **envelope; **all **comparisons** **(origin,** **mirror,** **relay) ** use **the** **node**’**s** **parsed** **“** **now** **”** **(UTC-** **normalized, **§4.1.1.1) ** **against** that **instant** **. ** **Implementations** **MUST** **compare** **parsed** **RFC** **3339** **instants,** **not** **raw** **timestamp** **strings** **as** **opaque** **sort** **keys** **. **

**Time-** **expired** (for a **node**’**s** **clock) **: ** the **envelope** **is** **time-** **expired** **when** that **node**’**s** **comparison** **instant** **is** **strictly** **after** the **parsed** **`expires_at` **(same **criterion** **as** **before) **. ** The **name** **distinguishes** this **from** **“** **pruned** **/ ** **absent** **” **(phase** **(C) **) **. **

**Three**-**phase** **model** **(clarifying** **history** **vs** **active** **availability,** **pruning,** **range** **queries,** **and** **mirror** **retention) **: **

* **(A) Acceptance** **(active** **for** **live** **semantics) **. ** **While** the **envelope** **is** **not** **time-** **expired** for **the** **relevant** **node** **(append** **origin,** **GET** **server,** **or** **relay) **, ** **normal** **v1.2**/**v1.3** **append** **, ** **log** **fetch, ** **and** **Fast** **Relay** **`PUB` ** **fan-** **out** **(§16.3, ** **§17, ** **§18.3) ** **apply; ** the **event** **MUST** **be** **treatable** **as** **active, ** **non-** **time-** **expired** **log** **content** **(including** **default** **range** **listings, ** **§17.4) ** **. **

* **(B) Expired** **serving** **(not** **active, ** **but** **MAY** **still** **be** **retrievable) **. ** **After** **the** **envelope** **is** **time-** **expired, ** **implementations** **MUST** **NOT** **treat** **it** **as** **active, ** **fresh** **log** **content** **for** **: ** **(1) ** **Fast** **Relay** **`PUB` ** **—** **MUST** **NOT** **accept** **or** **forward** **/ ** **fan-** **out** **the** **envelope** **(§18.3) **; ** **(2) ** **default** **log** **range** **or** **feed-** **like** **listings** **(§17.4) ** **—** **MUST** **NOT** **include** **it** **unless** the **client** **explicitly** **opts** **in** (e.g. **`include_expired=true` **) **; ** **(3) ** **origin** **append** **(§16.3) ** **—** **MUST** **NOT** **accept** a **new** **append** of **an** **envelope** **that** is **already** **time-** **expired** at **the** **origin**’**s** **clock** at **the** **time** of **the** **POST** **(no** **treating** **it** **as** **“** **current** **” ** **fresh** **input) **. ** For **an** **implementation-** **defined** **retention** **/ ** **grace** **period** **(possibly** **zero) ** after **time-** **expiry, ** **origins** **and** **mirrors** **MAY** **still** **return** the **envelope** **body** when **it** is **addressed** **by** **stable** **event** **id** **(§17.3) **; ** any **such** **200**-**class** (or** **body-** **bearing) ** **response** **MUST** **indicate** **time-** **expired** **status** in **a** **machine-** **readable** **way** **(§17.3) ** so ** **clients** **MUST** **not** **mistake** **it** **for** **“** **current** **” ** **active** **content** **(see** **also** **§20) **. **

* **(C) Garbage** **collection** **/ ** **unavailable** **. ** **After** **the** **implementation**’**s** **local** **retention** **/ ** **garbage-** **collection** **policy** **(following** **phases** **(A) **and **(B) ** **where** **applicable) **, ** the **node** **MAY** **physically** **delete** **a** **time-** **expired** **envelope** **or** **omit** **it** **from** **listings. ** A **pruned** **or** **garbage-** **collected** **id** **is** **not** **served; ** that **is** **independent** **of** the **signed** **fact** that **it** **may** **once** **have** **been** **validly** **appended. ** **Expiry** **means** **“** **no** **longer** **active** **” ** **(operational) **, ** not** **“** **never** **existed** **” ** **(audit** **truth) **—** **verifiers** **with** **a** **copy** **MAY** **still** **validate** **signatures; ** they **MUST** **not** **conflate** **serving** **absence** **(404) ** with **a** **protocol** **denial** **of** **existence. ** **Different** **mirrors** **or** **origins** **MAY** **reclaim** **storage** **on** **different** **schedules; ** that **MUST** **not** be **treated** **as** a **log** **consensus** **violation** **(§10.4) ** **as** **long** **as** each **node** **obeys** **(A) **and **(B) ** **for** **new** **traffic** **. ** **Range** **/ ** **history** **metadata** **(§17.4) ** **and** **fetch** **behavior** **(§17.3) ** **address** **omission** **hazards** **for** **audit** **clients. **

* **Type and shape:** if **present,** **`expires_at` MUST** be an **RFC** **3339** **string** **(§4.1.1.1) ** representing **an** **instant** **in** **time** **. **

* **`content_class` **pairing: **`expires_at` MUST** **not** **appear** on a **log** **event** **with** **`content_class`:** **`durable_public` **. **An** **origin** **MUST** **reject** an **append** **(§16.3) ** of **a** **log** **event** **that** **carries** both **`durable_public` **and** **a** **present** **`expires_at` **(including** **non-**`null` ** string** **) **. **

* **Valid** **`content_class` **for** **envelope** **expiry: **when **`expires_at` **is **present** **(non-**`null` **), **`content_class` MUST** be **`ephemeral` **or** **`revocable` **(see** **§9,** **v1.5** **log**-**only** **exception) **,** and **`storage_class` MUST** be **`log` **. **(These** **events** **obey** **all** **other** **§9** / **§10** **class** **rules** **. **) **

* **By-** **id** **GET** **(§17.3) **: **per** **(B) **, **an** **origin** **or** **mirror** **in** **the** **expired-** **serving** **retention** **window** **MAY** **return** a **time-** **expired** **envelope; ** in **(C) ** it **MAY** **not** **. ** **Normative** **indication** **of** **time-** **expired** **status** is **in** **§17.3 **(headers** **/ ** **wrapper** **object) **. **

* **Range** **queries** **(§17.4) **, **advisory** **query** **parameter: ** for **`GET` **/actors/.../log?...` **, **mirrors** **and** **origins** **MUST** **not** **include** **time-** **expired** **events** in **the** **default** **(no** **parameter) ** result **(phase** **(B) **, ** not ** “** **active** **” **). **A** **request** **MAY** **include** **`include_expired=true` **(boolean) **;** when **this** **name** (or a **documented** **alias) **is **set** **and** the **client** is **permitted,** the **server** **MAY** **include** **time-** **expired** **events** in **the** **result** **(e.g. **audit, ** or **a** **time** **window** **spanning** **the** **cutover) **; ** each **included** **time-** **expired** **envelope** **MUST** **be** **marked** as **time-** **expired** in **the** **response** **(same** **mechanism** **as** **§17.3) **. ** **Support** for **`include_expired` **is** **optional** **. **(Exact** **query** **shape** is **operator**-**defined** **;** **v1.5** **recommends** the **name **`include_expired` **. **) **. ** **Response** **SHOULD** **include** **omission-** **risk** **metadata** **( **`expired_omissions_possible` **, ** **`as_of` **) ** **as** **in** **§17.4 **. **

* **Fast** **Relay, ** `PUB` **(§18.3) **: **a** **Fast** **Relay** **MUST** **not** **accept** **or** **fan** **out** a **log** **envelope** **whose **`expires_at` **(if** **present) ** is **time-** **expired** **(phase** **(B) **) ** for **the** **relay**’**s** **clock** **at** the **time** of **`PUB` ** **handling** **. **(Align** **validity** **with** **§4.1.1.1** **. **) **

* **History** **vs** **active** **availability** **(non-** **normative) **: ** a **time-** **expired** **or** **garbage-** **collected** **envelope** **was** **still** a **valid** **append** **at** **ingestion** **(unless** **rejected** **at** **that** **time) **. ** **Operational** **rules** **govern** **relay, ** **listings, ** **serving, ** **and** **deletion** **(phases** **(B)** **/ ** **(C) **) **, ** not** **whether** a **verifier** **with** **an** **off-** **node** **copy** **can** **check** **hashes** **/ ** **chains. ** **Mirror** **/ ** **origin** **retention** **timing** **MAY** **differ** **without** **breaking** **interop** on **(A) **/ **(B) ** **rules. **

### 11. State primitive — state object schema (v1.4-1 / v1.5 wire; `relay.state.v1` role)

In **Relay 2.0** **State** is the **authoritative** **current** value of a **versioned** object (posts, feed defs, channels, etc.).


A state object is origin-authoritative and versioned.

```json
{
  "id": "post:01J...",
  "actor": "relay:actor:abc",
  "type": "post|profile|channel_config|group_profile|media_manifest",
  "version": 4,
  "created_at": "2026-04-21T00:00:00Z",
  "updated_at": "2026-04-21T00:05:00Z",
  "content_class": "mutable_public",
  "storage_class": "state",
  "reply_to": "post:01H...",
  "channel_refs": ["relay:channel:news"],
  "deleted": false,
  "payload": {},
  "meta": {
    "lang": "en",
    "visibility": "global|channel|followers|custom",
    "mime": "text/markdown"
  }
}
```

`created_at`, `updated_at`, and other instants on state objects **MUST** be **RFC 3339** **strings** (**§4.1.1.1**), not Unix epoch integers.

#### 11.1 ViewDefinition state object (`relay.feed.definition.v1`) (v1.4, normative)

In **Relay 2.0** this state **`type`** is the **ViewDefinition**: it names **inputs** (`sources`), a pure **reducer** (`reduce`), and parameters (`params`) (**§17.10**). **Normative (Relay 2.0):** the **only** **protocol-level** **ViewDefinition** **representation** **is** **`relay.feed.definition.v1`**; **MUST** **not** use an **alternate** **`type` **or **second** **wire** **shape** for **the** **same** **role** (**§0.3**).

A **portable, signed feed specification** is a **versioned** **state** object of **`type`:** **`relay.feed.definition.v1`**. It is **not** the materialized feed output: it is a **deterministic program** (sources + **reduce** + optional **params**) that honest clients (or an indexer that supports v1.4) **MUST** be able to **recompute** per **§17.10–§17.11**. **Relay 2.0** **unifies** **v1.4-1** “**audit** **/ ** **recompute** **ingredients**” with **the** **normative** **Boundary** object (**§0.6**); **MUST** **read** v1.4-1’s **advisory** **envelope** **below** **together** with **§0.6**–**§0.7** for **2.0** **determinism** **and** **snapshot** **interchange** **( **MUST** **not** **mix** **unpinned** and **snapshot-pinned** **boundaries** **without** **an** **explicit** **proof** **— ** **§0.7** **). **Feed definitions are **verifiable** artifacts over HTTP like other state objects: publish via **§16**; validate signatures per **§7**; use **§4.1** canonicalization for any **in-document** **hashing** the definition references.

**Required keys (in `payload` or top-level, depending on your deployment’s state envelope; v1.4 requires these fields to exist in the state object the origin treats as `relay.feed.definition.v1`—they MAY live under `payload` with `type: relay.feed.definition.v1` at the top level):**

* **`sources`:** **JSON array** of **source descriptors** (see below). **MUST** be **non-empty** for a well-formed definition. Order of **descriptors in the array** is **not** by itself a normative “priority order” unless a **reducer** says so; **chronological** reducers in **§17.10** use **per-source** fetches and **merge** rules there.
* **`reduce`:** **string**, **MUST** be a **reduction function id** in the form `relay.reduce.<name>.v<version>`; v1.4 **requires** support for at least **§17.10**’s two **required** **identifiers**. Unknown reducers are **treated** as **not implemented**; clients **MUST** **degrade** per **§22.4** (no silent corruption) and **MUST** **not** assert correct ordering for unknown `reduce` unless they implement the reducer.
* **`params` (optional):** **JSON object**; **MUST** be **canonical** per **§4.1** when **included** in any **signed** or **hashed** sub-object of a **recompute**; reducers **MUST** document which **`params` keys** they read. **MUST** be **pure data** (no **required** **external** fetches as **normative** **core**); see **§17.10**.

* **State `version` (from §11 / §16) as feed-definition revision (informative, but v1.4 SHOULD for shared artifacts):** The **state** object’s **integer** **`version`** (and **`updated_at`**) is the **only** **on-wire** **marker** in **v1.4** that **a** **definition** **body** **changed** **relative** to **earlier** **fetches**. **Deployments** that **export**, **store**, or **cache** a **feed** **output** (e.g. a **“materialized** **timeline**”** **blob** **or** **share** **link** **to** **an** **ordered** **id** **list**)** **SHOULD** **pair** that **output** with the **`object_id` +** **`version` (and** **an** **instant** such as **`as_of` **per** **below)** of the **`relay.feed.definition.v1` state** the **recompute** **used**—so **two** **honest** **peers** **can** **see** **why** **two** **valid** **recomputes** **differ** **(definition** **mutation**). This **is** a **SHOULD** **(not** **MUST**)** in v1.4; **a** **minimal** **logical** **envelope** for **audit** **(below)** is **advisory** **in** **core** **(not** a **MUST-** level **wire** object **);** **profile**-**gated** **or** **future** **revisions** **MAY** **tighten** it **(see** **status** **+** **§17.11**).

* **Feed recompute / audit boundary (v1.4, normative for *claims*):** **v1.4** **distinguishes** (1) **local** / **“** **latest** **available** **”** **rendering,** and (2) **deterministic** **audit** / **comparison** **across** **deployments** **or** **over** **time**. **A** **recompute** is **only** **strictly** **deterministic** for **bit-for-bit** **(or** **reducer-** **equivalent) ** **audit** **when** the **recomputer** and **any** **second** **party** **agree** on **both** the **feed** **definition** **identity** ( **`object_id` **+** **`version` **of** **the** **`relay.feed.definition.v1` ** state ** actually ** **used**) and **explicit** **per-**source **input** **boundaries** (e.g. **actor** log **head** **event** id, **channel**-**scoped** **snapshot** id, **or** **equivalent** **documented** **cut** **/ ** **range) **. ** “** **Same** **definition** **+** **same** **boundaries** **” ** ⇒ ** **same** **reducer** **output** **(§17.10–§17.11) **. ** If ** **boundaries** **are** **omitted** **or** **only** **implicit** ( **“** **whatever** **the** **client** **fetched** **this** ** session **” **) **, **a** **materialized** **list** **MAY** still **be** **valid** **for** **browsing,** **caching,** or **rough** **agreement,** but **MUST** **not** be **claimed** as **a** **strong** **cross-** **deployment,** **deterministic** **audit** **equivalent** **to** **a** **recompute** **with** **an** **explicit** **definition** **+** **per-**source **boundary** **(see** ** §11.1,** ** §17.11) **. **

* **v1.4** **MAY** **(local** **/ ** **interactive) **: **A** **client** **MAY** **recompute** **or** **display** a **feed** from **“** **latest** **fetched** **”** **inputs** without **storing** or **publishing** an **audit** **envelope**; **UIs** **MUST** **not** be **required** **to** **persist** a **full** **boundary** on **every** **render** **(§17.11) **. **

* **v1.4** **SHOULD** **(shared,** **exported,** **audited,** **cached** **artefacts** where **repro** **matters) **: **When** a **feed** **output** **(ordered** **ids** or **a** **projection) **is ** **shared,** **exported,** **or** **cached** for **independent** **verification,** the **holder** **SHOULD** **accompany** it **with** the **definition** **`object_id`**, **integer** **definition** **`version`**, an **`as_of`** **instant** (RFC 3339, **§4.1.1.1**), and **per-**source **boundaries** when **obtainable** **(see** **minimal** **shape** **below) **. **

**Minimal logical recompute / audit boundary (v1.4, document shape — not a required standalone protocol object; advisory):** a **convenient** **JSON** **object** for **naming** the **ingredients** of **a** **reproducible** **recompute** **(§17.11) **:

```json
{
  "definition_object_id": "relay:obj:...",
  "definition_version": 4,
  "as_of": "2026-04-22T19:00:00Z",
  "source_heads": [
    {"kind": "actor_log", "actor_id": "relay:actor:abc", "head": "relay:event:..."},
    {"kind": "channel", "channel_id": "relay:channel:tech", "snapshot_id": "snap:..."}
  ]
}
```

* **`source_heads`:** **each** **element** **MUST** **correspond** to **one** **or** **more** **entries** in **`sources` **(§11.1) **;** **kind** **values** **mirror** **those** **descriptor** **`kind` ** **strings. **`head`** ( **actor** **log) **is **the** **event** id **( **or** **documented** **equivalent) ** that **closes** the **fetched** **window**; **`snapshot_id`** ( **or** **similar) ** is **a** **stable** **label** for **a** **§17.6-** **consistent** **(or** **documented) ** **channel** **/ ** **state** **cut. ** For **`kind: "feed"`** **nested** **sources,** **a** **boundary** **object** **SHOULD** **include** the **nested** **`object_id`**,** **the** **nested** **definition** **`version` ** used, ** and **a** **stable** **cursor** **(e.g. ** **last** **included** **event** id **in** the **fully** **reduced** **inner** **list) ** so ** the ** **outer** **recompute** **(after** **§17.10** **nesting) ** is **replicable. **

**Source descriptor (each element of `sources` MUST be a JSON object with a discriminant and id fields):**

| `kind` | Required keys | Semantics |
| --- | --- | --- |
| `actor_log` | `actor_id` (`relay:actor:…`) | The feed input **MUST** include the **public** **append** **log** for this **actor** (or the union of events the **origin** would return for that log’s `GET` range the client requests under **§17.4**). |
| `channel` | `channel_id` (`relay:channel:…`) | The feed input **MUST** include **all** `state.commit` and other **durable** log events the definition’s **semantics** require from **posts** in that **channel** as exposed by the **origins** the client can reach (subject to **§13** and **indexer** **policy**; **recompute** **MUST** be **read-only**). ** **Channel** ** is ** not ** a ** **single** ** **append-** **only** ** **log** **: ** **resolving** ** “ ** **events** ** **in** ** **this** ** **channel** ** ” ** **requires** ** either ** **( ** **1** **) ** a ** **channel** ** **index** **( **e.g. ** ** **indexer**- **or** ** **owner-** **provided** ** **mapping** ** from ** **post** ** **/ ** **commit** ** **to** **`channel_id` **, ** **§17.6** ** **snapshots** **, ** or ** **equivalent** **) **, ** or ** **( ** **2** **) ** **scanning** ** **relevant** ** **actor** ** **logs** ** and ** **filtering** ** by ** **`channel_ref` **/ ** **membership** ** **in** ** the ** **client** **( ** **expensive** **, ** **asymptotic** ** **cost** ** **linear** ** **in** ** **events** ** **scanned** **, ** but ** **verifiable** ** if ** the ** **scan** ** is ** **complete** ** for ** the ** **agreed** ** **boundary** ** ) **. ** **Index** **- ** **backed** ** **expansion** ** is ** **typically** ** **O**(**changed** ** **set** **) **. ** For ** **audit** **, ** a ** **recompute** ** **envelope** **( ** **§11.1** ** **advisory** ** **boundary** **, ** **§17.11** **) ** **SHOULD** ** **record** ** which ** **strategy** ** was ** **used** ** if ** **cross-** **deployment** ** **comparison** ** **matters** **. ** |
| `feed` | `object_id` (string) | **Logical** `object_id` of a **`relay.feed.definition.v1`** state object (**§11**; e.g. `post:…`). **Not** a **content-addressed** or **immutability** id; **nesting** **does** **not** **pin** a **specific** **definition** **`version`**. **Verifiers** **MUST** **fetch** **that** **state** **via** **§17.5** **at** **recompute** **time** and **fully** **reduce** **the** **nested** **feed** **(§17.10) ** before **applying** **the** **enclosing** **`reduce` **. **The** same **`object_id`**,** **higher** **`version`**,** on **edit** **⇒** a **nested** **recompute** may **legitimately** **differ** **while** the **id** **stays** **fixed** **. |

**MUST NOT (normative):** implementations **MUST NOT** add **v1.4**-required **vector embeddings**, **ML model weights**, or other **unverifiable** **opaque** **blobs** as **required** **fields** in `relay.feed.definition.v1` **core** interop. Extensions **MAY** register optional **`params`** **schemas** in **`registry/`** (**§22**).

**Example (illustrative, not exhaustive):**

```json
{
  "type": "relay.feed.definition.v1",
  "sources": [
    { "kind": "actor_log", "actor_id": "relay:actor:abc" },
    { "kind": "channel", "channel_id": "relay:channel:tech" }
  ],
  "reduce": "relay.reduce.chronological.v1",
  "params": {}
}
```

### 12. Label schema

```json
{
  "id": "relay:label:hash",
  "issuer": "relay:actor:moderator",
  "target": "post:01J...|relay:actor:abc|relay:channel:xyz",
  "label": "spam|harassment|impersonation|nsfw|removed_from_channel|trusted_source|misleading_context",
  "reason": "optional short string",
  "scope": "global|channel:<id>|local_pack",
  "ts": "2026-04-21T00:00:00Z"
}
```

### 13. Channel schema

**Relay 2.0:** first-class **channels** are **State** (configuration) plus **Event**s for membership (**§0.1**).

```json
{
  "id": "relay:channel:tech",
  "owner": "relay:actor:group1",
  "kind": "group|topic|curated|org_stream",
  "created_at": "2026-04-21T00:00:00Z",
  "updated_at": "2026-04-21T00:00:00Z",
  "profile": {
    "name": "Tech",
    "description": "Technology discussion"
  },
  "policy": {
    "trust_floor": ["cryptographic_only"],
    "posting": "open|members|approved",
    "indexable": true
  },
  "content_class": "mutable_public",
  "storage_class": "state"
}
```

#### 13.1 Membership, posting mode, and verification (v1.2 baseline; v1.3 membership witness, normative)

`policy.posting` may be `open|members|approved`, and membership changes appear as `log` events with **`data`** per **Appendix C** (`membership.add` / `membership.remove`).

* **v1.2 (unchanged):** an **origin** (or a gateway) **MUST** **enforce** channel policy at accept time. A **fast relay** **MUST NOT** be assumed to have performed membership proof unless it **implements** the same **policy engine** or **consumes** **witnesses** below.

* **v1.3 — `relay.membership.witness.signed_v1` (portable, normative for verifiers that claim v1.3):** when **independent** verifiers (mirrors, third-party relays, remote readers) need to check **"actor A was allowed to post into channel C at time of event E"** without trusting only the first origin, the **posting** actor (or the **channel owner** on their behalf) **MUST** be able to present a **signed witness** object:

```json
{
  "kind": "relay.membership.witness.signed_v1",
  "channel_id": "relay:channel:…",
  "actor_id": "relay:actor:…",
  "membership_event_id": "relay:event:…",
  "as_of": "2026-04-21T00:00:00Z",
  "issuer": "relay:actor:…",
  "sig": { "alg": "ed25519", "key_id": "key:active:1", "value": "base64…" }
}
```

**Rules:**

* **`issuer`:** **MUST** be the **`owner` actor_id** of the **channel** object (see channel **state**), or an **`actor_id` listed in** the channel’s **`policy.delegates`** list (v1.3 extension) if present; otherwise the witness is **invalid** for v1.3.
* **`membership_event_id`:** **MUST** refer to a **`membership.add`** (Appendix C) on the **origin**-available **log** (typically the **member**’s or **owner**’s log per deployment; the witness **MUST** name which **origin** to query—same **bundle** as the post) whose **`data.channel_id`** matches **`channel_id`** and whose accepted time order is **before** the **`state.commit`** for the post (verifier **MUST** walk `prev` / seq until found or **reject**).
* **Signature:** **MUST** verify per **§7** using **`issuer`’s** active key from **that actor’s** identity at **`as_of`**.
* **Optional transport:** the witness **MAY** ride as **`ext_payload`** on the **post** state, **or** in **`PUB`** **relay** envelopes, **or** via `GET` from channel owner **(product-defined, out of v1.3 wire minimum)**.
* **Limitation (v1.3):** this is **O(1) signature + O(k)** log walk to the referenced event, **not** a **Merkle proof**; **Merkle / batched** membership remains **v1.5+** (see document status). Very large **members** sets should still be **verifiable** but may be **expensive** without batch proofs.

* **What honest v1.3 implementations do:** **origins** **SHOULD** **emit** `membership.add` / `remove` (Appendix C) to their logs; **SHOULD** offer witnesses alongside **member-only** **posts**; **MUST** **not** count relay fan-out as **proof** of policy unless **§18.4** auth extends to policy simulation.

* **Operator transparency (non-behavioral):** deployers **SHOULD** document whether they **emit** v1.3 **witnesses**; if not, **“members-only”** remains **origin-trusted** as in v1.2 for those implementations.

#### 13.2 Channel authority vs actor post authority (v1.2, normative)

* **Post authorship** is a property of the **author’s** state object; only the **author** (or the origin on their behalf) **MUST** be treated as able to **edit** the canonical post **payload** in that `object_id`’s state.
* A **channel** (owner, moderators) **MUST NOT** **mutate** the author’s **post state object** in place. Channel-level actions (pin, hide in channel, “staff picks,” local titles, order) **MUST** be represented by **separate** objects or references, for example:
  * a **label** (issuer = channel or moderator actor; **target** = post) with a `label` in an agreed enum (**§12**);
  * a **channel** state or **log** event that only records **pointers** / **curation** metadata (`channel_refs`, `channel.accept` / curation `log` event with `data` per registry);
  * optional **`ext_payload`** on channel state for `relay.ext.channel_pins.v1` etc.
* A channel **MAY** “annotate” a post in its UI by **composing** author state + **labels** + **channel** metadata; it **MUST** keep the **author** object immutable unless the **author** has authorized a co-authored edit in a **documented** way (out of band to v1.2 or via an extension).
* **Channel authority (clarification):** channels **MUST NOT** **mutate** **actor-owned** state objects. Channels **MAY** **attach** **labels**, **create** **references**, and **publish** **channel-scoped** **metadata**; all such material **MUST** remain **externally** **attached** and **separable** from the **original** **author** state (no in-place edit of the author’s canonical `payload` as stored under that `object_id`).
* This avoids ambiguous merge of “who owns the post body” when channel mods and author disagree.

#### 13.3 Channel equivalence / alias (v1.2, normative)

Channels **MAY** declare **equivalence** relationships with other channels. Equivalence is an **asserted** link object; it is **not** a substitute for **origin** authority over each channel’s id.

**Schema:**

```json
{
  "id": "relay:channel-alias:hash",
  "issuer": "relay:actor:abc",
  "source_channel": "relay:channel:abc",
  "target_channel": "relay:channel:def",
  "relation": "same_as|successor_of|mirror_of",
  "ts": "2026-04-21T00:00:00Z",
  "sig": "…"
}
```

**Issuance and authority (v1.2, normative):** The **`sig`** **MUST** **verify** under **`issuer`’s** key (**§7**). The **core** spec does **not** **require** that **`issuer`** be the **`owner`** of **`source_channel`**, **`target_channel`**, or **both**; **any** **actor** **may** **publish** a **signed** **alias** on **paths** their **software** and **peers** **accept**. **Equivalents** from an **`issuer`** that **does** **not** **control** (as **`owner`**, or a **documented** **delegate** on the **channel** object) **either** **referenced** **channel** are **self-asserted** and **MUST** **not** be **treated** as **authoritative** for **merging** **state** or **rebinding** **authority** without **local** **policy** or **out-of-band** **trust** in **`issuer`**. **Origins** **MAY** **refuse** to **index**, **replicate**, or **prioritize** **alias** objects that **do** **not** satisfy **operator**-defined **issuer** **rules** (e.g. require **`issuer`** to **control** at least one **side** of the **relation**).

**Client weighting (v1.2, non-normative; strongly recommended):** **Clients** **SHOULD** **weight** **equivalence** **claims** by **whether** **`issuer`** **controls** **one** or **both** of the **referenced** **channels** (e.g. **matches** **`owner`** on **channel** **state** the **client** **trusts**), to **mitigate** **equivalence** **spam**; **unrelated-issuer** **links** **SHOULD** **not** receive the **same** **default** **prominence** in **UI** or **merge** **suggestions** as **owner-** or **delegate-** **issued** **links** **unless** a **trusted** **attestation** or **policy** **says** **otherwise** (see **§6**).

**Semantics of `relation`:**

* **`same_as`:** the two channels represent the **same** conceptual **space** (from the issuer’s claim).
* **`successor_of`:** the **target** **replaces** the **source** in role or lineage (per issuer).
* **`mirror_of`:** the **target** **replicates** **source** content (per issuer).

**Client behavior:** clients **MAY** **group** equivalent channels in **UI** and **suggest** merged **views**. Clients **MUST** **not** **automatically** **merge** **channel** **state** or **assume** **authority** **transfer** from an alias alone.

**Indexers** **SHOULD** **expose** equivalence relationships via **API** when they index channel metadata, so clients can build on **issuer**-signed links.

#### 13.4 Action events (v1.4, normative)

Relay is a protocol for **signed, verifiable** artifacts: **action events** model **request → commit → result** for **agent** interaction without turning Relay into an **application** **runtime** or **global** **orchestrator**. The **MUST**s below are **verifiable** with **per-actor** logs (**§10**), **Ed25519** signatures (**§7**), and **content-defined** **commitment** over **hashed** **canonical** **bytes** (**§4.1**–**§4.2**).

**Placement and logs (normative):**

* **`action.request`:** the **requester** **MUST** append this to **their** **own** **actor** **log** (the `actor` field of the event is the requester’s `actor_id`). The **`target` MUST** be the **`actor_id` of the agent** (responder) per **§10.2.1**.
* **No** **normative** **obligation** **to** **commit** **(clarification):** the **target** **agent** **MUST** **be** **modeled** as **not** **required** by **this** spec **to** **append** **`action.commit` **(or** **`action.result` **) **. **Absence** **of** **`action.commit` **(and** **`action.result` **) **MUST** **not** be **read** as **a** **verifiable** **rejection,** a **nack,** or **proof** the **request** was **invisible**; **it** is **merely** **“** **no** **agent-** **signed** **evidence** **(yet** **or** **ever) ** for** the **v1.4** **receipt-class** **path** **(see** the **“** **Partial** **fetch** **and** **visibility**” **bullets** **below) **. **
* **`action.commit`:** the **agent** **MUST** append this to **the agent’s** **own** **actor** log (`actor` = agent). It **MUST** reference the **`action.request` event** from the **requester**’s log by **`data.request_event_id`**, which is a `relay:event:…` id.
* **`action.result`:** the **agent** **MUST** append this to the **agent’s** log after **`action.commit`**. It **MUST** include **`data.commitment_hash`**, which **MUST** equal the **`data.commitment_hash`** on the **`action.commit`**.

A verifier **MUST** **fetch** the **request** (from the **requester**’s **origin** or **authorized** **mirror**), the **commit** and **result** (from the **agent**’s **origin** or **authorized** **mirror**), and **verify** **all** **three** **signatures** in **context**; **if** any **step** is **missing** or **invalid**, the **action** is **untrusted** for v1.4 interop (clients **MUST** **treat** the flow as **failed** for **receipt** / **payment**-grade claims).

**Partial fetch and visibility (normative, clarifies v1.4 over async propagation):** If a **verifier** has **not** **yet** **retrieved** one **or** **more** of the **three** **events** (e.g. **transient** **replication** **lag**, **range** **query** **incomplete**), the **verifier** **MUST** **treat** the **action** as **not** **established** for **v1.4** **receipt**-class **claims**—**MUST** **not** **equate** **“** **pending** **fetch**”** with** **“** **invalid** **signature**”**. When **sufficient** **hashes** / **and** / **or** **events** **arrive**, the **verifier** **MUST** **apply** the **same** **rules** as **if** the **fetches** had **always** been **atomic**. A **sighted** **`action.request` alone** **MUST** **not** be **taken** as **evidence** that the **target** **agent** **consented** **to** **anything**; **only** **agent-** **signed** **`action.commit` / `action.result`** (with **valid** **hash** **recompute**) **implicate** the **agent**. **This** spec **MUST** **not** be **read** to **oblige** **agents** to **respond** to **requests**; an **unanswered** **request** **MUST** **not** be **treated** as a **verifiable** **“relationship** **with**”** the **target** for **v1.4** **—** see **§23.2** **(residual** **abuse** **/ UX** **honesty**).

**`data.input_refs` (on `action.request` only):** **`data` MUST** include **`input_refs`**, a **JSON array** of **strings**; each string **MUST** be a **`relay:obj:…`**, a **`relay:event:…`**, or another **documented** `object_id` / `event_id` **form** the **verifier** can **GET** and **check** (unknown references **MUST** fail verification for strict clients). The array **MUST** be **sorted in ascending Unicode code point order** of the **string** **values** before inclusion in the **commitment** **payload** (so **independent** implementations agree on **one** **commitment** **hash** for a given request).

**`data.action_id` and `data.action` (on `action.request` only):** **`data` MUST** **include** **at** **least** **one** **of** **`action_id` **(string) **or** **`action` **(string) **(not** **neither) **. **`data` MAY** **include** **both. **`data.action` **(when** **the** **key** **is** **present) **MUST** be a **string** **(NFC,** **§4.1.2) ** and **MUST** ** be ** ** understood ** as ** a ** ** human-**facing, ** ** debug, ** or ** ** legacy ** ** label **; ** it ** is ** not **, ** on ** its ** own, ** a ** ** globally ** ** interoperable ** ** name **. ** If **`data` ** has **`action` ** but ** not **`action_id` **(legacy-** only **) **, ** ** clients **MUST** **treat** **`data.action` **as **ecosystem-** **local** **/ ** ** legacy ** **, ** not ** as ** a ** ** portable ** ** v1.4- ** class ** interop ** name **. **

* **`data.action_id` (v1.4) **: **if** ** the **`action_id` ** key ** is ** ** present, **`data.action_id` **MUST** be a **string, **MUST** ** be ** the ** ** canonical, ** ** interoperable ** ** action ** ** identifier ** ** in ** the ** v1.4 ** ** sense **( **i.e. ** the ** value ** a ** ** verifier ** ** or ** ** client ** ** uses ** to ** ** resolve ** which ** ** named ** ** operation ** **( **in **a ** ** registry-** independent ** way **) **is **in **play **in ** ** cross-** deployment ** use **) **, ** and **MUST** ** be ** ** NFC **- **compliant ** ** text **( **§4.1.2) **. **Syntactic** **form** ( **v1.4, ** ** pattern **; ** not ** a ** ** closed ** ** set ** in ** this ** document **) **: ** a ** ** dot-**separated, ** ** namespaced, ** version **-** suffixed ** ** value **( **e.g. **`relay.basic.summarize.v1`**, **`acme.agent.extract_entities.v2` **) **. **

* ** If ** both **`data.action` ** and **`data.action_id` ** are ** ** present ** ** and ** a ** ** verifier ** ** or ** ** client ** ** determines ** a ** ** semantic ** ** conflict **( ** the ** two ** are ** not ** the ** same ** ** operation) **, **`data.action_id` **MUST** ** be ** ** authoritative ** ** for ** ** interoperability** **(matching,** **indexing,** **routing) **; **`data.action` **MUST** ** not ** ** override ** **`data.action_id` ** for ** that **. **(Both ** ** still ** ** participate ** ** in ** ** the ** same ** signed **`data` ** and **, ** when ** ** present, ** in **`relay.action.commitment.v1` **. **) **

**Optional** **`action_namespace` and `action_version` (v1.4, MAY) **: **`data` MAY** ** also ** ** include ** **`action_namespace` ** and ** **/** or **`action_version` **(strings, **NFC) **, ** e.g. ** for ** ** extra ** ** metadata **( **redundant** **in** ** some** **designs** **with** a **rich **`data.action_id` **) **. ** The ** ** commitment ** **( **`relay.action.commitment.v1` **, ** ** below) ** ** copies ** them ** if ** ** present **( ** not **`null` **) **. **

**Example (illustrative):** `{ "action_id": "relay.basic.summarize.v1", "input_refs": [ "relay:obj:…" ] }` with **`input_refs` **sorted**;** **`{** **"action"**:** **"summarize"** **,** **"action_id"**:** **"relay.ai.basic.summarize.v1"** **,** **"input_refs"**:** [**…**] **} **;** **or** legacy-only **`{** **"action"**:** **"com.example.opaque"** **,** **"input_refs"**:** [**…**] **} **( ** no **`action_id` **, ** not ** a ** ** portable ** ** id **) **. **

**Commitment payload and `commitment_hash` (normative):** define the **v1.4** **commitment** **object** **`relay.action.commitment.v1`:**

| Field | Rule |
| --- | --- |
| `kind` | **MUST** be the literal `relay.action.commitment.v1`. |
| `request_event_id` | **MUST** be the **`action.request` event id** the commit responds to. |
| `data_action` | If **`data.action` **is ** ** present ** on ** the **`action.request` **`data` **, **MUST** ** ** copy ** that ** string **; ** if ** ** absent, ** the **`data_action` **key **MUST** ** be ** ** omitted ** **(not** **`null` **) ** from **`relay.action.commitment.v1` **. ** |
| `data_action_id` | If **`data.action_id` **is ** ** present ** on ** the ** request **`data` **, **MUST** ** ** copy ** that ** string **; ** if ** ** absent, ** the **`data_action_id` **key **MUST** ** be ** ** omitted ** **(not** **`null` **) **. ** |
| `data_action_namespace` | If **`data.action_namespace`** is **present** on the **request,** **MUST** **copy** that **string;** **if** **absent** on the **request,** the **key** **MUST** be **omitted** **(not** **`null` **) ** from **`relay.action.commitment.v1` **. ** |
| `data_action_version` | If **`data.action_version`** is **present** on the **request,** **MUST** **copy** that **string;** **if** **absent,** the **key** **MUST** be **omitted** **(not** **`null` **) **. ** |
| `input_refs` | **MUST** be the **sorted** `input_refs` array from the request (as above), embedded as a **new** array. |
| `agent_params` | **MUST** be a **JSON object** (possibly `{}`). **Carries** **agent**-supplied **parameters** that **affect** the **result** (e.g. **model** **id** **as** **an** **extension**-registered string). **MUST** be **NFC**-normalized for **all** string **values** in **recursively** **nested** structure per **§4.1.2** if those strings are **part** of the **object**; **MUST** use **no** **floats** in **violation** of **§4.1.1**. |

* **`agent_params` size and shape (v1.4 SHOULD, origins MAY):** v1.4 imposes no normative cap on the serialized size or JSON nesting depth of **`agent_params`**; **§4.1** still governs the commitment object, and a pathologically large `agent_params` is still a valid **commitment** input if the origin accepts the append. **Agents SHOULD** keep **`agent_params`** compact (small on the wire, shallow nesting) so **constrained** **verifiers** can recompute without excessive work. An **origin MAY** document and enforce **local** **limits** on `action.commit` **body** size or depth; refusing an append is **not** a change to the verification rules for **other** log events the origin has **already** stored.

* **`commitment_hash`:** **MUST** equal **lowercase hex (64 characters, `0-9a-f`)** encoding of the **SHA-256** **digest** over the **UTF-8** **bytes** of the **canonical JSON** (**§4.1**; no extra signature wrapper fields) of the object **`relay.action.commitment.v1`**. **MUST** **not** use **multihash** or **base64** for the **in-`data`** value in v1.4 **core** interop. See **Appendix C** for field-level `data` requirements on **`action.commit`** and **`action.result`**.

* **`action.commit` MUST** **include** the **same** **`commitment_hash`** (hex) in **`data`**. **`action.result` MUST** **reference** that **same** **hash** in **`data.commitment_hash`**. Verifiers **MUST** **recompute** the **hash** from the **fetched** **request** + **`data.agent_params`** on the **commit** (see **Appendix C**) and **MUST** **reject** if the **recomputed** value **differs** from both **commit** and **result**.

**Ordering within the agent’s log (informative, not a global order):** **`action.commit` MUST** appear **before** **`action.result`** in **append** order on the **agent**’s log when both exist; a **result** without a **verifiable** **commit** (same **`commitment_hash`**, **valid** **signature** **on** **commit** **fetched** **from** **the** **agent**’s **log** **or** **mirror**)** **MUST** be **invalid** for v1.4 **(even** if **a** **buggy** **client** **or** **racing** **indexer** **surfaces** **result** **before** **commit** **in** a **list** **UI**)**. **In** **no** **case** **may** **a** **verifier** **accept** **result**-only **as** **sufficient** for **v1.4** **receipt** **claims.**

**`action.result` output references:** **`data.output_refs` MUST** be a **JSON array** of **strings** (same id forms as `input_refs`). The **result** is **signed** by the **agent**; **receipt** **of** a **result** **does** **not** **by** **itself** **prove** **correct** **computation** of an **off-protocol** **side** **effect**—**only** **what** is **captured** in **signed** **refs** and **verifiable** **objects** **counts** (honest **verifiers** **MUST** **fetch** **output** **objects** if **claims** **depend** on them).

**Non-normative:** *These events **do** **not** **execute** code on a **Relay** **origin**; they **record** **intent** and **outcomes** in **logs**. **Economic** or **safety** **semantics** **beyond** **signature** **verification** are **always** **deployment** **policy**.*

#### 13.5 Private `action.request` addressing (`relay.ext.private_action.v1`, v1.5, optional, normative)

**Purpose (v1.5):** **optional** **extension** **`relay.ext.private_action.v1` ** allows **`action.request` **(§13.4) ** to **omit** the **plaintext** **top-** **level** **`target` **(the** **agent**’**s** **`actor_id` **) ** and **conceal** the **conventional** **`data` **on** **the** **wire,** while **retaining** **verifiable** **Ed25519** **signatures** **(§7) ** and **a** **§13.4** **`commitment_hash` **recomputed** **over** the **decrypted,** **canonical** **inner** **request** **payload** **(§4.1) **. **

**`ext` and `ext_payload` (§22.3):** the **log** **event** **`type` **MUST** still **be** **`action.request` **. **The** **event** **`ext` **array** **(§22.3) **MUST** **include** the **literal** **string** **`"relay.ext.private_action.v1"` ** when** **this** **extension** **is** **in** **use** **. **`ext_payload` **MUST** **include** a **property** **whose** **key** **is** **`"relay.ext.private_action.v1"` ** **mapping** to a **JSON** **object** that **MUST** **include** at **least** **`tag` ** and **`encrypted_payload` ** (defined** **below) **. **

**Omission** **of** **`target` **: ** when **`relay.ext.private_action.v1` **is** **in** **`ext`**, the **top-** **level** **`target` **MUST** be **omitted** **(§10.2.1) **. **

**Top-** **level** **`data` **(normative) **: ** the **log** **event** **`data` **MUST** be **an** **empty** **JSON** **object** **`{ }` **(or** **omitted,** **treated** **as** **`{ }` **) **. **The** **plaintext** **`data` **fields** **for** **`action.request` **( **`action_id` **and/or** **`action`**, **`input_refs`**,** **and** any **optional** **`action_namespace` / `action_version` **per** **Appendix** **C,** **§13.4) **MUST** **appear** **only** **in** the **decrypted** **content** **of** **`encrypted_payload` **(§4.1) **. **

**`tag` (normative):** define **`relay.action.tag.v1` ** as **a** **JSON** **object** with **string** **keys **`kind`**,** **`requester`**,** **`agent`**,** **`salt` **; **`kind` **MUST** be the **literal** **`"relay.action.tag.v1"`, `requester` **and** **`agent` **MUST** be **`relay:actor:…` ** **values** **,** **`salt` **MUST** be a **base64url**-**encoded** **string** **(RFC** **4648) ** that **decodes** **(with** or **without** **padding,** **per** **the** **registry) ** to **a** **byte** **string** of **length** **at** **least** 16** **(CSPRNG) **. **`tag` **MUST** be the **lowercase** **64**-**character** **hex** **( **`0-9a-f` **only) ** of **the** **SHA-256** **digest** over **the** **UTF-8** **bytes** of **the** **§4.1** **canonical** **JSON** of **that** **`relay.action.tag.v1` ** object** **(§4.1,** **§4.2) **. **(This** **is** the **same** **hex** **style** as **`commitment_hash` **, **§13.4) **. **(Public** **verifiers** **MUST** **not** need **`salt` ** to **check** the **envelope** **signature**; **the** **tag** is **a** **one**-**way** **fingerprint) **. **

**`encrypted_payload` (normative, core):** **`encrypted_payload` **MUST** be a **string** **carrying** **a** **ciphertext** **(and** **any** **demarcation) ** for **an** **ECIES**-**style** **encryption** of **the** **UTF-8** **bytes** of **the** **§4.1** **canonical** **JSON** **`data` **object** **for** a **conventional** **`action.request` **(at ** **least** **one** of **`action` **/ **`action_id`**, **sorted** **`input_refs`**,** **and** any **other** **Appendix** **C**-**required** **keys) **. **JSON** **canonicalization,** **key** **and** **string** **encodings,** and **Asymmetric**-**key** **identity** **rules** **MUST** **follow** **§4** **(especially** **§4.1) ** **and** **§7.1** **/ **§7** **(Ed25519) **; **the** **concrete** **agreement-key** **derivation** **(Ed25519** **to** **X25519** or **successor) **, **KDF,** **AEAD,** and **AAD** **for** **`encrypted_payload` **MUST** be **defined** in **`registry/relay.ext.private_action.v1` **(v1.6+** **deferred** **table) **. **

**Key** **and** **identity** **(normative,** **surface) **: ** the **`agent` **value** in **`relay.action.tag.v1` **MUST** **be** the **`actor_id` **(§4.3) ** of **the** **intended** **responder,** and **MUST** **name** the **same** **identity** **whose** **active** **Ed25519** **key** (§7.1) **is** **used** **in** the **way** the **registry** **specifies** for **ciphertext** **(tag** **derivation** **only** **hashes** the **`actor_id` **string** and **`salt`**,** **per** **§4.1** **/ **§4.2) **. **The** **tag** and **ciphertext** **MUST** **be** **bound** **in** the **manner** **the** **registry** **entry** **specifies** to **the** **agent**’**s** **active** **Ed25519** **key** for **`agent` **(§7) **. **v1.5** **core** **defers** **all** **byte-** **level** **ECIES** **encapsulation** and **KDF** **details** to **the** **registry** **(see** **§4.1) **. **

**Decryption,** **commitment,** **and** **§13.4: ** a **party** who **can** **decrypt** **`encrypted_payload` **(typically** the **agent) **MUST** **obtain** **a** **JSON** **`data` **object** **satisfying** **Appendix** **C** for **`action.request` **. **The** **`commitment_hash` **MUST** **be** **computed** **per** **§13.4** **( **`relay.action.commitment.v1` **,** **Appendix** **C) ** using **the** **decrypted** **`data` **( **`data_action`**, **`data_action_id`**, **`input_refs` **, **as ** in ** **§13.4 **) ** and **`data.agent_params` **from** **the** **`action.commit` **—** the **same** **§13.4** **rules** **as** **when** **the** **request** **was** **plaintext** **. **`action.commit` / `action.result` **MUST** **not** **change** **(Appendix** **C) **. **

**Verifiers** **without** **the** **salt: ** a **verifier** **with** only **a** **public** **envelope** **(no** **salt** **) **MUST** **not** **infer** a **definite** **requester**–**agent** **link** **from** the **`tag` **string** **alone** **(preimage** **is** **infeasible) **. **

**Interoperability:** **`relay.ext.private_action.v1` **is** **OPTIONAL. ** **Implementations** **that** **do** **not** **implement** it **MUST** **degrade** per **§22.4** **(preserve** **signed** **bytes,** **no** **silent** **drop) **. **

**Agent** **identification (normative for agents** **that** **implement** **this** **extension) **: ** the **agent** **MUST** **scan** **incoming** **`action.request` **log** **events** **(including** **fetches** from **its** **own** **log** or **a** **mirror) ** and **MUST** **treat** **a** **candidate** as **a** **private** **request** **to** **this** **agent** when **the** **event**’**s** **`tag` **string** **(§4.1,** **§4.2) ** **equals** **the** **tag** **value** **obtained** **by** **applying** **the** **`tag` **(normative) ** **rules** **above** **to** **a** **`relay.action.tag.v1` **object** **the** **agent** **can** **form** from **a** **known** **`requester` **( **`actor` **) **,** the **`actor_id` **of** **this** **agent** **in** **the** **`agent` **field,** and **a** **`salt` **it** **obtains** **(salt** **delivery** is **OOB** or **as** **in** the **registry;** **v1.5** **does** **not** **define** the **OOB** **channel) **. **(Exact** **indexing** **data** **structures** are **implementation**-**defined. **) **

**Agent** **scan** **(informative,** **additional** **context) **: ** the **same** **tag**-**recompute** **pattern** is **a** **practical** **way** to **index** by **(requester,** **salt) **pair** **from** **known** **relationships. **

**Private action discovery (v1.5, optional, advisory — UX and convenience only):** the **core** **extension** **above** is **cryptographically** **well**-**defined,** but **it** **does** **not** **by** **itself** **tell** a **client** **that** a **new** **private** **`action.request` ** has **arrived,** **nor** **how** to **obtain** a **practical** **“** **pending** **/ ** **unread** **”** **list** **without** **walking** the **entire** **public** **actor** **log** **. ** v1.5 **adds** **no** **messaging** **subsystem**; **it** **adds** **only** **lightweight,** **explicitly** **advisory** **surfaces** **(below) ** **so** **products** **can** **build** **inbox-** or **alert-** **class** **UX** **. **

* **Advisory (only) — not a trust root:** any **index,** **feed,** or **WebSocket** **notice** **in** **this** **subsection** **MUST** be **treated** **as** **convenience** **and** **MUST** **not** **substitute** **for** the **signed** **log** **event. **The** **sole** **authoritative** **artefact** for **“** **a** **private** **request** **was** **posted** **and** **signed** **by** the **requester** **in** a **verifiable** **way** **”** **is** still **a** **successful** **fetch** of **the** **`action.request` **envelope** **(§7) ** and, **for** the **agent,** **verifiable** **decryption** **and** **§13.4** **`commitment_hash` **recompute. **

* **HTTP hint index (MAY):** an **origin** **MAY** expose **`GET /actors/{actor_id}/private-actions` **(same** **path** **convention** **as** **§17,** or **a** **documented** **absolute** **URL** in **§8.1) **. **The** **response** **MAY** be **a** **JSON** **array** **of** **hint** **objects,** or **a** **paged** **object** (e.g. **`{"items": [ … ], "next_cursor": "…"}` **)**. **Lack** **of** this **route** (e.g. **404) ** **MUST** **not** be **read** **as** **“** **no** **private** **actions** **exist** **”** **or** **as** **failing** **`relay.ext.private_action.v1` **. ** The** **extension** **remains** **valid** **with** **only** **§17.3** / **§17.4** **fetches** and **OOB** **notification. **

* **Hint** **object** **(advisory,** **MAY** be **opacity-** **preserving) **: ** each **element** **MAY** **carry** **only** **metadata,** e.g. **`event_id`**, **`ts` **(from** the **envelope) **, **`tag` **(hex) **, **`sender_hint` **(string,** e.g. **the** **requester** **`actor_id` **or** an **opaque** **id) **, **`unread` **/ **`seen` **(booleans) **, **and** **other** **keys** **(ignore-** **unknown) **. ** The** **listing** **MAY** **omit** **or** **reorder** **items;** **it** **MAY** **return** **stale** **or** **best-** **effort** **data. **

* **Client** **MUST (authenticity) **: ** a **client** **MUST** **fetch** **the** **referenced** **event** **by** **`event_id` **(§17.3) ** **or** **an** **equivalent** **signed** **copy,** **MUST** **verify** the **envelope** **per** **§7** **, ** and, **where** **the** **body** **uses** **`encrypted_payload` **,** **MUST** **decrypt** **and** **validate** **the** **inner** **`data` ** per **this** **section** **and** **Appendix** **C,** ** before** **treating** the **action** as **genuine,** **pending,** or **suitable** **for** **commit** / **result** **semantics. **

* **This** **is** **not** a **new** **required** **Relay** **role;** **it** is **an** **optional** **convenience** **on** the **actor** **origin** or **a** **co-** **located** **helper** that **MUST** be **labelled** **as** **advisory** in **operator** **docs** where **it** **is** **offered. **

**WebSocket (optional,** **advisory,** **§18) **: **a** **Fast** **Relay** **MAY** support **`SUB`** with **`"type"** **:** **"private_action"** **and** **`"actor"** **:** **`"relay:actor:…"`** **(§18.2) **, ** and **MAY** **push** **`PRIVATE_ACTION_HINT` **(§18.5) ** with **a** **JSON** **body** **using** the **same** **hint** **semantics** **as** the **HTTP** **index** **(arrival** **nudge** **only) **. **

### 14. Classification decision rules

Deterministic rule set:

1. If the object changes authority, membership, keys, moderation, recovery, or audit trail, it MUST be a `log` object.
2. If the object is primarily rendered as the current user-facing version, it MUST be a `state` object.
3. If both current renderability and durable audit history matter, it MUST be `dual` and emit a `state.commit` log event for every accepted state mutation.
4. Reply structure is stored on the post state object (`reply_to`) while reply arrival events may be indexed from state commits.
5. Channel membership actions are `log`; current channel profile/config is `state`.
6. **v1.4:** `action.request`, `action.commit`, and `action.result` are **`log` events**; they MUST NOT replace **state** for verifiable post bodies or **identity**; see **§13.4** for binding semantics.
7. **v1.4:** a **`relay.feed.definition.v1` object** is **`state`**: it describes **how to derive** a **view** from **fetched** **sources**; the **reduced** list is a **recomputed** **projection**, not a **new** **consensus** **layer**—see **§11.1** and **§17.10**–**§17.11**.
8. Edit history is never implicit. If a client wants user-visible history, the object MUST be `dual`.

### 15. Unified semantics matrix

| Object Type           | Content Class  | Storage Class |  Mutable | Mirror Expectation      | Delete Semantics           |
| --------------------- | -------------- | ------------: | -------: | ----------------------- | -------------------------- |
| Identity              | durable_public |          dual |  limited | mirror snapshots        | superseded, not erased     |
| Follow event          | durable_public |           log |       no | mirror indefinitely     | none                       |
| Membership action     | durable_public |           log |       no | mirror indefinitely     | none                       |
| Moderation label      | durable_public |           log |       no | mirror indefinitely     | superseded by later labels |
| Public post           | mutable_public | state or dual |      yes | mirror latest state     | origin delete + tombstone  |
| Essay/article         | durable_public |          dual | optional | mirror latest + commits | suppression only           |
| Revocable shared post | revocable      |         state |      yes | mirror ciphertext only  | key revoke + tombstone     |
| Ephemeral post        | ephemeral      |         state |      yes | short TTL cache only    | expiry + best-effort purge |
| Channel profile       | mutable_public |         state |      yes | mirror latest           | origin update              |
| Action event (v1.4)   | durable_public |           log |       no | mirror indefinitely     | none                       |
| Feed definition (v1.4) | mutable_public |         state |      yes | mirror latest           | origin update, supersession |

### 16. Publication APIs (Truth layer — append **Event**; publish **State**)

**2.0** **mapping:** `POST` log = append **Event**; `PUT` state = publish or revise **State**.


#### 16.1 Publish state object

`PUT /actors/{actor_id}/state/{object_id}`

Request body: state envelope

Rules:

* requires actor auth
* version MUST increment by 1 unless creating version 1
* server validates signature and schema
* on success, server persists latest state and MAY emit `state.commit` log event if object is `dual`

Response:

```json
{
  "ok": true,
  "actor": "relay:actor:abc",
  "object_id": "post:01J...",
  "version": 4,
  "etag": "W/\"state-4\""
}
```

#### 16.2 Soft-delete state object

`DELETE /actors/{actor_id}/state/{object_id}`

Effect:

* server marks state object `deleted=true`
* increments version
* emits `state.delete` log event for `dual` objects
* for `revocable`, also marks current key grants revoked

#### 16.3 Append log event

`POST /actors/{actor_id}/log`

Body: log envelope

Validation:

* `prev` MUST match current head unless explicit fork mode is enabled
* `type` MUST be permitted for actor role
* for `follow.add` and `follow.remove`, **`target` MUST** be set as in **§10.2.1**
* **v1.5 (§10.5) **: **if** **`expires_at` **is **present,** **MUST** **satisfy** **§10.5 **( **`content_class` **,** **pairing,** **RFC** **3339) **; **MUST** **reject** the **append** **otherwise** **(including** **`durable_public` **+ **`expires_at` **) **. ** If **the **envelope** **(with** **`expires_at` **) ** is **time-** **expired** **(§10.5) ** at **the **time** **of** **this** **request, ** **MUST** **reject** the **append** **(phase** **(B) **) **. **(The** **rejection** **is** **operational, ** **not** a **signed** **assertion** that **the** **bytes** **never** **validly** **existed; ** see **§9 ** **(v1.5** **exception) **, ** **§10.5 ** **(C) **. **) **
* **v1.5 (§10.5) **(storage) **: ** nothing **here** **requires** the **origin** **to** **retain** **a** **rejected** **body; ** **post-** **acceptance** **deletion** **/ ** **GC** **is** **§10.5 ** **(C) ** **and** **operator** **policy. **
* **v1.5 (§13.5) **: **if** **`ext` **includes **`relay.ext.private_action.v1`**,** **MUST** **satisfy** **§13.5 **( **`tag`**,** **`encrypted_payload`**,** **omitted** **`target` **) **; **MUST** **reject** the **append** **otherwise** **. **

Response:

```json
{
  "ok": true,
  "event_id": "relay:event:hash",
  "head": "relay:event:hash"
}
```

### 17. Fetch APIs (Truth layer fetches; **View** in §17.10–11)

**2.0** **mapping:** log fetches return **Event** envelopes; state fetches return **State**. Deterministic feeds (**View**) are defined in **§11.1** and evaluated per **§17.10**–**§17.11** (no separate `GET` for the view in core).


#### 17.1 Identity

* `GET /actors/{actor_id}/identity`

#### 17.2 Actor log head

* `GET /actors/{actor_id}/log/head`

Response:

```json
{"head": "relay:event:hash", "count": 2412}
```

#### 17.3 Log event by ID

* `GET /actors/{actor_id}/log/events/{event_id}`

* **v1.5 (§10.5) **, **envelope** **`expires_at` **(see **phases** **(B)** **/ ** **(C)** **, ** **§10.5) **: ** for **a** **time-** **expired** **envelope, ** the **server** **MUST** **not** **return** the **raw** **event** **as** **if** it **were** **active, ** **non-** **expired** **log** **content** **without** a **time-** **expired** **signal** **. ** **During** **expired-** **serving** **retention** **(B) **, ** a **200**-**class** (or** **other** **body-** **bearing) ** **response** **that** **carries** the **envelope** **MUST** **indicate** **time-** **expired** **status** in **a** **machine-** **readable** **way** **: ** **either** **the** **response** **header **`X-Relay-Log-Event-Expired: true` **(recommended) ** **or** **a** **documented** **top-** **level** **JSON** **flag** **(e.g. **`"event_expired": true` **) ** **wrapping** **or** **adjacent** **to** the **envelope. ** **After** **garbage** **collection** **(C) **, ** the **id** **MAY** **be** **unavailable** **(404, ** **410, ** **etc.) ** **per** **operator** **policy; ** a **“** **not** **found** **” ** **MUST** **not** be **treated** as **a** **global** **proof** the **id** **was** **never** **validly** **appended, ** **only** that **this** **node** **does** **not** **(or** **no** **longer) ** **serve** **it** **(§9 ** **(v1.5** **exception) **, ** **§10.5) **. ** **Stale** **caches** **MUST** **reconcile** **to** **§10.5** **. **

#### 17.4 Log range

* `GET /actors/{actor_id}/log?after=<event_id>&limit=100`
* `GET /actors/{actor_id}/log?before=<event_id>&limit=100`

* **v1.5 (§10.5) **: **default** **(no** **`include_expired` **) ** result **MUST** **not** **list** **time-** **expired** **events** as ** “** **active** **” ** **(§10.5) **. **`include_expired` **(or** **local** **alias) **: **per** **§10.5; ** each **returned** **time-** **expired** **envelope** **MUST** **use** the **same** **expired** **signalling** as **§17.3 **(header** **or** **JSON) **. **

* **v1.5 (§10.5) **, **range** **/ ** **history** **metadata** **(SHOULD) **: ** when **the** **response** **MAY** **omit** **time-** **expired** **or** **garbage-** **collected** **events** **(default** **listings, ** **(B), ** **(C) **—** **e.g. ** **without** **`include_expired` **, **or** **after** **(C) **) **, ** the **server** **SHOULD** **include** **top-** **level** **(or** **documented) ** **metadata** so **audit** **/ ** **history** **consumers** **can** **judge** **omission** **risk, ** e.g. **`expired_omissions_possible: true` **(boolean) ** **and** an **`as_of` ** **instant** **(RFC** **3339, ** **§4.1.1.1) ** **describing** the **view**’**s** **time** **cut** **(operator-** **defined** **exact** **meaning, ** **but** **MUST** be **documented) **. **

* **v1.5 (§10.5) **, **completeness** **(MUST, ** **clients) **: ** a **client** **MUST** **not** **treat** a **default** **(or** **unqualified) ** **range** **response** as **a** **guaranteed** **complete** **contiguous** **log** **slice** **across** **time-** **expiry** **/ ** **garbage-** **collection** **boundaries** **unless** the **server** **explicitly** **states** **otherwise** in **the** **response** **(e.g. ** **`expired_omissions_possible: false` ** **with** a **defined** **semantic, ** or **a** **documented** **“** **full** **over** **window** **” ** **flag) **. **

* **v1.5 (§13.5) **(optional) **: **`GET /actors/{actor_id}/private-actions` **— **advisory** **UX** **hint** **index** for **private** **`action.request` ** events **( **`relay.ext.private_action.v1` **) **. ** **Not** **a** **trust** **root;** **MUST** **not** be **cited** **for** **authenticity** **without** **fetching** **and** **verifying** **the** **signed** **event** **(§7,** **§17.3) **. ** **See** **§13.5,** **§8.1** **`private_action_hints` **. **

#### 17.5 State object

* `GET /actors/{actor_id}/state/{object_id}`

#### 17.6 State feed snapshot

* `GET /actors/{actor_id}/state?type=post&after_ts=...&limit=50`

**Snapshot consistency (v1.2, normative):** a response that is labeled or advertised as a **snapshot** (this feed, `GET /actors/{actor_id}/snapshots/latest`, or static **Part II §29** material) **MUST** represent a **self-consistent** view of **all** **included** objects as of a **single** **logical** **commit** **boundary** on the **origin**. A snapshot **MUST** **not** **mix** object **versions** from **different** logical **states**. A snapshot **MAY** be **partial** (not every object in the actor’s history); if **partial**, the response **MUST** include **metadata** indicating **partial** **coverage** so clients do not mistake the slice for a full dump. A response **MUST** **not** be labeled a **snapshot** if it would **contain** **inconsistent** state (mixed generations) for the objects it returns.

**Canonical snapshot metadata (v1.2):** implementations **SHOULD** expose the equivalent information using **these exact key names** (in the **snapshot** JSON document **alongside** object payloads, or in a **`snapshot_meta`** object at the top level of the response—**MUST** be documented per deployment if nested):

```json
{
  "snapshot_id": "<string, origin-defined stable identifier for this snapshot>",
  "as_of_ts": "<RFC 3339 instant, §4.1.1.1>",
  "partial": true
}
```

For a **full** snapshot, **`partial`** **SHOULD** be **`false`** (or omitted with **`snapshot_id`** + **`as_of_ts`** still present). Additional keys **MAY** be added under **`ext`** / documented extensions. Clients **SHOULD** accept **documented** synonyms only as a **legacy** path; new implementations **SHOULD** emit the canonical keys above to avoid per-server schema forks.

**Clients** **MAY** **assume** that **all** objects **within** a **valid** **snapshot** are **mutually** **consistent** for rendering and sync (**§2.5** baseline includes snapshot fetch for this reason). For **paged** or **incomplete** feeds **without** snapshot metadata, treat as ordinary **query** results, not a normative **snapshot** (**§2** profiles).

#### 17.7 Channel view

* `GET /channels/{channel_id}`
* `GET /channels/{channel_id}/feed?cursor=...&limit=50`

#### 17.8 Label view

* `GET /labels?target=<id>&scope=<scope>`

#### 17.9 Indexer transparency (optional but recommended when an Indexer role is offered)

Indexers influence **discovery** and ranking; clients **SHOULD** be able to fetch **machine-readable** inputs to that behavior (not only HTML). If a deployment exposes **Indexer** APIs, it **SHOULD** implement at least:

* `GET /indexer/policy` — JSON document describing **ranking / safety** policy (what is boosted, filtered, or down-ranked, in a machine-readable form). Example minimum shape:

```json
{
  "version": 1,
  "description": "human summary",
  "boost": ["follow_graph", "recency"],
  "downrank": ["low_trust_attestation", "reported_spam"],
  "fees": {"query_credits": 0}
}
```

* `GET /indexer/sources` — JSON list of **data sources** and **crawl** or **ingest** scope (e.g. which actor feeds, how often, whether third-party mirrors are used). Example:

```json
{
  "version": 1,
  "sources": [
    {"type": "actor_feed", "actor_id": "relay:actor:…", "last_indexed": "2026-04-21T00:00:00Z"}
  ]
}
```

These endpoints are **advisory** for transparency; they do **not** create a **global** ranking—clients **MUST** still treat Indexers as one input (**§1**, **§23.2**).

#### 17.10 View layer — feed definitions and reduction functions (v1.4, normative)

**Relay 2.0** name: this is the **View** **engine** — reducers are versioned pure functions over **bounded** inputs (**§0.3**).


A **feed** in v1.4 is a **pure function** of (a) a **`relay.feed.definition.v1` state object** and (b) the **set** of **log events** and **state objects** the **recomputer** can **obtain** by **read-only** **HTTP** **fetch** from **authoritative** or **cached** **sources** per **§17**—**not** a **trusted** **opaque** list from a **single** **indexer** unless the **client** **chooses** to **treat** it as **advisory** only.

**Input** **boundary** **(v1.4,** **normative) **: **A** **recompute** is **only** **defined** **over** the **fetches** the **recomputer** **actually** **performed** and **over** a **stated** **or** **implicit** **time** / **count** / **range** **window** for **each** **source** (e.g. **`actor_log` **as** **fetched** **via** **§17.3**–**§17.4,** **or** a **§17.6-** **consistent** **(or** **documented-** **equivalent) ** **snapshot** **at** **`as_of_ts` ** **plus** **deltas** **after** **that** **boundary) **. **v1.4** **does** **not** **require** **infinite** **log** **history** **. ** Two** **honest** **recomputes** that **differ** **only** in **how** **deeply** or **how** **far** **back** they **fetched** **MAY** **produce** **different** **outputs;** that **is** **not** **reducer** **non-** **determinism,** **it** is **a** **different** **input** **set** **(see** **§17.11) **. **

**Recompute / audit boundary (v1.4, ties to §11.1):** For **strong** **deterministic** **audit,** when **two** **parties** **compare** **a** **materialized** **feed** **output** or **recompute** **result,** the **input** **boundary** **SHOULD** be **made** **explicit** **as** **in** **§11.1** **(definition** **`object_id` **+** **`version`**, **`as_of`**, **per-**source **`source_heads` **) **. ** “** **Latest** **available** **”** **fetches** **without** **such** **a** **record** **are** **fine** **for** **local** **rendering** **but** **do** **not** **alone** **support** **the** **same** **cross-** **deployment** **audit** **claims** **(§11.1,** **§17.11) **. **

**Fetch (unchanged path):** **§17.5** **`GET /actors/{actor_id}/state/{object_id}`** returns the **feed definition** state. No **new** **HTTP** method is **required** in v1.4. Optional **`GET` convenience** endpoints (e.g. a server-side **“materialized”** feed) **MAY** exist as **extensions**; they **MUST** **not** be **treated** as the **sole** **normative** **artifact** in **core** interop for **receipt**-style **claims** about **reducer** **correctness**—**§17.11** is **authoritative** for **“did this match the definition?”** **questions**.

**Reduction function identifiers (normative):** each **`reduce` string` MUST** be **fixed** for a **revision**: **`relay.reduce.<name>.v<version>`** with **lowercase** **name** segments separated by **`.`**; **v1.4** **requires** the following two **identifiers** to be **implemented** by any implementation that claims v1.4 **feed** interop for **chronological** or **reverse** **views** as **defined** here:

* **`relay.reduce.chronological.v1`:** **inputs:** the **expansion** of **§11.1** **`sources`**, each yielding a **set** of **`relay:event:…` references** the client has **fetched** (with their **log event** bodies), plus **relevant** **state** objects the **reducer** **requires** to **interpret** **commits**; **output:** a **totally** **ordered** **list** of **event** **ids** (duplicates **removed**), **earliest** **first** by **( `ts` **RFC 3339** string, then **`event_id` lexicographic** **tie**-**break**)**. **MUST** **only** use **signed** `ts` from **events**; **MUST** **not** **introduce** a **new** **global** **clock** or **consensus** **layer**.
* **`relay.reduce.reverse_chronological.v1`:** **identical** **inputs**; **output** is **`relay.reduce.chronological.v1` followed by** **reversing** the **final** list.

**Declared** **input** **domains** **( ** **normative, ** **these** ** **two** ** **ids** **) **: ** **signed** ** **log** ** **events** ** **( ** **plus** ** **state** ** **objects** ** **needed** ** **for** ** **commit** ** **semantics** **) ** **drawn** ** **only** ** **from** ** **`sources` ** **( ** **§11.1** **) ** **as** ** **bounded** ** **by** ** **the** ** **Boundary** ** **( **`event_ranges`**, **`snapshot`**, **`state_scope`**, ** **or** ** **documented** ** **equivalents** ** per ** **§0.6** **/ ** **§11.1** **) **. **

**Multiple** **heads** **on** **a** **source** **log** **( **forks, ** **normative** **) **: ** When ** a ** **source** ** is ** an **`actor_log`** **( **or** ** **equivalent** **) ** and ** the ** **log** ** as ** **fetched** ** ( **or** ** **served** ** by ** the ** **origin** **) ** has ** more ** than ** one ** **head** ** event **( **a ** **fork** **) **, **a** ** **deterministic** ** **reducer** **MUST** ** **either: **( **1** )** **reject** ** the ** **input** ** as ** **ambiguous** **( **e.g. ** **treat** ** the ** **recompute** ** as ** **not** ** **fully** ** **verifiable** ** for ** that ** **input** ** set** **) **, **or** **( **2** )** **select** ** exactly ** one ** head ** per ** a ** **documented** ** **policy** **( **e.g. ** **longest** ** **valid** **`prev` ** **chain** **, ** most ** **recent** ** **signed** **`ts` **, ** **or** ** **an** ** **origin-** ** **declared** ** **`head` **) **. ** The ** **policy** **MUST** ** be ** **documented** ** in **`params`** **on** ** the **`relay.feed.definition.v1`** ** **state** ** and/or** ** the ** **implementation** ** **spec** ** for ** that ** **`reduce` ** **id. ** The ** **protocol** ** does ** not ** **mandate** ** a ** **single** ** **global** ** **fork**-** ** **resolution** ** **rule. **( ** **See** ** also ** **§0.6** **.) **

*Non-normative (UX):* **Lexicographic** `event_id` **tie**-**break** is over the **full** string (constant **`relay:event:`** **prefix** **plus** **hex**); **it** is **deterministic** and **functionally** **equivalent** to **sorting** the **event** **hash** **bytes** **alone**. **Equal** `ts` **strings** from **different** **actors** are **not** a **“simultaneous** **moment**” in **any** **physical** **sense**—the **reducer** **imposes** an **arbitrary** **but** **reproducible** **order** **via** `event_id`. **UIs** **SHOULD** **not** **present** **that** **order** as **“events** **at** **the** **same** **instant**” **without** **additional** **context** (e.g. **per-actor** **subordering** or **labelling** that the **order** is **spec-defined**, **not** **wall**-**clock** **resolution**). **This** is **not** a **protocol** **defect;** it **avoids** **false** **precision** from **comparing** **RFC 3339** **strings** with **1-second** (or **coarser)** **granularity** **across** **independent** **signers** **.**

**Nested `kind: "feed"` sources (§11.1), normative composition:** When a **source** **descriptor** **`kind: "feed"`** **names** the **`object_id`** of **another** **`relay.feed.definition.v1`**, **v1.4** **MUST** **fetch** **that** **nested** **definition**’s **state** **per** **§17.5** **at** **recompute** **time** and **MUST** **use** the **fetched** **object**’s **own** **`reduce`** and **`params`** to **materialize** that **nested** **definition** **into** an **ordered** **(or** **projected**)** **event** **list** **per** **that** **reducer**’s **specification** **. **A** **nested** **feed** **MUST** be **fully** **reduced** **(expanded** to **its** **output** **per** its **own** **definition) ** before **the** **enclosing** **feed**’**s** **`reduce`** is **applied** **;** this **order** **is** **not** **optional** **for** **audit** **: **an **outer** **recompute** **MUST** **not** **observe** **raw** **`kind: "feed"`** **source** **descriptors** **as** **if** they **were** **event** **streams. **Implementations** **MUST** **not** **merge** **unexpanded** **nested** **feed** **pointers** **(raw** **`kind: "feed"`** **source** **descriptors) ** with **sibling** **lists** or **treat** **them** **as** **if** they **were** **already** **chronological** **event** **streams** **. A** **later** **recompute** **at** **the** **same** **`object_id`** **may** **see** a **higher** **`version`**,** **so** **nested** **sourcing** **is** a **logical** **pointer** to **mutable** **state,** **not** a **content-addressed** **snapshot** of **one** **definition** **revision** **. The** **enclosing** **definition**’s **`reduce`** **then** **MUST** **merge** **that** **(fully** **reduced) ** **list** with **sibling** **sources** **according** to **the** **enclosing** **reducer** (for **`relay.reduce.chronological.v1`**, the **outer** **merge** is **the** **union** **chronological** **sort** **in** **§17.10**). If **both** use **the** **same** **`reduce` string** **and** **compatible** **params** **semantics**, **behavior** **matches** the **“** **single** **feed**”** case; **if** the **nested** **`reduce` differs** from the **outer** **`reduce`**, the **nested** **value** **governs** **only** **the** **subtree**—**v1.4** **does** **not** **redefine** **either** **reducer**; **it** **only** **requires** that **implementations** **not** **silently** **drop** the **distinction**. A **future** **revision** or **`registry/`** **entry** **MAY** add **tighter** **merge** **rules** for **specific** **(outer,** **inner)** **pairs**. **When** **documenting** **a** **recompute** **boundary** **(§11.1) **, **a** **`source_heads` **entry** **for** **`kind: "feed"`** **SHOULD** **capture** **the** **nested** **definition** **`version`** **and** **a** **cursor** **sufficient** **to** **replay** **the** **inner** **reduction** **(e.g. ** **last** **event** **id** **in** **the** **inner** **list) ** **so** **the** **enclosing** **audit** **is** **complete** **. **

*Non-normative (implementers):* **Outer** **feeds** **that** **nest** **`kind: "feed"`** **should** **expect** **recomputed** **output** to **vary** when **only** a **nested** **`relay.feed.definition.v1`** **`version`** **advances**—**including** **when** the **enclosing** **definition** **`version`** **and** **non-**`feed` **sources** **are** **unchanged** **(see** **Status** **—** **Deferred** **notes**, **Outer** **feed** **nesting** **a** **mutable** **`kind: "feed"`** **source**)** **.**

**Reducer input domains (normative):** Every **`reduce`** **identifier** ** **MUST** ** **have** ** **a** ** **formal** ** **definition** ** **that** ** **meets** ** **§22.7** **( ** **required** ** **input** ** **domain** ** **vocabulary; ** **required** ** **Boundary** ** **constraints** **) **. ** **Core** ** **ids** ** **in** ** **this** ** **section** ** **are** ** **defined** ** **here; ** **extensions** ** **MUST** ** **publish** ** **the** ** **same** ** **fields** ** **in** **`registry/`** ** **( ** **§22.7** **) ** **or** ** **a** ** **cited** ** **extension** ** **document** **. ** **The** ** **intent** ** **is** ** **static** ** **validation** ** **,** ** **tooling** **, ** **and** ** **execution** ** **that** ** **rejects** ** **invalid** ** **Boundary** ** **+ ** **`reduce` ** **pairs** ** **before** ** **running** ** **opaque** ** **code** **. **

**Additional reducers:** **MUST** **be** **registered** ** **per** ** **§22.7** ** **with** **`params`**, ** **types** **, ** **and** ** **merge** ** **semantics** ** **in** **`registry/`** ** **and/or** ** **cited** ** **from** ** **extension** ** **documents** **( ** **§22** **) **. ** **MUST** ** **be** ** **deterministic** ** **and** ** **versioned** **; ** **MUST** ** **not** ** **require** ** **out-** ** **of-** ** **band** ** **mutable** ** **global** ** **state** ** **as** ** **a** ** **MUST** ** **in** ** **core** ** **( ** **only** ** **fetched** ** **signed** ** **artifacts** ** **and** **`params` ** **bytes** ** **in** ** **the** ** **definition** ** **state** **) **. **

#### 17.11 View layer — feed output verification (v1.4, normative)

**Relay 2.0:** client-side (or indexer) **recompute** verifies a **View** over an agreed **boundary**; the origin does not solely define “correct” order for audit claims (**§0.2**–**§0.3**).


**Clients and mirrors MUST:**

1. **Obtain** the **feed** **definition** by **§17.5** (or an **equivalent** **signed** **snapshot** that **contains** the **state** at a **documented** **version**).
2. **Fetch** the **constituent** **logs** / **state** per **`sources`**, according to the **reducer** **rules** in **§17.10** (and **any** **extension** **spec** for **that** `reduce` **id** if **used**), **with** an **input** **boundary** **(§17.10) ** that **MUST** be **sufficient** **to** support **reproducible** **recompute** **(bounded** **window** and/or **snapshot+** **delta,** **as** **documented) **. ** For **cross-** **peer** **audit,** **the** **boundary** **SHOULD** **be** **the** **same** **logical** **one** **named** **in** **§11.1** **(definition** **id,** **`version`**, **`as_of`**, **`source_heads` **) ** when ** **those** **fields** **are** **exchanged. **
3. **Recompute** the **output** (ordered **list** of **events** or **documented** **projection** for that **reducer**) **independently** and **compare** to any **indexer-** or **origin-** **supplied** **ordering** (if **present**).

The **MUST** **in** this **list** is **reproducibility** **of** the **recompute** **for** a **stated** **(or** **implicitly** **agreed) ** **input** **set** and **the** **same** **definition;** **it** is **not** a **MUST** that **all** **implementations** use **the** **same** **unbounded** **log** **depth** **(see** **§17.10** **and** **“** **Scalability** **…** **”** **below) **. **

**Same** **definition** **+** **same** **explicit** **source** **boundaries** **(§11.1) ** ⇒ ** **same** **reducer** **output** for **a** **correct** **implementation;** **differing** **outputs** **with** **no** **other** **cause** **imply** **differing** **fetched** **input** **sets,** **differing** **definition** **state,** or **implementation** **bug. **UIs** **MUST** **not** be **obliged** to **store** a **full** **audit** **envelope** on **every** **frame**—**the** **spec** **governs** what **can** be **claimed** about **a** **view** when **boundaries** **are** **omitted** **(§11.1) **. **

If **recompute** **matches**, the **view** is **reproducible** for the **fetched** **inputs**. If it **fails** to **match** but **inputs** are **complete** and **signatures** **verify**, the **server**- or **indexer-** **supplied** **ordering** is **untrusted** for **v1.4** **interop**; the **recomputer** **MUST** **prefer** their **own** **deterministic** **output** for **subsequent** **downstream** **use** and **MUST** **not** **silently** **merge** **in** **inconsistent** **events**.

**Scalability and what the MUST does not require (v1.4, honesty):** The **MUST** **language** **above** **establishes** that **an** **honest** **verifier** **can** **always** **run** a **defined** **recompute** when **it** **chooses** to **settle** a **dispute** **or** **audit** a **view**—it **MUST** **not** be **read** as **“** every **client** **must** **fully** **recompute** **from** **all** **sources** **on** **every** **user** **interaction** **.”** **Large** **source** **logs** can **make** **full** **recompute** **expensive**; **typical** **products** **MAY** **cache** **results**, **recompute** **lazily**, or **spot-check** **stochastically**. Those **strategies** **reduce** **continuous** **cryptographic** **certainty** to **probabilistic** **/ policy-based** **confidence**—an **intentional** **trade** **this** spec **names** **rather** than **hides**. **If** a **stale** **cached** **view** is **re-used** after the **feed** **definition** **state** **gains** a **new** **`version`**, the **view** may **diverge** from **a** **fresh** **recompute** **(see** **§11.1** **SHOULD** for **tagging** **exports** with **definition** **`object_id` +** **`version`**). **When** **asserting** **strong** **cross-** **deployment** **repro** **or** **audit,** **pair** **the** **output** **with** the **recompute** **/** **audit** **boundary** **(§11.1) **; **caches** **without** **that** **pairing** **MUST** **not** be **described** **as** **the** **same** **class** of **artefact** **(§11.1) **. **

**Indexers and Feed Hosts (non-mandatory, behavior):** an **indexer** **MAY** return **caches**; **MUST** **not** be **treated** as **cryptographic** **proof** of **completeness** of **crawl** unless the **indexer** **also** **exposes** **transparency** **material** (**§17.9**). v1.4 **reproducible** **feeds** are **a** **tool** to **shift** **trust** to **verifiable** **recompute** **rather** than **unauditable** **curation** **alone** (**see §23.3**).

### 18. WebSocket relay protocol

Endpoint:

* `GET /ws`

Message envelope:

```json
{
  "op": "HELLO|SUB|UNSUB|PUB|EVENT|STATE|LABEL|PRIVATE_ACTION_HINT|ACK|ERROR|PING|PONG",
  "req_id": "client-generated-id",
  "body": {}
}
```

#### 18.1 HELLO

Client introduces itself.

```json
{
  "op": "HELLO",
  "req_id": "1",
  "body": {
    "client": "relay-web/0.1",
    "actor": "relay:actor:abc",
    "ws_endpoint": "wss://live.example/ws",
    "auth": {
      "nonce": "server-issued nonce (required when signing)",
      "ts": "2026-04-21T12:00:00Z",
      "sig": {
        "alg": "ed25519",
        "key_id": "key:active:1",
        "value": "base64..."
      }
    },
    "supports": ["state_push", "label_push", "channel_subscriptions"]
  }
}
```

**Unsigned `HELLO`:** `auth` **MAY** be omitted, or **`auth.sig`** omitted, for anonymous subscribe-only sessions as allowed by deployment policy.

#### 18.1.1 HELLO `auth` signature (v1.2, normative)

When **`auth.sig`** is present, the relay **MUST** verify an **Ed25519** signature (**§7.1**) over a **deterministic UTF-8 message** so that **independent implementations** agree on **what** is signed.

* **`auth.nonce`:** **MUST** be present and **non-empty**; **MUST** be the **server-issued** nonce for this connection attempt (or for this `HELLO` exchange if the server documents a challenge round-trip). The relay **MUST** enforce **replay** protection on **`nonce`** per **§18.4.4**.
* **`auth.ts`:** **MUST** be present; **MUST** be an **RFC 3339** instant (**§4.1.1.1**). The relay **MUST** enforce freshness per **§18.4.4** (align **±5 minutes** with server time unless documented otherwise).
* **`body.ws_endpoint`:** **MUST** be present when **`auth.sig`** is present; **MUST** be the **exact** WebSocket URL string the client used to open this connection (**scheme**, **host**, **port** if non-default, **path**; no trailing slash added unless actually used). This **binds** the signature to the relay endpoint and reduces cross-endpoint replay of captured `HELLO`s.
* **`sig`:** **MUST** use the same **`alg` / `key_id` / `value`** shape as envelope signatures (**§7**); **`key_id`** **MUST** resolve to an **active** key on **`body.actor`**’s identity document.

**Signature input (UTF-8 bytes, NFC on each line’s logical content per §4.1.2):** concatenate the following **five** lines, each terminated by a **single** **LF** (`0x0A`), **including** a final LF after the last line:

1. The **literal** domain-separator line: `relay.v1.2.ws_hello_auth`
2. **`body.actor`** (exact string)
3. **`auth.nonce`** (exact string)
4. **`auth.ts`** (exact string)
5. **`body.ws_endpoint`** (exact string)

The **Ed25519** signature **MUST** be computed over **those UTF-8 bytes** with no BOM. **Verifiers** **MUST** reject **`HELLO`** messages whose **`auth.sig`** does not verify against the message above.

#### 18.2 SUB

Subscribe to topics.

Supported subscription types:

* actor log head changes
* actor state changes
* channel feed changes
* label changes for target
* relay announcements
* **v1.5, optional, advisory (§13.5) **: **`private_action` **arrival **hints** for **an** **`actor` **(see **`PRIVATE_ACTION_HINT` **, **§18.5) **. **

```json
{
  "op": "SUB",
  "req_id": "2",
  "body": {
    "subscriptions": [
      {"type": "actor_state", "actor": "relay:actor:abc"},
      {"type": "channel_feed", "channel": "relay:channel:tech"},
      {"type": "private_action", "actor": "relay:actor:agent"}
    ]
  }
}
```

#### 18.3 PUB

Push signed object to relay for fan-out.

```json
{
  "op": "PUB",
  "req_id": "3",
  "body": {
    "kind": "state|log|label",
    "envelope": {}
  }
}
```

Relay behavior:

* validate envelope signature and schema
* optionally persist short-term cache
* fan out matching subscriptions
* **v1.5 (§10.5) **: **MUST** **not** **accept** **or** **fan-** **out** a **log** **envelope** on **`PUB` ** if **it** is **time-** **expired** **(phase** **(B) **) ** for **the** **relay** **(§10.5) **. **
* **(Non-** **normative) **: **a** **Fast** **Relay** **MAY** **evict** or **garbage-** **collect** **its** **own** **cache** **of** **envelopes** **per** **local** **policy** **(§10.5 ** **(C) **)** **; ** that **does** **not** **relax** **(A) **/ **(B) ** **acceptance** **for** **new** **`PUB` ** **or** **change** the **signed** **audit** **meaning** of **an** **event** **that** **peers** **store** **elsewhere. **
* relay does not become authoritative unless coupled with an origin service

**Normative** **security** and **enforcement** for `PUB` and sessions: **§18.4**.

#### 18.4 WebSocket security (v1.2, normative)

**18.4.1 Signed payloads**

`PUB` messages whose **`body.envelope`** carries **actor-authored** **signed** **objects** (**state** | **log** | **label** per **§7**) **MUST** include a **fully** **valid** **signed** **envelope** (signature verifies under the **actor**’s **current** key material per **identity** + **log** rules).

Relays **MUST**:

* **verify** **signatures** before **accepting** or **forwarding** a `PUB` payload
* **reject** **unsigned** or **invalid** objects

**18.4.2 Session binding**

If **`HELLO`** **authenticates** an **actor** (e.g. `body.actor` with **`auth.sig`** verifying per **§18.1.1**, or equivalent **documented** profile):

* the **WebSocket** **session** **MUST** be **bound** to that **actor**
* subsequent **actor-scoped** **operations** (e.g. `PUB` as that actor) **MUST** **match** the **authenticated** **actor**; **mismatch** **MUST** be **rejected**

**18.4.3 Session lifetime**

Relays **SHOULD** **enforce** **session** **expiration** (recommended: **≤ 1 hour** of inactivity or wall-clock, deployment-defined) and **require** **re-authentication** (new `HELLO` or new HTTP-secured token exchange) after expiration.

**18.4.4 Replay protection**

Relays **MUST**:

* **reject** **duplicate** **nonces** (or **equivalent** **anti-replay** **tokens**) **within** the implementation’s **replay** **window**
* **enforce** **timestamp** / **request** **freshness** within **±5** **minutes** of server time **unless** a **different** **bound** is **explicitly** **configured** and **documented** (align intent with **§19.4** for HTTP; WebSocket may use the same or a stricter local policy)

**18.4.5 Authorization**

Relays **MUST** **not** **accept**:

* **unsigned** **mutation**-class requests (no valid signature on the object to be propagated when signatures are required)
* **actor-scoped** **actions** **without** **valid** **authentication** when the op is not anonymous

#### 18.5 EVENT / STATE / LABEL

Server push message.

```json
{
  "op": "STATE",
  "req_id": "sub-2",
  "body": {
    "actor": "relay:actor:abc",
    "object_id": "post:01J...",
    "version": 4,
    "origin": "https://alice.example",
    "envelope": {}
  }
}
```

**`PRIVATE_ACTION_HINT` (v1.5, optional, advisory) **: **a** **Fast** **Relay** **MAY** **send** this **`op` ** to **a** **session** **that** **subscribed** **to **`private_action` **(§18.2) ** **for** a **given **`actor` **. ** The **`body` **MUST** **be** **treated** **as** a **convenience** **nudge** **only** **and** **MUST** **not** be **a** **substitute** **for** the **signed** **log** **envelope; ** see **§13.5 **(same **hint** **field** **semantics** **as** **`GET …/private-actions` **) **. **

```json
{
  "op": "PRIVATE_ACTION_HINT",
  "req_id": "sub-pa-1",
  "body": {
    "actor": "relay:actor:agent",
    "event_id": "relay:event:…",
    "ts": "2026-04-22T19:00:00Z",
    "tag": "64-char lowercase hex",
    "sender_hint": "relay:actor:requester",
    "unread": true
  }
}
```

* **Normative,** **v1.5 **(behavior) **: ** **Relays** **MUST** **not** **present** **`PRIVATE_ACTION_HINT` **as **proof** **that** **a** **private** **action** **was** **authentically** **received;** **clients** **MUST** **fetch** **and** **verify** **(§7,** **§17.3) **. **

### 19. Auth model

#### 19.1 Standard (v1.2, normative)

Relay v1.2 **MUST** use **[RFC 9421](https://www.rfc-editor.org/rfc/rfc9421) (HTTP Message Signatures)** for authenticated HTTP requests to origin APIs, including publication and other actor-bound mutations, unless a deployment is using a **deprecated** profile (§19.3) only for backward compatibility.

**Minimum signed components** (in addition to whatever the implementation needs for replay protection):

* **request target** (method and path; per RFC 9421)
* HTTP **Date** (or an agreed `created` / `expires` parameter in the signature as allowed by RFC 9421)
* **Content-Digest** (or equivalent body digest) over the **exact** request body bytes

The server **MUST** verify the digest and that the signature verifies under a key that is **bound** to the calling **actor** (§19.2).

#### 19.2 Actor binding

The HTTP message signature **MUST** map to an **actor identity** and an **active** (or permitted) key in that actor’s **identity document** at the time of verification. Implementations **SHOULD** reject requests where the key is not listed or is revoked.

#### 19.3 Legacy support (optional, deprecated)

Custom header auth as used in many v1.1 drafts **MAY** still be supported for transition (e.g. `X-Relay-Actor`, `X-Relay-Timestamp`, `X-Relay-Nonce`, `X-Relay-Signature`). It is **deprecated**; new implementations **SHOULD** implement RFC 9421 only.

For publication and actor-bound mutation without message signatures, servers **MAY** additionally accept:

* OAuth-style bearer token bound to actor identity
* session token from authenticated origin

when local policy allows; this is **not** a normative alternative to §19.1 for “Relay v1.2 interop” unless explicitly negotiated out of band.

#### 19.4 Replay and freshness (v1.2, normative)

**HTTP (RFC 9421)** and/or request metadata **MUST** bound how long a signed request (or its contained signature base) is valid, or replays and delayed replays can be abused.

* **Clock skew:** the server’s clock and the time claims in the request **MUST** agree within **±5 minutes (300 seconds)** for `Date` / `@date` and any `created` / `expires` (or equivalent) field used in the signature. The server **MUST** reject the request as **stale** or **invalid** if those times fall **outside** that skew window relative to the server’s current time, unless a deployment has a **documented** larger skew policy (not recommended for public interop).
* **Request freshness:** at least one of the following **MUST** be present and verified (exact header names can follow RFC 9421 and deployment profile):
  * a **`Signature` (or related) `created` / `expires` parameter** or **`@date`** such that the signature’s validity window is **bounded** and checked; **or**
  * a **nonce** (or one-time `request_id` bound to a server-issued **challenge** storage) in the **signed** components, **MUST** be **unique** per **actor** (and key id, if used) **within a rolling time window of at least 5 minutes** (server-defined retention, **MUST** be long enough to detect duplicates); **or**
  * a **combination** of `Date` + `Content-Digest` + a **short-lived** server-issued session id in the signed path (still subject to the skew rule above).
* The server **MUST** reject requests whose signature is **expired** (`expires` in the past, or equivalent) or whose nonce **reuses** a value already seen in the same actor+window.
* **WebSocket** `HELLO` / `PUB` and similar are **MUST** use the same skew and replay limits **if** they carry request-like signing; otherwise they rely on the secure transport + session rules in **§18** and deployment policy (still **SHOULD** use bounded tokens).

Clients **MUST** send a fresh **`Date`** header on signed HTTP requests; servers **MUST** validate it against **§19.4** in addition to **§19.1** verification.

### 20. Revocable and ephemeral APIs

#### 20.1 Key grant retrieval

`GET /actors/{actor_id}/keys/{key_id}`

Returns wrapped content-key grants for authorized clients.

#### 20.2 Key revoke

`POST /actors/{actor_id}/keys/{key_id}/revoke`

Body:

```json
{"reason": "delete|membership_change|manual_revoke"}
```

Server effect:

* publishes `state.revoke` log event
* stops serving future grants

Important semantic note:

* revocation prevents future authorized reads only
* it does not erase prior plaintext copies

#### 20.3 Revocable content (clarified)

* **Guarantees:** revocation **prevents future authorized reads** of protected material at honest origins/relays.
* **Does not guarantee:** deletion from all **mirrors**, all **recipients** who already copied data, or **compromised** or malicious **clients**.

#### 20.4 Ephemeral content (clarified)

* **Provides:** time-bounded availability and **best-effort purge** by **compliant** clients and servers; metadata MAY carry expiry and TTL.
* **Does not provide:** cryptographic erasure, screenshot protection, or enforceable “no retention” against malicious peers.

**Client requirements (ephemeral and expired content):**

* **MUST** purge local **plaintext** after expiry (best-effort where the OS allows)
* **MUST NOT** render or treat as current objects past their effective expiry
* **MUST** surface expiration metadata where relevant (e.g. “expired at …”)
* **MUST** **not** **assume** a **single** **`GET` ** **log** **range** **(§17.4) ** is **a** **complete** **contiguous** **history** **for** **audit** **across** **time-** **expiry** **/ ** **garbage-** **collection** **unless** the **response** **metadata** **(e.g. ** **`expired_omissions_possible` **, ** **`as_of` **) ** or **a **strong** **completeness** **claim** **makes** **that** **warranted** **(see** **§17.4) **
* **MUST NOT** imply **guaranteed** deletion, memory wiping, or peer behavior

**UX (compose time):** for ephemeral posts, the composer **MUST** show a short warning such as: **“Ephemeral content may still be captured by recipients.”**

### 21. Error model

All APIs return structured errors.

```json
{
  "ok": false,
  "error": {
    "code": "invalid_signature|conflict_version|conflict_detected|unknown_actor|forbidden|unsupported_extension|schema_error|fork_detected",
    "message": "human-readable detail"
  }
}
```

Error objects **MAY** add fields such as `object_id` and `expected_version` (integer) for machine-readable repair (see `conflict_detected` below).

**`conflict_detected` (v1.2, required new code):** returned when the server has detected a state **version** conflict. Example:

```json
{
  "ok": false,
  "error": {
    "code": "conflict_detected",
    "message": "State version conflict detected",
    "object_id": "post:01J…",
    "expected_version": 4
  }
}
```

### 22. Extension model

#### 22.1 Registry and naming

Core extension identifiers use the **namespace**:

* `relay.ext.<name>.v<version>`

The **MVP** log-event **`data`** payload shapes for the most common `type` values are **normative in Appendix B** of this document. **Other** `type` values use **deferred** `data` schemas and **SHOULD** be named and versioned the same way (or in a companion “log event data” spec) so that `trust.attest`, `membership.add`, etc. are not **silently** incompatible—see **§10.2**.

**Extension registry (companion, v1.2):** This repository’s **`registry/`** directory is the **MVP** **public** **registry** for log-event `data` definitions and (optionally) **`relay.ext.*`** object extensions. Each entry is one **JSON** (or **Markdown**) file; see **`registry/README.md`**, **`registry/CONTRIBUTING.md`**, and the **seed** entries (e.g. `trust.attest`, `membership.add`, `state.revoke`) there. The registry **supplements** this spec; it does **not** **override** **Appendix B** for the five **MVP** **normative** `type` + `data` rows.

**Broader registry coverage**—making **additional** log-event **`data`** types **first-class normative interop** in the **core** spec (beyond **Appendix B** / **Appendix C** and companion **`registry/`** drafts for types **not** yet promoted)—remains the **default** for **arbitrary** new **`type`** strings. **v1.4** has **promoted** **`action.request`**, **`action.commit`**, and **`action.result`** into **Appendix C**; other **`data` shapes** follow **§22.1** until a future revision. See **Status** in this document.

**`action_id` **and ** **`registry/`** **(v1.4) **: **Using ** **`data.action_id` **on **`action.request` **(§13.4) ** does ** ** not ** ** require ** ** a ** ** companion ** ** registry ** file **. ** A ** ** registry ** **- ** backed ** ** set ** of ** ** standard **`action_id` ** ** strings ** ** MAY ** be ** ** added ** ** later ** under ** this ** ** §22 ** process **( **e.g. ** ** to ** ** ease ** ** discovery ** ** or ** ** pin ** ** common ** ** names **) **; ** that ** is ** ** optional ** ** convenience **, ** not ** a ** ** gate ** to ** ** wire ** **- ** level ** use **. **

#### 22.2 Extension object requirements

Each published extension (when used in `ext` / `ext_payload`) **MUST** define, in human-readable specification form:

* **schema** and field semantics
* **validation** rules
* **compatibility** behavior (ignore vs reject unknown fields) for forward/backward version pairs

#### 22.3 Core fields

Objects MAY include:

* `ext`: array of extension identifiers
* `ext_payload`: namespaced extension data
* `ext_required` (optional boolean, default **false**): if **true**, a **consumer** that does not implement **all** listed `ext` ids **MUST NOT** treat the object as a **complete** or **canonical** rendering of that type (see **§22.5**).

Example:

```json
{
  "type": "post",
  "ext": ["relay.ext.richtext.v1"],
  "ext_required": false,
  "ext_payload": {
    "relay.ext.richtext.v1": {"format": "markdown"}
  }
}
```

#### 22.4 Client behavior (optional extensions)

If **`ext_required` is absent or false** and an extension is **unsupported** on the client, the client **MUST** ignore unknown `ext_payload` fields **safely** (no corrupt round-trips), **MUST NOT** mutate the object in a way that would invalidate signatures or state, and **SHOULD** render a **fallback** (metadata-only) view when possible.

#### 22.5 Required extensions and version negotiation (v1.2, normative)

If **`ext_required` is true**:

* the object **MUST** list in **`ext`** every extension that is **required** for a faithful representation;
* a client that **lacks** one or more of those extensions **MUST** treat the object as **partially renderable** only: it **MUST NOT** show it as the same **UI class** as a fully supported post (e.g. must not use the normal “post card” with full metrics if layout depends on a missing ext), **MUST** show **unsupported** / **incomplete** affordance, and **MUST** still **preserve** `ext` / `ext_payload` on round-trip if it edits other fields;
* **safety (additional, v1.2):** clients **MUST** **not** perform **operations** that **assume** full **semantic** **understanding** of the object (e.g. merges, “smart” edits, ranking) as if the **missing** extensions were **absent** in meaning. Clients **MUST** **not** **modify** or **reserialize** the object in ways that could **corrupt** **extension**-controlled **meaning** (preserve raw signed **material**; follow **round-trip** rules in **§22.4**);
* **Clients** **SHOULD** use **fallback** **rendering** and a clear **indicator** that an **extension** is **required** but **unsupported**;
* **version negotiation** is by **`ext` id** including a **version suffix** (`relay.ext.name.v1` vs `v2`). A client that speaks only `v1` and receives `v2` **MUST** treat that extension as **unsupported** and apply the same **§22.4** / **§22.5** rules for optional vs **ext_required** as appropriate.

**Ignore-unknown** (§22.4) **does not** mean “pretend a required extension is present”; it means **no silent corruption** of unknown bytes.

#### 22.6 Relay policy JSON (client handling)

The same **ignore-unknown** and **round-trip** discipline applies to **top-level** JSON from **§32.1** (`GET /relay/policy` or equivalent): **MUST** ignore unknown policy keys for automation; **MUST NOT** base security or rate-limit bypass decisions solely on unauthenticated policy text; **SHOULD** treat a failed or missing policy document as “unknown” and use conservative local defaults.

#### 22.7 Reducer identifiers (`relay.reduce.*`) — registry fields (normative)

Every **`relay.reduce.<name>.v<version>`** **identifier** **MUST** **have** **a** ** **single** ** **authoritative** ** **machine-** ** **readable** ** **definition** **: ** **core** ** **ids** ** **in** ** **§17.10** **; ** **all** ** **others** ** **in** **`registry/`** ** **( ** **companion** ** **JSON** ** **or** ** **Markdown** ** **per** ** **§22.1** **) ** **or** ** **in** ** **an** ** **extension** ** **document** ** **cited** ** **by** ** **the** ** **registry** ** **entry** **. ** **That** ** **definition** ** **MUST** ** **declare** ** **both** ** **of** ** **the** ** **following** ** **( ** **validators** ** **and** ** **execution** ** **engines** ** **use** ** **these** ** **to** ** **check** ** **Boundaries** ** **before** ** **evaluation** **) **: **

1. **Required input domains** — a ** **closed** ** **set** ** **of** ** **tokens** ** **drawn** ** **from** ** **this** ** **vocabulary** ** **( ** **extend** ** **only** ** **with** ** **a** ** **profile** ** **or** ** **spec** ** **revision** **) **: **`event_log`** **( ** **per-** **`actor` ** **append-** **only** ** **events** **) **; **`state_object`** **; **`snapshot_membership`** **( ** **state** ** **set** ** **from** **`relay.snapshot.v1` **) **; **`channel_expansion`** **; **`nested_feed`** **. ** **The** ** **definition** ** **MUST** ** **list** ** **exactly** ** **which** ** **of** ** **these** ** **the** ** **`reduce` ** **implementation** ** **reads** ** **( ** **and** ** **any** ** **optional** ** **domains** **) **. **

2. **Required Boundary constraints** — **which** ** **§0.6** ** **Boundary** ** **keys** ** **( ** **`snapshot`**, **`event_ranges`**, **`state_scope` ** **/ **`id_range`**, ** **or** ** **profile-** ** **equivalents** **) ** **MUST** ** **be** ** **present** ** **( ** **and** ** **any** ** **additional** ** **constraints, ** **e.g. ** **nested** ** **`feed` ** **version** ** **pins** **) ** **so** ** **that** ** **( **a **) ** **the** ** **finite-** ** **input** ** **rule** ** **( ** **§0.6** ** **( **1** ) ** **–** **( **3** **) **) ** **is** ** **satisfied, ** **and** ** ( **b** ) ** **the** ** **reducer’s** ** **fetches** ** **are** ** **unambiguous** **. **

**Registry** ** **conformance** **: ** **A** ** **validator** ** **MUST** ** **reject** ** **an** ** **evaluation** ** **request** ** **( **`reduce` ** **+** ** **Boundary** **) ** **at** ** **validation** ** **( ** **static** ** **/ ** **plan** ** **time** **) ** **when** ** **the** ** **Boundary** ** **does** ** **not** ** **meet** ** **the** ** **declared** ** **constraints, ** **or** ** **when** ** **the** ** **`reduce` ** **id** ** **has** ** **no** ** **such** ** **definition** **( ** **unknown** ** **id** ** **) **. ** **It** ** **MUST** ** **not** ** **run** ** **the** ** **reducer** ** **and** ** **claim** ** **a** ** **deterministic** ** **/ ** **audited** ** **result** **. **

**Core** ** **`reduce` ** **ids** ** **( ** **`relay.reduce.chronological.v1`**, **`relay.reduce.reverse_chronological.v1`**) **: ** **the** ** **authoritative** ** **declaration** ** **for** ** **( **1** ) ** **and** ** **( **2** ) ** **is** ** **the** ** **bullets** ** **and** ** **“** **Declared** ** **input** ** **domains** **” ** **in** ** **§17.10** **, ** **together** ** **with** ** **the** ** **finite-** ** **input** ** **rule** ** **( ** **§0.6** ** **( **1** ) ** **–** **( **3** **) **) **. **

### 23. Security considerations (v1.2, normative)

#### 23.1 Threat model summary (what Relay defends)

* **host loss** → mirrors and multi-origin hints improve availability of public artifacts
* **replay** → mitigated by signatures, **§19.4** freshness (skew, nonce / expires), and state **version** discipline
* **impersonation** → mitigated by identity keys, rotation, and recovery rules
* **spam amplification** → mitigated by relay and origin **policy** (rate limits, accept lists), not by protocol magic

#### 23.2 Non-goals and residual risks (honesty requirements)

* Relay does **not** guarantee **deletion** after a recipient (or a compromised client) has learned plaintext
* Relay does **not** promise **global** censorship-resistance; availability is operator- and network-dependent
* Relay does **not** guarantee **global identity uniqueness** (handles are not a substitute for out-of-band binding)
* **Malicious** or non-conforming **clients** may retain, forward, or mis-display data; the protocol can only make honest behavior unambiguous
* **Dominant indexers** can skew discovery; clients **SHOULD** diversify sources
* **Trust signals** can still social-centralize if users converge on a few issuers; this spec only requires verifiable attestation, not a fixed hierarchy
* **`channel_id` and global vs legacy (v1.3 update):** **§4.3.1** normatively defines **`relay.channel.genesis.v1`**, so any two deployments that use the **same** genesis object **MUST** produce the same **`channel_id`** (shared genesis out of band, or migration tool). **Legacy** (pre-v1.3) **opaque** ids **MAY** still differ for the “same” human-meaning channel, so **§13.3** **aliases** and **indexers** may remain **load-bearing** for older data. v1.3 **reduces** accidental fragmentation for **new** channels but **does not** force migrations.
* **v1.4 `data.action` strings (residual interop):** the **commitment** and **log** **signatures** **bind** a **concrete** **`data.action` string** and **`input_refs`**, not an **abstract** “intent.” **No** two **vendors** are **obliged** to **use** the **same** string for a **logically** **identical** **operation** **until** a **later** spec **or** **registry** **standardizes** **action** **identifiers**; **verifiers** **MUST** **treat** **mismatched** **strings** as **different** **actions** in **conformance** **and** **security** **analysis** **even** if **product** **marketing** conflates them. (See **status** **deferred** **row**; **largest** **practical** **open** **interop** **item** for **action** **events**.)
* **`agent_params` in `action.commit` (v1.4, honesty):** the **object** is **covered** by **`commitment_hash`**, so **independent** **verifiers** **can** **detect** **tampering** after the **commit** **is** **signed**. v1.4 **does** **not** **normatively** **constrain** what **belongs** **inside** **`agent_params`** **beyond** **§4.1**; **a** **malicious** or **incompetent** **agent** **can** **commit** to **params** that **yield** **wildly** **different** **downstream** **outputs** or **mislead** **about** off-protocol **model** **use**. **Payment**-grade **reliance** on **`agent_params`** **requires** **deployment** **policy**, **reputation**, **or** **extensions** that **v1.4** **does** **not** **supply**.
* **`action.request` addressing any `target` (v1.4, abuse / UX):** the **request** **event** is **on** the **requester**’s **log** **only**; the **target** **agent** **does** **not** sign it **and** **is** **not** **obliged** to **acknowledge** it **or** to **append** **`action.commit` / `action.result` **. **Absence** **of** **commit/result** **MUST** **not** be **interpreted** as **a** **warranty** of **nack,** **rejection,** or **non-** **delivery**; **it** is **only** **“** **no** **agent-** **signed** **receipt** **(yet** **or** **ever) **. **A** **verifier** **MUST** **not** **infer** **consent**, **partnership**, or that **the** **agent** **agreed** to **X** from a **lone** **`action.request`**. Unanswered **requests** are **a** **normal** **outcome**; they **MUST** **not** be **read** as **proof** of **a** **relationship** **or** **endorsement** by the **target**. (Aligns with **§13.4**; **rate** / **spam** **controls** are **out-of-origin** **policy**, as for other **public** **append** **surfaces**.)

#### 23.3 Non-normative: v1.4 agent interaction and deterministic feeds (ecosystem notes)

*This section is **informational** for protocol implementers. It **MUST** **not** be **treated** as a **MUST/SHALL** test vector.*

* **Why action events?** The **action** **event** **chain** **`action.request` / `action.commit` / `action.result`** (**§13.4**) **gives** a **portable, signed, auditable** way to model **“A asked B to do X, B bound itself to a commitment, B published outputs”** using **the same** **per-actor** **logs** and **Ed25519** **rules** as the rest of Relay. It **enables** **ecosystem**-level **agent** and **automation** **flows** (summarization, tool use, human-in-the-loop) **without** **embedding** a **Turing**-complete **runtime** in the **protocol** or **requiring** a **shared** **global** **scheduler**—**each** **origin** and **verifier** **decides** **policy** and **safety** **outside** this spec.

* **Why deterministic feed definitions?** If **all** a **“feed”** is, is a **proprietary** **indexer** **ranking** **array**, then **“what you see”** is only as **strong** as **that** **operator**’s **word**. **`relay.feed.definition.v1` + `relay.reduce.*` (§11.1, §17.10–§17.11)** make **a** **feed** a **verifiable, reproducible** **view** of **fetched, signed** **inputs**—**reducing** the **chance** that **a** **single** **indexer** becomes an **unauditable** **bottleneck** for “what the network is,” **without** a **chain-wide** **consensus** **engine**.

* **Composability vs applications:** v1.4 **adds** **primitives**; it **does** **not** **standardize** **full** **applications** (a **messaging** **UI**, a **recommendation** **product**, an **MCP** **router**). **Action** and **feed** **objects** are **meant** to be **stacked** with **state**, **channel**, **label**, and **extension** **objects** (**§22**). **Clients** and **communities** **define** which **`data.action` strings** and **`params`** are **trustworthy** for **which** **purposes**—**the** **protocol** only **makes** **mis**-**representation** and **inconsistent** **ordering** **detectable** when **peers** **check** the **signed** **artifacts**.

* **Non-normative — private** **action** **addressing** **(v1.5,** **§13.5) **: **Hiding** **plaintext** **`target` **and** **inner** **`data` **(via **`relay.ext.private_action.v1` **) **on** the **signed** **public** **log** **reduces** **metadata** **leakage** for **sensitive** **agent** **interactions**; **onlookers** **see** only **a** **tag** and **ciphertext,** not **cleartext** **“** **who** **asked** **whom** **”** **on** the **wire. **The** **commitment-** **chain** **audit** **model** **(§13.4) ** is **not** **broken: ** any** **party** **with** **decryption** **keys** **(typically** the **agent) ** and **the** **usual** **§13.4** **fetch** / **recompute** **path** **still** **derives** the **same** **`commitment_hash` ** from **decrypted,** **§4.1**-**canonical** **request** **bytes,** so **independent** **verifiers** **retain** the **same** **receipt-class** **assurances** as **for** **plaintext** **`action.request` **. **(Observers** **who** **only** **see** **`tag` **without** the **preimage** **MUST** **not** **infer** **a** **unique** **requester**–**agent** **pair;** **see** **§13.5) **. **

* **Non-normative — private** **action** **discovery** **(v1.5,** **UX) **: **an** **optional** **`GET …/private-actions` ** **index** **and/or** **`SUB` **+ **`PRIVATE_ACTION_HINT` **(§13.5, **§17,** **§18) ** can **nudge** **agent** **clients** **that** **new** **events** **may** **exist,** **but** they **are** **explicitly** **advisory** **and** **do** **not** **constitute** a **messaging** **system** or **a** **substitute** **for** **fetching** **and** **verifying** the **signed** **envelope. **

---

## Part II — Reference server + relay implementation (non-normative reference)

*Relay 2.0* **roles** (Actor Origin, Feed Host, Fast Relay, Mirror, Indexer) implement Truth transport and View materialization in a concrete deployment (**§1** with Part I below).


### 24. Deployment topology

Reference implementation is split into three services plus optional extras:

1. **Origin API**

   * authoritative identity + state + log write path
2. **Static Feed Host**

   * serves immutable log chunks and state snapshots
3. **Fast Relay Service**

   * WebSocket fan-out and short-lived caches
4. **Optional Indexer**

   * search, channel aggregation, and discovery views; expose **§17.9** (`GET /indexer/policy`, `GET /indexer/sources`) when offering an Indexer so clients can inspect **ranking inputs**

A small install may run Origin API + Static Feed Host + Fast Relay in one process.

#### 24.1 Snapshot emission cadence (operational, non-normative)

Part I does not prescribe when origins MUST create `relay.snapshot.v1` objects. Typical policies include time-based schedules, after large ingests, before expensive queries, or never (relying only on on-demand state fetches and Views). Publish SLOs or runbooks for auditors where strong snapshot-backed claims matter.

### 25. Recommended stack

Reference choices:

* language: TypeScript/Node for fastest ecosystem reach, or Go for simpler deployment and lower memory
* durable database: PostgreSQL
* blob/object storage: S3-compatible bucket or local object store
* cache/pubsub: Redis or NATS
* WebSocket: native ws server or NATS-backed gateway

### 26. Core modules

#### 26.1 Identity module

Responsibilities:

* resolve and serve identity docs
* key lookup
* guardian recovery workflows
* trust signal attestation storage

Tables:

* actors
* actor_keys
* guardians
* handles
* trust_signals

#### 26.2 State module

Responsibilities:

* validate state object writes
* maintain latest state per object
* maintain version history if enabled
* emit commit hooks

Tables:

* state_objects_latest
* state_versions (optional but recommended)
* object_tombstones

#### 26.3 Log module

Responsibilities:

* append validated events
* maintain head pointer per actor
* expose pagination and range queries
* detect forks/conflicts

Tables:

* log_events
* actor_log_heads
* log_forks

#### 26.4 Channel module

Responsibilities:

* channel state
* membership actions
* acceptance/removal refs
* policy resolution

Tables:

* channels
* channel_membership_events
* channel_content_refs

#### 26.5 Label module

Responsibilities:

* store and query labels
* scope filtering
* issuer authenticity

Tables:

* labels
* label_targets

#### 26.6 Relay module

Responsibilities:

* websocket sessions
* subscriptions
* fan-out
* rate limits
* short-term object cache

In-memory or Redis-backed structures:

* sessions
* subscription_index
* rate_limit_buckets
* relay_recent_cache

### 27. Publication flow

#### 27.1 State publish flow

1. authenticate request
2. parse + canonicalize object
3. verify signature
4. validate schema + content/storage class pairing
5. compare version against latest
6. upsert latest state
7. persist version history if enabled
8. emit event to message bus
9. if `storage_class=dual`, append `state.commit` log event
10. notify Fast Relay
11. asynchronously write snapshot/update to object storage

#### 27.2 Log append flow

1. authenticate request
2. canonicalize + verify signature
3. validate `prev`
4. append row
5. update head pointer
6. write immutable chunk or append segment file
7. notify Fast Relay

### 28. Feed hosting layout

Static layout suggestion:

```text
/actors/{actor_id}/identity.json
/actors/{actor_id}/log/head.json
/actors/{actor_id}/log/chunks/000001.jsonl
/actors/{actor_id}/log/chunks/000002.jsonl
/actors/{actor_id}/state/latest/posts/{object_id}.json
/actors/{actor_id}/state/latest/profile.json
/channels/{channel_id}.json
```

Log chunks SHOULD be append-once immutable JSONL segments.

### 29. Snapshot strategy

To reduce polling cost:

* generate actor state snapshots every N writes or T minutes
* include object IDs, versions, updated timestamps, and hashes
* **Consistency (align Part I, §17.6, normative):** a **published** **snapshot** (file or `GET /actors/{actor_id}/snapshots/latest`) **MUST** be **self-consistent** for **all** **included** objects as of a **single** **logical** **commit** **boundary** on the origin. **MUST** **not** **mix** **versions** from **different** **generations** of the same object. A snapshot **MAY** be **partial**; if so, **metadata** **MUST** make **partial** **coverage** **clear**. Implementations **SHOULD** use the **canonical** **`snapshot_id` / `as_of_ts` / `partial`** shape from **Part I §17.6**. **MUST** **not** label a response a **snapshot** if it is **inconsistent**. See **Part I §17.6** for feed pagination vs snapshot labeling.
* It remains **valid** to serve **non-snapshot** **incomplete** lists (cursors, limits) as ordinary query results, not as a normative **snapshot** unless documented as such.

Endpoint:

* `GET /actors/{actor_id}/snapshots/latest`

### 30. Relay implementation behavior

Fast Relay is explicitly non-authoritative.

Responsibilities:

* accept authenticated or anonymous subscriptions
* accept signed pub pushes from origins or clients
* deduplicate by object/event ID
* fan out matching updates
* optionally cache recent updates for replay window

Non-responsibilities:

* permanent storage
* canonical history
* trust adjudication beyond local relay policy

### 31. Relay replay window

Recommended:

* keep 1 to 30 minutes of recent updates in memory or Redis
* allow reconnecting clients to request replay since last seen cursor

Endpoint via WebSocket message:

```json
{
  "op": "SUB",
  "req_id": "9",
  "body": {
    "subscriptions": [{"type": "channel_feed", "channel": "relay:channel:tech"}],
    "since": "relay:cursor:12345"
  }
}
```

If replay unavailable, client falls back to HTTP snapshot.

### 32. Rate limiting and abuse control

Reference server policies:

* per-IP and per-actor publish rate limits
* per-relay session subscription limits
* per-channel submission throttles
* optional relay write fees or membership policies

Policy surfaces **MUST** be inspectable by clients. When an implementation exposes a policy URL (e.g. `GET /relay/policy`), the response **SHOULD** be **machine-readable** JSON as in **§32.1** so clients are not required to scrape HTML. (Part II is **reference**; a production profile built on v1.2 may **normatively** require this shape in a separate deployment spec.)

#### 32.1 Machine-readable policy response (v1.2)

Implementations that expose `GET /relay/policy` (or an equivalent) **SHOULD** return `Content-Type: application/json` and a top-level object usable by automation. Example (values are **illustrative**; servers set their own limits and fee schedules). Extra keys are **allowed**; **client** handling is **Part I, §22.4**.

```json
{
  "version": 1,
  "max_publishes_per_minute_per_actor": 120,
  "max_publishes_per_minute_per_ip": 600,
  "max_websocket_subscriptions_per_connection": 200,
  "max_channel_submissions_per_minute": 30,
  "default_trust_floor": ["cryptographic_only"],
  "write_cost_credits": 0,
  "credits_per_actor_per_day": null,
  "notes": "Human-readable; do not use as machine control surface."
}
```

* **`version`:** non-negative integer; **SHOULD** be present in new deployments so clients can branch on future formats.
* **Rate and cost fields** (`max_publishes_per_minute_per_actor`, `write_cost_credits`, etc.): if present, values are a non-negative number or `null` where `null` means “no cap / not applicable (per server’s docs).”
* **`default_trust_floor`:** optional array of strings, same intent as `policy.trust_floor` on channels; clients **MAY** use for UI defaults.
* **Client requirements:** see **Part I, §22.4** (this Part II example is not normative in isolation).

### 33. Consistency model

#### 33.1 State

* the **origin** is authoritative
* the **last** valid, accepted version is current (subject to conflict repair per §5)
* equal `version` with different payload is a **conflict**; clients and mirrors **MUST** follow §5

#### 33.2 Log

* append-only per actor chain; **forks** are a normal possibility
* forks **MUST NOT** be **silently collapsed**; at least one honest implementation strategy is to preserve divergent heads for inspection
* **identity** supersession (recovery, rotation) is governed by the identity and key rules; the log may show multiple valid-looking histories that clients reconcile per §5.4

#### 33.3 Fork causes (v1.2)

Common causes: **network partition**, **concurrent writes** from multiple devices, **malicious** actors, **mirror** inconsistency, or **replay** from stale caches. None of these justify silent collapse of a fork without policy.

#### 33.4 Client strategy (non-normative; aligns with Part III)

Clients **SHOULD**: detect divergence, attempt **origin** reconciliation, mark fork or conflict state in UI, and when choosing a chain prefer (in order, when applicable): **valid signatures**, a **consistent** chain, and **recovery-key** or equivalent authority (§5.4) over stale branches.

### 34. Recovery workflows

#### 34.1 Guardian recovery

1. actor requests recovery challenge
2. origin publishes pending recovery object
3. guardians submit signatures
4. waiting period begins
5. original key may veto during delay
6. if not vetoed and threshold met, new active key becomes valid
7. origin emits `key.rotate` and identity update

### 35. Optional P2P support

Reference implementation MAY add a fetch/mirror daemon:

* announces available actor feed chunks
* serves cached immutable log chunks and public state snapshots
* never becomes sole required path

This allows pure P2P survival mode without making it the primary UX path.

---

## Part III — Client architecture (non-normative reference)

*Relay 2.0* clients **materialize** **Views** by fetching **Event** / **State** per Part I and optionally recomputing feeds (**§17.10**–**§17.11**).


### 36. Client goals

A Relay client should:

* own keys safely
* render current state consistently
* preserve local moderation control
* sync reliably over flaky networks
* degrade gracefully from live relay to HTTP polling

### 37. Client layers

#### 37.1 Identity & key manager

* actor keys
* recovery config viewer
* device session keys
* optional secure enclave / OS keychain integration

#### 37.2 Local store

Use a normalized local database (SQLite/IndexedDB).

Suggested stores:

* actors
* identities
* log_events
* state_latest
* state_history_refs
* labels
* channels
* subscriptions
* sync_cursors
* relay_policies

#### 37.3 Sync engine

Responsibilities:

* bootstrap identity
* fetch snapshots
* subscribe to Fast Relay
* reconcile state updates
* detect divergence, **mark fork/conflict** state, and refetch or reconcile with **origin** (see **§5**, **§10.4**; **Part II §33**)

#### 37.4 Policy engine

Responsibilities:

* apply local moderation rules
* merge labels from selected sources
* apply channel policy and trust floors
* compute final visibility state

#### 37.5 Composer/publisher

Responsibilities:

* build canonical objects
* sign locally
* publish to origin
* optionally push to relay for fast fan-out

### 38. Client sync flow

#### 38.1 Bootstrap

1. resolve identity doc
2. fetch actor snapshot(s)
3. fetch log head(s) if needed
4. populate local store
5. connect to one or more relays from origin hints or user config
6. subscribe to followed actors/channels

#### 38.2 Live sync

When relay sends update:

1. verify envelope signature
2. if state object version is newer than local, apply
3. if version skips beyond one and object is important, schedule origin fetch
4. update UI from local store
5. store cursor for replay

#### 38.3 Reconnect flow

1. reconnect to previous relay(s)
2. request replay from last cursor
3. if replay gap, fetch HTTP snapshot from origin
4. reconcile

### 39. Timeline architecture

The client timeline is a projection, not a protocol object.

Pipeline:

1. collect followed actor posts + channel accepted refs
2. filter through policy engine
3. sort according to selected timeline strategy
4. render from local state cache

The protocol does not mandate ranking.

### 40. Channel integration

Client keeps separate concepts for:

* authorship (post owner)
* inclusion (channels referencing or accepting a post)
* moderation (labels and channel removal actions)

A post removed from a channel is not erased from the actor profile unless locally filtered.

### 41. Edit/delete UX semantics

The client MUST present different semantics by content class:

* `durable_public`: “Public and durable; deletion is suppressive only.”
* `mutable_public`: “Public; latest version is authoritative.”
* `revocable`: “Future access can be revoked for authorized viewers.”
* `ephemeral`: “Time-bounded visibility only; recipients may still retain copies.”

For `ephemeral` (and, where applicable, other time-limited content), the compose surface **MUST** also make clear that **ephemeral content may still be captured by recipients** (screenshots, other clients, etc.). Warnings for audience and retention class should be **visible at compose time**, not only after send.

### 42. Offline mode

Client MUST support:

* local draft composition
* delayed publish queue
* cached reading of synced state/logs
* eventual resend when origin/relay available

If pure P2P add-on exists, client MAY fetch public cached chunks from peers.

### 43. Multi-account architecture

Recommended model:

* one workspace
* multiple actor identities
* per-identity key storage
* per-identity relay/origin preferences
* shared but partitioned local cache

### 44. Security architecture

Client SHOULD:

* store private keys in OS keychain/secure enclave where possible
* never send raw private keys to origin or relay
* sign locally
* verify every incoming signature before durable local commit
* isolate extension rendering from core data model

### 45. Extension handling

Clients advertise supported extensions and **degrade** gracefully, consistent with **§22.4–§22.6**: ignore unknown `ext` fields without corrupting the signed core; never serialize edits that would invalidate foreign extensions you do not understand.

If **`ext_required`** is **true** (for meaningful rendering) and a listed extension is not supported, follow **§22.5** (do **not** present as the normal canonical post type).

If an object includes a **required** (for meaningful rendering) extension that is not supported:

* display **fallback** / **incomplete** metadata
* **MUST NOT** mutate the object in a way that breaks signatures, versions, or unknown payloads
* **MUST** preserve unknown extension payloads when re-emitting as an editor or proxy, unless the user explicitly waives that guarantee in a product-specific way (out of band to this spec)

### 46. Minimal screens / surfaces

A usable reference client should include:

* identity/profile view
* home timeline
* channel view
* post detail thread view
* moderation settings
* trust signal view
* compose/edit/delete flows
* relay/origin diagnostics
* recovery settings

### 47. First implementation recommendation

Reference client stack:

* web: React + TypeScript + IndexedDB
* desktop/mobile later via shared state engine
* transport abstraction supporting HTTP + WebSocket first

### 48. MVP cut line

For a realistic first build, implement in this order:

#### Server MVP

* identity docs
* publish/fetch state
* append/fetch log
* static snapshots
* basic WebSocket relay fan-out
* channel refs
* labels

#### Client MVP

* single-account login
* follow actors
* home timeline from followed actors
* channel browse
* compose/edit/delete mutable public posts
* local moderation filters
* relay reconnect + snapshot fallback

#### Deferred

* guardian recovery UX
* revocable/ephemeral content
* optional P2P daemon
* extension registry UI
* advanced indexer/search

---

## Closing summary

Relay v1.2 is a **hybrid protocol stack**; Part I (wire protocol) is the interoperability core, and Parts II–III are implementation guidance.

* **Conformance** **profiles** and **`relay_profiles`** on **identity** make partial implementations and **interoperability** **claims** explicit (**§2**)
* **The `registry/` directory** in this repository holds **draft** **log-event `data`** (and future **`relay.ext.*`**) **entries** for **types** beyond **Appendix B**, so “register before interop” is **actionable** (**§22.1**)
* **HTTP** provides authoritative fetch and publication (v1.2 standardizes on **HTTP Message Signatures** for interop; see **§19**)
* **WebSocket relays** provide fast fan-out and replay windows (**§18.4** for security on `PUB` / sessions)
* **Static feed hosting** provides durability and cheap mirroring
* **Optional P2P** provides resilience, not the primary UX path
* **Clients** own **keys** and **local** policy, including attestation and extension handling
* **v1.3** content is **inherited** in this file, including **section status (top)**, **§4.3.1**, **§8.1**, **§13.1**, and the **v1.3** **Appendix C** **rows**; **v1.4 (this file)** **adds** **§13.4** (**action** **events**), **§11.1** / **§17.10**–**§17.11** (**feed** **definitions** and **recompute**), **Appendix C** **action.*** **rows**, and **§23.3** (non-normative **notes**). Remaining work is under **“Deferred to a future core revision (v1.5+)”** in the status section

The architecture is intended to be implementable, resistant to **silent** data loss in logs, and **explicit** about who is authoritative, what is conflicted, and what security properties are **not** guaranteed.

---

## Appendix B — Normative MVP seed: log event `data` (v1.2)

This appendix **instantiates** the minimum **`data`** object for the five event **`type`** values that **MVP** implementations are most likely to emit. It is **part of** this specification (not a separate registry). Two implementations that interoperate on these types **MUST** use **`data`** objects that are **compatible** with the tables below: **required** keys and JSON types **MUST** match; **additional** keys in `data` are **allowed**. Rules for the top-level **`target`** field (required vs optional, and meaning) are **normative in §10.2.1**, not only in the table notes. **§4.1.1** applies to numbers; **§4.1.1.1** does not apply inside `data` except where a field is explicitly a timestamp string.

| `type` | Required `data` shape (JSON object) | Notes |
| --- | --- | --- |
| `follow.add` | `{}` (empty object) | **§10.2.1:** `target` **MUST** = followed actor’s `actor_id`; event `actor` = follower. |
| `follow.remove` | `{}` | Same as `follow.add`. |
| `state.commit` | `{ "object_id": "<string>", "version": <integer> }` | `object_id` is the state object id (e.g. `post:…`). `version` is the **new** version after commit. |
| `state.delete` | `{ "object_id": "<string>", "version": <integer> }` | `version` is the version after tombstone/delete per **§16.2**. |
| `key.rotate` | `{ "new_key_id": "<string>" }` with optional `"previous_key_id": "<string>"` | **Keys** are identity key ids (e.g. `key:active:2`). **§10.2.1:** `target` **MAY** be omitted; if present, **SHOULD** = `actor` (the account whose **identity** is updated). **Invalidation:** after the origin applies the new identity, the **replaced** active key (identified by `previous_key_id` when present) **MUST NOT** be accepted for **new** HTTP or object signatures; the updated **`keys.active`** in the identity document is authoritative together with this event. For extra audit, implementations **MAY** add e.g. `"superseded_by_event": "relay:event:…"` in `data` (extension) but it is **not** required in the seed. |

**Not in v1.2 this seed, but in v1.3 / v1.4:** `membership.add`, `membership.remove`, `trust.revoke`, and `state.revoke` are in **Appendix C** (v1.3). **`action.request`**, **`action.commit`**, **`action.result`** are in **Appendix C** (v1.4). Types such as `trust.attest` remain in **`registry/`** or future revisions. See **§22.1**.

---

## Appendix C — Normative v1.3 and v1.4 log event `data` (additional types)

This appendix is **part** of this specification. **v1.3** added the first four `type` rows; **v1.4** adds the **`action.*`** rows and the **`relay.action.commitment.v1` verification object** (below the table). For each **`type`**, **`data` MUST** include at least the keys below; **extra** keys are **allowed** per **§10.2** unless a section forbids. **`target` rules** follow **§10.2.1** and the per-row **Notes** column.

| `type` | Required `data` shape (JSON object) | Notes |
| --- | --- | --- |
| `membership.add` | `{ "channel_id": "<string>", "role": "member" }` | `role` **MAY** be extended in **`registry/`**; `target` **SHOULD** be the invited **`actor_id`** when the event is on the **owner** or **actor** log; if absent, the log event’s **`actor`** is the member. |
| `membership.remove` | `{ "channel_id": "<string>" }` | `target` **SHOULD** be the removed **`actor_id`**. |
| `trust.revoke` | `{ "attestation_id": "<string>" }` | `target` **MAY** point at the attestation or claim being revoked. See **§6.5**. |
| `state.revoke` | `{ "object_id": "<string>", "version": <integer> }` | Revocation / tombstone of **revocable** state; **`version`** is the new version after delete/revoke per **§16**. |
| `action.request` (v1.4) | **At least** **`"input_refs"`** and **at least one of** **`"action_id"`** or **`"action"`** (each a string); **MAY** include **both** **`action_id`** and **`action`**; **MAY** include optional **`action_namespace`**, **`action_version`**. | **`input_refs` MUST** be **sorted** ascending (Unicode). **`action_id`**, when present, **MUST** be the **canonical interoperable** action name (**§13.4**; e.g. `relay.basic.summarize.v1`). **`action` without `action_id`** is **ecosystem-local** / **legacy** (not globally interoperable). **§10.2.1:** **`target` MUST** = **agent** `actor_id`. **Optional** fields **participate** in **`relay.action.commitment.v1` **when** **present** **(§13.4) **. ** |
| `action.commit` (v1.4) | `{ "request_event_id": "relay:event:…", "commitment_hash": "<64-char lowercase hex>", "agent_params": { } }` | `agent_params` **MAY** be `{}`. Verifier **MUST** recompute `commitment_hash` from **`relay.action.commitment.v1`**. **§13.4** (**SHOULD** keep **`agent_params`** compact; **origins** **MAY** reject abnormally **large** `data` / deep nesting). |
| `action.result` (v1.4) | `{ "commitment_hash": "<64-char lowercase hex, matches commit>", "output_refs": [ "<id>", "…" ] }` | **`output_refs` MAY** be `[]` if allowed by the **resolved** action semantics (**§13.4**; **`data.action_id`** when present, else legacy **`data.action`**, **plus** any **extension** / **policy**). **§13.4** |

**`relay.action.commitment.v1` (recomputation only; not a free-standing wire object in v1.4):** `kind` = `relay.action.commitment.v1` — `request_event_id` = **`data.request_event_id` on the commit** — `data_action` = **copy** **`data.action` from `action.request` **if** **present** **(else** **omit** **key) **— `data_action_id` = **copy** **`data.action_id` from `action.request` **if** **present** **(else** **omit** **key) **— `data_action_namespace` = **copy** **`data.action_namespace` **if** **present** **(else** **omit** **key) **— `data_action_version` = **copy** **`data.action_version` **if** **present** **(else** **omit** **key) **— `input_refs` = **sorted** **`data.input_refs` from `action.request`** — `agent_params` = **`data.agent_params` from `action.commit`**. The **`commitment_hash` field** on **commit and result** = **lowercase** **64**-char **hex** of **SHA-256** of **UTF-8** of **canonical JSON** of that object per **§4.1** (the commitment object **itself** has **no** `sig` field; **§7** applies to the **enclosing** log event **as usual**).

Implementations that **only** support **Appendix B** remain **v1.2**-conformant. **v1.3** and **v1.4** **MUST** rules apply to the **v1.3** and **`action.*`** **rows** **respectively** when a deployment claims the corresponding version.

---

## Appendix A — Conformance checklist (normative scope)

**A.1 Part I wire requirements (§1–§23)** — the table below lists **MUST** / **MUST NOT** rules that apply to **Part I** **only**. Section numbers refer to **Part I** unless a row explicitly says otherwise. Wording in the main text prevails. **SHOULD** / **MAY** are mostly omitted; a few **SHOULD** rows are included where they gate interop.

**A.2 Documentary / operator items (not wire tests):** **§13.1** **operator transparency** remains **advisory**; v1.3 adds **byte-level** **witness** rules for those who need them, not a replacement for your **Terms**.

**A.3 Cross-part references:** **Part II §29** repeats snapshot **semantics** from **Part I §17.6** for implementers reading the reference server section; **compliance** for **snapshot** **MUST** rules is assessed against **§17.6** (Part I). **Appendix B** is **normative** for the five v1.2 MVP `type` values; **Appendix C** is **normative** for the **v1.3** four `type` values **and** the **v1.4** **`action.*`** **three** `type` values when **v1.4** is claimed.

| Ref. | Must / must not | § |
| --- | --- | --- |
| C0 | **`relay_profiles`** on the **identity** document **MUST** be present for new v1.2 interop; values **MUST** honestly reflect **§2** support. | §2, §8 |
| C1 | Use canonical JSON for hashing and signing of protocol objects. | §4, intro |
| C1a | **Numbers:** **§4.1.1** — no `e`/`E` exponents; JSON `number` only for **integers**; fractions/precision in **strings** or fixed-scale integers per schema. | §4.1.1 |
| C1a1 | **Instants / timestamps:** `ts`, `created_at`, `*\_at` / `*\_ts` fields **MUST** be **RFC 3339 strings**; **not** Unix epoch **numbers**. | §4.1.1.1, §10.3 |
| C1b | **Strings in signed/hashed objects:** UTF-8; **MUST** NFC before digest/sign/verify; RFC 8259-consistent minimal escaping. | §4.1.2 |
| C1c | **Signature algorithms (core interop):** `ed25519` **MUST**; other algorithms only via **extension** + no silent `alg` substitution. | §7.1 |
| C2 | Use **SHA-256** for all base-protocol **content-addressed** `relay:obj:…` identifiers; **clients** must implement and accept **SHA-256** for that purpose. | §4.2 |
| C3 | Derive new **`actor_id`** as `relay:actor:` + SHA-256 **multihash** over **32-byte raw Ed25519** public key (decoded from the identity `keys.active` style material); do **not** hash PEM/JWK/wrapper encodings. | §4.3 |
| C3a | **`channel_id`:** **v1.3** **MUST** mint new channels with **§4.3.1** genesis; **legacy** opaque ids **MAY** exist (**§23.2**). | §4.3.1, §23.2 |
| C4 | On state conflict, **receivers** follow origin, mark conflict, replace local, fetch origin, retain diagnostics; **mirrors** do not assert non-authoritative state as authoritative; follow **§5** for repair. | §5 |
| C5 | Do **not** **silently** collapse or merge log forks; **preserve** branches; do **not** **discard** valid signed events (except out-of-band policy). | §5.3 |
| C5a | **No** global log **consensus**; **divergent** **valid** branches **MUST** be **preserved**; the protocol **MUST** **not** **enforce** a **single** **canonical** global chain. | §10.4 |
| C6 | **Prefer** recovery-signed identity chain per **§5.4** when both appear. | §5.4 |
| C6a | **Multi-device (optional):** core remains integer `version` +1; `device_id` / clocks only in **§5.5** as optional. | §5.5 |
| C7 | Back **trust signals** in interoperable use with a **verifiable** attestation; **verifiers** apply **local** policy; treat unknown attestation `type` as **unverified**; **clients** verify attestation signature, issuer, then policy. | §6 |
| C7a | **Attestation** `expires_at` / `supersedes` / **§6.5** **trust.revoke** and supersession. | §6, §6.5, §10 |
| C8 | User-visible content declares `content_class` and `storage_class`; obey **§9** / **§10** / **§14** class rules. | §9, §10, §14 |
| C8.1b | **v1.5: **`routing_hint` **(§8.1) **is** **advisory;** **clients** **MUST** **not** use **it** **as** an **authoritative** **source** for **identity** or **security;** **SHOULD** **cache** it **per** **§8.1** **with** **capabilities. **| §8.1 |
| C9 | If both live state and audit log are required, use **`dual`** and emit the required `state.*` log events. | §9.1 |
| C10 | **`prev`**: JSON `null` for genesis, never the string `"null"`; first chain event must use `prev: null`; accept genesis; no silent merge of forks. | §10.1 |
| C10a | **Clocks / ordering:** `ts` is not global total order; **§19.4** for HTTP; origin **MAY** use monotonic **append** order; **`prev`** is source of truth for history. | §10.3, §19.4 |
| C10b | **v1.5:** If **`expires_at` **is **present** on **a** **log** **event,** **origins,** **mirrors,** **and** **Fast** **Relays** **MUST** **enforce** the **three-** **phase** **model** **per** **§10.5: ** time-** **expired** **envelopes** **MUST** **not** be **treated** **as** **active** **for** **new** **append, ** **default** **listings, ** **or** **relay** **`PUB` **; ** (C) ** **GC** **permitted; ** by-** **id** **(range** **opt-** **in) ** **MAY** **serve** **during** **(B) ** **with** **mandatory** **expired** **signalling** **(§17.3) **; ** **range** **SHOULD** **metadata** **(§17.4) **. **| §10.5, §16.3, §17.3, §17.4, §18.3 |
| C11 | For unknown `data`+`type` (types **not** in **Appendix B** or **Appendix C**), if storing the event, still store/forward **signed** content (best-effort). | §10.2 |
| C11b | **MVP** log `data` for `follow.add|follow.remove|state.commit|state.delete|key.rotate` **MUST** match **Appendix B** (allow extra keys). | Appendix B, §10.2 |
| C11b1 | **v1.3** log `data` for `membership.add|membership.remove|trust.revoke|state.revoke` **MUST** match **Appendix C** (allow extra keys). | Appendix C, §10.2 |
| C11b1a | **v1.4** log `data` for `action.request|action.commit|action.result` **MUST** match **Appendix C** and **§13.4** / **§10.2.1** (allow extra keys only where **§** allows). | Appendix C, §10.2, §13.4 |
| C13.5a | **v1.5,** **optional: **`relay.ext.private_action.v1` **(§13.5) **—** if **implemented,** **MUST** **satisfy** **§13.5** **(tag, **`encrypted_payload`**,** omitted **`target`**,** **decrypted** **`commitment_hash` **per** **§13.4) **;** if **unimplemented,** **MUST** **degrade** per **§22.4** **. **| §13.5, §4.1, §4.2, §7, §13.4, §22.4 |
| C11f | **v1.4:** **`relay.feed.definition.v1` state** and required **reducers** **§17.10**; **recompute** **§17.11**. | §11.1, §17.10, §17.11 |
| C11c | **`target` on log events:** `follow.*` **MUST** populate `target` with followee `actor_id`; `key.rotate` **`target`** optional, see **§10.2.1**; old key invalidation per **§10.2.1** / identity. | §10.2.1, Appendix B |
| C11d | **Snapshots (Part I):** **MUST** be **self-consistent** at a **single** **logical** **commit** **boundary**; **MUST** **not** **mix** **generations**; if **partial**, **MUST** declare **metadata**; **MUST** **not** use the **snapshot** label for **inconsistent** responses. Non-snapshot **paged** feeds: **§17.6**. *See **A.3** for Part II echo.* | §17.6 |
| C11e | **Snapshot metadata:** if **partial** (or full) snapshot metadata is emitted, **SHOULD** use **`snapshot_id`**, **`as_of_ts`**, **`partial`** per **§17.6** canonical shape. | §17.6 |
| C12 | **v1.3:** for portable checks use **`relay.membership.witness.signed_v1` (**§13.1**); without witness, same trust caveats as v1.2. | §13.1 |
| C12a | Channels **MUST NOT** mutate author post state in place; use **labels** / **refs** / **log** per **§13.2**; **equivalence** / **alias** objects **MUST** follow **§13.3** if used. | §13.2, §13.3 |
| C13 | **RFC 9421** for authenticated origin HTTP in v1.2 interop; **server** validates digest and binds key to `actor` identity. | §19 |
| C13a | **§19.4** replay: **±5 min** skew; require **created/expires** or **nonce** uniqueness per actor+window; reject **expired** / reused nonce. | §19.4 |
| C13b | **WebSocket:** verify **PUB** **signatures**; **session** **binding**; **no** **unsigned** **mutations**; **replay** and **auth** per **§18.4** when a Fast Relay is offered. | §18, §18.4 |
| C13c | **HELLO `auth.sig` (when present):** **MUST** verify **Ed25519** over **`relay.v1.2.ws_hello_auth` + LF + `actor` + LF + `nonce` + LF + `ts` + LF + `ws_endpoint` + LF** (UTF-8, **§18.1.1**); **`nonce`**, **`ts`**, **`ws_endpoint`** **MUST** be present as required there. | §18.1.1 |
| C14 | **Ephemeral** / expiry client **MUST**s and **MUST NOT**s (render, delete claims, copy warning; range **completeness** **/ ** **omission** **hazard). | §17.4, §20.3–20.4 |
| C15 | Return structured errors; support **`conflict_detected`** where version conflicts are surfaced. | §21 |
| C16 | Extensions: optional vs **ext_required** (**§22.5**); **§22.4** ignore-unknown for optional; **§22.6** relay policy JSON. | §22.4–§22.6 |
| C16a | **Indexer (optional):** if offered, use **§17.9** transparency endpoints. | §17.9, §1 |

*Optional:* extend this table with your own test vectors for **§4.1** canonicalization, **§4.1.1.1** timestamps, **Appendix B** `data` objects, and **§4.3** `actor_id` bytes; those sections use normative “must” language in narrative form as well as the table.

**Not Part I (reference only, but has MUST text):** Part II’s “policy surfaces **MUST** be inspectable” (§32) and Part III (§**36**–**48**) include additional **MUST** / **MUST NOT** language for a reference client. Part III is **not** interoperability core. Scan **§41** (edit semantics), **§42** (offline), **§45** (extensions), and nearby sections for a full list.

| Ref. | Must / must not | § (Part II/III) |
| --- | --- | --- |
| R1 | Policy surfaces must be **inspectable**; see **§32** / **§32.1** (example `GET /relay/policy` shape). | §32 |
| R2 | Example: client **MUST** (Part III) present content-class and ephemeral warnings (**§41**), **MUST** support offline behaviors (**§42**), and extension **MUST**s (**§45**). | Part III |

---

## Supplement — v1.4 illustrative example flows (non-normative)

*This supplement is **not** part of the **conformance** **surface**. **Identifiers** and **field** **values** are **examples** only; **wire** **MUST** **rules** are **in** the **cited** **§** **sections**.*

### S.1 Agent summarization using `action.*` (sketch)

1. **Requester** `A` appends **`action.request`** to **`A`’s** log: **`data.action_id`** = `relay.basic.summarize.v1` (the **canonical** interoperable name), **optional** **`data.action`** = `Summarize` (human-facing label), **`data.input_refs`** = `["post:01H…"]` **sorted** if multiple, **`target`** = **`B`**’s `actor_id` (the **summarizer** **agent**).
2. **Agent** `B` fetches the **request** event from **`A`’s** origin, validates **signature** and **`target`**, then appends **`action.commit`** to **`B`’s** log: **`data.request_event_id`**, **`data.agent_params`** (e.g. `{"max_words": 120}`), **`data.commitment_hash`** = **SHA-256** hex of **canonical** **`relay.action.commitment.v1`** built per **Appendix C**.
3. `B` produces a **new** `post:…` or **`relay:obj:…` state** (normal **state** **rules**), then appends **`action.result`**: **`data.commitment_hash`** (same as commit), **`data.output_refs`** = `[ "post:01J…" ]` pointing at the **summary** object.
4. A **verifier** **MUST** **fetch** all three **events**, **verify** all **Ed25519** **signatures**, **recompute** **`commitment_hash`**, and **only then** **treat** the **summary** **ref** as **bound** to the **commit** for **v1.4** **“action** **audit”**—**not** as proof the **NLP** was **“correct** **English**”** (that is **out** **of** **band**).

### S.2 Feed definition and recomputed ordering (sketch)

1. **Curator** `C` publishes a **state** object with **`type`:** `relay.feed.definition.v1` and **`payload`–level** (or top-level) **`sources`:** `[{ "kind": "actor_log", "actor_id": "relay:actor:news" }, { "kind": "actor_log", "actor_id": "relay:actor:local" }]`, **`reduce`:** `relay.reduce.chronological.v1`, **`params`:** `{}` (**§11.1**).
2. A **client** fetches both **actor** **logs** via **§17.4**, **collects** **events** needed for a **stated** **query** (e.g. “last 100”), applies **`relay.reduce.chronological.v1`** as in **§17.10** (sort keys **`ts`**, tie-break `event_id`).
3. The **client** **compares** the **recomputed** **list** to any **indexer-** or **app-** **sorted** list; **mismatch** **with** the **same** **inputs** ⇒ **distrust** the **supplied** **order**; **recompute** **wins** for **v1.4** **honest** **readers** (**§17.11**).
4. For **shared** / **archived** **exports** of **the** **ordered** **id** **list,** a **verifier-friendly** **attestation** **SHOULD** **pair** the **list** with a **recompute** **/** **audit** **boundary** **(definition** **`object_id`**, **`version`**, **`as_of`**, **per-**source **head** **ids**; **§11.1**); for **browsing** **only,** “** **latest** **fetched** **”** **without** **that** **record** **is** **normal**.

---
