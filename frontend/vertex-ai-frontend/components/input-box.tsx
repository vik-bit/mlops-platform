'use client';

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { SendHorizonal, Loader2 } from 'lucide-react';

interface InputBoxProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function InputBox({
  onSend,
  isLoading = false,
  placeholder = 'Ask about your models, predictions, or drift…',
}: InputBoxProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 140) + 'px';
  }, [input]);

  const submit = () => {
    const msg = input.trim();
    if (!msg || isLoading) return;
    onSend(msg);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading}
        rows={1}
        className={cn(
          'flex-1 resize-none overflow-hidden rounded-lg border border-input bg-background px-4 py-2.5',
          'text-sm text-foreground placeholder:text-muted-foreground',
          'focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent',
          'transition-shadow duration-150',
          isLoading && 'opacity-60 cursor-not-allowed'
        )}
        style={{ maxHeight: 140 }}
      />
      <button
        onClick={submit}
        disabled={isLoading || !input.trim()}
        className={cn(
          'h-10 w-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center flex-shrink-0',
          'hover:bg-primary/90 transition-colors duration-150',
          'disabled:opacity-40 disabled:cursor-not-allowed'
        )}
      >
        {isLoading
          ? <Loader2 className="w-4 h-4 animate-spin" />
          : <SendHorizonal className="w-4 h-4" />
        }
      </button>
    </div>
  );
}