import { useState } from "react";
import { Image, Smile, Globe, Users, Lock } from "lucide-react";
import { Button } from "./ui/button";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { getStoredUser, createPost } from "../lib/mesh";

type PostAccess = "public" | "friends" | "private";

interface ComposeBoxProps {
  replyTo?: string;
  onPostCreated?: () => void;
  placeholder?: string;
}

export function ComposeBox({ replyTo, onPostCreated, placeholder = "What's happening?" }: ComposeBoxProps) {
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const [access, setAccess] = useState<PostAccess>("public");
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
      await createPost(text, replyTo, access);
      setText("");
      setAccess("public");
      onPostCreated?.();
    } catch (err) {
      console.error("Failed to post:", err);
    } finally {
      setPosting(false);
    }
  };

  const accessOptions: { value: PostAccess; label: string; icon: typeof Globe }[] = [
    { value: "public", label: "Public", icon: Globe },
    { value: "friends", label: "Friends Only", icon: Users },
    { value: "private", label: "Only Me", icon: Lock },
  ];

  const selectedAccess = accessOptions.find(o => o.value === access)!;
  const AccessIcon = selectedAccess.icon;

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
            <div className="flex gap-2 items-center">
              <Button variant="ghost" size="icon" className="text-primary" disabled>
                <Image className="w-5 h-5" />
              </Button>
              <Button variant="ghost" size="icon" className="text-primary" disabled>
                <Smile className="w-5 h-5" />
              </Button>
              
              {/* Privacy Selector */}
              <div className="relative group">
                <button 
                  className="flex items-center gap-1 px-2 py-1 rounded text-sm text-primary hover:bg-primary/10 transition"
                >
                  <AccessIcon className="w-4 h-4" />
                  <span className="hidden sm:inline">{selectedAccess.label}</span>
                </button>
                <div className="absolute left-0 top-full mt-1 bg-background border rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10 min-w-[140px]">
                  {accessOptions.map(option => {
                    const Icon = option.icon;
                    return (
                      <button
                        key={option.value}
                        onClick={() => setAccess(option.value)}
                        className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition first:rounded-t-lg last:rounded-b-lg ${
                          access === option.value ? 'bg-primary/10 text-primary' : ''
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm ${text.length > 260 ? "text-destructive" : "text-muted-foreground"}`}>
                {text.length}/280
              </span>
              <Button
                variant="invert"
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
