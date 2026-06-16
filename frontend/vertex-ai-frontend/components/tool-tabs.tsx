'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { MessageSquare, BarChart2, TrendingUp, GitCompare } from 'lucide-react';

export type ToolType = 'chat' | 'shap' | 'drift' | 'comparison';

interface ToolTabsProps {
  activeTool: ToolType;
  onToolChange: (tool: ToolType) => void;
}

const tools: { id: ToolType; label: string; icon: React.ElementType; description: string }[] = [
  { id: 'chat',       label: 'Chat',           icon: MessageSquare, description: 'Ask questions about your models' },
  { id: 'shap',       label: 'SHAP Explainer', icon: BarChart2,     description: 'Understand feature importance' },
  { id: 'drift',      label: 'Drift Analysis', icon: TrendingUp,    description: 'Detect and analyze model drift' },
  { id: 'comparison', label: 'Model Compare',  icon: GitCompare,    description: 'Compare model versions' },
];

export function ToolTabs({ activeTool, onToolChange }: ToolTabsProps) {
  return (
    <div className="border-b border-border bg-card px-6 flex-shrink-0">
      <div className="flex gap-0">
        {tools.map((tool) => {
          const Icon = tool.icon;
          const isActive = activeTool === tool.id;
          return (
            <button
              key={tool.id}
              onClick={() => onToolChange(tool.id)}
              title={tool.description}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-all duration-150 whitespace-nowrap',
                isActive
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              )}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{tool.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}