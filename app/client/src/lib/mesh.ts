/**
 * MESH Protocol Client Library
 * Handles key management, authentication, and API calls
 */

// Use relative URLs when proxied, or explicit URL for external access
const API_BASE = import.meta.env?.VITE_API_URL || '';

// Simple Ed25519 implementation using Web Crypto
// Note: In production, use a proper Ed25519 library like @noble/ed25519

export interface KeyPair {
  publicKey: string;
  privateKey: string;
}

export interface User {
  id: string;
  handle: string | null;
  profile: {
    name?: string;
    bio?: string;
    avatar?: string;
  };
  public_key: string;
}

export interface Post {
  id: string;
  author: string;
  author_handle?: string;
  author_profile?: {
    name?: string;
    avatar?: string;
  };
  kind: string;
  body: {
    text?: string;
    media?: { url: string; type: string }[];
  };
  reply_to: string | null;
  created_at: string;
  access: string;
  like_count: number;
  reply_count: number;
  liked_by_me?: boolean;
}

export interface Group {
  id: string;
  name: string;
  description: string;
  owner: string;
  access: 'public' | 'private';
  member_count: number;
  created_at: string;
}

// Key storage
const KEYS_STORAGE_KEY = 'mesh_keys';
const TOKEN_STORAGE_KEY = 'mesh_token';
const USER_STORAGE_KEY = 'mesh_user';

export function getStoredKeys(): KeyPair | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(KEYS_STORAGE_KEY);
  return stored ? JSON.parse(stored) : null;
}

export function storeKeys(keys: KeyPair): void {
  localStorage.setItem(KEYS_STORAGE_KEY, JSON.stringify(keys));
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getStoredUser(): User | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(USER_STORAGE_KEY);
  return stored ? JSON.parse(stored) : null;
}

export function storeUser(user: User): void {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
}

// Generate a random key pair (simplified - use proper Ed25519 in production)
export function generateKeyPair(): KeyPair {
  // Generate 32 random bytes for each key
  const privateBytes = new Uint8Array(32);
  const publicBytes = new Uint8Array(32);
  crypto.getRandomValues(privateBytes);
  crypto.getRandomValues(publicBytes);
  
  return {
    privateKey: bytesToHex(privateBytes),
    publicKey: bytesToHex(publicBytes),
  };
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
  }
  return bytes;
}

// Sign a message (simplified - use proper Ed25519 in production)
export async function signMessage(message: string, privateKey: string): Promise<string> {
  // For demo purposes, we'll use HMAC-SHA256 as a placeholder
  // In production, use proper Ed25519 signing
  const encoder = new TextEncoder();
  const keyData = hexToBytes(privateKey);
  const key = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return bytesToHex(new Uint8Array(signature));
}

// API helpers
export async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const url = new URL(endpoint, API_BASE);
  
  if (token) {
    url.searchParams.set('token', token);
  }
  
  const response = await fetch(url.toString(), {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }
  
  return response.json();
}

// Store entity ID separately from keys
const ENTITY_ID_STORAGE_KEY = 'mesh_entity_id';

export function getStoredEntityId(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ENTITY_ID_STORAGE_KEY);
}

export function storeEntityId(entityId: string): void {
  localStorage.setItem(ENTITY_ID_STORAGE_KEY, entityId);
}

// Auth API
export async function register(
  handle: string,
  name: string,
  bio: string = ''
): Promise<{ id: string; handle: string }> {
  const keys = generateKeyPair();
  storeKeys(keys);
  
  const result = await apiCall<{ id: string; handle: string }>('/api/entities', {
    method: 'POST',
    body: JSON.stringify({
      public_key: keys.publicKey,
      handle,
      profile: { name, bio },
    }),
  });
  
  // Store the entity ID returned by server
  storeEntityId(result.id);
  
  // Auto login
  await login();
  
  return result;
}

export async function login(): Promise<User> {
  const keys = getStoredKeys();
  if (!keys) {
    throw new Error('No keys found. Please register first.');
  }
  
  // Use stored entity ID (from registration) or compute from keys
  let entityId = getStoredEntityId();
  if (!entityId) {
    // Fallback: compute from public key (must match server's computation)
    entityId = 'ent:' + keys.publicKey.slice(0, 32);
  }
  
  // Get challenge
  const { challenge } = await apiCall<{ challenge: string }>('/api/auth/challenge', {
    method: 'POST',
    body: JSON.stringify({ entity_id: entityId }),
  });
  
  // Sign challenge
  const signature = await signMessage(challenge, keys.privateKey);
  
  // Verify
  const { token } = await apiCall<{ token: string }>('/api/auth/verify', {
    method: 'POST',
    body: JSON.stringify({
      entity_id: entityId,
      challenge,
      signature,
    }),
  });
  
  storeToken(token);
  
  // Get user info
  const user = await apiCall<User>(`/api/entities/${entityId}`);
  storeUser(user);
  
  return user;
}

