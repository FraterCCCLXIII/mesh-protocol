/**
 * MESH Identity Vault Client + Protocol Crypto
 * 
 * This library handles:
 * - Client-side key encryption/decryption
 * - Communication with the Identity Vault service
 * - E2EE for DMs using X25519 + AES-GCM
 * - Device key management
 * 
 * Security Model:
 * - Keys are encrypted CLIENT-SIDE using a key derived from password
 * - Vault NEVER sees plaintext private keys
 * - DMs use ephemeral key exchange for forward secrecy
 */

import * as nacl from 'tweetnacl';
import * as naclUtil from 'tweetnacl-util';

// ========== MESH Protocol Crypto ==========

/**
 * Generate a signing key pair (Ed25519)
 */
export function generateSigningKeyPair(): nacl.SignKeyPair {
  return nacl.sign.keyPair();
}

/**
 * Generate an encryption key pair (X25519)
 */
export function generateEncryptionKeyPair(): nacl.BoxKeyPair {
  return nacl.box.keyPair();
}

/**
 * Generate entity ID from public key
 */
export function generateEntityId(publicKey: Uint8Array): string {
  const hash = nacl.hash(publicKey);
  const hex = Array.from(hash.slice(0, 16))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `ent:${hex}`;
}

/**
 * Sign a message
 */
export function sign(message: Uint8Array, secretKey: Uint8Array): Uint8Array {
  return nacl.sign.detached(message, secretKey);
}

/**
 * Verify a signature
 */
export function verify(message: Uint8Array, signature: Uint8Array, publicKey: Uint8Array): boolean {
  return nacl.sign.detached.verify(message, signature, publicKey);
}

/**
 * Encrypted envelope for E2EE DMs
 */
export interface EncryptedEnvelope {
  ephemeralPublicKey: string; // hex
  nonce: string; // hex
  ciphertext: string; // hex
}

/**
 * Encrypt a message for a recipient (DM)
 * Uses ephemeral key exchange for forward secrecy
 */
export function encryptForRecipient(
  plaintext: string,
  recipientEncryptionPublicKey: Uint8Array
): EncryptedEnvelope {
  // Generate ephemeral key pair
  const ephemeral = nacl.box.keyPair();
  
  // Compute shared secret
  const sharedSecret = nacl.box.before(recipientEncryptionPublicKey, ephemeral.secretKey);
  
  // Generate nonce
  const nonce = nacl.randomBytes(nacl.box.nonceLength);
  
  // Encrypt
  const message = naclUtil.decodeUTF8(plaintext);
  const ciphertext = nacl.box.after(message, nonce, sharedSecret);
  
  return {
    ephemeralPublicKey: naclUtil.encodeBase64(ephemeral.publicKey),
    nonce: naclUtil.encodeBase64(nonce),
    ciphertext: naclUtil.encodeBase64(ciphertext),
  };
}

/**
 * Decrypt a message from sender (DM)
 */
export function decryptFromSender(
  envelope: EncryptedEnvelope,
  recipientSecretKey: Uint8Array
): string | null {
  try {
    const ephemeralPublicKey = naclUtil.decodeBase64(envelope.ephemeralPublicKey);
    const nonce = naclUtil.decodeBase64(envelope.nonce);
    const ciphertext = naclUtil.decodeBase64(envelope.ciphertext);
    
    // Compute shared secret
    const sharedSecret = nacl.box.before(ephemeralPublicKey, recipientSecretKey);
    
    // Decrypt
    const plaintext = nacl.box.open.after(ciphertext, nonce, sharedSecret);
    if (!plaintext) return null;
    
    return naclUtil.encodeUTF8(plaintext);
  } catch {
    return null;
  }
}

/**
 * Device key for multi-device support
 */
export interface DeviceKey {
  deviceId: string;
  publicKey: string; // hex
  name: string;
  authorizedAt: string;
  revoked: boolean;
  capabilities: string[];
}

/**
 * Generate a new device key pair
 */
export function generateDeviceKeyPair(): {
  deviceId: string;
  keyPair: nacl.SignKeyPair;
} {
  const keyPair = nacl.sign.keyPair();
  const hash = nacl.hash(keyPair.publicKey);
  const deviceId = `dev:${Array.from(hash.slice(0, 8)).map(b => b.toString(16).padStart(2, '0')).join('')}`;
  return { deviceId, keyPair };
}

