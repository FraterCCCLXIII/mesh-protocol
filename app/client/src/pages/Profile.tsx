import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Calendar, MapPin, Link as LinkIcon, UserPlus, UserMinus, Loader2, ArrowLeft } from "lucide-react";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { PostCard } from "../components/PostCard";
import { getStoredUser, apiCall, getUserByHandle, getStoredToken } from "../lib/mesh";

interface User {
  id: string;
  handle: string;
  profile: { name?: string; bio?: string; location?: string; website?: string };
  created_at: string;
}

interface Post {
  id: string;
  author: string;
  author_handle?: string;
  author_profile?: { name?: string };
  body: string | { text?: string };
  created_at: string;
  like_count: number;
  reply_count: number;
  liked?: boolean;
}

interface FollowUser {
  id: string;
  handle: string;
  profile: { name?: string };
}

export function ProfilePage() {
  const { handle } = useParams();
  const currentUser = getStoredUser();
  const token = getStoredToken();
  
  const [user, setUser] = useState<User | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("posts");
  
  // Follow state
  const [isFollowing, setIsFollowing] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);
  const [followingCount, setFollowingCount] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Follow lists dialog
  const [showFollowers, setShowFollowers] = useState(false);
  const [showFollowing, setShowFollowing] = useState(false);
  const [followers, setFollowers] = useState<FollowUser[]>([]);
  const [following, setFollowing] = useState<FollowUser[]>([]);

  const isOwnProfile = currentUser?.id === user?.id;

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        let profileUser: User;
        if (handle) {
          profileUser = await getUserByHandle(handle);
        } else if (currentUser) {
          profileUser = currentUser as User;
        } else {
          return;
        }
        setUser(profileUser);

        // Load user's posts
        const postsData = await apiCall<{ items: Post[] }>(
          `/api/content?author=${profileUser.id}&limit=50`
        );
        setPosts(postsData.items || []);

        // Load follow counts
        const [followersData, followingData] = await Promise.all([
          apiCall<{ users: FollowUser[] }>(`/api/users/${profileUser.id}/followers`),
          apiCall<{ users: FollowUser[] }>(`/api/users/${profileUser.id}/following`),
        ]);
        setFollowerCount(followersData.users?.length || 0);
        setFollowingCount(followingData.users?.length || 0);

        // Check if current user follows this user
        if (currentUser && currentUser.id !== profileUser.id) {
          const isFollowingUser = followersData.users?.some(f => f.id === currentUser.id);
          setIsFollowing(isFollowingUser || false);
        }
      } catch (err) {
        console.error("Failed to load profile:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [handle]);

  async function handleFollow() {
    if (!user || !token || isProcessing) return;
    setIsProcessing(true);
    
    try {
      if (isFollowing) {
        // Unfollow
        await apiCall(`/api/links`, {
          method: "DELETE",
          body: JSON.stringify({
            source: currentUser?.id,
            target: user.id,
            kind: "follow",
          }),
        });
        setIsFollowing(false);
        setFollowerCount(prev => prev - 1);
      } else {
        // Follow
        await apiCall(`/api/links`, {
          method: "POST",
          body: JSON.stringify({
            source: currentUser?.id,
            target: user.id,
            kind: "follow",
          }),
        });
        setIsFollowing(true);
        setFollowerCount(prev => prev + 1);
      }
    } catch (err) {
      console.error("Failed to toggle follow:", err);
    } finally {
      setIsProcessing(false);
    }
  }

  async function loadFollowers() {
    if (!user) return;
    const data = await apiCall<{ users: FollowUser[] }>(`/api/users/${user.id}/followers`);
    setFollowers(data.users || []);
    setShowFollowers(true);
  }

  async function loadFollowing() {
    if (!user) return;
    const data = await apiCall<{ users: FollowUser[] }>(`/api/users/${user.id}/following`);
    setFollowing(data.users || []);
    setShowFollowing(true);
  }

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || user?.handle?.[0]?.toUpperCase() || "?";

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="sticky top-0 bg-background/95 backdrop-blur border-b z-10 p-4 flex items-center gap-4">
        <Link to="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="font-bold">{user?.profile?.name || user?.handle || "Profile"}</h1>
          {user && <p className="text-sm text-muted-foreground">{posts.length} posts</p>}
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-muted-foreground">Loading...</div>
      ) : !user ? (
        <div className="p-8 text-center text-muted-foreground">User not found</div>
      ) : (
        <>
          {/* Cover & Avatar */}
          <div className="h-32 bg-gradient-to-r from-primary/20 to-primary/5" />
          <div className="px-4 pb-4 border-b">
            <div className="flex justify-between items-start">
              <Avatar className="w-24 h-24 -mt-12 border-4 border-background">
                <AvatarFallback className="text-2xl bg-primary/10">{initials}</AvatarFallback>
              </Avatar>
              
              <div className="mt-2">
                {isOwnProfile ? (
                  <Button variant="outline">Edit Profile</Button>
                ) : token ? (
                  <Button
                    variant={isFollowing ? "outline" : "default"}
                    onClick={handleFollow}
                    disabled={isProcessing}
                  >
                    {isProcessing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : isFollowing ? (
                      <>
                        <UserMinus className="h-4 w-4 mr-2" />
                        Unfollow
                      </>
                    ) : (
                      <>
                        <UserPlus className="h-4 w-4 mr-2" />
                        Follow
                      </>
                    )}
                  </Button>
                ) : (
                  <Link to="/login">
                    <Button>Follow</Button>
                  </Link>
                )}
              </div>
            </div>

            {/* User Info */}
            <div className="mt-4">
              <h1 className="text-xl font-bold">{user.profile?.name || user.handle}</h1>
              <p className="text-muted-foreground">@{user.handle}</p>
              
              {user.profile?.bio && (
                <p className="mt-3">{user.profile.bio}</p>
              )}

              <div className="flex flex-wrap gap-4 mt-3 text-sm text-muted-foreground">
                {user.profile?.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    {user.profile.location}
                  </span>
                )}
                {user.profile?.website && (
                  <a 
                    href={user.profile.website} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-primary hover:underline"
                  >
                    <LinkIcon className="h-4 w-4" />
                    {user.profile.website.replace(/^https?:\/\//, '')}
                  </a>
                )}
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Joined {formatDate(user.created_at)}
                </span>
              </div>

              {/* Follow Stats */}
              <div className="flex gap-4 mt-3">
                <button 
                  onClick={loadFollowing}
                  className="hover:underline"
                >
                  <span className="font-bold">{followingCount}</span>
                  <span className="text-muted-foreground ml-1">Following</span>
                </button>
                <button 
                  onClick={loadFollowers}
                  className="hover:underline"
                >
                  <span className="font-bold">{followerCount}</span>
                  <span className="text-muted-foreground ml-1">Followers</span>
                </button>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full justify-start rounded-none border-b bg-transparent h-auto p-0">
              <TabsTrigger 
                value="posts"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3 flex-1"
              >
                Posts
              </TabsTrigger>
              <TabsTrigger 
                value="replies"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3 flex-1"
              >
                Replies
              </TabsTrigger>
              <TabsTrigger 
                value="likes"
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary px-6 py-3 flex-1"
              >
                Likes
              </TabsTrigger>
            </TabsList>

            <TabsContent value="posts">
              {posts.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  No posts yet
                </div>
              ) : (
                posts.map((post) => <PostCard key={post.id} post={post} />)
              )}
            </TabsContent>

            <TabsContent value="replies">
              <div className="p-8 text-center text-muted-foreground">
                No replies yet
              </div>
            </TabsContent>

            <TabsContent value="likes">
              <div className="p-8 text-center text-muted-foreground">
                No likes yet
              </div>
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Followers Dialog */}
      <Dialog open={showFollowers} onOpenChange={setShowFollowers}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Followers</DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {followers.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">No followers yet</p>
            ) : (
              followers.map(f => (
                <Link
                  key={f.id}
                  to={`/profile/${f.handle}`}
                  onClick={() => setShowFollowers(false)}
                  className="flex items-center gap-3 p-3 hover:bg-muted rounded-lg"
                >
                  <Avatar>
                    <AvatarFallback>{(f.profile?.name || f.handle)[0].toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{f.profile?.name || f.handle}</p>
                    <p className="text-sm text-muted-foreground">@{f.handle}</p>
                  </div>
                </Link>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Following Dialog */}
      <Dialog open={showFollowing} onOpenChange={setShowFollowing}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Following</DialogTitle>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {following.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">Not following anyone yet</p>
            ) : (
              following.map(f => (
                <Link
                  key={f.id}
                  to={`/profile/${f.handle}`}
                  onClick={() => setShowFollowing(false)}
                  className="flex items-center gap-3 p-3 hover:bg-muted rounded-lg"
                >
                  <Avatar>
                    <AvatarFallback>{(f.profile?.name || f.handle)[0].toUpperCase()}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{f.profile?.name || f.handle}</p>
                    <p className="text-sm text-muted-foreground">@{f.handle}</p>
                  </div>
                </Link>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ProfilePage;
