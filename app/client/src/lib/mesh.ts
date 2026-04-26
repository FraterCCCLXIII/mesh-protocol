/**
 * MESH Protocol Client Library
 * Handles key management, authentication, and API calls
 */

/**
 * Base URL for resolving API paths. When `VITE_API_URL` is unset, use the page
 * origin so `new URL('/api/...', base)` works with the Vite dev proxy (same
 * origin → `/api` proxied to the mesh node). An empty string is **not** a valid
 * `URL` base and throws "Invalid base URL".
 */
function resolveApiBase(): string {
  const fromEnv = import.meta.env?.VITE_API_URL;
  if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
    return fromEnv;
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return 'http://localhost:12000';
}

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
  body: string;
  media?: string[];
  reply_to: string | null;
  created_at: string;
  access: string;
  like_count: number;
  reply_count: number;
  liked_by_me?: boolean;
}

/**
 * Renders `content.body` from the API. The node stores top-level text as a string;
 * some code paths use `{ text: string }`.
 */
export function postBodyText(body: unknown): string {
  if (body == null) return '';
  if (typeof body === 'string') return body;
  if (typeof body === 'object' && body !== null && 'text' in body) {
    const t = (body as { text?: unknown }).text;
    return typeof t === 'string' ? t : '';
  }
  return '';
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
const ENTITY_ID_STORAGE_KEY = 'mesh_entity_id';

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
  // Vault session is authoritative when present — legacy mesh_token must not shadow it
  // or apiCall/createPost use a stale token while useAuth() uses relayToken.
  const sessionRaw = localStorage.getItem('mesh_session');
  if (sessionRaw) {
    try {
      const session = JSON.parse(sessionRaw) as { relayToken?: string };
      if (typeof session.relayToken === 'string' && session.relayToken.length > 0) {
        return session.relayToken;
      }
    } catch {
      /* ignore */
    }
  }
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getStoredUser(): User | null {
  if (typeof window === 'undefined') return null;
  const sessionRaw = localStorage.getItem('mesh_session');
  if (sessionRaw) {
    try {
      const session = JSON.parse(sessionRaw) as {
        user?: { entityId?: string; handle?: string; profile?: User['profile'] };
      };
      const u = session.user;
      if (u?.entityId) {
        return {
          id: u.entityId,
          handle: u.handle ?? null,
          profile: u.profile ?? {},
          public_key: '',
        };
      }
    } catch {
      /* ignore */
    }
  }
  const stored = localStorage.getItem(USER_STORAGE_KEY);
  if (stored) {
    try {
      return JSON.parse(stored) as User;
    } catch {
      return null;
    }
  }
  return null;
}

export function storeUser(user: User): void {
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
}

/** Dispatched when relay token is rejected; AuthProvider should clear session. */
export const MESH_AUTH_INVALID_EVENT = 'mesh:auth-invalid';

/** Clear vault + legacy auth storage and notify the app (e.g. stale or server-missing relay session). */
export function invalidateClientAuth(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('mesh_session');
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
  localStorage.removeItem(ENTITY_ID_STORAGE_KEY);
  window.dispatchEvent(new Event(MESH_AUTH_INVALID_EVENT));
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
  const url = new URL(endpoint, resolveApiBase());
  
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
    const errBody = await response.text();
    let msg = `API error: ${response.status}`;
    const ct = response.headers.get('content-type') ?? '';
    if (ct.includes('application/json') && errBody) {
      try {
        const error = JSON.parse(errBody) as { detail?: unknown; message?: string };
        const d = error.detail;
        if (typeof d === 'string') msg = d;
        else if (Array.isArray(d)) {
          const parts = d.map((e: unknown) =>
            typeof e === 'object' && e !== null && 'msg' in e
              ? String((e as { msg: string }).msg)
              : JSON.stringify(e),
          );
          msg = parts.join('; ') || msg;
        } else if (d != null) msg = String(d);
        else if (error.message) msg = error.message;
      } catch {
        msg = errBody.slice(0, 300);
      }
    } else if (errBody) {
      msg = errBody.replace(/\s+/g, ' ').trim().slice(0, 300);
    }
    if (
      response.status === 401 &&
      token &&
      !endpoint.includes('/api/auth/challenge') &&
      !endpoint.includes('/api/auth/verify')
    ) {
      invalidateClientAuth();
      msg = 'Session expired. Please sign in again.';
    }
    throw new Error(msg);
  }
  
  return response.json();
}

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
export async function createPost(
  text: string,
  replyTo?: string,
  access: 'public' | 'friends' | 'private' | 'group' = 'public',
  media: string[] = [],
  groupId?: string,
): Promise<{ id: string }> {
  const user = getStoredUser();
  if (!user) throw new Error('Not logged in');

  const effectiveAccess = groupId ? 'group' : access;

  return apiCall<{ id: string }>('/api/content', {
    method: 'POST',
    body: JSON.stringify({
      kind: replyTo ? 'reply' : 'post',
      body: text,
      media,
      reply_to: replyTo,
      access: effectiveAccess,
      group_id: groupId ?? null,
    }),
  });
}

export async function getPost(postId: string): Promise<Post> {
  return apiCall<Post>(`/api/content/${postId}`);
}

export async function getPosts(params: {
  author?: string;
  reply_to?: string;
  group_id?: string;
  limit?: number;
}): Promise<{ items: Post[]; total: number }> {
  const searchParams = new URLSearchParams();
  if (params.author) searchParams.set('author', params.author);
  if (params.reply_to) searchParams.set('reply_to', params.reply_to);
  if (params.group_id) searchParams.set('group_id', params.group_id);
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

// Group Admin API
export async function addGroupAdmin(groupId: string, userId: string, role: 'admin' | 'moderator' = 'admin'): Promise<void> {
  await apiCall(`/api/groups/${groupId}/admins`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export async function removeGroupAdmin(groupId: string, userId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/admins/${userId}`, { method: 'DELETE' });
}

export async function transferGroupOwnership(groupId: string, newOwnerId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/transfer`, {
    method: 'POST',
    body: JSON.stringify({ new_owner_id: newOwnerId }),
  });
}

// Group Moderation API
export async function kickFromGroup(groupId: string, userId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/kick`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function banFromGroup(groupId: string, userId: string, reason: string = ''): Promise<void> {
  await apiCall(`/api/groups/${groupId}/ban`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, reason }),
  });
}

export async function unbanFromGroup(groupId: string, userId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/ban/${userId}`, { method: 'DELETE' });
}

export async function getGroupBans(groupId: string): Promise<{ bans: Array<{ user_id: string; handle: string; reason: string; banned_at: string }> }> {
  return apiCall(`/api/groups/${groupId}/bans`);
}

export async function removeGroupContent(groupId: string, contentId: string, reason: string = ''): Promise<void> {
  await apiCall(`/api/groups/${groupId}/content/${contentId}/remove`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
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