// ========== Types ==========

export interface VaultKeys {
  entityId: string;
  signingKeyPair: nacl.SignKeyPair;
  encryptionKeyPair?: nacl.BoxKeyPair;
}

export interface VaultUser {
  id: string;
  email: string;
  emailVerified: boolean;
  createdAt: string;
}

export interface VaultDevice {
  id: string;
  deviceName: string;
  authorizedAt: string;
  lastUsedAt: string;
  revoked: boolean;
}

export interface VaultIdentity {
  entityId: string;
  createdAt: string;
}

// ========== Crypto Helpers ==========

/**
 * Derive encryption key from password using PBKDF2
 * (Using PBKDF2 since Argon2 isn't available in browsers)
 */
async function deriveKey(password: string, salt: Uint8Array): Promise<Uint8Array> {
  const encoder = new TextEncoder();
  const passwordKey = await crypto.subtle.importKey(
    'raw',
    encoder.encode(password),
    'PBKDF2',
    false,
    ['deriveBits']
  );

  const bits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: salt,
      iterations: 100000,
      hash: 'SHA-256',
    },
    passwordKey,
    256 // 32 bytes
  );

  return new Uint8Array(bits);
}

/**
 * Encrypt data with password-derived key
 */
async function encryptWithPassword(
  data: Uint8Array,
  password: string
): Promise<{ encrypted: Uint8Array; params: object }> {
  const salt = nacl.randomBytes(32);
  const key = await deriveKey(password, salt);
  const nonce = nacl.randomBytes(nacl.secretbox.nonceLength);

  const encrypted = nacl.secretbox(data, nonce, key);

  return {
    encrypted: new Uint8Array([...nonce, ...encrypted]),
    params: {
      algorithm: 'pbkdf2-sha256',
      salt: naclUtil.encodeBase64(salt),
      iterations: 100000,
    },
  };
}

/**
 * Decrypt data with password-derived key
 */
async function decryptWithPassword(
  encrypted: Uint8Array,
  password: string,
  params: { salt: string }
): Promise<Uint8Array> {
  const salt = naclUtil.decodeBase64(params.salt);
  const key = await deriveKey(password, salt);

  const nonce = encrypted.slice(0, nacl.secretbox.nonceLength);
  const ciphertext = encrypted.slice(nacl.secretbox.nonceLength);

  const decrypted = nacl.secretbox.open(ciphertext, nonce, key);
  if (!decrypted) {
    throw new VaultError('Failed to decrypt - wrong password?');
  }

  return decrypted;
}

// ========== Error ==========

export class VaultError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'VaultError';
  }
}

// ========== Vault Client ==========

export class VaultClient {
  private vaultUrl: string;
  private accessToken: string | null = null;
  private userId: string | null = null;

  constructor(vaultUrl: string) {
    this.vaultUrl = vaultUrl.replace(/\/$/, '');
  }

  private headers(): HeadersInit {
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    return headers;
  }

