import ReactMarkdown from 'react-markdown'
import { Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface Props {
  content: string
}

function CodeBlock({ className, children, ...props }: any) {
  const [copied, setCopied] = useState(false)
  const match = /language-(\w+)/.exec(className || '')
  const language = match?.[1] || ''
  const code = String(children).replace(/\n$/, '')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Inline code
  if (!language && !code.includes('\n')) {
    return (
      <code className="bg-bg/50 px-1.5 py-0.5 rounded text-sm text-accent" {...props}>
        {children}
      </code>
    )
  }

  // Code block
  return (
    <div className="relative my-3 group">
      <div className="flex items-center justify-between px-4 py-1.5 bg-elevated border border-border rounded-t-lg">
        <span className="text-xs text-text-muted font-mono">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-sec transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className="bg-bg border border-t-0 border-border rounded-b-lg p-4 overflow-x-auto">
        <code className="text-sm font-mono text-text leading-relaxed" {...props}>
          {children}
        </code>
      </pre>
    </div>
  )
}

export function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
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
          <div className="overflow-x-auto my-3">
            <table className="w-full text-sm border-collapse" {...props}>
              {children}
            </table>
          </div>
        ),
        th: ({ children, ...props }) => (
          <th className="px-3 py-2 text-left bg-elevated border border-border font-medium text-text-sec" {...props}>
            {children}
          </th>
        ),
        td: ({ children, ...props }) => (
          <td className="px-3 py-2 border border-border text-text" {...props}>
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
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
