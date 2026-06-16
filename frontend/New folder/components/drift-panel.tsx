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

export function DriftPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('fraud_detector_v2');

  const models = [
    'fraud_detector_v1',
    'fraud_detector_v2',
    'recommendation_model_v1',
    'churn_predictor_v3',
  ];

  const handleSend = async (message: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await copilot.explainDrift(selectedModel);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.explanation,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      let errorText = 'Failed to analyze drift';
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
      {/* Model Selection Panel */}
      <div className="border-b border-gray-700 p-4 bg-gray-900/50">
        <h3 className="text-white font-semibold mb-4">Select Model</h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {models.map((model) => (
            <button
              key={model}
              onClick={() => setSelectedModel(model)}
              className={cn(
                'p-3 rounded-lg text-left transition-all duration-200',
                selectedModel === model
                  ? 'bg-purple-600 text-white border-2 border-purple-400'
                  : 'bg-gray-800 text-gray-300 border-2 border-gray-700 hover:border-gray-600'
              )}
            >
              <div className="font-medium">{model}</div>
              <div className="text-xs opacity-75 mt-1">
                {model.includes('v1') && 'Older version'}
                {model.includes('v2') && 'Current version'}
                {model.includes('v3') && 'Latest version'}
              </div>
            </button>
          ))}
        </div>

        {/* Drift Metrics Preview */}
        <div className="mt-4 p-3 bg-gray-800 rounded border border-gray-700">
          <h4 className="text-sm text-gray-300 font-medium mb-2">Drift Metrics</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-400">Data Drift:</span>
              <span className="text-red-400 ml-2 font-medium">High</span>
            </div>
            <div>
              <span className="text-gray-400">Prediction Drift:</span>
              <span className="text-yellow-400 ml-2 font-medium">Medium</span>
            </div>
            <div>
              <span className="text-gray-400">Accuracy Change:</span>
              <span className="text-red-400 ml-2 font-medium">-3.2%</span>
            </div>
            <div>
              <span className="text-gray-400">Model Age:</span>
              <span className="text-gray-300 ml-2">45 days</span>
            </div>
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
          placeholder="Ask about drift analysis and recommendations..."
        />
      </div>
    </div>
  );
}
