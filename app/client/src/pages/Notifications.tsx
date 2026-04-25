/**
 * Notifications Page
 */
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Bell, Heart, MessageCircle, UserPlus, Repeat2, 
  AtSign, CheckCheck, Settings 
} from 'lucide-react';

interface Notification {
  id: string;
  type: 'like' | 'reply' | 'follow' | 'mention' | 'repost';
  actorId: string;
  actorHandle: string;
  actorName: string;
  targetId?: string;
  targetPreview?: string;
  read: boolean;
  createdAt: string;
}

const API_URL = '/api';

export default function Notifications() {
  const { token } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'mentions'>('all');

  useEffect(() => {
    if (token) {
      loadNotifications();
    }
  }, [token]);

  async function loadNotifications() {
    try {
      const resp = await fetch(`${API_URL}/notifications?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setNotifications(data.items || []);
      }
    } catch (err) {
      console.error('Failed to load notifications:', err);
    } finally {
      setIsLoading(false);
    }
  }

  async function markAllRead() {
    try {
      await fetch(`${API_URL}/notifications/read-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (err) {
      console.error('Failed to mark as read:', err);
    }
  }

  function getIcon(type: string) {
    switch (type) {
      case 'like': return <Heart className="h-5 w-5 text-red-500" />;
      case 'reply': return <MessageCircle className="h-5 w-5 text-blue-500" />;
      case 'follow': return <UserPlus className="h-5 w-5 text-green-500" />;
      case 'mention': return <AtSign className="h-5 w-5 text-purple-500" />;
      case 'repost': return <Repeat2 className="h-5 w-5 text-emerald-500" />;
      default: return <Bell className="h-5 w-5" />;
    }
  }

  function getMessage(notif: Notification) {
    switch (notif.type) {
      case 'like': return 'liked your post';
      case 'reply': return 'replied to your post';
      case 'follow': return 'followed you';
      case 'mention': return 'mentioned you';
      case 'repost': return 'reposted your post';
      default: return 'interacted with you';
    }
  }

  function formatTime(dateStr: string) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const mins = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (mins < 60) return `${mins}m`;
    if (hours < 24) return `${hours}h`;
    if (days < 7) return `${days}d`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  const filteredNotifications = filter === 'mentions' 
    ? notifications.filter(n => n.type === 'mention')
    : notifications;

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="sticky top-0 bg-background/95 backdrop-blur border-b z-10">
        <div className="flex items-center justify-between p-4">
          <h1 className="text-xl font-bold">Notifications</h1>
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" onClick={markAllRead}>
                <CheckCheck className="h-4 w-4 mr-2" />
                Mark all read
              </Button>
            )}
            <Button variant="ghost" size="icon">
              <Settings className="h-5 w-5" />
            </Button>
          </div>
        </div>
        
        <Tabs value={filter} onValueChange={(v) => setFilter(v as any)}>
          <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-auto p-0">
            <TabsTrigger 
              value="all"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-3"
            >
              All
            </TabsTrigger>
            <TabsTrigger 
              value="mentions"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-3"
            >
              Mentions
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Notifications List */}
      <div>
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            Loading notifications...
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No notifications yet</p>
            <p className="text-sm mt-2">
              When someone interacts with your posts, you'll see it here.
            </p>
          </div>
        ) : (
          filteredNotifications.map(notif => (
            <Link
              key={notif.id}
              to={notif.targetId ? `/post/${notif.targetId}` : `/profile/${notif.actorHandle}`}
              className={`flex gap-4 p-4 border-b hover:bg-muted/50 transition ${
                !notif.read ? 'bg-primary/5' : ''
              }`}
            >
              <div className="flex-shrink-0 mt-1">
                {getIcon(notif.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start gap-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>
                      {notif.actorName[0].toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <p>
                      <span className="font-semibold">{notif.actorName}</span>
                      {' '}
                      <span className="text-muted-foreground">{getMessage(notif)}</span>
                    </p>
                    {notif.targetPreview && (
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {notif.targetPreview}
                      </p>
                    )}
                  </div>
                  <span className="text-sm text-muted-foreground flex-shrink-0">
                    {formatTime(notif.createdAt)}
                  </span>
                </div>
              </div>
              {!notif.read && (
                <div className="flex-shrink-0">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                </div>
              )}
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
