/**
 * Authenticated MESH relay API client.
 * Session: `mesh_session` written by AuthContext (Vault) or `localIdentity` (dev). Always use entityId for relay APIs.
 */
import { getIdentityMode } from '@/config/identityMode';

const API_BASE = import.meta.env?.VITE_API_URL || '';

function apiOrigin(): string {
  if (API_BASE) {
    return API_BASE;
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return 'http://localhost:12001';
}

const SESSION_KEY = 'mesh_session';

/** Current user for API calls: `id` is always the MESH entity id. */
export interface CurrentUser {
  id: string;
  entityId: string;
  email?: string;
  handle?: string;
  public_key?: string;
  profile?: {
    name?: string;
    bio?: string;
    avatar?: string;
  };
}

export interface User {
  id: string;
  handle: string | null;
  created_at?: string;
  profile: {
    name?: string;
    bio?: string;
    avatar?: string;
    location?: string;
    website?: string;
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
  body: string | { text?: string };
  media?: string[];
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

function parseSession(): { relayToken: string; user: Record<string, unknown> } | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }
  try {
    const s = JSON.parse(raw) as { relayToken?: string; user?: Record<string, unknown> };
    if (!s.relayToken || !s.user) {
      return null;
    }
    return { relayToken: s.relayToken, user: s.user };
  } catch {
    return null;
  }
}

/**
 * Resolve relay user: always use `entityId` (never the Vault account id) for MESH entity routes.
 */
export function getStoredUser(): CurrentUser | null {
  const s = parseSession();
  if (!s) {
    return null;
  }
  const u = s.user;
  const entityId = typeof u.entityId === 'string' ? u.entityId : null;
  if (!entityId) {
    return null;
  }
  return {
    id: entityId,
    entityId,
    email: typeof u.email === 'string' ? u.email : undefined,
    handle: typeof u.handle === 'string' ? u.handle : undefined,
    public_key: typeof u.public_key === 'string' ? u.public_key : undefined,
    profile: (u.profile as CurrentUser['profile']) || undefined,
  };
}

export function getStoredToken(): string | null {
  return parseSession()?.relayToken ?? null;
}

function patchSessionUserProfile(profile: { name?: string; bio?: string; avatar?: string }): void {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) {
    return;
  }
  try {
    const s = JSON.parse(raw) as { user?: { profile?: Record<string, string | undefined> } };
    s.user = s.user || {};
    s.user.profile = { ...s.user.profile, ...profile };
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}

/**
 * All relay calls use `?token=` from `mesh_session` (Vault or local dev).
 */
export async function apiCall<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const url = new URL(endpoint, apiOrigin());
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
    throw new Error((error as { detail?: string }).detail || `API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function getUser(entityId: string): Promise<User> {
  return apiCall<User>(`/api/entities/${entityId}`);
}

export async function getUserByHandle(handle: string): Promise<User> {
  return apiCall<User>(`/api/entities/by-handle/${handle}`);
}

export async function updateProfile(profile: { name?: string; bio?: string; avatar?: string }): Promise<void> {
  const user = getStoredUser();
  if (!user) {
    throw new Error('Not logged in');
  }
  await apiCall(`/api/entities/${user.entityId}`, {
    method: 'PUT',
    body: JSON.stringify(profile),
  });
  patchSessionUserProfile(profile);
}

export async function createPost(
  text: string,
  replyTo?: string,
  access: 'public' | 'friends' | 'private' | 'group' = 'public',
  media: string[] = [],
  groupId?: string,
): Promise<{ id: string }> {
  if (!getStoredUser()) {
    throw new Error('Not logged in');
  }

  const payload: Record<string, unknown> = {
    kind: replyTo ? 'reply' : 'post',
    body: text,
    media,
    reply_to: replyTo,
    access: groupId ? 'group' : access,
  };
  if (groupId) {
    payload.group_id = groupId;
  }

  return apiCall<{ id: string }>('/api/content', {
    method: 'POST',
    body: JSON.stringify(payload),
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
  if (params.author) {
    searchParams.set('author', params.author);
  }
  if (params.reply_to) {
    searchParams.set('reply_to', params.reply_to);
  }
  if (params.limit) {
    searchParams.set('limit', params.limit.toString());
  }

  return apiCall<{ items: Post[]; total: number }>(`/api/content?${searchParams}`);
}

export async function deletePost(postId: string): Promise<void> {
  await apiCall(`/api/content/${postId}`, { method: 'DELETE' });
}

export async function getFeed(
  entityId: string,
  limit = 50,
): Promise<{ items: Post[]; total: number }> {
  return apiCall<{ items: Post[]; total: number }>(`/api/users/${entityId}/feed?limit=${limit}`);
}

export async function follow(targetId: string): Promise<void> {
  await apiCall('/api/links', {
    method: 'POST',
    body: JSON.stringify({ target: targetId, kind: 'follow' }),
  });
}

export async function unfollow(targetId: string): Promise<void> {
  const user = getStoredUser();
  if (!user) {
    throw new Error('Not logged in');
  }
  const linkId = `lnk:${user.entityId}:follow:${targetId}`.slice(0, 40);
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
  if (!user) {
    throw new Error('Not logged in');
  }
  const linkId = `lnk:${user.entityId}:like:${contentId}`.slice(0, 40);
  await apiCall(`/api/links/${linkId}`, { method: 'DELETE' });
}

export async function getFollowers(entityId: string): Promise<{ items: User[]; total: number }> {
  return apiCall<{ items: User[]; total: number }>(`/api/users/${entityId}/followers`);
}

export async function getFollowing(entityId: string): Promise<{ items: User[]; total: number }> {
  return apiCall<{ items: User[]; total: number }>(`/api/users/${entityId}/following`);
}

export async function createGroup(
  name: string,
  description: string,
  access: 'public' | 'private',
): Promise<{ id: string }> {
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

export async function addGroupAdmin(
  groupId: string,
  userId: string,
  role: 'admin' | 'moderator' = 'admin',
): Promise<void> {
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

export async function kickFromGroup(groupId: string, userId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/kick`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function banFromGroup(groupId: string, userId: string, reason = ''): Promise<void> {
  await apiCall(`/api/groups/${groupId}/ban`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, reason }),
  });
}

export async function unbanFromGroup(groupId: string, userId: string): Promise<void> {
  await apiCall(`/api/groups/${groupId}/ban/${userId}`, { method: 'DELETE' });
}

export async function getGroupBans(
  groupId: string,
): Promise<{ bans: Array<{ user_id: string; handle: string; reason: string; banned_at: string }> }> {
  return apiCall(`/api/groups/${groupId}/bans`);
}

export async function removeGroupContent(
  groupId: string,
  contentId: string,
  reason = '',
): Promise<void> {
  await apiCall(`/api/groups/${groupId}/content/${contentId}/remove`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

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

/**
 * @deprecated Identity is via Vault or local dev (`getIdentityMode`). Removed HMAC "demo" register/login.
 */
export async function registerUser(): Promise<never> {
  const hint =
    getIdentityMode() === 'local'
      ? 'Use the Local dev form on the login page, or set VITE_IDENTITY_MODE=local.'
      : 'Use Login / Register with the Identity Vault.';
  throw new Error(`registerUser() was removed. ${hint}`);
}

export async function loginUser(): Promise<never> {
  return registerUser();
}
