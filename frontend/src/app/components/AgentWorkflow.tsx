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

export default function AgentWorkflow({ activeAgent, completedAgents }: AgentWorkflowProps) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 mb-6 overflow-x-auto">
      <div className="flex items-center justify-between min-w-max gap-2">
        {workflowSteps.map((step, index) => {
          const isActive = activeAgent?.toLowerCase() === step.id;
          const isCompleted = completedAgents.has(step.id);
          const Icon = step.icon;
          
          return (
            <div key={step.id} className="flex items-center">
              {/* Step node */}
              <motion.div
                animate={{
                  scale: isActive ? 1.1 : 1,
                }}
                className="flex flex-col items-center"
              >
                <div 
                  className={`
                    relative w-12 h-12 rounded-full flex items-center justify-center
                    transition-all duration-300
                    ${isActive 
                      ? 'bg-blue-500 shadow-lg shadow-blue-500/30' 
                      : isCompleted 
                        ? 'bg-emerald-500/20 border-2 border-emerald-500' 
                        : 'bg-slate-800 border border-slate-700'
                    }
                  `}
                >
                  {/* Pulse animation for active */}
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
                
                <span 
                  className={`
                    mt-2 text-xs font-medium
                    ${isActive 
                      ? 'text-blue-400' 
                      : isCompleted 
                        ? 'text-emerald-400' 
                        : 'text-slate-500'
                    }
                  `}
                >
                  {step.label}
                </span>
              </motion.div>
              
              {/* Connector arrow */}
              {index < workflowSteps.length - 1 && (
                <div className="mx-2 flex items-center justify-center w-6">
                  <ArrowRight 
                    className={`
                      w-4 h-4-mt-4
                      ${isCompleted ? 'text-emerald-500' : 'text-slate-700'}
                    `} 
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
