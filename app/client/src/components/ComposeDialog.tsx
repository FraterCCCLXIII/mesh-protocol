import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "./ui/button";
import { createPost, getStoredUser } from "../lib/mesh";

interface ComposeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ComposeDialog({ open, onOpenChange }: ComposeDialogProps) {
  const [text, setText] = useState("");
  const [posting, setPosting] = useState(false);
  const user = getStoredUser();

  if (!open) return null;

  const handleSubmit = async () => {
    if (!text.trim() || posting) return;
    
    setPosting(true);
    try {
      await createPost(text);
      setText("");
      onOpenChange(false);
      window.location.reload();
    } catch (err) {
      console.error("Failed to post:", err);
    } finally {
      setPosting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center pt-20 z-50">
      <div className="bg-background rounded-xl w-full max-w-xl shadow-xl">
        <div className="flex items-center justify-between p-4 border-b">
          <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)}>
            <X className="w-5 h-5" />
          </Button>
          <Button 
            onClick={handleSubmit}
            disabled={!text.trim() || posting}
            className="rounded-full"
          >
            {posting ? "Posting..." : "Post"}
          </Button>
        </div>
        <div className="p-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What's happening?"
            className="w-full resize-none border-0 focus:ring-0 focus:outline-none text-xl placeholder:text-muted-foreground bg-transparent min-h-[150px]"
            maxLength={280}
            autoFocus
          />
          <div className="flex justify-end pt-3 border-t">
            <span className={`text-sm ${text.length > 260 ? "text-red-500" : "text-muted-foreground"}`}>
              {text.length}/280
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
