import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Heart, MessageCircle, Repeat2, Share } from "lucide-react";
import { Button } from "../components/ui/button";
import { Avatar, AvatarFallback } from "../components/ui/avatar";
import { Sidebar } from "../components/Sidebar";
import { ComposeBox } from "../components/ComposeBox";
import { apiCall, getPost, postBodyText } from "../lib/mesh";

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
  reply_to?: string;
}

export function PostDetailPage() {
  const { id } = useParams();
  const [post, setPost] = useState<Post | null>(null);
  const [replies, setReplies] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPost = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const postData = await getPost(id);
      setPost(postData);

      // Load replies
      const repliesData = await apiCall<{ items: Post[] }>(
        `/api/content?reply_to=${id}&limit=50`
      );
      setReplies(repliesData.items || []);
    } catch (err) {
      console.error("Failed to load post:", err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const getInitials = (name?: string) =>
    name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  const handleLike = async () => {
    if (!post) return;
    try {
      if (post.liked) {
        await apiCall(`/api/content/${post.id}/unlike`, { method: "POST" });
      } else {
        await apiCall(`/api/content/${post.id}/like`, { method: "POST" });
      }
      loadPost();
    } catch (err) {
      console.error("Failed to like:", err);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />

        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center gap-4 p-4">
              <Link to="/">
                <Button variant="ghost" size="icon">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <h1 className="text-xl font-bold">Post</h1>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading...</div>
          ) : !post ? (
            <div className="p-8 text-center text-muted-foreground">Post not found</div>
          ) : (
            <>
              {/* Main Post */}
              <article className="p-4 border-b">
                <div className="flex items-start gap-3">
                  <Avatar>
                    <AvatarFallback>
                      {getInitials(post.author_profile?.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-bold">{post.author_profile?.name || "User"}</p>
                    <p className="text-muted-foreground text-sm">
                      @{post.author_handle || post.author?.slice(4, 12)}
                    </p>
                  </div>
                </div>
                <p className="mt-4 text-xl whitespace-pre-wrap">{postBodyText(post.body)}</p>
                <p className="mt-4 text-sm text-muted-foreground">
                  {formatTime(post.created_at)}
                </p>
                <div className="flex items-center gap-6 py-4 mt-4 border-t border-b">
                  <span className="text-sm">
                    <strong>{post.reply_count || 0}</strong>{" "}
                    <span className="text-muted-foreground">Replies</span>
                  </span>
                  <span className="text-sm">
                    <strong>{post.like_count || 0}</strong>{" "}
                    <span className="text-muted-foreground">Likes</span>
                  </span>
                </div>
                <div className="flex items-center justify-around py-2">
                  <Button variant="ghost" size="icon">
                    <MessageCircle className="w-5 h-5" />
                  </Button>
                  <Button variant="ghost" size="icon">
                    <Repeat2 className="w-5 h-5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleLike}
                    className={post.liked ? "text-red-500" : ""}
                  >
                    <Heart className={`w-5 h-5 ${post.liked ? "fill-current" : ""}`} />
                  </Button>
                  <Button variant="ghost" size="icon">
                    <Share className="w-5 h-5" />
                  </Button>
                </div>
              </article>

              {/* Reply Box */}
              <ComposeBox
                replyTo={post.id}
                onPostCreated={loadPost}
                placeholder="Post your reply"
              />

              {/* Replies */}
              {replies.length > 0 && (
                <div>
                  {replies.map((reply) => (
                    <article key={reply.id} className="p-4 border-b">
                      <div className="flex gap-3">
                        <Avatar>
                          <AvatarFallback>
                            {getInitials(reply.author_profile?.name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <div className="flex items-center gap-1 text-sm">
                            <span className="font-bold">
                              {reply.author_profile?.name || "User"}
                            </span>
                            <span className="text-muted-foreground">
                              @{reply.author_handle || reply.author?.slice(4, 12)}
                            </span>
                          </div>
                          <p className="mt-1 whitespace-pre-wrap">
                            {postBodyText(reply.body)}
                          </p>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </main>

        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}

export default PostDetailPage;
