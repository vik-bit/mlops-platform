"use client";

import { Send } from "lucide-react";
import { useRef, useEffect } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isDisabled: boolean;
  placeholder?: string;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  isDisabled,
  placeholder = "Ask me anything...",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        120
      ) + "px";
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="flex gap-3 rounded-lg border border-border bg-card p-3">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        rows={1}
        className="flex-1 resize-none bg-transparent text-sm focus:outline-none disabled:opacity-50"
      />
      <button
        onClick={onSubmit}
        disabled={isDisabled || !value.trim()}
        className="mt-1 flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        <Send size={18} />
      </button>
    </div>
  );
}