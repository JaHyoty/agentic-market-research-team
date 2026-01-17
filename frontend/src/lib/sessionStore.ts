// Session management for storing research sessions in browser localStorage

export interface Session {
  id: string;
  query: string;
  status: string;
  createdAt: string;
  lastUpdatedAt: string;
}

const SESSIONS_KEY = 'research_sessions';
const CURRENT_SESSION_KEY = 'current_session_id';
const BROWSER_SESSION_KEY = 'browser_session_id';

/**
 * Get or create a unique browser session ID.
 * This persists across page reloads and uniquely identifies this browser.
 */
export function getBrowserSessionId(): string {
  if (typeof window === 'undefined') return '';
  
  let sessionId = localStorage.getItem(BROWSER_SESSION_KEY);
  if (!sessionId) {
    // Generate a new UUID for this browser
    sessionId = crypto.randomUUID();
    localStorage.setItem(BROWSER_SESSION_KEY, sessionId);
  }
  return sessionId;
}

/**
 * Get all sessions from localStorage
 */
export function getSessions(): Session[] {
  if (typeof window === 'undefined') return [];
  const data = localStorage.getItem(SESSIONS_KEY);
  if (!data) return [];
  try {
    return JSON.parse(data);
  } catch {
    return [];
  }
}

/**
 * Save a session to localStorage
 */
export function saveSession(session: Session): void {
  if (typeof window === 'undefined') return;
  const sessions = getSessions();
  const existingIndex = sessions.findIndex(s => s.id === session.id);
  
  if (existingIndex >= 0) {
    sessions[existingIndex] = { ...sessions[existingIndex], ...session };
  } else {
    sessions.unshift(session); // Add new sessions at the beginning
  }
  
  // Keep only the last 50 sessions
  const trimmed = sessions.slice(0, 50);
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(trimmed));
}

/**
 * Get a specific session by ID
 */
export function getSession(id: string): Session | null {
  const sessions = getSessions();
  return sessions.find(s => s.id === id) || null;
}

/**
 * Update session status
 */
export function updateSessionStatus(id: string, status: string): void {
  const sessions = getSessions();
  const session = sessions.find(s => s.id === id);
  if (session) {
    session.status = status;
    session.lastUpdatedAt = new Date().toISOString();
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
  }
}

/**
 * Delete a session
 */
export function deleteSession(id: string): void {
  if (typeof window === 'undefined') return;
  const sessions = getSessions().filter(s => s.id !== id);
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
  
  // Clear current session if it was deleted
  if (getCurrentSessionId() === id) {
    clearCurrentSession();
  }
}

/**
 * Get current active session ID
 */
export function getCurrentSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(CURRENT_SESSION_KEY);
}

/**
 * Set current active session
 */
export function setCurrentSession(id: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(CURRENT_SESSION_KEY, id);
}

/**
 * Clear current session
 */
export function clearCurrentSession(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(CURRENT_SESSION_KEY);
}
