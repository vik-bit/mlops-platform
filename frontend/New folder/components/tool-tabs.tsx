'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export type ToolType = 'chat' | 'shap' | 'drift' | 'comparison';

interface ToolTabsProps {
  activeTool: ToolType;
  onToolChange: (tool: ToolType) => void;
}

const tools: { id: ToolType; label: string; icon: string; description: string }[] = [
  {
    id: 'chat',
    label: 'Chat',
    icon: '💬',
    description: 'Ask questions about your models',
  },
  {
    id: 'shap',
    label: 'SHAP Explainer',
    icon: '📊',
    description: 'Understand feature importance',
  },
  {
    id: 'drift',
    label: 'Drift Analysis',
    icon: '📈',
    description: 'Detect and analyze model drift',
  },
  {
    id: 'comparison',
    label: 'Model Compare',
    icon: '⚖️',
    description: 'Compare model versions',
  },
];

export function ToolTabs({ activeTool, onToolChange }: ToolTabsProps) {
  return (
    <div className="border-b border-gray-700 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-6xl mx-auto">
        <div className="flex gap-1 p-2">
          {tools.map((tool) => (
            <button
              key={tool.id}
              onClick={() => onToolChange(tool.id)}
              className={cn(
                'px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                'flex items-center gap-2 whitespace-nowrap',
                activeTool === tool.id
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )}
              title={tool.description}
            >
              <span className="text-base">{tool.icon}</span>
              <span className="hidden sm:inline">{tool.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
