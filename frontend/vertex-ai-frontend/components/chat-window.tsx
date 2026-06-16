'use client';

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from './chat-message';
import { Sparkles } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

interface ChatWindowProps {
  messages: Message[];
  isLoading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}

export function ChatWindow({
  messages,
  isLoading,
  emptyTitle = 'AI Copilot',
  emptyDescription = 'Ask questions about your models, predictions, drift analysis, or any MLOps insights.',
}: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center gap-3 py-16">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground mb-1">{emptyTitle}</h2>
            <p className="text-sm text-muted-foreground max-w-xs">{emptyDescription}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4 max-w-3xl mx-auto">
          {messages.map((m) => (
            <ChatMessage key={m.id} role={m.role} content={m.content} isLoading={m.isLoading} />
          ))}
          {isLoading && <ChatMessage role="assistant" content="" isLoading />}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}