  private async request<T>(method: string, path: string, data?: object): Promise<T> {
    const url = `${this.vaultUrl}${path}`;
    const options: RequestInit = {
      method,
      headers: this.headers(),
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    const resp = await fetch(url, options);

    if (!resp.ok) {
      const text = await resp.text();
      throw new VaultError(`Vault error ${resp.status}: ${text}`);
    }

    if (resp.status === 204 || !resp.headers.get('content-type')?.includes('json')) {
      return {} as T;
    }

    return resp.json();
  }

  // ========== Auth ==========

  /**
   * Register a new user with email and password
   */
  async register(email: string, password: string): Promise<string> {
    const data = await this.request<{
      access_token: string;
      user_id: string;
    }>('POST', '/api/auth/register', { email, password });

    this.accessToken = data.access_token;
    this.userId = data.user_id;

    return this.accessToken;
  }

  /**
   * Login with email and password
   */
  async login(email: string, password: string): Promise<string> {
    const data = await this.request<{
      access_token: string;
      user_id: string;
    }>('POST', '/api/auth/login', { email, password });

    this.accessToken = data.access_token;
    this.userId = data.user_id;

    return this.accessToken;
  }

  /**
   * Request a magic link for passwordless login
   */
  async requestMagicLink(email: string): Promise<void> {
    await this.request('POST', '/api/auth/magic-link', { email });
  }

  /**
   * Verify magic link and get access token
   */
  async verifyMagicLink(token: string): Promise<string> {
    const data = await this.request<{
      access_token: string;
      user_id: string;
    }>('POST', `/api/auth/magic-link/verify?token=${token}`, {});

    this.accessToken = data.access_token;
    this.userId = data.user_id;

    return this.accessToken;
  }

  /**
   * Logout and invalidate session
   */
  async logout(): Promise<void> {
    await this.request('POST', '/api/auth/logout', {});
    this.accessToken = null;
    this.userId = null;
  }

  /**
   * Get current user info
   */
  async getMe(): Promise<VaultUser> {
    const data = await this.request<{
      id: string;
      email: string;
      email_verified: boolean;
      created_at: string;
    }>('GET', '/api/auth/me');

    return {
      id: data.id,
      email: data.email,
      emailVerified: data.email_verified,
      createdAt: data.created_at,
    };
  }

  /**
   * Check if authenticated
   */
  isAuthenticated(): boolean {
    return this.accessToken !== null;
  }

  /**
   * Get current user ID
   */
  getUserId(): string | null {
    return this.userId;
  }

  /**
   * Get access token
   */
  getAccessToken(): string | null {
    return this.accessToken;
  }

  /**
   * Set access token (for restoring session)
   */
  setAccessToken(token: string, userId: string): void {
    this.accessToken = token;
    this.userId = userId;
  }

  // ========== Key Management ==========

  /**
   * Create a new MESH identity with keys stored in the vault.
   * 
   * 1. Generates Ed25519 signing key
   * 2. Optionally generates X25519 encryption key
   * 3. Encrypts keys with password-derived key
   * 4. Stores encrypted keys in vault
   */
  async createIdentity(
    password: string,
    createEncryptionKey: boolean = true
  ): Promise<VaultKeys> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    // Generate keys
    const signingKeyPair = nacl.sign.keyPair();
    const encryptionKeyPair = createEncryptionKey ? nacl.box.keyPair() : undefined;

    // Calculate entity ID
    const entityId = generateEntityId(signingKeyPair.publicKey);

    // Encrypt signing key
    const { encrypted: encryptedSigning, params } = await encryptWithPassword(
      signingKeyPair.secretKey,
      password
    );

    // Encrypt encryption key if present
    let encryptedEncryption: string | null = null;
    if (encryptionKeyPair) {
      const salt = naclUtil.decodeBase64((params as { salt: string }).salt);
      const key = await deriveKey(password, salt);
      const nonce = nacl.randomBytes(nacl.secretbox.nonceLength);
      const encrypted = nacl.secretbox(encryptionKeyPair.secretKey, nonce, key);
      encryptedEncryption = naclUtil.encodeBase64(new Uint8Array([...nonce, ...encrypted]));
    }

    // Store in vault
    await this.request('POST', '/api/keys/store', {
      entity_id: entityId,
      encrypted_signing_key: naclUtil.encodeBase64(encryptedSigning),
      encrypted_encryption_key: encryptedEncryption,
      key_derivation_params: JSON.stringify(params),
    });

    return {
      entityId,
      signingKeyPair,
      encryptionKeyPair,
    };
  }

