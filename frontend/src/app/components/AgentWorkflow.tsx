'use client';

import { AgentEvent } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Crown, Search, Compass, BarChart3, PenTool, CheckSquare, ArrowRight 
} from 'lucide-react';

// Workflow steps in order
const workflowSteps = [
  { id: 'supervisor', label: 'Supervisor', icon: Crown },
  { id: 'researcher', label: 'Researcher', icon: Search },
  { id: 'scout', label: 'Scout', icon: Compass },
  { id: 'quant', label: 'Quant', icon: BarChart3 },
  { id: 'writer', label: 'Writer', icon: PenTool },
  { id: 'reviewer', label: 'Reviewer', icon: CheckSquare },
];

interface AgentWorkflowProps {
  activeAgent: string | null;
  completedAgents: Set<string>;
}

const AgentNode = ({ 
    id, 
    label, 
    icon: Icon, 
    activeAgent, 
    completedAgents,
    showLabel = true
}: { 
    id: string; 
    label: string; 
    icon: any; 
    activeAgent: string | null; 
    completedAgents: Set<string>;
    showLabel?: boolean;
}) => {
    const isActive = activeAgent?.toLowerCase() === id;
    const isCompleted = completedAgents.has(id);

    return (
        <div className="flex flex-col items-center z-10">
            <motion.div
                animate={{ scale: isActive ? 1.1 : 1 }}
                className="relative"
            >
                <div 
                    className={`
                        w-12 h-12 rounded-full flex items-center justify-center
                        transition-all duration-300 relative bg-slate-900
                        ${isActive 
                            ? 'bg-blue-600 shadow-lg shadow-blue-500/30 ring-2 ring-blue-500' 
                            : isCompleted 
                                ? 'bg-emerald-900/30 border-2 border-emerald-500/50' 
                                : 'bg-slate-800 border-2 border-slate-700'
                        }
                    `}
                >
                    {isActive && (
                        <motion.div
                            initial={{ scale: 1, opacity: 0.5 }}
                            animate={{ scale: 1.5, opacity: 0 }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            className="absolute inset-0 rounded-full bg-blue-500"
                        />
                    )}
                    <Icon 
                        className={`
                            w-5 h-5 relative z-10
                            ${isActive 
                                ? 'text-white' 
                                : isCompleted 
                                    ? 'text-emerald-400' 
                                    : 'text-slate-500'
                            }
                        `} 
                    />
                </div>
            </motion.div>
            {showLabel && (
                <span className={`
                    mt-2 text-xs font-medium px-2 py-0.5 rounded-full border
                    ${isActive 
                        ? 'bg-blue-900/30 border-blue-500/30 text-blue-200' 
                        : isCompleted 
                            ? 'bg-emerald-900/30 border-emerald-500/30 text-emerald-300' 
                            : 'bg-slate-800 border-slate-700 text-slate-500'
                    }
                `}>
                    {label}
                </span>
            )}
        </div>
    );
};

export default function AgentWorkflow({ activeAgent, completedAgents }: AgentWorkflowProps) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 mb-6 overflow-x-auto">
      <div className="flex flex-col items-center min-w-[600px]">
        
        {/* Level 1: Leader */}
        <div className="relative flex flex-col items-center">
            <AgentNode 
                id="supervisor" label="Supervisor (Leader)" icon={Crown} 
                activeAgent={activeAgent} completedAgents={completedAgents} 
            />
            {/* Vertical line from Supervisor down to horizontal bar */}
            <div className="w-px h-8 bg-slate-700" />
        </div>

        {/* Connector Horizontal Structure */}
        <div className="relative w-full flex justify-center -mt-px">
            {/* The horizontal line spanning the groups */}
            <div className="absolute top-0 w-[50%] h-px bg-slate-700" />
            
            {/* Left Vertical Drop to Managers */}
            <div className="absolute left-[25%] top-0 w-px h-6 bg-slate-700" />
            
            {/* Right Vertical Drop to Workers */}
            <div className="absolute right-[25%] top-0 w-px h-6 bg-slate-700" />
        </div>

        {/* Level 2: Groups */}
        <div className="flex w-full justify-center gap-16 mt-6">
            
            {/* Managers */}
            <div className="flex flex-col items-center gap-4 bg-slate-800/30 p-4 rounded-xl border border-slate-700/50 w-full max-w-xs">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Managers</span>
                <div className="flex gap-4 relative">
                    {/* Connection line between managers */}
                    <div className="absolute top-6 left-1/2 -translate-x-1/2 w-8 h-px bg-slate-700" />
                    <AgentNode id="writer" label="Writer" icon={PenTool} activeAgent={activeAgent} completedAgents={completedAgents} />
                    <AgentNode id="reviewer" label="Reviewer" icon={CheckSquare} activeAgent={activeAgent} completedAgents={completedAgents} />
                </div>
            </div>

            {/* Workers */}
            <div className="flex flex-col items-center gap-4 bg-slate-800/30 p-4 rounded-xl border border-slate-700/50 w-full max-w-md">
                 <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Workers</span>
                 <div className="flex gap-6">
                    <AgentNode id="researcher" label="Researcher" icon={Search} activeAgent={activeAgent} completedAgents={completedAgents} />
                    <AgentNode id="quant" label="Quant" icon={BarChart3} activeAgent={activeAgent} completedAgents={completedAgents} />
                    <AgentNode id="scout" label="Scout" icon={Compass} activeAgent={activeAgent} completedAgents={completedAgents} />
                 </div>
            </div>

        </div>
      </div>
    </div>
  );
}
