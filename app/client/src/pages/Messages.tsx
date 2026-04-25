/**
 * Direct Messages Page with E2EE
 */
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAuth } from '@/contexts/AuthContext';
import { 
  MessageCircle, Send, Search, Lock, ArrowLeft, 
  Plus, Check, CheckCheck 
} from 'lucide-react';

interface Conversation {
  id: string;
  participantId: string;
  participantHandle: string;
  participantName: string;
  lastMessage: string;
  lastMessageAt: string;
  unreadCount: number;
}

interface Message {
  id: string;
  senderId: string;
  content: string;
  timestamp: string;
  encrypted: boolean;
  status: 'sent' | 'delivered' | 'read';
}

const API_URL = '/api';

export default function Messages() {
  const { oderId } = useParams();
  const conversationId = oderId;
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<string | null>(conversationId || null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [showNewChat, setShowNewChat] = useState(false);
  const [searchUsers, setSearchUsers] = useState<any[]>([]);

  useEffect(() => {
    if (token) {
      loadConversations();
    }
  }, [token]);

  useEffect(() => {
    if (selectedConversation) {
      loadMessages(selectedConversation);
    }
  }, [selectedConversation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadConversations() {
    try {
      const resp = await fetch(`${API_URL}/messages/conversations?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data.conversations || []);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadMessages(oderId: string) {
    try {
      const resp = await fetch(`${API_URL}/messages/${conversationId}?token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setMessages(data.messages || []);
      }
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  }

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!newMessage.trim() || !selectedConversation) return;

    const tempMessage: Message = {
      id: `temp-${Date.now()}`,
      senderId: user?.entityId || '',
      content: newMessage,
      timestamp: new Date().toISOString(),
      encrypted: true,
      status: 'sent',
    };

    setMessages(prev => [...prev, tempMessage]);
    setNewMessage('');

    try {
      const resp = await fetch(`${API_URL}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          recipient_id: selectedConversation,
          content: newMessage,
          encrypted: true,
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        setMessages(prev => 
          prev.map(m => m.id === tempMessage.id ? { ...m, id: data.id, status: 'delivered' } : m)
        );
      }
    } catch (err) {
      console.error('Failed to send message:', err);
    }
  }

  async function searchForUsers(query: string) {
    if (!query.trim()) {
      setSearchUsers([]);
      return;
    }
    try {
      const resp = await fetch(`${API_URL}/search?q=${encodeURIComponent(query)}&type=users&token=${token}`);
      if (resp.ok) {
        const data = await resp.json();
        setSearchUsers(data.results || []);
      }
    } catch (err) {
      console.error('Search failed:', err);
    }
  }

  function startConversation(targetUserId: string) {
    setSelectedConversation(targetUserId);
    setShowNewChat(false);
    setSearchUsers([]);
    navigate(`/messages/${targetUserId}`);
  }

  function formatTime(dateStr: string) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    
    if (hours < 24) {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  const selectedChat = conversations.find(c => c.participantId === selectedConversation);

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-background">
      {/* Conversations List */}
      <div className={`w-full md:w-80 border-r flex flex-col ${selectedConversation ? 'hidden md:flex' : 'flex'}`}>
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold">Messages</h1>
            <Button size="icon" variant="ghost" onClick={() => setShowNewChat(true)}>
              <Plus className="h-5 w-5" />
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search conversations..."
              className="pl-9"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <ScrollArea className="flex-1">
          {showNewChat ? (
            <div className="p-4">
              <div className="flex items-center gap-2 mb-4">
                <Button size="icon" variant="ghost" onClick={() => setShowNewChat(false)}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <span className="font-medium">New Message</span>
              </div>
              <Input
                placeholder="Search users..."
                onChange={e => searchForUsers(e.target.value)}
                autoFocus
              />
              <div className="mt-4 space-y-2">
                {searchUsers.map(u => (
                  <button
                    key={u.id}
                    className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-muted transition"
                    onClick={() => startConversation(u.id)}
                  >
                    <Avatar>
                      <AvatarFallback>
                        {(u.profile?.name || u.handle || '?')[0].toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <div className="text-left">
                      <p className="font-medium">{u.profile?.name || u.handle}</p>
                      <p className="text-sm text-muted-foreground">@{u.handle}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <MessageCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No conversations yet</p>
              <Button className="mt-4" onClick={() => setShowNewChat(true)}>
                Start a conversation
              </Button>
            </div>
          ) : (
            conversations
              .filter(c => 
                !searchQuery || 
                c.participantName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                c.participantHandle.toLowerCase().includes(searchQuery.toLowerCase())
              )
              .map(conv => (
                <button
                  key={conv.id}
                  className={`w-full flex items-center gap-3 p-4 hover:bg-muted transition border-b ${
                    selectedConversation === conv.participantId ? 'bg-muted' : ''
                  }`}
                  onClick={() => {
                    setSelectedConversation(conv.participantId);
                    navigate(`/messages/${conv.participantId}`);
                  }}
                >
                  <Avatar>
                    <AvatarFallback>
                      {conv.participantName[0].toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 text-left min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="font-medium truncate">{conv.participantName}</p>
                      <span className="text-xs text-muted-foreground">
                        {formatTime(conv.lastMessageAt)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground truncate">
                      {conv.lastMessage}
                    </p>
                  </div>
                  {conv.unreadCount > 0 && (
                    <span className="bg-primary text-primary-foreground text-xs px-2 py-0.5 rounded-full">
                      {conv.unreadCount}
                    </span>
                  )}
                </button>
              ))
          )}
        </ScrollArea>
      </div>

      {/* Chat Area */}
      <div className={`flex-1 flex flex-col ${selectedConversation ? 'flex' : 'hidden md:flex'}`}>
        {selectedConversation ? (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b flex items-center gap-3">
              <Button 
                size="icon" 
                variant="ghost" 
                className="md:hidden"
                onClick={() => {
                  setSelectedConversation(null);
                  navigate('/messages');
                }}
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <Avatar>
                <AvatarFallback>
                  {(selectedChat?.participantName || '?')[0].toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <p className="font-medium">{selectedChat?.participantName || 'User'}</p>
                <p className="text-sm text-muted-foreground flex items-center gap-1">
                  <Lock className="h-3 w-3" />
                  End-to-end encrypted
                </p>
              </div>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {messages.map(msg => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.senderId === user?.entityId ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[70%] rounded-2xl px-4 py-2 ${
                        msg.senderId === user?.entityId
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      }`}
                    >
                      <p>{msg.content}</p>
                      <div className={`flex items-center gap-1 mt-1 text-xs ${
                        msg.senderId === user?.entityId ? 'text-primary-foreground/70' : 'text-muted-foreground'
                      }`}>
                        <span>{formatTime(msg.timestamp)}</span>
                        {msg.senderId === user?.entityId && (
                          msg.status === 'read' ? (
                            <CheckCheck className="h-3 w-3" />
                          ) : (
                            <Check className="h-3 w-3" />
                          )
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Message Input */}
            <form onSubmit={sendMessage} className="p-4 border-t">
              <div className="flex gap-2">
                <Input
                  placeholder="Type a message..."
                  value={newMessage}
                  onChange={e => setNewMessage(e.target.value)}
                  className="flex-1"
                />
                <Button type="submit" size="icon" disabled={!newMessage.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <MessageCircle className="h-16 w-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg">Select a conversation</p>
              <p className="text-sm">or start a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
