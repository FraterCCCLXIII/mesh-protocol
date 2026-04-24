import { useEffect, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Sidebar } from "../components/Sidebar";
import { ComposeBox } from "../components/ComposeBox";
import { PostCard } from "../components/PostCard";
import { AuthPage } from "../components/AuthPage";
import { getStoredUser, apiCall } from "../lib/mesh";

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

export function HomePage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(getStoredUser());

  const loadPosts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiCall<{ items: Post[] }>("/api/content?limit=50");
      setPosts(data.items || []);
    } catch (err) {
      console.error("Failed to load posts:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      loadPosts();
    }
  }, [user, loadPosts]);

  if (!user) {
    return <AuthPage onAuth={() => setUser(getStoredUser())} />;
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        
        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center justify-between p-4">
              <h1 className="text-xl font-bold">Home</h1>
              <Button variant="ghost" size="icon" onClick={loadPosts}>
                <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          {/* Compose */}
          <ComposeBox onPostCreated={loadPosts} />

          {/* Posts */}
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading...
            </div>
          ) : posts.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <p>No posts yet</p>
              <p className="text-sm mt-2">Be the first to post something!</p>
            </div>
          ) : (
            <div>
              {posts.map((post) => (
                <PostCard key={post.id} post={post} onLike={loadPosts} />
              ))}
            </div>
          )}
        </main>

        {/* Right Sidebar */}
        <aside className="w-80 p-4 hidden lg:block">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About MESH</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>
                A decentralized social protocol with self-sovereign identity,
                end-to-end encryption, and verifiable feeds.
              </p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
