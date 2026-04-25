/**
 * Group Detail Page with Admin Settings
 */
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/contexts/AuthContext';
import { PostCard } from '@/components/PostCard';
import { ComposeBox } from '@/components/ComposeBox';
import { 
  Users, Shield, UserPlus, UserMinus, 
  Crown, Ban, AlertTriangle, Loader2,
  Hash
} from 'lucide-react';

interface Group {
  id: string;
  name: string;
  description: string;
  owner: string;
  access: 'public' | 'private';
  member_count: number;
  created_at: string;
}

interface Member {
  id: string;
  handle: string;
  profile: { name?: string };
  role: 'owner' | 'admin' | 'moderator' | 'member';
  joined_at?: string;
}

interface BannedUser {
  user_id: string;
  handle: string;
  reason: string;
  banned_at: string;
}

const API_URL = '/api';

export default function GroupDetail() {
  const { groupId } = useParams();
  const { user, token } = useAuth();
  
  const [group, setGroup] = useState<Group | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [posts, setPosts] = useState<any[]>([]);
  const [bannedUsers, setBannedUsers] = useState<BannedUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMember, setIsMember] = useState(false);
  const [activeTab, setActiveTab] = useState('posts');
  
  // Admin actions
  const [showBanDialog, setShowBanDialog] = useState(false);
  const [banTarget, setBanTarget] = useState<Member | null>(null);
  const [banReason, setBanReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const isOwner = group?.owner === user?.entityId;
  const currentUserRole = members.find(m => m.id === user?.entityId)?.role;
  const isAdmin = isOwner || currentUserRole === 'admin' || currentUserRole === 'moderator';

  useEffect(() => {
    if (groupId) {
      loadGroup();
      loadPosts();
    }
  }, [groupId, token]);

  async function loadGroup() {
    if (!groupId) return;
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}${token ? `?token=${token}` : ''}`);
      if (resp.ok) {
        const data = await resp.json();
        setGroup(data);
        setIsMember(data.is_member || false);
        setMembers(data.members || []);
      }
    } catch (err) {
      console.error('Failed to load group:', err);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadPosts() {
    if (!groupId) return;
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/content${qs}`);
      if (resp.ok) {
        const data = await resp.json();
        setPosts(data.items || []);
      }
    } catch (err) {
      console.error('Failed to load posts:', err);
    }
  }

  async function loadBannedUsers() {
    if (!isAdmin) return;
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/bans?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setBannedUsers(data.bans || []);
      }
    } catch (err) {
      console.error('Failed to load banned users:', err);
    }
  }

  async function joinGroup() {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/join?token=${token}`, {
        method: 'POST',
      });
      if (resp.ok) {
        setIsMember(true);
        await loadGroup();
        loadPosts();
      }
    } catch (err) {
      console.error('Failed to join group:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function leaveGroup() {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/leave?token=${token}`, {
        method: 'POST',
      });
      if (resp.ok) {
        setIsMember(false);
        await loadGroup();
        loadPosts();
      }
    } catch (err) {
      console.error('Failed to leave group:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function promoteMember(memberId: string, role: 'admin' | 'moderator') {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/admins?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: memberId, role }),
      });
      if (resp.ok) {
        loadGroup();
      }
    } catch (err) {
      console.error('Failed to promote member:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function demoteMember(memberId: string) {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/admins/${memberId}?token=${token}`, {
        method: 'DELETE',
      });
      if (resp.ok) {
        loadGroup();
      }
    } catch (err) {
      console.error('Failed to demote member:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function kickMember(memberId: string) {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/kick?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: memberId }),
      });
      if (resp.ok) {
        await loadGroup();
      }
    } catch (err) {
      console.error('Failed to kick member:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function banMember() {
    if (!banTarget) return;
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/ban?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: banTarget.id, reason: banReason }),
      });
      if (resp.ok) {
        setShowBanDialog(false);
        setBanTarget(null);
        setBanReason('');
        loadGroup();
        loadBannedUsers();
      }
    } catch (err) {
      console.error('Failed to ban member:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function unbanUser(userId: string) {
    setIsProcessing(true);
    try {
      const resp = await fetch(`${API_URL}/groups/${groupId}/ban/${userId}?token=${token}`, {
        method: 'DELETE',
      });
      if (resp.ok) {
        loadBannedUsers();
      }
    } catch (err) {
      console.error('Failed to unban user:', err);
    } finally {
      setIsProcessing(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!group) {
    return (
      <div className="text-center p-8">
        <p className="text-muted-foreground">Group not found</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Group Header */}
      <div className="bg-gradient-to-r from-primary/10 to-primary/5 p-8 border-b">
        <div className="flex items-start gap-6">
          <div className="h-24 w-24 rounded-2xl bg-primary/20 flex items-center justify-center">
            <Hash className="h-12 w-12 text-primary" />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold">{group.name}</h1>
            <p className="text-muted-foreground mt-2">{group.description}</p>
            <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Users className="h-4 w-4" />
                {group.member_count} members
              </span>
              <span className="capitalize">{group.access}</span>
            </div>
          </div>
          <div>
            {isMember ? (
              <Button variant="outline" onClick={leaveGroup} disabled={isProcessing || isOwner}>
                {isOwner ? 'Owner' : 'Leave Group'}
              </Button>
            ) : (
              <Button onClick={joinGroup} disabled={isProcessing}>
                <UserPlus className="h-4 w-4 mr-2" />
                Join Group
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-auto p-0">
          <TabsTrigger 
            value="posts"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3"
          >
            Posts
          </TabsTrigger>
          <TabsTrigger 
            value="members"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3"
          >
            Members
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger 
              value="admin"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3"
              onClick={() => loadBannedUsers()}
            >
              <Shield className="h-4 w-4 mr-2" />
              Admin
            </TabsTrigger>
          )}
        </TabsList>

        {/* Posts Tab */}
        <TabsContent value="posts">
          {isMember && groupId && (
            <ComposeBox groupId={groupId} onPostCreated={loadPosts} />
          )}
          {!isMember && (
            <div className="p-4 text-center text-sm text-muted-foreground border-b">
              Join this group to post in the feed.
            </div>
          )}
          {posts.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No posts yet. Be the first to post!
            </div>
          ) : (
            posts.map((post) => <PostCard key={post.id} post={post} onLike={loadPosts} />)
          )}
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members">
          <div className="divide-y">
            {members.map(member => (
              <div key={member.id} className="flex items-center gap-4 p-4">
                <Avatar>
                  <AvatarFallback>
                    {(member.profile?.name || member.handle)[0].toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Link to={`/profile/${member.handle}`} className="font-medium hover:underline">
                      {member.profile?.name || member.handle}
                    </Link>
                    {member.role === 'owner' && (
                      <Crown className="h-4 w-4 text-yellow-500" />
                    )}
                    {member.role === 'admin' && (
                      <Shield className="h-4 w-4 text-blue-500" />
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">@{member.handle}</p>
                </div>
                {isAdmin && member.id !== user?.entityId && member.role !== 'owner' && (
                  <div className="flex gap-2">
                    {isOwner && member.role === 'member' && (
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => promoteMember(member.id, 'admin')}
                      >
                        Make Admin
                      </Button>
                    )}
                    {isOwner && member.role === 'admin' && (
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => demoteMember(member.id)}
                      >
                        Remove Admin
                      </Button>
                    )}
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={() => kickMember(member.id)}
                    >
                      <UserMinus className="h-4 w-4" />
                    </Button>
                    <Button 
                      size="sm" 
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => {
                        setBanTarget(member);
                        setShowBanDialog(true);
                      }}
                    >
                      <Ban className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </TabsContent>

        {/* Admin Tab */}
        {isAdmin && (
          <TabsContent value="admin" className="p-4 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Banned Users</CardTitle>
                <CardDescription>Users who are banned from this group</CardDescription>
              </CardHeader>
              <CardContent>
                {bannedUsers.length === 0 ? (
                  <p className="text-muted-foreground">No banned users</p>
                ) : (
                  <div className="space-y-4">
                    {bannedUsers.map(banned => (
                      <div key={banned.user_id} className="flex items-center justify-between p-3 border rounded-lg">
                        <div>
                          <p className="font-medium">@{banned.handle}</p>
                          <p className="text-sm text-muted-foreground">
                            Reason: {banned.reason || 'No reason given'}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Banned: {new Date(banned.banned_at).toLocaleDateString()}
                          </p>
                        </div>
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => unbanUser(banned.user_id)}
                        >
                          Unban
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Group Settings</CardTitle>
                <CardDescription>Manage group configuration</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Group Name</Label>
                  <Input value={group.name} disabled={!isOwner} />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea value={group.description} disabled={!isOwner} />
                </div>
                {isOwner && (
                  <Button>Save Changes</Button>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      {/* Ban Dialog */}
      <Dialog open={showBanDialog} onOpenChange={setShowBanDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Ban User
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p>
              Are you sure you want to ban <strong>@{banTarget?.handle}</strong> from this group?
            </p>
            <div className="space-y-2">
              <Label>Reason (optional)</Label>
              <Textarea
                value={banReason}
                onChange={e => setBanReason(e.target.value)}
                placeholder="Provide a reason for the ban..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBanDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={banMember} disabled={isProcessing}>
              {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Ban User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
