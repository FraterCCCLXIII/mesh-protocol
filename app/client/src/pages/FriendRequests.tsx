/**
 * Friend Requests Page
 */
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/contexts/AuthContext';
import { apiCall } from '@/lib/mesh';
import { 
  UserPlus, UserCheck, UserX, Loader2, Users, Clock 
} from 'lucide-react';

interface FriendRequest {
  from_id?: string;
  to_id?: string;
  handle: string;
  profile: { name?: string };
  created_at: string;
}

export default function FriendRequests() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<'received' | 'sent'>('received');
  const [receivedRequests, setReceivedRequests] = useState<FriendRequest[]>([]);
  const [sentRequests, setSentRequests] = useState<FriendRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadRequests();
  }, [token]);

  async function loadRequests() {
    if (!token) return;
    setIsLoading(true);
    try {
      const [received, sent] = await Promise.all([
        apiCall<{ requests: FriendRequest[] }>('/api/friends/requests'),
        apiCall<{ requests: FriendRequest[] }>('/api/friends/sent'),
      ]);
      setReceivedRequests(received.requests || []);
      setSentRequests(sent.requests || []);
    } catch (err) {
      console.error('Failed to load friend requests:', err);
    } finally {
      setIsLoading(false);
    }
  }

  async function acceptRequest(fromId: string) {
    setProcessingIds(prev => new Set(prev).add(fromId));
    try {
      await apiCall('/api/friends/accept', {
        method: 'POST',
        body: JSON.stringify({ from_id: fromId }),
      });
      setReceivedRequests(prev => prev.filter(r => r.from_id !== fromId));
    } catch (err) {
      console.error('Failed to accept request:', err);
    } finally {
      setProcessingIds(prev => {
        const next = new Set(prev);
        next.delete(fromId);
        return next;
      });
    }
  }

  async function rejectRequest(fromId: string) {
    setProcessingIds(prev => new Set(prev).add(fromId));
    try {
      await apiCall('/api/friends/reject', {
        method: 'POST',
        body: JSON.stringify({ from_id: fromId }),
      });
      setReceivedRequests(prev => prev.filter(r => r.from_id !== fromId));
    } catch (err) {
      console.error('Failed to reject request:', err);
    } finally {
      setProcessingIds(prev => {
        const next = new Set(prev);
        next.delete(fromId);
        return next;
      });
    }
  }

  function formatTime(dateStr: string) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="sticky top-0 bg-background/95 backdrop-blur border-b z-10 p-4">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Users className="h-5 w-5" />
          Friend Requests
        </h1>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-auto p-0">
          <TabsTrigger 
            value="received"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3 flex-1"
          >
            Received ({receivedRequests.length})
          </TabsTrigger>
          <TabsTrigger 
            value="sent"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3 flex-1"
          >
            Sent ({sentRequests.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="received">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mx-auto" />
            </div>
          ) : receivedRequests.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <UserPlus className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No pending friend requests</p>
            </div>
          ) : (
            <div className="divide-y">
              {receivedRequests.map(req => (
                <div key={req.from_id} className="flex items-center gap-4 p-4">
                  <Link to={`/profile/${req.handle}`}>
                    <Avatar className="h-12 w-12">
                      <AvatarFallback>
                        {(req.profile?.name || req.handle)[0].toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                  </Link>
                  <div className="flex-1 min-w-0">
                    <Link to={`/profile/${req.handle}`} className="hover:underline">
                      <p className="font-semibold">{req.profile?.name || req.handle}</p>
                    </Link>
                    <p className="text-sm text-muted-foreground">@{req.handle}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      <Clock className="h-3 w-3 inline mr-1" />
                      {formatTime(req.created_at)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => acceptRequest(req.from_id!)}
                      disabled={processingIds.has(req.from_id!)}
                    >
                      {processingIds.has(req.from_id!) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <UserCheck className="h-4 w-4 mr-1" />
                          Accept
                        </>
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => rejectRequest(req.from_id!)}
                      disabled={processingIds.has(req.from_id!)}
                    >
                      <UserX className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="sent">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin mx-auto" />
            </div>
          ) : sentRequests.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No pending sent requests</p>
            </div>
          ) : (
            <div className="divide-y">
              {sentRequests.map(req => (
                <div key={req.to_id} className="flex items-center gap-4 p-4">
                  <Link to={`/profile/${req.handle}`}>
                    <Avatar className="h-12 w-12">
                      <AvatarFallback>
                        {(req.profile?.name || req.handle)[0].toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                  </Link>
                  <div className="flex-1 min-w-0">
                    <Link to={`/profile/${req.handle}`} className="hover:underline">
                      <p className="font-semibold">{req.profile?.name || req.handle}</p>
                    </Link>
                    <p className="text-sm text-muted-foreground">@{req.handle}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      <Clock className="h-3 w-3 inline mr-1" />
                      Sent {formatTime(req.created_at)}
                    </p>
                  </div>
                  <span className="text-sm text-muted-foreground px-3 py-1 bg-muted rounded-full">
                    Pending
                  </span>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