  /**
   * Retrieve and decrypt keys from the vault.
   * Keys are decrypted CLIENT-SIDE using the password.
   */
  async getKeys(entityId: string, password: string): Promise<VaultKeys> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      entity_id: string;
      encrypted_signing_key: string;
      encrypted_encryption_key?: string;
      key_derivation_params: string;
    }>('GET', `/api/keys/${entityId}`);

    const params = JSON.parse(data.key_derivation_params);

    // Decrypt signing key
    const encryptedSigning = naclUtil.decodeBase64(data.encrypted_signing_key);
    const signingSecretKey = await decryptWithPassword(encryptedSigning, password, params);
    const signingKeyPair = nacl.sign.keyPair.fromSecretKey(signingSecretKey);

    // Decrypt encryption key if present
    let encryptionKeyPair: nacl.BoxKeyPair | undefined;
    if (data.encrypted_encryption_key) {
      const encryptedEncryption = naclUtil.decodeBase64(data.encrypted_encryption_key);
      const encryptionSecretKey = await decryptWithPassword(encryptedEncryption, password, params);
      encryptionKeyPair = nacl.box.keyPair.fromSecretKey(encryptionSecretKey);
    }

    return {
      entityId: data.entity_id,
      signingKeyPair,
      encryptionKeyPair,
    };
  }

  /**
   * List all entity IDs with stored keys
   */
  async listIdentities(): Promise<VaultIdentity[]> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      entities: Array<{ entity_id: string; created_at: string }>;
    }>('GET', '/api/keys');

    return data.entities.map((e) => ({
      entityId: e.entity_id,
      createdAt: e.created_at,
    }));
  }

  /**
   * Delete keys for an identity (careful!)
   */
  async deleteIdentity(entityId: string): Promise<void> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    await this.request('DELETE', `/api/keys/${entityId}`);
  }

  // ========== Devices ==========

  /**
   * Authorize a new device
   */
  async authorizeDevice(deviceName: string): Promise<VaultDevice> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      device_id: string;
      device_name: string;
      authorized_at: string;
    }>('POST', '/api/devices', { device_name: deviceName });

    return {
      id: data.device_id,
      deviceName: data.device_name,
      authorizedAt: data.authorized_at,
      lastUsedAt: data.authorized_at,
      revoked: false,
    };
  }

  /**
   * List authorized devices
   */
  async listDevices(): Promise<VaultDevice[]> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      devices: Array<{
        id: string;
        device_name: string;
        authorized_at: string;
        last_used_at: string;
        revoked: boolean;
      }>;
    }>('GET', '/api/devices');

    return data.devices.map((d) => ({
      id: d.id,
      deviceName: d.device_name,
      authorizedAt: d.authorized_at,
      lastUsedAt: d.last_used_at,
      revoked: d.revoked,
    }));
  }

  /**
   * Revoke a device
   */
  async revokeDevice(deviceId: string): Promise<void> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    await this.request('DELETE', `/api/devices/${deviceId}`);
  }

  // ========== Recovery ==========

  /**
   * Setup backup codes for recovery
   * Returns codes that should be saved by the user
   */
  async setupBackupCodes(): Promise<string[]> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      backup_codes: string[];
    }>('POST', '/api/recovery/setup', {
      method: 'backup_codes',
      config: {},
    });

    return data.backup_codes;
  }

  /**
   * Get recovery configuration status
   */
  async getRecoveryStatus(): Promise<{
    configured: boolean;
    method?: string;
    configuredAt?: string;
  }> {
    if (!this.accessToken) {
      throw new VaultError('Not authenticated');
    }

    const data = await this.request<{
      configured: boolean;
      method?: string;
      configured_at?: string;
    }>('GET', '/api/recovery');

    return {
      configured: data.configured,
      method: data.method,
      configuredAt: data.configured_at,
    };
  }
}

// ========== Convenience Functions ==========

/**
 * Create a new MESH identity with vault storage
 */
export async function createVaultIdentity(
  vaultUrl: string,
  email: string,
  password: string,
  register: boolean = true
): Promise<{ vault: VaultClient; keys: VaultKeys }> {
  const vault = new VaultClient(vaultUrl);

  if (register) {
    await vault.register(email, password);
  } else {
    await vault.login(email, password);
  }

  const keys = await vault.createIdentity(password);

  return { vault, keys };
}

/**
 * Load an existing MESH identity from vault
 */
export async function loadVaultIdentity(
  vaultUrl: string,
  email: string,
  password: string,
  entityId: string
): Promise<{ vault: VaultClient; keys: VaultKeys }> {
  const vault = new VaultClient(vaultUrl);
  await vault.login(email, password);

  const keys = await vault.getKeys(entityId, password);

  return { vault, keys };
}

// ========== Local Storage Helpers ==========

const STORAGE_KEY = 'mesh_vault_session';

export interface StoredSession {
  vaultUrl: string;
  accessToken: string;
  userId: string;
  entityId: string;
}

/**
 * Save vault session to local storage
 */
export function saveVaultSession(
  vaultUrl: string,
  accessToken: string,
  userId: string,
  entityId: string
): void {
  const session: StoredSession = {
    vaultUrl,
    accessToken,
    userId,
    entityId,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

/**
 * Load vault session from local storage
 */
export function loadVaultSession(): StoredSession | null {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return null;

  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

/**
 * Clear vault session from local storage
 */
export function clearVaultSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Restore vault client from saved session
 */
export function restoreVaultClient(session: StoredSession): VaultClient {
  const vault = new VaultClient(session.vaultUrl);
  vault.setAccessToken(session.accessToken, session.userId);
  return vault;
}
