'use client';

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from './chat-message';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

interface ChatWindowProps {
  messages: Message[];
  isLoading?: boolean;
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center">
          <div className="text-5xl mb-4">🤖</div>
          <h2 className="text-2xl font-bold text-white mb-2">AI Copilot</h2>
          <p className="text-gray-400 max-w-sm">
            Ask questions about your models, predictions, drift analysis, model comparisons, or any MLOps insights.
          </p>
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              isLoading={message.isLoading}
            />
          ))}
          {isLoading && (
            <ChatMessage
              role="assistant"
              content=""
              isLoading={true}
            />
          )}
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
}
