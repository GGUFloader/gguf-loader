import { useState, useEffect } from 'react'
import { Search, Save, Trash2, Clock, Hash, Code, FileText, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'

interface SearchResult {
  session_id: string
  message_index: number
  role: string
  match: string
  context: string
  score: number
}

interface SavedQuery {
  id: string
  name: string
  pattern: string
  search_type: string
  scope: string
  created_at: number
}

export function AdvancedSearchPanel() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState<'text' | 'regex' | 'code'>('text')
  const [scope, setScope] = useState<'all' | 'sessions' | 'code'>('all')
  const [caseSensitive, setCaseSensitive] = useState(false)
  const [results, setResults] = useState<SearchResult[]>([])
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([])
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'results' | 'saved' | 'history'>('results')
  const [expandedResult, setExpandedResult] = useState<number | null>(null)
  const [saveName, setSaveName] = useState('')
  const [showSave, setShowSave] = useState(false)

  useEffect(() => { loadSaved() }, [])

  async function loadSaved() {
    try {
      const [q, h] = await Promise.all([
        fetch('/api/search/queries').then(r => r.json()),
        fetch('/api/search/history').then(r => r.json()),
      ])
      setSavedQueries(q)
      setHistory(h.reverse())
    } catch {}
  }

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: query, search_type: searchType, case_sensitive: caseSensitive, scope }),
      })
      const data = await res.json()
      setResults(data.results || [])
      setActiveTab('results')
      loadSaved() // refresh history
    } catch {}
    setLoading(false)
  }

  async function handleSave() {
    if (!saveName || !query) return
    try {
      await fetch('/api/search/queries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveName, pattern: query, search_type: searchType, scope }),
      })
      setSaveName('')
      setShowSave(false)
      loadSaved()
    } catch {}
  }

  async function handleDeleteQuery(id: string) {
    try {
      await fetch(`/api/search/queries/${id}`, { method: 'DELETE' })
      loadSaved()
    } catch {}
  }

  function loadQuery(q: SavedQuery) {
    setQuery(q.pattern)
    setSearchType(q.search_type as any)
    setScope(q.scope as any)
  }

  const SEARCH_TYPES = [
    { id: 'text', label: 'Text', icon: FileText },
    { id: 'regex', label: 'Regex', icon: Hash },
    { id: 'code', label: 'Code', icon: Code },
  ]

  return (
    <div className="h-full flex flex-col p-4 space-y-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Search size={14} className="text-accent" />
          Advanced Search
        </h3>
        <button onClick={loadSaved} className="p-1.5 text-text-muted hover:text-text rounded hover:bg-elevated transition-colors">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Search input */}
      <div className="flex items-center gap-2 px-2 py-1.5 bg-elevated border border-border rounded-lg">
        <Search size={14} className="text-text-muted flex-shrink-0" />
        <input type="text" placeholder={searchType === 'regex' ? 'Regex pattern...' : 'Search text...'} value={query}
          onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()}
          className="bg-transparent text-sm text-text placeholder-text-muted outline-none w-full" />
      </div>

      {/* Options */}
      <div className="flex flex-wrap gap-2">
        {/* Search type */}
        <div className="flex gap-0.5 bg-elevated rounded-lg p-0.5">
          {SEARCH_TYPES.map(t => {
            const Icon = t.icon
            return (
              <button key={t.id} onClick={() => setSearchType(t.id as any)}
                className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-md transition-colors ${searchType === t.id ? 'bg-accent/15 text-accent' : 'text-text-muted hover:text-text'}`}>
                <Icon size={10} /> {t.label}
              </button>
            )
          })}
        </div>

        {/* Scope */}
        <select value={scope} onChange={e => setScope(e.target.value as any)}
          className="bg-elevated border border-border rounded-lg px-2 py-1 text-[10px] text-text-sec outline-none">
          <option value="all">All</option>
          <option value="sessions">Sessions</option>
          <option value="code">Code Only</option>
        </select>

        {/* Case sensitive */}
        <button onClick={() => setCaseSensitive(!caseSensitive)}
          className={`text-[10px] px-2 py-1 rounded-lg border transition-colors ${caseSensitive ? 'bg-accent/15 text-accent border-accent/30' : 'text-text-muted border-border hover:text-text'}`}>
          Aa
        </button>

        {/* Search button */}
        <button onClick={handleSearch} disabled={loading || !query.trim()}
          className="flex items-center gap-1 px-3 py-1 bg-accent text-onAccent rounded-lg text-[10px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
          <Search size={10} /> Search
        </button>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button onClick={() => setActiveTab('results')}
          className={`flex-1 text-[10px] py-1 rounded-md transition-colors ${activeTab === 'results' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          Results ({results.length})
        </button>
        <button onClick={() => setActiveTab('saved')}
          className={`flex-1 text-[10px] py-1 rounded-md transition-colors ${activeTab === 'saved' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          Saved ({savedQueries.length})
        </button>
        <button onClick={() => setActiveTab('history')}
          className={`flex-1 text-[10px] py-1 rounded-md transition-colors ${activeTab === 'history' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          History ({history.length})
        </button>
      </div>

      {/* Save query */}
      {activeTab === 'results' && results.length > 0 && (
        <div className="flex items-center gap-2">
          {showSave ? (
            <div className="flex-1 flex items-center gap-1">
              <input placeholder="Query name" value={saveName} onChange={e => setSaveName(e.target.value)}
                className="flex-1 bg-elevated border border-border rounded px-2 py-1 text-[10px] text-text outline-none focus:border-accent" />
              <button onClick={handleSave} className="px-2 py-1 bg-accent/10 text-accent rounded text-[10px]">Save</button>
            </div>
          ) : (
            <button onClick={() => setShowSave(true)} className="flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover transition-colors">
              <Save size={10} /> Save Query
            </button>
          )}
        </div>
      )}

      {/* Results */}
      {activeTab === 'results' && (
        <div className="space-y-1.5">
          {loading ? (
            <div className="text-xs text-text-muted text-center py-4">Searching...</div>
          ) : results.length === 0 ? (
            <div className="text-center py-6 text-text-muted text-xs">
              {query ? 'No results found' : 'Enter a search query'}
            </div>
          ) : (
            results.map((r, i) => (
              <div key={i} className="bg-elevated border border-border rounded-lg overflow-hidden">
                <button onClick={() => setExpandedResult(expandedResult === i ? null : i)}
                  className="w-full text-left px-3 py-2 flex items-center gap-2">
                  <span className="text-[8px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">{r.role}</span>
                  <span className="text-[10px] text-accent font-mono flex-1 truncate">"{r.match}"</span>
                  <span className="text-[8px] text-text-muted">{r.session_id.slice(0, 8)}</span>
                  {expandedResult === i ? <ChevronDown size={10} className="text-text-muted" /> : <ChevronRight size={10} className="text-text-muted" />}
                </button>
                {expandedResult === i && (
                  <div className="px-3 pb-2 border-t border-border/50">
                    <pre className="text-[9px] text-text-sec font-mono whitespace-pre-wrap mt-1.5 max-h-24 overflow-y-auto">{r.context}</pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Saved queries */}
      {activeTab === 'saved' && (
        <div className="space-y-1.5">
          {savedQueries.length === 0 ? (
            <div className="text-center py-6 text-text-muted text-xs">No saved queries</div>
          ) : (
            savedQueries.map(q => (
              <div key={q.id} className="bg-elevated border border-border rounded-lg px-3 py-2 flex items-center justify-between">
                <button onClick={() => { loadQuery(q); setActiveTab('results') }} className="text-left flex-1">
                  <div className="text-[11px] text-text">{q.name}</div>
                  <div className="text-[9px] text-text-muted font-mono truncate">{q.pattern}</div>
                </button>
                <button onClick={() => handleDeleteQuery(q.id)} className="p-1 text-text-muted hover:text-red-400 transition-colors">
                  <Trash2 size={10} />
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* History */}
      {activeTab === 'history' && (
        <div className="space-y-1">
          {history.length === 0 ? (
            <div className="text-center py-6 text-text-muted text-xs">No search history</div>
          ) : (
            history.map((h, i) => (
              <button key={i} onClick={() => { setQuery(h.pattern); setSearchType(h.search_type); setScope(h.scope); handleSearch() }}
                className="w-full text-left bg-elevated border border-border rounded-lg px-3 py-1.5 flex items-center gap-2 hover:border-accent/30 transition-colors">
                <Clock size={10} className="text-text-muted flex-shrink-0" />
                <span className="text-[10px] text-text-sec font-mono truncate flex-1">{h.pattern}</span>
                <span className="text-[8px] text-text-muted">{h.search_type}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
