'use client';

import React, { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

interface InputBoxProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function InputBox({
  onSend,
  isLoading = false,
  placeholder = 'Ask about your models, predictions, or drift...',
}: InputBoxProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading}
        className={cn(
          'flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500',
          'focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500',
          'resize-none overflow-hidden',
          'transition-colors duration-200',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
        rows={1}
        style={{ maxHeight: '150px' }}
      />
      <button
        type="submit"
        disabled={isLoading || !input.trim()}
        className={cn(
          'bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 rounded-lg',
          'transition-colors duration-200',
          'flex items-center justify-center',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'h-12'
        )}
      >
        {isLoading ? (
          <div className="w-5 h-5 border-2 border-gray-300 border-t-white rounded-full animate-spin" />
        ) : (
          'Send'
        )}
      </button>
    </form>
  );
}
