'use client';

import React, { useState } from 'react';
import { InputBox } from './input-box';
import { ChatWindow } from './chat-window';
import { copilot, type CopilotModelComparison } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
}

interface ModelMetrics extends Omit<CopilotModelComparison, 'training_time'> {
  training_time_hours?: number;
}

const DEFAULT_MODELS: ModelMetrics[] = [
  {
    name: 'fraud_detector_v1',
    accuracy: 0.92,
    precision: 0.85,
    recall: 0.88,
    f1: 0.865,
    latency_ms: 45,
    training_time_hours: 2,
  },
  {
    name: 'fraud_detector_v2',
    accuracy: 0.94,
    precision: 0.89,
    recall: 0.91,
    f1: 0.90,
    latency_ms: 120,
    training_time_hours: 4,
  },
];

export function ComparisonPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState<ModelMetrics[]>(DEFAULT_MODELS);

  const handleSend = async (message: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await copilot.compareModels(models, message);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.comparison,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      let errorText = 'Failed to compare models';
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
      {/* Models Comparison Table */}
      <div className="border-b border-gray-700 p-4 bg-gray-900/50 overflow-x-auto">
        <h3 className="text-white font-semibold mb-4">Model Metrics</h3>
        
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 px-3 text-gray-400 font-medium">Model</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">Accuracy</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">Precision</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">Recall</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">F1-Score</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">Latency (ms)</th>
              <th className="text-center py-2 px-3 text-gray-400 font-medium">Train Time (h)</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model, idx) => (
              <tr
                key={model.name}
                className={cn(
                  'border-b border-gray-700 hover:bg-gray-800/50 transition-colors',
                  idx % 2 === 0 ? 'bg-gray-900/30' : 'bg-gray-800/20'
                )}
              >
                <td className="py-3 px-3 text-white font-medium">{model.name}</td>
                <td className="text-center py-3 px-3">
                  <span className={cn('font-medium', model.accuracy >= 0.93 ? 'text-green-400' : 'text-yellow-400')}>
                    {(model.accuracy * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="text-center py-3 px-3 text-gray-300">{(model.precision * 100).toFixed(1)}%</td>
                <td className="text-center py-3 px-3 text-gray-300">{(model.recall * 100).toFixed(1)}%</td>
                <td className="text-center py-3 px-3 text-gray-300">{(model.f1 * 100).toFixed(1)}%</td>
                <td className={cn('text-center py-3 px-3', model.latency_ms > 100 ? 'text-red-400' : 'text-green-400')}>
                  {model.latency_ms}
                </td>
                <td className="text-center py-3 px-3 text-gray-300">{model.training_time_hours}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Chat Area */}
      <ChatWindow messages={messages} isLoading={isLoading} />

      {/* Input */}
      <div className="border-t border-gray-700 p-4 bg-gray-900">
        <InputBox
          onSend={handleSend}
          isLoading={isLoading}
          placeholder="Compare models: accuracy vs speed, which to deploy, etc..."
        />
      </div>
    </div>
  );
}
