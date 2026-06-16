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
}

const MODELS = [
  'fraud_detector_v1',
  'fraud_detector_v2',
  'recommendation_model_v1',
  'churn_predictor_v3',
];

const MOCK_METRICS: Record<string, { dataDrift: string; predDrift: string; accuracyChange: string; age: string; color: string }> = {
  'fraud_detector_v1':       { dataDrift: 'Low',    predDrift: 'Low',    accuracyChange: '-0.5%',  age: '120 days', color: 'green' },
  'fraud_detector_v2':       { dataDrift: 'High',   predDrift: 'Medium', accuracyChange: '-3.2%',  age: '45 days',  color: 'red' },
  'recommendation_model_v1': { dataDrift: 'Medium', predDrift: 'Low',    accuracyChange: '-1.1%',  age: '67 days',  color: 'yellow' },
  'churn_predictor_v3':      { dataDrift: 'Low',    predDrift: 'Low',    accuracyChange: '+0.3%',  age: '12 days',  color: 'green' },
};

const driftColor = (level: string) =>
  level === 'High' ? 'text-destructive' : level === 'Medium' ? 'text-amber-600' : 'text-green-600';

export function DriftPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState('fraud_detector_v2');

  const metrics = MOCK_METRICS[selectedModel];

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'user', content: message }]);
    setIsLoading(true);
    try {
      const res = await copilot.explainDrift(selectedModel);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: res.explanation },
      ]);
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to analyze drift';
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
      {/* Model selector + metrics */}
      <div className="border-b border-border bg-card px-6 py-4 flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs font-medium text-muted-foreground mb-2">Select Model</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {MODELS.map((m) => (
              <button
                key={m}
                onClick={() => setSelectedModel(m)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium border transition-colors',
                  selectedModel === m
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-secondary text-foreground border-border hover:bg-secondary/80'
                )}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Metrics row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Data Drift',      value: metrics.dataDrift,       colorFn: driftColor(metrics.dataDrift) },
              { label: 'Prediction Drift',value: metrics.predDrift,       colorFn: driftColor(metrics.predDrift) },
              { label: 'Accuracy Change', value: metrics.accuracyChange,  colorFn: metrics.accuracyChange.startsWith('+') ? 'text-green-600' : 'text-destructive' },
              { label: 'Model Age',       value: metrics.age,             colorFn: 'text-foreground' },
            ].map(({ label, value, colorFn }) => (
              <div key={label} className="bg-secondary/40 rounded-lg px-3 py-2.5 border border-border">
                <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
                <p className={cn('text-sm font-semibold', colorFn)}>{value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        emptyTitle="Drift Analysis"
        emptyDescription="Select a model above and ask the AI to explain its drift patterns and recommended actions."
      />

      <div className="border-t border-border px-6 py-4 bg-card flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <InputBox onSend={handleSend} isLoading={isLoading} placeholder="Ask about drift analysis and recommendations…" />
        </div>
      </div>
    </div>
  );
}