'use client';

import { SessionSummary } from '@/lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  PanelLeftClose, PanelLeft, Clock, CheckCircle, Loader2, 
  AlertCircle, Trash2, HelpCircle, Plus 
} from 'lucide-react';

interface SidebarProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onNewResearch: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

// Status to icon/color mapping
const statusConfig: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string }> = {
  QUEUED: { icon: Clock, color: 'text-yellow-400' },
  PROCESSING: { icon: Loader2, color: 'text-blue-400' },
  COMPLETED: { icon: CheckCircle, color: 'text-emerald-400' },
  FAILED: { icon: AlertCircle, color: 'text-red-400' },
  CLARIFICATION_REQUIRED: { icon: HelpCircle, color: 'text-orange-400' },
};

export default function Sidebar({ 
  sessions, 
  currentSessionId, 
  onSelectSession, 
  onDeleteSession,
  onNewResearch,
  isOpen,
  onToggle 
}: SidebarProps) {
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown date';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    
    if (diffHours < 24) {
      return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } else if (diffHours < 48) {
      return 'Yesterday';
    } else {
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    }
  };

  return (
    <>
      {/* Toggle button when closed */}
      {!isOpen && (
        <motion.button
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          onClick={onToggle}
          className="fixed left-4 top-4 z-50 bg-slate-800 hover:bg-slate-700 p-2 rounded-lg border border-slate-700 transition-colors"
        >
          <PanelLeft className="w-5 h-5 text-slate-300" />
        </motion.button>
      )}
      
      {/* Sidebar */}
      <AnimatePresence>
        {isOpen && (
          <motion.aside
            initial={{ x: -280, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -280, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 h-full w-72 bg-slate-950/95 backdrop-blur-sm border-r border-slate-800 z-40 flex flex-col"
          >
            {/* Header */}
            <div className="p-4 border-b border-slate-800">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-white">Research History</h2>
                <button
                  onClick={onToggle}
                  className="p-1.5 hover:bg-slate-800 rounded-lg transition-colors"
                >
                  <PanelLeftClose className="w-5 h-5 text-slate-400" />
                </button>
              </div>
              
              {/* New Research Button */}
              <button
                onClick={onNewResearch}
                className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white p-2.5 rounded-lg transition-colors mb-1 font-medium text-sm"
              >
                <Plus className="w-4 h-4" />
                New Research
              </button>
            </div>
            
            {/* Sessions list */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {sessions.length === 0 ? (
                <div className="text-center text-slate-500 py-8">
                  <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No research history yet</p>
                </div>
              ) : (
                sessions.map((session) => {
                  const status = statusConfig[session.status] || statusConfig.QUEUED;
                  const StatusIcon = status.icon;
                  const isActive = session.task_id === currentSessionId;
                  
                  return (
                    <motion.div
                      key={session.task_id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`
                        group relative p-3 rounded-lg cursor-pointer transition-colors
                        ${isActive 
                          ? 'bg-blue-500/10 border border-blue-500/30' 
                          : 'hover:bg-slate-800/50 border border-transparent'
                        }
                      `}
                      onClick={() => onSelectSession(session.task_id)}
                    >
                      <div className="flex items-start gap-2">
                        <StatusIcon 
                          className={`
                            w-4 h-4 mt-0.5 shrink-0 ${status.color}
                            ${session.status === 'PROCESSING' ? 'animate-spin' : ''}
                          `} 
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white truncate">
                            {session.query || 'Untitled research'}
                          </p>
                          <p className="text-xs text-slate-500 mt-0.5">
                            {formatDate(session.created_at)}
                          </p>
                        </div>
                      </div>
                      
                      {/* Delete button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(session.task_id);
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 rounded transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                      </button>
                    </motion.div>
                  );
                })
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
      
      {/* Overlay for mobile */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
            className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          />
        )}
      </AnimatePresence>
    </>
  );
}
