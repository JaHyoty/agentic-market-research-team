import axios from 'axios';
import { getBrowserSessionId } from './sessionStore';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const api = axios.create({
  baseURL: API_URL,
});

// Add browser session ID to all requests
api.interceptors.request.use((config) => {
  const sessionId = getBrowserSessionId();
  if (sessionId) {
    config.headers['X-Browser-Session-Id'] = sessionId;
  }
  return config;
});

// Handle rate limit errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      alert('Rate limit reached. Please wait a moment before trying again.');
    }
    return Promise.reject(error);
  }
);

// Types for structured events
export interface AgentEvent {
  agent: string;
  action: 'thinking' | 'tool_call' | 'tool_result' | 'result' | 'error' | 'clarification' | 'complete' | 'input' | 'info';
  message: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  events: AgentEvent[];
  report_url: string | null;
  query: string | null;
  created_at: string | null;
}

export interface SessionSummary {
  task_id: string;
  status: string;
  created_at: string | null;
  query: string | null;
}

export const submitResearch = async (query: string) => {
  const response = await api.post('/research', { query });
  return response.data;
};

export const answerClarification = async (taskId: string, answer: string) => {
  const response = await api.post('/research', { task_id: taskId, answer });
  return response.data;
};

export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
  const response = await api.get(`/tasks/${taskId}`);
  return response.data;
};

export const getReportUrl = async (taskId: string): Promise<{ url: string }> => {
  const response = await api.get(`/reports/${taskId}`);
  return response.data;
};

export const getSessions = async (): Promise<{ sessions: SessionSummary[] }> => {
  const response = await api.get('/sessions');
  return response.data;
};

/**
 * Poll task events at a configurable interval
 * @param taskId - The task ID to poll
 * @param callbacks - Event handlers
 * @param intervalMs - Polling interval in milliseconds (default: 2000)
 * @returns Cleanup function to stop polling
 */
export function pollTaskEvents(
  taskId: string,
  callbacks: {
    onEvents?: (events: AgentEvent[], allEvents: AgentEvent[]) => void;
    onStatus?: (status: string) => void;
    onComplete?: (data: { status: string; report_url: string | null }) => void;
    onError?: (error: string) => void;
  },
  intervalMs: number = 2000
): () => void {
  let lastEventCount = 0;
  let isPolling = true;
  
  const poll = async () => {
    if (!isPolling) return;
    
    try {
      const data = await getTaskStatus(taskId);
      
      // Notify status update
      callbacks.onStatus?.(data.status);
      
      // Check for new events
      const allEvents = data.events || [];
      if (allEvents.length > lastEventCount) {
        const newEvents = allEvents.slice(lastEventCount);
        callbacks.onEvents?.(newEvents, allEvents);
        lastEventCount = allEvents.length;
      }
      
      // Check for terminal states
      if (['COMPLETED', 'FAILED', 'CLARIFICATION_REQUIRED'].includes(data.status)) {
        callbacks.onComplete?.({
          status: data.status,
          report_url: data.report_url
        });
        isPolling = false;
        return;
      }
      
      // Continue polling
      if (isPolling) {
        setTimeout(poll, intervalMs);
      }
    } catch (err) {
      callbacks.onError?.(err instanceof Error ? err.message : 'Polling failed');
      // Continue polling on errors (transient network issues)
      if (isPolling) {
        setTimeout(poll, intervalMs);
      }
    }
  };
  
  // Start polling
  poll();
  
  // Return cleanup function
  return () => {
    isPolling = false;
  };
}
