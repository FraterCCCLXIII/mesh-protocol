"use client";

import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getStoredUser, createPost } from "@/lib/mesh";
import { ImagePlus, Smile } from "lucide-react";

interface ComposeBoxProps {
  onPostCreated?: () => void;
  replyTo?: string;
  placeholder?: string;
}

export function ComposeBox({ 
  onPostCreated, 
  replyTo,
  placeholder = "What's happening?"
}: ComposeBoxProps) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const user = getStoredUser();

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const handleSubmit = async () => {
    if (!text.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      await createPost(text, replyTo);
      setText("");
      onPostCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create post");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const charCount = text.length;
  const maxChars = 280;
  const isOverLimit = charCount > maxChars;

  return (
    <div className="p-4">
      <div className="flex gap-3">
        <Avatar className="w-10 h-10">
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>

        <div className="flex-1">
          <Textarea
            placeholder={placeholder}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[80px] border-0 resize-none focus-visible:ring-0 p-0 text-lg"
          />

          {error && (
            <p className="text-sm text-red-600 mt-2">{error}</p>
          )}

          <div className="flex items-center justify-between pt-3 border-t mt-3">
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" className="text-muted-foreground">
                <ImagePlus className="w-5 h-5" />
              </Button>
              <Button variant="ghost" size="icon" className="text-muted-foreground">
                <Smile className="w-5 h-5" />
              </Button>
            </div>

            <div className="flex items-center gap-3">
              <span className={`text-sm ${isOverLimit ? "text-red-600" : "text-muted-foreground"}`}>
                {charCount}/{maxChars}
              </span>
              <Button 
                onClick={handleSubmit}
                disabled={!text.trim() || loading || isOverLimit}
                className="rounded-full"
              >
                {loading ? "Posting..." : "Post"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
