"use client";

import { useState } from "react";
import Link from "next/link";
import { Heart, MessageCircle, Share2, MoreHorizontal } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { type Post } from "@/lib/mesh";

interface PostCardProps {
  post: Post;
  onLike?: () => void;
  showThread?: boolean;
}

export function PostCard({ post, onLike, showThread = false }: PostCardProps) {
  const initials = post.author_profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const timeAgo = formatTimeAgo(new Date(post.created_at));

  return (
    <article className="border-b hover:bg-muted/50 transition-colors">
      <div className="p-4">
        <div className="flex gap-3">
          {/* Avatar */}
          <Link href={`/profile/${post.author_handle || post.author}`}>
            <Avatar className="w-10 h-10">
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
          </Link>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-center gap-2 text-sm">
              <Link 
                href={`/profile/${post.author_handle || post.author}`}
                className="font-semibold hover:underline truncate"
              >
                {post.author_profile?.name || "Anonymous"}
              </Link>
              <span className="text-muted-foreground">
                @{post.author_handle || post.author.slice(4, 12)}
              </span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{timeAgo}</span>
            </div>

            {/* Reply indicator */}
            {post.reply_to && (
              <p className="text-sm text-muted-foreground mt-1">
                Replying to a post
              </p>
            )}

            {/* Text */}
            <Link href={`/post/${post.id}`}>
              <p className="mt-1 whitespace-pre-wrap break-words">
                {post.body?.text}
              </p>
            </Link>

            {/* Media */}
            {post.body?.media && post.body.media.length > 0 && (
              <div className="mt-3 rounded-xl overflow-hidden border">
                {post.body.media.map((media, idx) => (
                  <img
                    key={idx}
                    src={media.url}
                    alt=""
                    className="w-full max-h-96 object-cover"
                  />
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-6 mt-3 -ml-2">
              <Link href={`/post/${post.id}`}>
                <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-primary">
                  <MessageCircle className="w-4 h-4" />
                  <span className="text-sm">{post.reply_count || 0}</span>
                </Button>
              </Link>

              <Button 
                variant="ghost" 
                size="sm" 
                className={`gap-2 ${post.liked_by_me ? "text-red-500" : "text-muted-foreground hover:text-red-500"}`}
                onClick={onLike}
              >
                <Heart className={`w-4 h-4 ${post.liked_by_me ? "fill-current" : ""}`} />
                <span className="text-sm">{post.like_count || 0}</span>
              </Button>

              <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-primary">
                <Share2 className="w-4 h-4" />
              </Button>

              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-primary ml-auto">
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
  
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d`;
  
  return date.toLocaleDateString();
}
