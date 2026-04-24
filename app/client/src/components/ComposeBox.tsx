import { useState } from "react";
import { Image, Smile } from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { getStoredUser, createPost } from "../lib/mesh";

interface ComposeBoxProps {
  replyTo?: string;
  onPostCreated?: () => void;
  placeholder?: string;
}

export function ComposeBox({ replyTo, onPostCreated, placeholder = "What's happening?" }: ComposeBoxProps) {
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const user = getStoredUser();

  const initials = user?.profile?.name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  const handleSubmit = async () => {
    if (!text.trim() || posting) return;
    
    setPosting(true);
    try {
      await createPost(text, replyTo);
      setText("");
      onPostCreated?.();
    } catch (err) {
      console.error("Failed to post:", err);
    } finally {
      setPosting(false);
    }
  };

  if (!user) return null;

  return (
    <div className="p-4 border-b">
      <div className="flex gap-3">
        <Avatar>
          <AvatarFallback>{initials}</AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder}
            className="w-full resize-none border-0 focus:ring-0 focus:outline-none text-lg placeholder:text-muted-foreground bg-transparent min-h-[80px]"
            maxLength={280}
          />
          <div className="flex items-center justify-between pt-3 border-t">
            <div className="flex gap-2">
              <Button variant="ghost" size="icon" className="text-primary" disabled>
                <Image className="w-5 h-5" />
              </Button>
              <Button variant="ghost" size="icon" className="text-primary" disabled>
                <Smile className="w-5 h-5" />
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm ${text.length > 260 ? "text-destructive" : "text-muted-foreground"}`}>
                {text.length}/280
              </span>
              <Button 
                onClick={handleSubmit}
                disabled={!text.trim() || posting || text.length > 280}
                className="rounded-full px-4"
              >
                {posting ? "Posting..." : "Post"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
