'use client';

import React, { useState } from 'react';
import { ToolTabs, type ToolType } from '@/components/tool-tabs';
import { ChatPanel } from '@/components/chat-panel';
import { SHAPPanel } from '@/components/shap-panel';
import { DriftPanel } from '@/components/drift-panel';
import { ComparisonPanel } from '@/components/comparison-panel';

export default function CopilotPage() {
  const [activeTool, setActiveTool] = useState<ToolType>('chat');

  const renderPanel = () => {
    switch (activeTool) {
      case 'chat':
        return <ChatPanel />;
      case 'shap':
        return <SHAPPanel />;
      case 'drift':
        return <DriftPanel />;
      case 'comparison':
        return <ComparisonPanel />;
      default:
        return <ChatPanel />;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-to-b from-slate-950 to-slate-900">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-900/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-3xl">🤖</div>
            <div>
              <h1 className="text-xl font-bold text-white">AI Copilot</h1>
              <p className="text-sm text-gray-400">MLOps Intelligence Platform</p>
            </div>
          </div>
          <div className="text-sm text-gray-400">
            Powered by Groq • Tool calling enabled
          </div>
        </div>
      </div>

      {/* Tool Tabs */}
      <ToolTabs activeTool={activeTool} onToolChange={setActiveTool} />

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {renderPanel()}
      </div>
    </div>
  );
}
