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
  body: { text?: string } | string;
  created_at: string;
  like_count: number;
  reply_count: number;
  liked?: boolean;
  liked_by_me?: boolean;
  moderation_labels?: Array<{ type: string; issuer: string; id?: string }>;
}

export function HomePage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMeta, setViewMeta] = useState<{ view_cost?: Record<string, unknown>; labels_status?: string } | null>(null);
  const [user, setUser] = useState(getStoredUser());

  const loadPosts = useCallback(async () => {
    setLoading(true);
    try {
      const u = getStoredUser();
      if (!u) return;
      const data = await apiCall<{
        items: Post[];
        view?: string;
        view_cost?: Record<string, unknown>;
        labels_status?: string;
      }>(
        `/api/users/${u.id}/feed?limit=50&offset=0&view=home_timeline&labels=1`
      );
      setViewMeta({
        view_cost: data.view_cost,
        labels_status: data.labels_status,
      });
      const items = (data.items || []).map((p) => ({
        ...p,
        liked: p.liked_by_me ?? p.liked,
      }));
      setPosts(items);
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
              <CardTitle className="text-base">About Holons</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>
                A decentralized social protocol with self-sovereign identity,
                end-to-end encryption, and verifiable feeds.
              </p>
              {viewMeta?.view_cost && (
                <p className="mt-2 text-xs font-mono text-muted-foreground/90">
                  View: home_timeline · est. scan:{" "}
                  {String((viewMeta.view_cost as { estimated_events_scanned?: number }).estimated_events_scanned ?? "—")}{" "}
                  {viewMeta.labels_status && viewMeta.labels_status !== "off"
                    ? `· labels: ${viewMeta.labels_status}`
                    : ""}
                </p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

export default HomePage;
