'use client';

import React, { useState, useEffect } from 'react';
import { ToolTabs, type ToolType } from '@/components/tool-tabs';
import { ChatPanel } from '@/components/chat-panel';
import { SHAPPanel } from '@/components/shap-panel';
import { DriftPanel } from '@/components/drift-panel';
import { ComparisonPanel } from '@/components/comparison-panel';
import { copilot } from '@/lib/api';
import { Sparkles, Wifi, WifiOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function CopilotPage() {
  const [activeTool, setActiveTool] = useState<ToolType>('chat');
  const [health, setHealth] = useState<{ status: string; llm_model: string } | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    copilot
      .health()
      .then((h) => setHealth(h))
      .catch(() => setHealthError(true));
  }, []);

  const renderPanel = () => {
    switch (activeTool) {
      case 'chat':       return <ChatPanel />;
      case 'shap':       return <SHAPPanel />;
      case 'drift':      return <DriftPanel />;
      case 'comparison': return <ComparisonPanel />;
      default:           return <ChatPanel />;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="border-b border-border bg-card px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-foreground">AI Copilot</h1>
            <p className="text-xs text-muted-foreground">MLOps Intelligence Assistant</p>
          </div>
        </div>

        {/* Health badge */}
        <div
          className={cn(
            'flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium',
            healthError
              ? 'border-destructive/30 bg-destructive/10 text-destructive'
              : health
              ? 'border-green-300 bg-green-50 text-green-700'
              : 'border-border bg-secondary text-muted-foreground'
          )}
        >
          {healthError ? (
            <>
              <WifiOff className="w-3 h-3" />
              Disconnected
            </>
          ) : health ? (
            <>
              <Wifi className="w-3 h-3" />
              {health.llm_model}
            </>
          ) : (
            <span className="animate-pulse">Connecting…</span>
          )}
        </div>
      </div>

      {/* Tool Tabs */}
      <ToolTabs activeTool={activeTool} onToolChange={setActiveTool} />

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        {renderPanel()}
      </div>
    </div>
  );
}