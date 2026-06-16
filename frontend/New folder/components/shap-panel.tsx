'use client';

import React, { useState } from 'react';
import { InputBox } from './input-box';
import { ChatWindow } from './chat-window';
import { copilot } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

export function SHAPPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [modelName, setModelName] = useState('fraud_detector_v2');
  const [shapValues, setShapValues] = useState({
    base_value: 0.5,
    values: { feature_1: 0.2, feature_2: -0.1, feature_3: 0.15 },
    features: { feature_1: 'Age', feature_2: 'Income', feature_3: 'Credit' },
  });

  const handleSend = async (message: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await copilot.explainSHAP(shapValues, modelName);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.explanation,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      let errorText = 'Failed to explain SHAP values';
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
    <div className="flex flex-col h-full max-w-6xl mx-auto">
      {/* Configuration Panel */}
      <div className="border-b border-gray-700 p-4 bg-gray-900/50">
        <h3 className="text-white font-semibold mb-4">Configuration</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-2">Model Name</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className={cn(
                'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white',
                'focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
              )}
              placeholder="e.g., fraud_detector_v2"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-2">Base Value</label>
            <input
              type="number"
              step="0.01"
              value={shapValues.base_value}
              onChange={(e) =>
                setShapValues((prev) => ({
                  ...prev,
                  base_value: parseFloat(e.target.value),
                }))
              }
              className={cn(
                'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white',
                'focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
              )}
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-2">Features (JSON)</label>
            <textarea
              value={JSON.stringify(shapValues.values, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setShapValues((prev) => ({
                    ...prev,
                    values: parsed,
                  }));
                } catch {
                  // Keep current value if JSON is invalid
                }
              }}
              className={cn(
                'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white',
                'focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500',
                'font-mono text-sm resize-none'
              )}
              rows={4}
            />
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <ChatWindow messages={messages} isLoading={isLoading} />

      {/* Input */}
      <div className="border-t border-gray-700 p-4 bg-gray-900">
        <InputBox
          onSend={handleSend}
          isLoading={isLoading}
          placeholder="Ask about these SHAP values..."
        />
      </div>
    </div>
  );
}
