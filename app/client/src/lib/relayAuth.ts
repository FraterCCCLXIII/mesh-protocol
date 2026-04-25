/**
 * Challenge–response session token from the MESH relay using Ed25519 (tweetnacl).
 * Shared by AuthContext (Vault) and local dev identity.
 */
const API_URL = '/api';

export async function fetchRelayToken(secretKey: Uint8Array, entityId: string): Promise<string> {
  const challengeResp = await fetch(`${API_URL}/auth/challenge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_id: entityId }),
  });

  if (!challengeResp.ok) {
    throw new Error('Failed to get auth challenge');
  }

  const { challenge } = (await challengeResp.json()) as { challenge: string };
  const nacl = await import('tweetnacl');
  const messageBytes = new TextEncoder().encode(challenge);
  const signature = nacl.sign.detached(messageBytes, secretKey);
  const signatureHex = Array.from(signature)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  const verifyResp = await fetch(`${API_URL}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      entity_id: entityId,
      challenge,
      signature: signatureHex,
    }),
  });

  if (!verifyResp.ok) {
    throw new Error('Relay authentication failed');
  }

  const { token } = (await verifyResp.json()) as { token: string };
  return token;
}
