"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Heart, MessageCircle, Share2, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Sidebar } from "@/components/sidebar";
import { ComposeBox } from "@/components/compose-box";
import { PostCard } from "@/components/post-card";
import { getPost, getPosts, like, unlike, type Post } from "@/lib/mesh";

export default function PostDetailPage() {
  const params = useParams();
  const postId = params.id as string;
  
  const [post, setPost] = useState<Post | null>(null);
  const [replies, setReplies] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPost = useCallback(async () => {
    if (!postId) return;
    
    setLoading(true);
    setError("");
    
    try {
      const [postData, repliesData] = await Promise.all([
        getPost(postId),
        getPosts({ reply_to: postId }),
      ]);
      setPost(postData);
      setReplies(repliesData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load post");
    } finally {
      setLoading(false);
    }
  }, [postId]);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  const handleLike = async () => {
    if (!post) return;
    try {
      if (post.liked_by_me) {
        await unlike(post.id);
      } else {
        await like(post.id);
      }
      setPost({
        ...post,
        liked_by_me: !post.liked_by_me,
        like_count: post.liked_by_me ? post.like_count - 1 : post.like_count + 1,
      });
    } catch (err) {
      console.error("Failed to like/unlike:", err);
    }
  };

  const handleReplyLike = async (replyId: string, liked: boolean) => {
    try {
      if (liked) {
        await unlike(replyId);
      } else {
        await like(replyId);
      }
      setReplies(replies.map(r => 
        r.id === replyId 
          ? { 
              ...r, 
              liked_by_me: !liked,
              like_count: liked ? r.like_count - 1 : r.like_count + 1
            }
          : r
      ));
    } catch (err) {
      console.error("Failed to like/unlike:", err);
    }
  };

  const initials = post?.author_profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto flex">
        <Sidebar />
        <main className="flex-1 border-x border-border min-h-screen">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="flex items-center gap-4 p-4">
              <Link href="/">
                <Button variant="ghost" size="icon">
                  <ArrowLeft className="w-5 h-5" />
                </Button>
              </Link>
              <h1 className="text-xl font-bold">Post</h1>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading...
            </div>
          ) : error ? (
            <div className="p-8 text-center text-red-600">
              {error}
            </div>
          ) : post ? (
            <>
              {/* Main Post */}
              <article className="p-4 border-b">
                <div className="flex gap-3">
                  <Link href={`/profile/${post.author_handle || post.author}`}>
                    <Avatar className="w-12 h-12">
                      <AvatarFallback>{initials}</AvatarFallback>
                    </Avatar>
                  </Link>
                  <div className="flex-1">
                    <Link 
                      href={`/profile/${post.author_handle || post.author}`}
                      className="font-bold hover:underline"
                    >
                      {post.author_profile?.name || "Anonymous"}
                    </Link>
                    <p className="text-muted-foreground">
                      @{post.author_handle || post.author.slice(4, 12)}
                    </p>
                  </div>
                  <Button variant="ghost" size="icon">
                    <MoreHorizontal className="w-5 h-5" />
                  </Button>
                </div>

                {/* Post Content */}
                <div className="mt-4">
                  <p className="text-xl whitespace-pre-wrap break-words">
                    {post.body?.text}
                  </p>
                  
                  {/* Media */}
                  {post.body?.media && post.body.media.length > 0 && (
                    <div className="mt-4 rounded-xl overflow-hidden border">
                      {post.body.media.map((media, idx) => (
                        <img
                          key={idx}
                          src={media.url}
                          alt=""
                          className="w-full max-h-[500px] object-cover"
                        />
                      ))}
                    </div>
                  )}
                </div>

                {/* Timestamp */}
                <div className="mt-4 text-muted-foreground">
                  {formatDate(post.created_at)}
                </div>

                {/* Stats */}
                <div className="flex gap-4 py-4 border-y mt-4 text-sm">
                  <span>
                    <strong>{post.reply_count || 0}</strong>{" "}
                    <span className="text-muted-foreground">Replies</span>
                  </span>
                  <span>
                    <strong>{post.like_count || 0}</strong>{" "}
                    <span className="text-muted-foreground">Likes</span>
                  </span>
                </div>

                {/* Actions */}
                <div className="flex justify-around py-2 border-b">
                  <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
                    <MessageCircle className="w-5 h-5" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className={`gap-2 ${post.liked_by_me ? "text-red-500" : "text-muted-foreground hover:text-red-500"}`}
                    onClick={handleLike}
                  >
                    <Heart className={`w-5 h-5 ${post.liked_by_me ? "fill-current" : ""}`} />
                  </Button>
                  <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
                    <Share2 className="w-5 h-5" />
                  </Button>
                </div>
              </article>

              {/* Reply Box */}
              <div className="border-b">
                <ComposeBox 
                  replyTo={post.id}
                  onPostCreated={loadPost}
                  placeholder="Post your reply"
                />
              </div>

              {/* Replies */}
              <div>
                {replies.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    No replies yet. Be the first to reply!
                  </div>
                ) : (
                  replies.map((reply) => (
                    <PostCard 
                      key={reply.id} 
                      post={reply}
                      onLike={() => handleReplyLike(reply.id, reply.liked_by_me || false)}
                    />
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              Post not found
            </div>
          )}
        </main>
        <aside className="w-80 p-4 hidden lg:block" />
      </div>
    </div>
  );
}
