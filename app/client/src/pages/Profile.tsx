import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Calendar } from "lucide-react";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { Sidebar } from "../components/Sidebar";
import { PostCard } from "../components/PostCard";
import { getStoredUser, apiCall, getUserByHandle } from "../lib/mesh";

interface User {
  id: string;
  handle: string;
  profile: { name?: string; bio?: string };
  created_at: string;
}

interface Post {
  id: string;
  author: string;
  author_handle?: string;
  author_profile?: { name?: string };
  body: { text?: string };
  created_at: string;
  like_count: number;
  reply_count: number;
  liked?: boolean;
}

export function ProfilePage() {
  const { handle } = useParams();
  const currentUser = getStoredUser();
  const [user, setUser] = useState<User | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);

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
        const data = await apiCall<{ items: Post[] }>(
          `/api/content?author=${profileUser.id}&limit=50`
        );
        setPosts(data.items || []);
      } catch (err) {
        console.error("Failed to load profile:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [handle, currentUser]);

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />

        <main className="flex-1 border-x border-border min-h-screen">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : !user ? (
            <div className="p-8 text-center text-muted-foreground">User not found</div>
          ) : (
            <>
              {/* Profile Header */}
              <div className="h-32 bg-muted" />
              <div className="px-4 pb-4 border-b">
                <div className="flex justify-between">
                  <Avatar className="w-24 h-24 -mt-12 border-4 border-background">
                    <AvatarFallback className="text-2xl">{initials}</AvatarFallback>
                  </Avatar>
                  {currentUser?.id === user.id && (
                    <Button variant="outline" className="mt-4">
                      Edit Profile
                    </Button>
                  )}
                </div>
                <div className="mt-4">
                  <h1 className="text-xl font-bold">{user.profile?.name || "User"}</h1>
                  <p className="text-muted-foreground">@{user.handle}</p>
                  {user.profile?.bio && <p className="mt-2">{user.profile.bio}</p>}
                  <div className="flex items-center gap-1 text-sm text-muted-foreground mt-2">
                    <Calendar className="w-4 h-4" />
                    <span>Joined {formatDate(user.created_at)}</span>
                  </div>
                </div>
              </div>

              {/* Posts */}
              <div>
                {posts.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    No posts yet
                  </div>
                ) : (
                  posts.map((post) => <PostCard key={post.id} post={post} />)
                )}
              </div>
            </>
          )}
        </main>

        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}
