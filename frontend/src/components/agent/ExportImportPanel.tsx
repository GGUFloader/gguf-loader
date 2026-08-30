import { useState, useRef } from 'react'
import { Download, Upload, FileText, Check, RefreshCw } from 'lucide-react'
import { notify } from '../../stores/notificationStore'

const DATA_TYPES = [
  { id: 'sessions', label: 'Sessions', description: 'Chat history and agent sessions', icon: FileText },
  { id: 'settings', label: 'Settings', description: 'Application preferences and config', icon: FileText },
  { id: 'templates', label: 'Templates', description: 'Custom prompt templates', icon: FileText },
  { id: 'plugins', label: 'Plugins', description: 'Plugin configurations', icon: FileText },
]



export function ExportImportPanel() {
  const [activeTab, setActiveTab] = useState<'export' | 'import'>('export')
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['sessions', 'settings', 'templates']))
  const [exportName, setExportName] = useState('')
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [conflict, setConflict] = useState<'skip' | 'overwrite' | 'merge'>('skip')
  const [importResult, setImportResult] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function toggleType(id: string) {
    setSelectedTypes(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleExport() {
    setExporting(true)
    try {
      const types = Array.from(selectedTypes)
      const params = types.map(t => `${t}=true`).join('&')
      const res = await fetch(`/api/agent/exports/create?${params}&name=${encodeURIComponent(exportName || 'export')}`, {
        method: 'POST',
      })
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `ggufloader-export-${Date.now()}.json`
        a.click()
        URL.revokeObjectURL(url)
        notify.success('Export Complete', `Exported ${types.join(', ')}`)
      }
    } catch (e: any) {
      notify.error('Export Failed', e.message)
    }
    setExporting(false)
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)

    try {
      const text = await file.text()
      const bundle = JSON.parse(text)

      // Validate
      if (!bundle.version || !bundle.data) {
        notify.error('Invalid Bundle', 'Missing version or data field')
        setImporting(false)
        return
      }

      // Send to backend
      const formData = new FormData()
      formData.append('file', file)
      formData.append('conflict', conflict)

      const res = await fetch('/api/agent/imports/upload', {
        method: 'POST',
        body: formData,
      })

      if (res.ok) {
        const result = await res.json()
        setImportResult(result)
        notify.success('Import Complete', `Imported ${result.imported} items`)
      } else {
        const err = await res.json()
        notify.error('Import Failed', err.detail || 'Unknown error')
      }
    } catch (e: any) {
      notify.error('Import Failed', e.message)
    }

    setImporting(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="h-full flex flex-col p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center gap-2">
        <Download size={14} className="text-accent" />
        <h3 className="text-sm font-semibold text-text">Export / Import</h3>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 bg-elevated rounded-lg p-0.5">
        <button onClick={() => setActiveTab('export')}
          className={`flex-1 flex items-center justify-center gap-1.5 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'export' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          <Download size={12} /> Export
        </button>
        <button onClick={() => setActiveTab('import')}
          className={`flex-1 flex items-center justify-center gap-1.5 text-[11px] py-1.5 rounded-md transition-colors ${activeTab === 'import' ? 'bg-accent/15 text-accent font-medium' : 'text-text-muted hover:text-text'}`}>
          <Upload size={12} /> Import
        </button>
      </div>

      {/* Export tab */}
      {activeTab === 'export' && (
        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-text-muted uppercase block mb-1">Bundle Name</label>
            <input placeholder="my-export" value={exportName} onChange={e => setExportName(e.target.value)}
              className="w-full bg-elevated border border-border rounded-lg px-3 py-1.5 text-[11px] text-text outline-none focus:border-accent" />
          </div>

          <div>
            <label className="text-[10px] text-text-muted uppercase block mb-1.5">Data to Export</label>
            <div className="space-y-1">
              {DATA_TYPES.map(dt => (
                <button key={dt.id} onClick={() => toggleType(dt.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border text-left transition-colors ${
                    selectedTypes.has(dt.id) ? 'border-accent/30 bg-accent/5' : 'border-border bg-elevated hover:border-accent/20'
                  }`}>
                  <div className={`w-4 h-4 rounded border flex items-center justify-center ${selectedTypes.has(dt.id) ? 'bg-accent border-accent' : 'border-border'}`}>
                    {selectedTypes.has(dt.id) && <Check size={10} className="text-onAccent" />}
                  </div>
                  <div>
                    <div className="text-[11px] text-text">{dt.label}</div>
                    <div className="text-[9px] text-text-muted">{dt.description}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button onClick={handleExport} disabled={exporting || selectedTypes.size === 0}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-accent text-onAccent rounded-lg text-[11px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
            <Download size={12} /> {exporting ? 'Exporting...' : `Export ${selectedTypes.size} items`}
          </button>
        </div>
      )}

      {/* Import tab */}
      {activeTab === 'import' && (
        <div className="space-y-3">
          <div>
            <label className="text-[10px] text-text-muted uppercase block mb-1.5">Conflict Resolution</label>
            <div className="flex gap-1">
              {(['skip', 'overwrite', 'merge'] as const).map(c => (
                <button key={c} onClick={() => setConflict(c)}
                  className={`flex-1 text-[10px] py-1.5 rounded-lg border transition-colors ${
                    conflict === c ? 'border-accent/30 bg-accent/10 text-accent' : 'border-border bg-elevated text-text-muted hover:text-text'
                  }`}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </button>
              ))}
            </div>
            <div className="text-[9px] text-text-muted mt-1">
              {conflict === 'skip' && 'Skip items that already exist'}
              {conflict === 'overwrite' && 'Replace existing items with imported data'}
              {conflict === 'merge' && 'Merge imported data with existing data'}
            </div>
          </div>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-border rounded-lg px-4 py-8 text-center cursor-pointer hover:border-accent/30 transition-colors"
          >
            <Upload size={24} className="mx-auto mb-2 text-text-muted/50" />
            <p className="text-[11px] text-text-sec">Click to select a bundle file</p>
            <p className="text-[9px] text-text-muted mt-1">Accepts .json export bundles</p>
          </div>
          <input ref={fileInputRef} type="file" accept=".json" onChange={handleImport} className="hidden" />

          {importing && (
            <div className="text-[10px] text-accent text-center py-2">
              <RefreshCw size={12} className="animate-spin inline mr-1" /> Importing...
            </div>
          )}

          {importResult && (
            <div className="bg-green-500/5 border border-green-500/20 rounded-lg px-3 py-2">
              <div className="text-[10px] text-green-400 font-medium mb-1">Import Results</div>
              <div className="space-y-0.5 text-[9px] text-text-sec">
                <div>Imported: {importResult.imported} items</div>
                {importResult.skipped > 0 && <div>Skipped: {importResult.skipped}</div>}
                {importResult.conflicts > 0 && <div>Conflicts: {importResult.conflicts}</div>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
