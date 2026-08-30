import { useState, useEffect, useCallback, useRef } from 'react'
import { collabApi } from '../../api/client'
import { Users, Circle, MousePointer2, Send, Copy, UserPlus } from 'lucide-react'

interface CollabUser {
  id: string
  name: string
  color: string
  cursor_position?: { line: number; col: number }
  last_active: number
  is_typing: boolean
}

interface CollabSession {
  id: string
  session_id: string
  collaborators: CollabUser[]
  collaborator_count: number
  created_at: number
  last_event: number
}

const PRESET_NAMES = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']

export function CollabPanel() {
  const [sessions, setSessions] = useState<CollabSession[]>([])
  const [activeSession, setActiveSession] = useState<CollabSession | null>(null)
  const [userName, setUserName] = useState('')
  const [userId, setUserId] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<Array<{ user: string; text: string; time: number }>>([])
  const [chatInput, setChatInput] = useState('')
  const [_showJoin, setShowJoin] = useState(false)
  const [newSessionName, setNewSessionName] = useState('')
  const [cursors, setCursors] = useState<Record<string, { x: number; y: number; name: string; color: string }>>({})
  const canvasRef = useRef<HTMLDivElement>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadSessions = useCallback(async () => {
    try {
      const s = await collabApi.active()
      setSessions(s)
    } catch { /* ok */ }
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

  // Simulated cursor movement for demo
  useEffect(() => {
    if (!activeSession || !isConnected) return
    const interval = setInterval(() => {
      const newCursors: Record<string, { x: number; y: number; name: string; color: string }> = {}
      for (const c of (activeSession.collaborators || [])) {
        newCursors[c.id] = {
          x: 50 + Math.random() * 400,
          y: 50 + Math.random() * 200,
          name: c.name,
          color: c.color,
        }
      }
      setCursors(newCursors)
    }, 2000)
    return () => clearInterval(interval)
  }, [activeSession, isConnected])

  const generateId = () => `user_${Math.random().toString(36).slice(2, 8)}`

  const joinSession = async (sessionId: string) => {
    if (!userName.trim()) return
    const uid = userId || generateId()
    setUserId(uid)
    try {
      await collabApi.join(sessionId, uid)
      const info = await collabApi.session(sessionId)
      setActiveSession(info)
      setIsConnected(true)
      setShowJoin(false)

      // Add system message
      setMessages(prev => [...prev, {
        user: 'System', text: `${userName} joined the session`, time: Date.now(),
      }])

      // Start polling for updates
      pollRef.current = setInterval(async () => {
        try {
          const updated = await collabApi.session(sessionId)
          setActiveSession(updated)
        } catch { /* ok */ }
      }, 3000)
    } catch { /* ok */ }
  }

  const leaveSession = async () => {
    if (!activeSession || !userId) return
    try {
      await collabApi.leave(activeSession.session_id, userId)
    } catch { /* ok */ }
    setActiveSession(null)
    setIsConnected(false)
    setCursors({})
    setMessages([])
    if (pollRef.current) clearInterval(pollRef.current)
  }

  const sendMessage = async () => {
    if (!chatInput.trim() || !activeSession || !userId) return
    const msg = { user: userName, text: chatInput, time: Date.now() }
    setMessages(prev => [...prev, msg])
    setChatInput('')
    // In a real impl, this would go through WebSocket
  }

  const copySessionId = () => {
    if (activeSession) navigator.clipboard?.writeText(activeSession.session_id)
  }

  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className="h-full flex flex-col">
      {!activeSession ? (
        /* Session list / join view */
        <div className="flex-1 overflow-auto p-3 space-y-3">
          {/* User setup */}
          <div className="bg-elevated rounded-lg p-3">
            <label className="text-[10px] text-text-muted uppercase tracking-wide">Your Name</label>
            <div className="flex gap-2 mt-1">
              <input
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="Enter your name..."
                className="flex-1 bg-surface border border-border rounded px-2 py-1.5 text-sm text-text"
              />
            </div>
            <div className="flex gap-1 mt-2">
              {PRESET_NAMES.map(name => (
                <button
                  key={name}
                  onClick={() => setUserName(name)}
                  className={`text-[10px] px-2 py-0.5 rounded-full border ${
                    userName === name ? 'border-accent text-accent' : 'border-border text-text-muted'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          {/* Active sessions */}
          <div>
            <h3 className="text-xs font-medium text-text mb-2">Active Sessions</h3>
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-xs">
                <Users size={24} className="mx-auto mb-2 opacity-50" />
                No active sessions
              </div>
            ) : (
              <div className="space-y-2">
                {sessions.map(s => (
                  <div key={s.id} className="bg-elevated rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm text-text font-medium">Session {s.session_id.slice(0, 8)}</div>
                        <div className="text-[10px] text-text-muted">
                          {s.collaborator_count} collaborator{s.collaborator_count !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <button
                        onClick={() => joinSession(s.session_id)}
                        disabled={!userName.trim()}
                        className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-30"
                      >
                        Join
                      </button>
                    </div>
                    {/* Show collaborator avatars */}
                    <div className="flex gap-1 mt-2">
                      {(s.collaborators || []).slice(0, 5).map((c: CollabUser) => (
                        <div
                          key={c.id}
                          className="w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold text-black"
                          style={{ backgroundColor: c.color }}
                          title={c.name}
                        >
                          {c.name[0]}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Create / Join by ID */}
          <div className="bg-elevated rounded-lg p-3">
            <h3 className="text-xs font-medium text-text mb-2">Join by Session ID</h3>
            <div className="flex gap-2">
              <input
                value={newSessionName}
                onChange={(e) => setNewSessionName(e.target.value)}
                placeholder="Session ID..."
                className="flex-1 bg-surface border border-border rounded px-2 py-1.5 text-xs text-text"
              />
              <button
                onClick={() => { if (newSessionName.trim()) joinSession(newSessionName.trim()) }}
                disabled={!userName.trim() || !newSessionName.trim()}
                className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-30"
              >
                <UserPlus size={12} />
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Active collaboration view */
        <>
          {/* Session header */}
          <div className="flex items-center gap-2 p-2 border-b border-border bg-surface">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <span className="text-xs text-text font-medium truncate">
              Session {activeSession.session_id.slice(0, 8)}
            </span>
            <div className="flex items-center gap-1 ml-auto">
              <button onClick={copySessionId} className="p-1 text-text-muted hover:text-text" title="Copy session ID">
                <Copy size={12} />
              </button>
              <button onClick={leaveSession} className="text-[10px] px-2 py-0.5 bg-danger/20 text-danger rounded">
                Leave
              </button>
            </div>
          </div>

          {/* Collaborators */}
          <div className="flex items-center gap-1 px-3 py-2 border-b border-border overflow-x-auto">
            {(activeSession.collaborators || []).map((c: CollabUser) => (
              <div
                key={c.id}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border"
                style={{ borderColor: c.color, color: c.color }}
              >
                <Circle size={6} fill={c.color} stroke={c.color} />
                {c.name}
                {c.is_typing && <span className="animate-pulse">typing...</span>}
              </div>
            ))}
          </div>

          {/* Canvas with cursors */}
          <div ref={canvasRef} className="relative flex-1 bg-[#0d1117] overflow-hidden">
            <div className="absolute inset-0 flex items-center justify-center text-text-muted text-xs">
              Collaborative canvas area
            </div>
            {/* Live cursors */}
            {Object.entries(cursors).map(([id, cursor]) => (
              <div
                key={id}
                className="absolute pointer-events-none transition-all duration-500"
                style={{ left: cursor.x, top: cursor.y }}
              >
                <MousePointer2 size={16} style={{ color: cursor.color }} />
                <span
                  className="text-[9px] font-bold px-1 rounded ml-3 -mt-1"
                  style={{ backgroundColor: cursor.color, color: '#000' }}
                >
                  {cursor.name}
                </span>
              </div>
            ))}
          </div>

          {/* Chat */}
          <div className="border-t border-border">
            <div className="h-32 overflow-auto p-2 space-y-1">
              {messages.map((msg, i) => (
                <div key={i} className="text-[11px]">
                  <span className="font-medium text-text">{msg.user}: </span>
                  <span className="text-text-sec">{msg.text}</span>
                  <span className="text-text-muted ml-1 text-[9px]">{formatTime(msg.time)}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-2 p-2 border-t border-border">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Type a message..."
                className="flex-1 bg-elevated border border-border rounded px-2 py-1 text-xs text-text"
              />
              <button onClick={sendMessage} className="p-1 text-accent hover:bg-accent/20 rounded">
                <Send size={14} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
