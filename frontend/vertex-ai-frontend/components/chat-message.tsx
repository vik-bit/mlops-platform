import React from 'react';
import { cn } from '@/lib/utils';
import { User, Sparkles } from 'lucide-react';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

export function ChatMessage({ role, content, isLoading }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <div
      className={cn(
        'flex gap-3 max-w-3xl',
        isUser ? 'flex-row-reverse ml-auto' : 'flex-row mr-auto'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
          isUser ? 'bg-primary' : 'bg-secondary border border-border'
        )}
      >
        {isUser
          ? <User className="w-3.5 h-3.5 text-primary-foreground" />
          : <Sparkles className="w-3.5 h-3.5 text-primary" />
        }
      </div>

      {/* Bubble */}
      <div
        className={cn(
          'px-4 py-2.5 rounded-xl text-sm leading-relaxed max-w-[calc(100%-2.5rem)] whitespace-pre-wrap break-words',
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : 'bg-secondary text-foreground border border-border rounded-tl-sm'
        )}
      >
        {isLoading ? (
          <div className="flex gap-1 items-center h-5">
            {[0, 150, 300].map((delay) => (
              <div
                key={delay}
                className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce"
                style={{ animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
        ) : (
          content
        )}
      </div>
    </div>
  );
}