'use client';

import React, { useState } from 'react';
import { InputBox } from './input-box';
import { ChatWindow } from './chat-window';
import { copilot } from '@/lib/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'user', content: message }]);
    setIsLoading(true);

    try {
      const res = await copilot.chat(message, false);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: res.response },
      ]);
    } catch (err) {
      const text =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'detail' in err
          ? String((err as Record<string, unknown>).detail)
          : 'Failed to get response';
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: `Error: ${text}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ChatWindow messages={messages} isLoading={isLoading} />
      <div className="border-t border-border px-6 py-4 bg-card flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <InputBox onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}