"use client";

import { useEffect, useState, useCallback } from "react";
import { getFeed, getStoredUser, like, unlike, type Post } from "@/lib/mesh";
import { PostCard } from "@/components/post-card";
import { ComposeBox } from "@/components/compose-box";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Feed() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const user = getStoredUser();

  const loadFeed = useCallback(async () => {
    if (!user) return;
    
    setLoading(true);
    setError("");
    
    try {
      const result = await getFeed(user.id);
      setPosts(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load feed");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const handleLike = async (postId: string, liked: boolean) => {
    try {
      if (liked) {
        await unlike(postId);
      } else {
        await like(postId);
      }
      // Update local state
      setPosts(posts.map(p => 
        p.id === postId 
          ? { 
              ...p, 
              liked_by_me: !liked,
              like_count: liked ? p.like_count - 1 : p.like_count + 1
            }
          : p
      ));
    } catch (err) {
      console.error("Failed to like/unlike:", err);
    }
  };

  const handlePostCreated = () => {
    loadFeed();
  };

  return (
    <div>
      {/* Header */}
      <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
        <div className="flex items-center justify-between p-4">
          <h1 className="text-xl font-bold">Home</h1>
          <Button 
            variant="ghost" 
            size="icon"
            onClick={loadFeed}
            disabled={loading}
          >
            <RefreshCw className={`w-5 h-5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Compose Box */}
      <div className="border-b">
        <ComposeBox onPostCreated={handlePostCreated} />
      </div>

      {/* Posts */}
      <div>
        {error && (
          <div className="p-4 text-center text-red-600">
            {error}
          </div>
        )}

        {loading && posts.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            Loading...
          </div>
        ) : posts.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <p className="mb-2">No posts yet</p>
            <p className="text-sm">Follow some people or create your first post!</p>
          </div>
        ) : (
          posts.map((post) => (
            <PostCard 
              key={post.id} 
              post={post}
              onLike={() => handleLike(post.id, post.liked_by_me || false)}
            />
          ))
        )}
      </div>
    </div>
  );
}
