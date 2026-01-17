'use client';

import { AgentEvent } from '@/lib/api';
import { motion } from 'framer-motion';
import { 
  Crown, Search, Compass, BarChart3, PenTool, CheckSquare, 
  Wrench, User, Bot, Loader2 
} from 'lucide-react';
import { useState } from 'react';

// Map agent names to icons
const agentIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  supervisor: Crown,
  researcher: Search,
  scout: Compass,
  quant: BarChart3,
  writer: PenTool,
  reviewer: CheckSquare,
  user: User,
  system: Bot,
};

// Agent display colors (gradient classes)
const agentColors: Record<string, string> = {
  supervisor: 'from-purple-500 to-purple-600',
  researcher: 'from-blue-500 to-blue-600',
  scout: 'from-green-500 to-green-600',
  quant: 'from-orange-500 to-orange-600',
  writer: 'from-pink-500 to-pink-600',
  reviewer: 'from-cyan-500 to-cyan-600',
  user: 'from-slate-400 to-slate-500',
  system: 'from-slate-600 to-slate-700',
};

interface AgentCardProps {
  agent: string;
  isActive: boolean;
  events: AgentEvent[];
}

export default function AgentCard({ agent, isActive, events }: AgentCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const Icon = agentIcons[agent.toLowerCase()] || Wrench;
  const colorClass = agentColors[agent.toLowerCase()] || 'from-slate-500 to-slate-600';
  
  // Get last event for this agent
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  
  // Action type to human-readable text
  const actionLabels: Record<string, string> = {
    thinking: 'Thinking...',
    tool_call: 'Calling tool',
    tool_result: 'Got result',
    result: 'Completed',
    error: 'Error',
    clarification: 'Needs clarification',
    complete: 'Done',
    input: 'Input received',
    info: 'Info',
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`
        relative bg-slate-900/60 border rounded-xl p-4 
        transition-all duration-300 cursor-pointer
        ${isActive 
          ? 'border-blue-500/50 shadow-lg shadow-blue-500/10' 
          : 'border-slate-700/50 hover:border-slate-600'
        }
      `}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* Active indicator pulse */}
      {isActive && (
        <div className="absolute -top-1 -right-1">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
          </span>
        </div>
      )}
      
      <div className="flex items-center gap-3">
        {/* Agent icon */}
        <div className={`
          w-10 h-10 rounded-lg bg-gradient-to-br ${colorClass}
          flex items-center justify-center shadow-lg
        `}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        
        {/* Agent info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white capitalize truncate">
            {agent}
          </h3>
          <p className="text-sm text-slate-400 truncate">
            {isActive ? (
              <span className="flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                {latestEvent?.action ? actionLabels[latestEvent.action] : 'Working...'}
              </span>
            ) : latestEvent ? (
              actionLabels[latestEvent.action] || 'Idle'
            ) : (
              'Waiting...'
            )}
          </p>
        </div>
      </div>
      
      {/* Expanded view with event log */}
      {isExpanded && events.length > 0 && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="mt-3 pt-3 border-t border-slate-700/50"
        >
          <div className="space-y-2 max-h-40 overflow-y-auto text-sm">
            {events.slice(-5).map((event, i) => (
              <div key={i} className="flex items-start gap-2 text-slate-400">
                <span className="text-xs text-slate-500 whitespace-nowrap">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <span className="truncate">{event.message}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
