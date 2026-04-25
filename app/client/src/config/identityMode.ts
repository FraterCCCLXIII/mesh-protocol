/**
 * Single supported modes:
 * - `vault` (default): Identity Vault at VITE_VAULT_URL + email/password. Keys never leave the client unencrypted.
 * - `local`: Development-only in-browser keypair (no vault). Set VITE_IDENTITY_MODE=local.
 */
export type IdentityMode = 'vault' | 'local';

export function getIdentityMode(): IdentityMode {
  const v = import.meta.env.VITE_IDENTITY_MODE;
  if (v === 'local') {
    return 'local';
  }
  return 'vault';
}

export function isLocalIdentityMode(): boolean {
  return getIdentityMode() === 'local';
}
