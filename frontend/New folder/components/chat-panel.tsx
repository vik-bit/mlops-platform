'use client';

import React, { useState } from 'react';
import { InputBox } from './input-box';
import { ChatWindow } from './chat-window';
import { copilot } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (message: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await copilot.chat(message, false);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      let errorText = 'Failed to get response';
      if (error instanceof Error) {
        errorText = error.message;
      } else if (typeof error === 'object' && error !== null && 'detail' in error) {
        const detail = (error as Record<string, unknown>).detail;
        errorText = typeof detail === 'string' ? detail : JSON.stringify(detail);
      }
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${errorText}`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ChatWindow messages={messages} isLoading={isLoading} />
      <div className="border-t border-gray-700 p-4 bg-gray-900">
        <InputBox onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}
