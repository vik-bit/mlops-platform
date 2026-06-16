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
}

interface ModelMetrics extends Omit<CopilotModelComparison, 'training_time'> {
  training_time_hours?: number;
}

const DEFAULT_MODELS: ModelMetrics[] = [
  { name: 'fraud_detector_v1', accuracy: 0.92, precision: 0.85, recall: 0.88, f1: 0.865, latency_ms: 45,  training_time_hours: 2 },
  { name: 'fraud_detector_v2', accuracy: 0.94, precision: 0.89, recall: 0.91, f1: 0.90,  latency_ms: 120, training_time_hours: 4 },
];

const pct = (v?: number) => (v !== undefined ? `${(v * 100).toFixed(1)}%` : '—');

export function ComparisonPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [models] = useState<ModelMetrics[]>(DEFAULT_MODELS);

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'user', content: message }]);
    setIsLoading(true);
    try {
      const res = await copilot.compareModels(models, message);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: res.comparison },
      ]);
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to compare models';
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: `Error: ${text}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Find best value per column for highlighting
  const bestAccuracy = Math.max(...models.map((m) => m.accuracy ?? 0));
  const bestLatency  = Math.min(...models.map((m) => m.latency_ms ?? Infinity));

  return (
    <div className="flex flex-col h-full">
      {/* Metrics table */}
      <div className="border-b border-border bg-card px-6 py-4 flex-shrink-0 overflow-x-auto">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-medium text-muted-foreground mb-3">Model Metrics</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Model', 'Accuracy', 'Precision', 'Recall', 'F1', 'Latency (ms)', 'Train (h)'].map((h) => (
                  <th
                    key={h}
                    className={cn(
                      'py-2 font-medium text-muted-foreground',
                      h === 'Model' ? 'text-left pr-4' : 'text-center px-3'
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.name} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                  <td className="py-2.5 pr-4 font-medium text-foreground">{m.name}</td>
                  <td className="text-center px-3">
                    <span className={cn('font-semibold', m.accuracy === bestAccuracy ? 'text-primary' : 'text-foreground')}>
                      {pct(m.accuracy)}
                    </span>
                  </td>
                  <td className="text-center px-3 text-muted-foreground">{pct(m.precision)}</td>
                  <td className="text-center px-3 text-muted-foreground">{pct(m.recall)}</td>
                  <td className="text-center px-3 text-muted-foreground">{pct(m.f1)}</td>
                  <td className="text-center px-3">
                    <span className={cn('font-medium', m.latency_ms === bestLatency ? 'text-green-600' : m.latency_ms! > 100 ? 'text-destructive' : 'text-foreground')}>
                      {m.latency_ms ?? '—'}
                    </span>
                  </td>
                  <td className="text-center px-3 text-muted-foreground">{m.training_time_hours ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        emptyTitle="Model Comparison"
        emptyDescription="Ask the AI to compare these models — accuracy vs speed, which to deploy, trade-offs, and more."
      />

      <div className="border-t border-border px-6 py-4 bg-card flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <InputBox onSend={handleSend} isLoading={isLoading} placeholder="Compare models: accuracy vs speed, which to deploy…" />
        </div>
      </div>
    </div>
  );
}