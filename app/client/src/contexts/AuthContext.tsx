/**
 * Authentication Context - Vault Integration
 */
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: string;
  email: string;
  entityId: string;
  handle?: string;
  profile?: { name?: string; bio?: string; avatar?: string };
}

interface AuthContextType {
  isLoading: boolean;
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  register: (email: string, password: string, handle: string, name: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API_URL = '/api';
const VAULT_URL = 'http://localhost:12003';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('mesh_session');
    if (saved) {
      try {
        const session = JSON.parse(saved);
        setToken(session.token);
        setUser(session.user);
        setIsAuthenticated(true);
      } catch {}
    }
    setIsLoading(false);
  }, []);

  async function register(email: string, password: string, handle: string, name: string) {
    // Register with vault
    const vaultResp = await fetch(`${VAULT_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!vaultResp.ok) throw new Error('Vault registration failed');
    const vaultData = await vaultResp.json();

    // Generate keys (simplified - in production use tweetnacl)
    const keyArray = new Uint8Array(32);
    crypto.getRandomValues(keyArray);
    const publicKey = Array.from(keyArray).map(b => b.toString(16).padStart(2, '0')).join('');

    // Create entity on relay
    const entityResp = await fetch(`${API_URL}/entities`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public_key: publicKey, handle, profile: { name } }),
    });
    if (!entityResp.ok) throw new Error('Entity creation failed');
    const entity = await entityResp.json();

    const userData: User = {
      id: vaultData.user_id,
      email,
      entityId: entity.id,
      handle,
      profile: { name },
    };

    localStorage.setItem('mesh_session', JSON.stringify({ token: vaultData.access_token, user: userData }));
    setToken(vaultData.access_token);
    setUser(userData);
    setIsAuthenticated(true);
  }

  async function login(email: string, password: string) {
    const vaultResp = await fetch(`${VAULT_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!vaultResp.ok) throw new Error('Login failed');
    const vaultData = await vaultResp.json();

    // For demo, we need to find the entity - in production this comes from vault keys
    const userData: User = {
      id: vaultData.user_id,
      email,
      entityId: '',
      handle: email.split('@')[0],
    };

    localStorage.setItem('mesh_session', JSON.stringify({ token: vaultData.access_token, user: userData }));
    setToken(vaultData.access_token);
    setUser(userData);
    setIsAuthenticated(true);
  }

  async function logout() {
    localStorage.removeItem('mesh_session');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ isLoading, isAuthenticated, user, token, register, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be within AuthProvider');
  return ctx;
}
