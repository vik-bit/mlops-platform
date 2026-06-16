'use client';

import React, { useState } from 'react';
import { InputBox } from './input-box';
import { ChatWindow } from './chat-window';
import { copilot } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface ShapValues {
  base_value: number;
  values: Record<string, number>;
  features?: Record<string, string>;
}

const DEFAULT_SHAP: ShapValues = {
  base_value: 0.5,
  values: { feature_1: 0.2, feature_2: -0.1, feature_3: 0.15 },
  features: { feature_1: 'Age', feature_2: 'Income', feature_3: 'Credit Score' },
};

export function SHAPPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [modelName, setModelName] = useState('fraud_detector_v2');
  const [shapValues, setShapValues] = useState<ShapValues>(DEFAULT_SHAP);
  const [jsonText, setJsonText] = useState(JSON.stringify(DEFAULT_SHAP.values, null, 2));
  const [jsonError, setJsonError] = useState(false);
  const [configOpen, setConfigOpen] = useState(true);

  const handleSend = async (message: string) => {
    setMessages((prev) => [...prev, { id: Date.now().toString(), role: 'user', content: message }]);
    setIsLoading(true);
    try {
      const res = await copilot.explainSHAP(shapValues, modelName);
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: res.explanation },
      ]);
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to explain SHAP values';
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: 'assistant', content: `Error: ${text}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleJsonChange = (val: string) => {
    setJsonText(val);
    try {
      const parsed = JSON.parse(val);
      setShapValues((prev) => ({ ...prev, values: parsed }));
      setJsonError(false);
    } catch {
      setJsonError(true);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Collapsible config */}
      <div className="border-b border-border bg-card flex-shrink-0">
        <button
          onClick={() => setConfigOpen((v) => !v)}
          className="w-full flex items-center justify-between px-6 py-3 text-sm font-medium text-foreground hover:bg-secondary/50 transition-colors"
        >
          <span>Configuration</span>
          {configOpen ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </button>

        {configOpen && (
          <div className="px-6 pb-5 grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl">
            {/* Model name */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Model Name</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="e.g. fraud_detector_v2"
              />
            </div>

            {/* Base value */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">Base Value</label>
              <input
                type="number"
                step="0.01"
                value={shapValues.base_value}
                onChange={(e) =>
                  setShapValues((prev) => ({ ...prev, base_value: parseFloat(e.target.value) || 0 }))
                }
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Feature values JSON */}
            <div>
              <label className={cn('block text-xs font-medium mb-1.5', jsonError ? 'text-destructive' : 'text-muted-foreground')}>
                SHAP Values (JSON){jsonError && ' — invalid JSON'}
              </label>
              <textarea
                value={jsonText}
                onChange={(e) => handleJsonChange(e.target.value)}
                rows={3}
                className={cn(
                  'w-full rounded-md border bg-background px-3 py-2 text-xs font-mono text-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring',
                  jsonError ? 'border-destructive' : 'border-input'
                )}
              />
            </div>
          </div>
        )}
      </div>

      {/* SHAP bar preview */}
      {Object.keys(shapValues.values).length > 0 && (
        <div className="border-b border-border bg-secondary/30 px-6 py-3 flex-shrink-0">
          <div className="max-w-3xl mx-auto space-y-1.5">
            {Object.entries(shapValues.values)
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .map(([key, val]) => {
                const max = Math.max(...Object.values(shapValues.values).map(Math.abs));
                const pct = max > 0 ? (Math.abs(val) / max) * 100 : 0;
                const positive = val >= 0;
                return (
                  <div key={key} className="flex items-center gap-3 text-xs">
                    <span className="w-24 text-right text-muted-foreground truncate shrink-0">
                      {shapValues.features?.[key] ?? key}
                    </span>
                    <div className="flex-1 h-4 bg-secondary rounded-sm overflow-hidden">
                      <div
                        className={cn('h-full rounded-sm transition-all', positive ? 'bg-primary/70' : 'bg-destructive/60')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className={cn('w-12 font-mono shrink-0', positive ? 'text-primary' : 'text-destructive')}>
                      {val > 0 ? '+' : ''}{val.toFixed(3)}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        emptyTitle="SHAP Explainer"
        emptyDescription="Configure your SHAP values above, then ask the AI to explain what drives this prediction."
      />

      <div className="border-t border-border px-6 py-4 bg-card flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <InputBox onSend={handleSend} isLoading={isLoading} placeholder="Ask about these SHAP values…" />
        </div>
      </div>
    </div>
  );
}