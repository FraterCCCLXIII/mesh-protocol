/**
 * Authentication Context - Vault Integration
 * 
 * Supports cross-device login via Identity Vault:
 * 1. Register: Creates vault account + MESH entity + stores encrypted keys
 * 2. Login: Fetches encrypted keys from vault, decrypts client-side
 * 3. Keys are NEVER sent unencrypted to vault
 */
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { VaultClient, type VaultKeys } from '@/lib/vault';

interface User {
  id: string;           // Vault user ID
  email: string;
  entityId: string;     // MESH entity ID
  handle?: string;
  profile?: { name?: string; bio?: string; avatar?: string };
}

interface AuthContextType {
  isLoading: boolean;
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;           // Relay token
  vaultToken: string | null;      // Vault token
  keys: VaultKeys | null;         // Decrypted keys (in memory only)
  register: (email: string, password: string, handle: string, name: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API_URL = '/api';
const VAULT_URL = import.meta.env.VITE_VAULT_URL || 'http://localhost:12003';

// Storage keys
const SESSION_KEY = 'mesh_session';
const ENTITY_KEY = 'mesh_entity_id';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [vaultToken, setVaultToken] = useState<string | null>(null);
  const [keys, setKeys] = useState<VaultKeys | null>(null);

  // Restore session on mount
  useEffect(() => {
    const saved = localStorage.getItem(SESSION_KEY);
    if (saved) {
      try {
        const session = JSON.parse(saved);
        setToken(session.relayToken);
        setVaultToken(session.vaultToken);
        setUser(session.user);
        setIsAuthenticated(true);
        // Note: Keys are not stored - user must re-enter password for sensitive operations
      } catch {}
    }
    setIsLoading(false);
  }, []);

  /**
   * Register a new account
   * 1. Create vault account
   * 2. Generate keys client-side
   * 3. Encrypt keys with password
   * 4. Store encrypted keys in vault
   * 5. Create MESH entity on relay
   */
  async function register(email: string, password: string, handle: string, name: string) {
    setIsLoading(true);
    try {
      // 1. Create vault account
      const vault = new VaultClient(VAULT_URL);
      const vaultAccessToken = await vault.register(email, password);
      
      // 2. Generate and store keys in vault (encrypted client-side)
      const vaultKeys = await vault.createIdentity(password, true);
      
      // 3. Create MESH entity on relay
      const publicKeyHex = Array.from(vaultKeys.signingKeyPair.publicKey)
        .map(b => b.toString(16).padStart(2, '0')).join('');
      
      const entityResp = await fetch(`${API_URL}/entities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          public_key: publicKeyHex, 
          handle, 
          profile: { name } 
        }),
      });
      
      if (!entityResp.ok) {
        const err = await entityResp.json();
        throw new Error(err.detail || 'Entity creation failed');
      }
      const entity = await entityResp.json();
      
      // 4. Get relay token
      const relayToken = await authenticateWithRelay(vaultKeys, entity.id);
      
      // 5. Save session
      const userData: User = {
        id: vault.getUserId() || '',
        email,
        entityId: entity.id,
        handle,
        profile: { name },
      };
      
      saveSession(vaultAccessToken, relayToken, userData);
      setVaultToken(vaultAccessToken);
      setToken(relayToken);
      setUser(userData);
      setKeys(vaultKeys);
      setIsAuthenticated(true);
      
    } finally {
      setIsLoading(false);
    }
  }

  /**
   * Login to existing account
   * 1. Authenticate with vault
   * 2. Fetch encrypted keys
   * 3. Decrypt keys client-side with password
   * 4. Authenticate with relay
   */
  async function login(email: string, password: string) {
    setIsLoading(true);
    try {
      // 1. Authenticate with vault
      const vault = new VaultClient(VAULT_URL);
      const vaultAccessToken = await vault.login(email, password);
      
      // 2. List identities stored in vault
      const identities = await vault.listIdentities();
      
      if (identities.length === 0) {
        throw new Error('No MESH identity found. Please register first.');
      }
      
      // Use first identity (could show picker if multiple)
      const identity = identities[0];
      
      // 3. Fetch and decrypt keys
      const vaultKeys = await vault.getKeys(identity.entityId, password);
      
      // 4. Authenticate with relay
      const relayToken = await authenticateWithRelay(vaultKeys, identity.entityId);
      
      // 5. Fetch user profile from relay
      const entityResp = await fetch(`${API_URL}/entities/${identity.entityId}?token=${relayToken}`);
      const entity = entityResp.ok ? await entityResp.json() : null;
      
      // 6. Save session
      const userData: User = {
        id: vault.getUserId() || '',
        email,
        entityId: identity.entityId,
        handle: entity?.handle || email.split('@')[0],
        profile: entity?.profile || { name: email.split('@')[0] },
      };
      
      saveSession(vaultAccessToken, relayToken, userData);
      setVaultToken(vaultAccessToken);
      setToken(relayToken);
      setUser(userData);
      setKeys(vaultKeys);
      setIsAuthenticated(true);
      
    } finally {
      setIsLoading(false);
    }
  }

  async function logout() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(ENTITY_KEY);
    setToken(null);
    setVaultToken(null);
    setUser(null);
    setKeys(null);
    setIsAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ 
      isLoading, 
      isAuthenticated, 
      user, 
      token, 
      vaultToken,
      keys,
      register, 
      login, 
      logout 
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be within AuthProvider');
  return ctx;
}

// ========== Helpers ==========

function saveSession(vaultToken: string, relayToken: string, user: User) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({ 
    vaultToken, 
    relayToken, 
    user 
  }));
  localStorage.setItem(ENTITY_KEY, user.entityId);
}

/**
 * Authenticate with MESH relay using cryptographic keys
 */
async function authenticateWithRelay(keys: VaultKeys, entityId: string): Promise<string> {
  // Get challenge
  const challengeResp = await fetch(`${API_URL}/auth/challenge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_id: entityId }),
  });
  
  if (!challengeResp.ok) {
    throw new Error('Failed to get auth challenge');
  }
  
  const { challenge } = await challengeResp.json();
  
  // Sign challenge with private key
  const encoder = new TextEncoder();
  const messageBytes = encoder.encode(challenge);
  
  // Use tweetnacl to sign
  const nacl = await import('tweetnacl');
  const signature = nacl.sign.detached(messageBytes, keys.signingKeyPair.secretKey);
  const signatureHex = Array.from(signature).map(b => b.toString(16).padStart(2, '0')).join('');
  
  // Verify with relay
  const verifyResp = await fetch(`${API_URL}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      entity_id: entityId, 
      challenge, 
      signature: signatureHex 
    }),
  });
  
  if (!verifyResp.ok) {
    throw new Error('Authentication failed');
  }
  
  const { token } = await verifyResp.json();
  return token;
}
