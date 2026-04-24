import { Link } from "react-router-dom";
import { Heart, MessageCircle, Repeat2, Share } from "lucide-react";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { Button } from "./ui/button";
import { apiCall, getStoredToken } from "../lib/mesh";

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

interface PostCardProps {
  post: Post;
  onLike?: () => void;
}

export function PostCard({ post, onLike }: PostCardProps) {
  const initials = post.author_profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    
    if (hours < 1) return `${Math.floor(diff / (1000 * 60))}m`;
    if (hours < 24) return `${hours}h`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  const handleLike = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    const token = getStoredToken();
    if (!token) return;
    
    try {
      if (post.liked) {
        await apiCall(`/api/content/${post.id}/unlike`, { method: "POST" });
      } else {
        await apiCall(`/api/content/${post.id}/like`, { method: "POST" });
      }
      onLike?.();
    } catch (err) {
      console.error("Failed to like:", err);
    }
  };

  return (
    <Link to={`/post/${post.id}`} className="block">
      <article className="p-4 border-b hover:bg-muted/30 transition cursor-pointer">
        <div className="flex gap-3">
          <Avatar>
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1 text-sm">
              <span className="font-bold truncate">
                {post.author_profile?.name || "User"}
              </span>
              <span className="text-muted-foreground truncate">
                @{post.author_handle || post.author?.slice(4, 12)}
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">
                {formatTime(post.created_at)}
              </span>
            </div>
            <p className="mt-1 whitespace-pre-wrap break-words">
              {post.body?.text}
            </p>
            <div className="flex items-center gap-6 mt-3 -ml-2">
              <Button 
                variant="ghost" 
                size="sm" 
                className="text-muted-foreground hover:text-primary gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <MessageCircle className="w-4 h-4" />
                <span className="text-xs">{post.reply_count || ""}</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="text-muted-foreground hover:text-green-500 gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <Repeat2 className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className={`gap-1 ${post.liked ? "text-red-500" : "text-muted-foreground hover:text-red-500"}`}
                onClick={handleLike}
              >
                <Heart className={`w-4 h-4 ${post.liked ? "fill-current" : ""}`} />
                <span className="text-xs">{post.like_count || ""}</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                className="text-muted-foreground hover:text-primary"
                onClick={(e) => e.stopPropagation()}
              >
                <Share className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
}