// Entity API
export async function getUser(entityId: string): Promise<User> {
  return apiCall<User>(`/api/entities/${entityId}`);
}

export async function getUserByHandle(handle: string): Promise<User> {
  return apiCall<User>(`/api/entities/by-handle/${handle}`);
}

export async function updateProfile(profile: { name?: string; bio?: string; avatar?: string }): Promise<void> {
  const user = getStoredUser();
  if (!user) throw new Error('Not logged in');
  
  await apiCall(`/api/entities/${user.id}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
  
  // Update stored user
  storeUser({ ...user, profile: { ...user.profile, ...profile } });
}

// Content API
export async function createPost(text: string, replyTo?: string): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/api/content', {
    method: 'POST',
    body: JSON.stringify({
      kind: replyTo ? 'reply' : 'post',
      body: { text },
      reply_to: replyTo,
      access: 'public',
    }),
  });
}

export async function getPost(postId: string): Promise<Post> {
  return apiCall<Post>(`/api/content/${postId}`);
}

export async function getPosts(params: {
  author?: string;
  reply_to?: string;
  limit?: number;
}): Promise<{ items: Post[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params.author) searchParams.set('author', params.author);
  if (params.reply_to) searchParams.set('reply_to', params.reply_to);
  if (params.limit) searchParams.set('limit', params.limit.toString());
  
  return apiCall<{ items: Post[]; total: number }>(`/api/content?${searchParams}`);
}

export async function deletePost(postId: string): Promise<void> {
  await apiCall(`/api/content/${postId}`, { method: 'DELETE' });
}

// Feed API
export async function getFeed(entityId: string, limit = 50): Promise<{ items: Post[]; total: number }> {
  return apiCall<{ items: Post[]; total: number }>(`/api/users/${entityId}/feed?limit=${limit}`);
}

// Link API (follows, likes)
export async function follow(targetId: string): Promise<void> {
  await apiCall('/api/links', {
    method: 'POST',
    body: JSON.stringify({ target: targetId, kind: 'follow' }),
  });
}

export async function unfollow(targetId: string): Promise<void> {
  const user = getStoredUser();
  if (!user) throw new Error('Not logged in');
  
  // Generate link ID
  const linkId = `lnk:${user.id}:follow:${targetId}`.slice(0, 40);
  
  await apiCall(`/api/links/${linkId}`, { method: 'DELETE' });
}

export async function like(contentId: string): Promise<void> {
  await apiCall('/api/links', {
    method: 'POST',
    body: JSON.stringify({ target: contentId, kind: 'like' }),
  });
}

export async function unlike(contentId: string): Promise<void> {
  const user = getStoredUser();
  if (!user) throw new Error('Not logged in');
  
  const linkId = `lnk:${user.id}:like:${contentId}`.slice(0, 40);
  
  await apiCall(`/api/links/${linkId}`, { method: 'DELETE' });
}

export async function getFollowers(entityId: string): Promise<{ items: User[]; total: number }> {
  return apiCall<{ items: User[]; total: number }>(`/api/users/${entityId}/followers`);
}

export async function getFollowing(entityId: string): Promise<{ items: User[]; total: number }> {
  return apiCall<{ items: User[]; total: number }>(`/api/users/${entityId}/following`);
}

// Group API
export async function createGroup(name: string, description: string, access: 'public' | 'private'): Promise<{ id: string }> {
  return apiCall<{ id: string }>('/api/groups', {
    method: 'POST',
    body: JSON.stringify({ name, description, access }),
  });
}

export async function getGroups(access = 'public'): Promise<{ items: Group[]; total: number }> {
  return apiCall<{ items: Group[]; total: number }>(`/api/groups?access=${access}`);
}

export async function getGroup(groupId: string): Promise<Group & { members: User[] }> {
  return apiCall<Group & { members: User[] }>(`/api/groups/${groupId}`);
}

export async function joinGroup(groupId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/join`, { method: 'POST' });
}

export async function leaveGroup(groupId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/leave`, { method: 'POST' });
}

// Node info
export async function getNodeInfo(): Promise<{
  node_id: string;
  node_url: string;
  protocol_version: string;
}> {
  return apiCall('/.well-known/mesh-node');
}

export async function getStats(): Promise<Record<string, number>> {
  return apiCall('/api/stats');
}

// Aliases for backwards compatibility
export const registerUser = register;
export const loginUser = login;

