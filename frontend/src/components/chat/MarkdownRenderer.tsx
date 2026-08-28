import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'

interface Props {
  content: string
}

function CodeBlock({ className, children, ...props }: any) {
  const [copied, setCopied] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const language = match?.[1] || ''
  const code = String(children).replace(/\n$/, '')
  const lineCount = code.split('\n').length

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Inline code
  if (!language && !code.includes('\n')) {
    return (
      <code className="bg-bg/50 px-1.5 py-0.5 rounded text-sm text-accent font-mono" {...props}>
        {children}
      </code>
    )
  }

  // Code block with syntax highlighting
  return (
    <div className="relative my-3 group rounded-lg border border-border overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-elevated/80">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-text-muted hover:text-text-sec transition-colors"
          >
            {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
          </button>
          <span className="text-xs text-text-muted font-mono">{language || 'code'}</span>
          <span className="text-[10px] text-text-muted/50">{lineCount} lines</span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-sec transition-colors opacity-0 group-hover:opacity-100"
        >
          {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* Code content */}
      {!collapsed && (
        <pre className="bg-bg p-4 overflow-x-auto text-sm leading-relaxed">
          <code
            className={`language-${language} text-text font-mono`}
            {...props}
          >
            {children}
          </code>
        </pre>
      )}

      {/* Collapsed indicator */}
      {collapsed && (
        <div className="px-3 py-1.5 bg-bg/50 text-xs text-text-muted">
          {lineCount} lines hidden — click to expand
        </div>
      )}
    </div>
  )
}

export function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      rehypePlugins={[rehypeHighlight]}
      components={{
        code: CodeBlock,
        a: ({ children, href, ...props }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
            {...props}
          >
            {children}
          </a>
        ),
        table: ({ children, ...props }) => (
          <div className="overflow-x-auto my-3 rounded-lg border border-border">
            <table className="w-full text-sm border-collapse" {...props}>
              {children}
            </table>
          </div>
        ),
        th: ({ children, ...props }) => (
          <th className="px-3 py-2 text-left bg-elevated border-b border-border font-medium text-text-sec" {...props}>
            {children}
          </th>
        ),
        td: ({ children, ...props }) => (
          <td className="px-3 py-2 border-b border-border/50 text-text" {...props}>
            {children}
          </td>
        ),
        ul: ({ children, ...props }) => (
          <ul className="list-disc list-inside space-y-1 my-2" {...props}>
            {children}
          </ul>
        ),
        ol: ({ children, ...props }) => (
          <ol className="list-decimal list-inside space-y-1 my-2" {...props}>
            {children}
          </ol>
        ),
        h1: ({ children, ...props }) => (
          <h1 className="text-xl font-bold text-text mt-4 mb-2" {...props}>{children}</h1>
        ),
        h2: ({ children, ...props }) => (
          <h2 className="text-lg font-semibold text-text mt-3 mb-2" {...props}>{children}</h2>
        ),
        h3: ({ children, ...props }) => (
          <h3 className="text-base font-semibold text-text mt-3 mb-1" {...props}>{children}</h3>
        ),
        p: ({ children, ...props }) => (
          <p className="my-2 leading-relaxed" {...props}>{children}</p>
        ),
        blockquote: ({ children, ...props }) => (
          <blockquote className="border-l-4 border-accent pl-4 my-2 text-text-sec italic" {...props}>
            {children}
          </blockquote>
        ),
        hr: (props) => (
          <hr className="my-4 border-border" {...props} />
        ),
        strong: ({ children, ...props }) => (
          <strong className="font-semibold text-text" {...props}>{children}</strong>
        ),
        em: ({ children, ...props }) => (
          <em className="italic text-text-sec" {...props}>{children}</em>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
