"use client";

import { useEffect, useState } from "react";
import { Calendar, Link as LinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sidebar } from "@/components/sidebar";
import { PostCard } from "@/components/post-card";
import { 
  getStoredUser, 
  getPosts, 
  getFollowers, 
  getFollowing,
  like,
  unlike,
  type Post, 
  type User 
} from "@/lib/mesh";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [followers, setFollowers] = useState<User[]>([]);
  const [following, setFollowing] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"posts" | "replies" | "likes">("posts");

  useEffect(() => {
    const loadProfile = async () => {
      const currentUser = getStoredUser();
      if (!currentUser) return;

      setUser(currentUser);

      try {
        const [postsResult, followersResult, followingResult] = await Promise.all([
          getPosts({ author: currentUser.id }),
          getFollowers(currentUser.id),
          getFollowing(currentUser.id),
        ]);

        setPosts(postsResult.items);
        setFollowers(followersResult.items);
        setFollowing(followingResult.items);
      } catch (err) {
        console.error("Failed to load profile:", err);
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, []);

  const handleLike = async (postId: string, liked: boolean) => {
    try {
      if (liked) {
        await unlike(postId);
      } else {
        await like(postId);
      }
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

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="p-4">
              <h1 className="text-xl font-bold">Profile</h1>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading...
            </div>
          ) : user ? (
            <>
              {/* Banner */}
              <div className="h-32 bg-gradient-to-r from-neutral-200 to-neutral-300 dark:from-neutral-800 dark:to-neutral-900" />

              {/* Profile Info */}
              <div className="px-4 pb-4">
                <div className="flex justify-between items-start -mt-16">
                  <Avatar className="w-32 h-32 border-4 border-background">
                    <AvatarFallback className="text-4xl">{initials}</AvatarFallback>
                  </Avatar>
                  <Button variant="outline" className="mt-20">
                    Edit Profile
                  </Button>
                </div>

                <div className="mt-4">
                  <h2 className="text-xl font-bold">
                    {user.profile?.name || "Anonymous"}
                  </h2>
                  <p className="text-muted-foreground">
                    @{user.handle || user.id.slice(4, 12)}
                  </p>

                  {user.profile?.bio && (
                    <p className="mt-3">{user.profile.bio}</p>
                  )}

                  <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-4 h-4" />
                      Joined recently
                    </span>
                  </div>

                  <div className="flex gap-4 mt-3">
                    <span>
                      <strong>{following.length}</strong>{" "}
                      <span className="text-muted-foreground">Following</span>
                    </span>
                    <span>
                      <strong>{followers.length}</strong>{" "}
                      <span className="text-muted-foreground">Followers</span>
                    </span>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b">
                {(["posts", "replies", "likes"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`flex-1 py-4 text-center font-medium capitalize transition-colors ${
                      activeTab === tab
                        ? "border-b-2 border-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* Posts */}
              <div>
                {posts.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    No posts yet
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
            </>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              User not found
            </div>
          )}
        </main>
        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}
