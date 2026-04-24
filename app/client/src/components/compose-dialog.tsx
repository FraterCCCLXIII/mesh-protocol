"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ComposeBox } from "@/components/compose-box";

interface ComposeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  replyTo?: string;
}

export function ComposeDialog({ open, onOpenChange, replyTo }: ComposeDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    };

    if (open) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50"
        onClick={() => onOpenChange(false)}
      />

      {/* Dialog */}
      <div 
        ref={dialogRef}
        className="fixed left-1/2 top-20 -translate-x-1/2 w-full max-w-xl bg-background rounded-xl shadow-lg"
      >
        <div className="flex items-center justify-between p-4 border-b">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => onOpenChange(false)}
          >
            <X className="w-5 h-5" />
          </Button>
        </div>

        <ComposeBox 
          replyTo={replyTo}
          onPostCreated={() => onOpenChange(false)}
          placeholder={replyTo ? "Post your reply" : "What's happening?"}
        />
      </div>
    </div>
  );
}
