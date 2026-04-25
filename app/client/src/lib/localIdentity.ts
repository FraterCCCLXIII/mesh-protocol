/**
 * Local (dev) identity: Ed25519 keypair in localStorage, no Identity Vault.
 * Enable with VITE_IDENTITY_MODE=local. Not for production.
 */
import { fetchRelayToken } from './relayAuth';

const API_URL = '/api';
const SESSION_KEY = 'mesh_session';
const ENTITY_KEY = 'mesh_entity_id';
const LOCAL_KEY_MATERIAL = 'mesh_local_key_material';

export interface LocalKeyMaterial {
  entityId: string;
  /** tweetnacl sign secret key (64 bytes) */
  secretKey: number[];
}

export function getLocalKeyMaterial(): LocalKeyMaterial | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = localStorage.getItem(LOCAL_KEY_MATERIAL);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as LocalKeyMaterial;
  } catch {
    return null;
  }
}

/**
 * Create a new relay entity and session (browser-only keys).
 */
export async function registerLocalIdentity(handle: string, displayName: string): Promise<void> {
  const nacl = await import('tweetnacl');
  const keyPair = nacl.sign.keyPair();
  const publicKeyHex = Array.from(keyPair.publicKey)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  const entityResp = await fetch(`${API_URL}/entities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      public_key: publicKeyHex,
      handle,
      profile: { name: displayName },
    }),
  });

  if (!entityResp.ok) {
    const err = await entityResp.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Entity creation failed');
  }

  const entity = (await entityResp.json()) as { id: string };
  const token = await fetchRelayToken(keyPair.secretKey, entity.id);

  const material: LocalKeyMaterial = {
    entityId: entity.id,
    secretKey: Array.from(keyPair.secretKey),
  };
  localStorage.setItem(LOCAL_KEY_MATERIAL, JSON.stringify(material));

  const session = {
    vaultToken: '',
    relayToken: token,
    user: {
      id: entity.id,
      email: 'local@mesh.dev',
      entityId: entity.id,
      handle,
      profile: { name: displayName },
    },
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  localStorage.setItem(ENTITY_KEY, entity.id);
}

/**
 * Restore relay session from stored key material.
 */
export async function loginLocalIdentity(): Promise<void> {
  const material = getLocalKeyMaterial();
  if (!material) {
    throw new Error('No local identity. Create a local account first.');
  }
  const secretKey = new Uint8Array(material.secretKey);
  const token = await fetchRelayToken(secretKey, material.entityId);

  const entResp = await fetch(`${API_URL}/entities/${material.entityId}?token=${encodeURIComponent(token)}`);
  const entity = entResp.ok ? ((await entResp.json()) as { handle?: string; profile?: { name?: string } }) : null;

  const session = {
    vaultToken: '',
    relayToken: token,
    user: {
      id: material.entityId,
      email: 'local@mesh.dev',
      entityId: material.entityId,
      handle: entity?.handle,
      profile: entity?.profile,
    },
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  localStorage.setItem(ENTITY_KEY, material.entityId);
}

export function clearLocalIdentityStorage(): void {
  localStorage.removeItem(LOCAL_KEY_MATERIAL);
  localStorage.removeItem(ENTITY_KEY);
}
