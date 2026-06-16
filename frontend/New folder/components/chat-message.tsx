import React from 'react';
import { cn } from '@/lib/utils';

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
        'flex gap-3 pb-4 max-w-3xl',
        isUser ? 'flex-row-reverse ml-auto' : 'flex-row mr-auto'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white text-sm font-semibold',
          isUser ? 'bg-blue-600' : 'bg-purple-600'
        )}
      >
        {isUser ? 'U' : 'AI'}
      </div>

      {/* Message Bubble */}
      <div
        className={cn(
          'px-4 py-2 rounded-lg max-w-2xl whitespace-pre-wrap break-words',
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-100 border border-gray-700'
        )}
      >
        {isLoading ? (
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        ) : (
          content
        )}
      </div>
    </div>
  );
}
