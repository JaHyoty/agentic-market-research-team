"use client";

import { useState, useEffect, useCallback } from 'react';
import { 
  submitResearch, 
  answerClarification,
  getTaskStatus, 
  getSessions as fetchSessions,
  pollTaskEvents,
  getReportUrl,
  AgentEvent,
  SessionSummary 
} from '@/lib/api';
import { 
  saveSession, 
  getSessions as getLocalSessions, 
  deleteSession as deleteLocalSession,
  getCurrentSessionId,
  setCurrentSession,
  clearCurrentSession 
} from '@/lib/sessionStore';
import { Send, Loader2, FileText, CheckCircle, AlertCircle, Plus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import AgentCard from './components/AgentCard';
import AgentWorkflow from './components/AgentWorkflow';
import Sidebar from './components/Sidebar';

// Known agents in our workflow
const KNOWN_AGENTS = ['supervisor', 'researcher', 'scout', 'quant', 'writer', 'reviewer'];

export default function Home() {
  const [query, setQuery] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskQuery, setTaskQuery] = useState<string | null>(null); // Original research goal
  const [status, setStatus] = useState<string>('IDLE');
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Session management
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  // Active agent tracking
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [completedAgents, setCompletedAgents] = useState<Set<string>>(new Set());

  // ... (unchanged eventsByAgent logic) ...
  const eventsByAgent = events.reduce((acc, event) => {
    const agent = event.agent.toLowerCase();
    if (!acc[agent]) acc[agent] = [];
    acc[agent].push(event);
    return acc;
  }, {} as Record<string, AgentEvent[]>);
  
  // Load sessions and sidebar state on mount
  useEffect(() => {
    loadSessions();
    
    // Load sidebar state
    const savedSidebar = localStorage.getItem('sidebarOpen');
    if (savedSidebar !== null) {
      setSidebarOpen(savedSidebar === 'true');
    }
    
    // Check for existing session
    const savedTaskId = getCurrentSessionId();
    if (savedTaskId) {
      setTaskId(savedTaskId);
      loadExistingTask(savedTaskId);
    }
  }, []);
  
  const toggleSidebar = () => {
    const newState = !sidebarOpen;
    setSidebarOpen(newState);
    localStorage.setItem('sidebarOpen', String(newState));
  };
  
  const loadSessions = async () => {
    try {
      // Try to fetch from server first
      const response = await fetchSessions();
      setSessions(response.sessions);
    } catch {
      // Fall back to local storage
      const localSessions = getLocalSessions();
      setSessions(localSessions.map(s => ({
        task_id: s.id,
        status: s.status,
        created_at: s.createdAt,
        query: s.query
      })));
    }
  };
  
  const loadExistingTask = async (id: string) => {
    try {
      const data = await getTaskStatus(id);
      setStatus(data.status);
      setEvents(data.events || []);
      setReportUrl(data.report_url);
      setTaskQuery(data.query || null); // Load the original query
      
      if (data.status !== 'COMPLETED' && data.status !== 'FAILED') {
        setLoading(true);
        subscribeToEvents(id);
      }
    } catch (err) {
      console.error('Failed to load existing task:', err);
      clearCurrentSession();
    }
  };
  
  // ... (subscribeToEvents) ...
  const subscribeToEvents = useCallback((id: string) => {
    const cleanup = pollTaskEvents(id, {
      onEvents: (newEvents, allEvents) => {
        setEvents(allEvents);
        
        // Track active agent from new events
        for (const event of newEvents) {
          if (KNOWN_AGENTS.includes(event.agent.toLowerCase())) {
            setActiveAgent(event.agent.toLowerCase());
            
            // Mark as completed if it's a result action
            if (event.action === 'result') {
              setCompletedAgents(prev => new Set([...prev, event.agent.toLowerCase()]));
            }
          }
        }
      },
      onStatus: (newStatus) => {
        setStatus(newStatus);
      },
      onComplete: (data) => {
        setStatus(data.status);
        setReportUrl(data.report_url);
        setLoading(false);
        setActiveAgent(null);
        
        if (data.status === 'COMPLETED') {
          clearCurrentSession();
        }
        
        loadSessions(); // Refresh sessions list
      },
      onError: (err) => {
        setError(err);
        setLoading(false);
      }
    });
    
    return cleanup;
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    // If answering clarification
    if (status === 'CLARIFICATION_REQUIRED' && taskId) {
        try {
            await answerClarification(taskId, query); 
            setQuery(''); // Clear answer input
            setLoading(true); // Show loading state
            subscribeToEvents(taskId); // Restart polling since it stopped on CLARIFICATION_REQUIRED
        } catch (err) {
            setError("Failed to submit clarification.");
            setLoading(false);
        }
        return;
    }

    // New Research
    setEvents([]);
    setReportUrl(null);
    setActiveAgent(null);
    setCompletedAgents(new Set());
    
    try {
      const data = await submitResearch(query);
      setTaskId(data.task_id);
      setTaskQuery(query); // Set explicit goal
      setStatus('QUEUED');
      
      // Save to local storage
      saveSession({
        id: data.task_id,
        query: query,
        status: 'QUEUED',
        createdAt: new Date().toISOString(),
        lastUpdatedAt: new Date().toISOString()
      });
      setCurrentSession(data.task_id);
      
      // Start polling for events
      subscribeToEvents(data.task_id);
      
      // Refresh sessions list
      loadSessions();
      
      setQuery(''); // Clear input
    } catch (err) {
      setError("Failed to submit research request.");
      setLoading(false);
    }
  };
  
  const handleSelectSession = async (sessionId: string) => {
    setTaskId(sessionId);
    setCurrentSession(sessionId);
    setEvents([]);
    setCompletedAgents(new Set());
    setActiveAgent(null);
    
    await loadExistingTask(sessionId);
  };
  
  const handleDeleteSession = (sessionId: string) => {
    deleteLocalSession(sessionId);
    setSessions(prev => prev.filter(s => s.task_id !== sessionId));
    
    if (taskId === sessionId) {
      setTaskId(null);
      setTaskQuery(null);
      setStatus('IDLE');
      setEvents([]);
      setReportUrl(null);
      clearCurrentSession();
    }
  };
  
  const handleNewResearch = () => {
    setTaskId(null);
    setTaskQuery(null);
    setStatus('IDLE');
    setEvents([]);
    setReportUrl(null);
    setLoading(false);
    clearCurrentSession();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSessionId={taskId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onNewResearch={handleNewResearch}
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
      />
      
      {/* Main content */}
      <main className={`transition-all duration-300 ${sidebarOpen ? 'lg:ml-72' : ''}`}>
        <div className="max-w-5xl mx-auto p-8 space-y-8">
          <header className="text-center space-y-4">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              Agentic Market Research Team
            </h1>
            <p className="text-slate-400">
              Deploy a virtual team of AI agents to research any market topic.
            </p>
          </header>

          {/* Input form or Session Title */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm relative">
            {taskId ? (
              <div className="space-y-4">
                  {/* Always show the Research Query if active */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-semibold text-slate-200 mb-1">Current Research Session</h2>
                      <p className="text-lg text-blue-400 font-medium">{taskQuery || 'Loading...'}</p>
                    </div>
                    {status !== 'COMPLETED' && status !== 'FAILED' && status !== 'CLARIFICATION_REQUIRED' && (
                      <div className="flex items-center gap-2 text-slate-400 bg-slate-900 px-3 py-1.5 rounded-full text-sm border border-slate-800">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Running...
                      </div>
                    )}
                    {(status === 'COMPLETED' || status === 'FAILED') && (
                      <button
                        onClick={handleNewResearch}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                        New Research
                      </button>
                    )}
                  </div>

                  {/* Clarification Input if Needed */}
                  {status === 'CLARIFICATION_REQUIRED' && (
                    <div className="border-t border-slate-800 pt-4">
                       <div className="mb-3 text-amber-400 flex flex-col gap-1 text-sm font-medium">
                         <div className="flex items-center gap-2">
                           <AlertCircle className="w-4 h-4" />
                           Clarification Needed:
                         </div>
                         <p className="pl-6 text-amber-200/90">
                           {events.find(e => e.action === 'clarification')?.message || "Please provide more details below."}
                         </p>
                       </div>
                       <form onSubmit={handleSubmit} className="relative">
                           <input
                             type="text"
                             value={query}
                             onChange={(e) => setQuery(e.target.value)}
                             placeholder="Enter your clarification here..."
                             className="w-full bg-slate-950 border border-amber-500/50 rounded-xl py-4 px-6 pr-16 text-lg focus:outline-none focus:ring-2 focus:ring-amber-500 transition-all"
                             autoFocus
                           />
                           <button
                             type="submit"
                             disabled={loading}
                             className="absolute right-2 bottom-2 top-2 h-10 w-10 flex items-center justify-center rounded-lg text-white bg-amber-600 hover:bg-amber-500 transition-colors"
                           >
                             {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                           </button>
                       </form>
                    </div>
                  )}
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="relative">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g., Analyze the EV market in Brazil..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl py-4 px-6 pr-16 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  disabled={loading}
                  autoFocus
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="absolute right-2 bottom-2 top-2 h-10 w-10 flex items-center justify-center rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </form>
            )}
          </div>

          {/* Error display */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
              <p className="text-red-300">{error}</p>
            </div>
          )}
          
          {/* Workflow visualization */}
          {taskId && status !== 'IDLE' && (
            <AgentWorkflow 
              activeAgent={activeAgent} 
              completedAgents={completedAgents} 
            />
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Agent Cards Section */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Loader2 className={`w-5 h-5 ${loading && status !== 'COMPLETED' ? 'animate-spin' : ''}`} />
                Agent Activity
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {KNOWN_AGENTS.map(agent => (
                  <AgentCard
                    key={agent}
                    agent={agent}
                    isActive={activeAgent === agent}
                    events={eventsByAgent[agent] || []}
                  />
                ))}
              </div>
              
              {/* Live event stream */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 h-[200px] overflow-y-scroll space-y-2 custom-scrollbar">
                <AnimatePresence initial={false}>
                  {events.length === 0 ? (
                    <p className="text-slate-500 text-center italic py-8">Agent actions will appear here once processing begins.</p>
                  ) : (
                    events
                      .filter(e => 
                        !e.message.includes('scrape_website') && 
                        !e.message.includes('page restricted') &&
                        e.message.trim().length > 0 &&
                        e.action !== 'tool_result'
                      )
                      // .slice(-15)
                      .map((event, i) => {
                        // Format message if it's a JSON string (for tool calls)
                        let displayMessage = event.message;
                        try {
                          if (event.message.trim().startsWith('{')) {
                            const parsed = JSON.parse(event.message);
                            if (parsed.query) {
                              displayMessage = `Searching: "${parsed.query}"`;
                            }
                          }
                        } catch (e) {
                          // keep original if parse fails
                        }

                        return (
                          <motion.div
                            key={`${event.timestamp}-${i}`}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="flex items-start gap-3 text-sm text-slate-300 bg-slate-800/50 p-2 rounded-lg"
                          >
                            <span className="text-xs text-slate-500 whitespace-nowrap pt-0.5">
                              {new Date(event.timestamp).toLocaleTimeString()}
                            </span>
                            <span className="font-medium text-blue-400 capitalize shrink-0 pt-0.5">
                              {event.agent}
                            </span>
                            <span className="truncate flex-1">{displayMessage}</span>
                          </motion.div>
                        );
                      })
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Result Section */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Research Report
              </h2>
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 h-[400px] flex flex-col items-center justify-center text-center">
                {status === 'COMPLETED' && reportUrl ? (
                  <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="space-y-4"
                  >
                    <div className="w-16 h-16 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center mx-auto">
                      <CheckCircle className="w-8 h-8" />
                    </div>
                    <h3 className="text-xl font-bold text-white">Report Ready!</h3>
                    <p className="text-slate-400 max-w-xs">
                      Your market research report has been generated successfully.
                    </p>
                    <div className="flex gap-4 items-center justify-center">
                        <button
                        onClick={async () => {
                            if (!taskId) return;
                            try {
                                setDownloading(true);
                                const data = await getReportUrl(taskId);
                                window.open(data.url, '_blank');
                            } catch (err) {
                                console.error("Failed to get report URL:", err);
                                alert("Failed to download report.");
                            } finally {
                                setDownloading(false);
                            }
                        }}
                        disabled={downloading}
                        className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                        >
                        {downloading ? (
                             <Loader2 className="w-5 h-5 animate-spin" />
                        ) : (
                            <FileText className="w-5 h-5" />
                        )}
                        {downloading ? "Preparing Download..." : "Download Report"}
                        </button>
                    </div>
                  </motion.div>
                ) : status === 'FAILED' ? (
                  <div className="text-red-400 space-y-2">
                    <AlertCircle className="w-10 h-10 mx-auto" />
                    <p>Research failed. Please try again.</p>
                  </div>
                ) : status === 'QUEUED' ? (
                  <div className="text-red-400 space-y-2">
                    <AlertCircle className="w-10 h-10 mx-auto" />
                    <p>Research is queued. Waiting for the next available resource.</p>
                  </div>
                ) : status === 'CLARIFICATION_REQUIRED' ? (
                  <div className="text-orange-400 space-y-2 max-w-xs">
                    <div className="w-12 h-12 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto">
                      <AlertCircle className="w-6 h-6" />
                    </div>
                    <p className="font-medium">Clarification Needed</p>
                  </div>
                ) : loading ? (
                  <div className="text-slate-400 space-y-3">
                    <Loader2 className="w-10 h-10 mx-auto animate-spin text-blue-400" />
                    <p>Agents are working...</p>
                    <p className="text-sm text-slate-500">
                      {events.length} events processed
                    </p>
                  </div>
                ) : (
                  <div className="text-slate-500 space-y-2">
                    <div className="w-16 h-16 border-2 border-dashed border-slate-700 rounded-lg mx-auto flex items-center justify-center">
                      <FileText className="w-6 h-6 opacity-50" />
                    </div>
                    <p>Report will appear here when ready</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
