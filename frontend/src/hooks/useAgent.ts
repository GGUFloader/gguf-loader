import { useCallback, useRef, useState } from 'react'
import { useChatStore } from '../stores/chatStore'

interface UseAgentOptions {
  onToken?: (token: string) => void
  onToolCall?: (call: { name: string; args: any; call_id: string }) => void
  onApproval?: (approval: { call_id: string; tool: string; risk: string }) => void
  onComplete?: (result: { content: string; tokens_used: number; duration_ms: number }) => void
  onError?: (error: string) => void
}

interface UseAgentReturn {
  sendMessage: (content: string, options?: { system_prompt?: string; session_id?: string }) => void
  stopGeneration: () => void
  approveToolCall: (callId: string, approved: boolean) => void
  isStreaming: boolean
  status: 'idle' | 'connecting' | 'streaming' | 'tool_call' | 'awaiting_approval'
}

export function useAgent(options: UseAgentOptions = {}): UseAgentReturn {
  const [isStreaming, setIsStreaming] = useState(false)
  const [status, setStatus] = useState<UseAgentReturn['status']>('idle')
  const wsRef = useRef<WebSocket | null>(null)
  const { addMessage, appendToMessage, setThinking } = useChatStore()

  const sendMessage = useCallback(
    (content: string, opts?: { system_prompt?: string; session_id?: string }) => {
      if (isStreaming) return

      // Add user message
      addMessage({
        id: `user_${Date.now()}`,
        role: 'user',
        content,
        timestamp: Date.now(),
      })

      // Create assistant message placeholder
      const msgId = `assistant_${Date.now()}`
      addMessage({
        id: msgId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      })

      setIsStreaming(true)
      setStatus('connecting')

      // Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('streaming')
        ws.send(
          JSON.stringify({
            type: 'chat',
            message: content,
            session_id: opts?.session_id,
            system_prompt: opts?.system_prompt,
          })
        )
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'token':
            appendToMessage(msgId, data.content)
            options.onToken?.(data.content)
            break

          case 'reasoning':
            setThinking(msgId, data.content)
            break

          case 'tool_call':
            setStatus('tool_call')
            appendToMessage(msgId, `\n\n🔧 Calling ${data.name}...\n`)
            options.onToolCall?.(data)
            break

          case 'approval_needed':
            setStatus('awaiting_approval')
            options.onApproval?.(data)
            break

          case 'message_complete':
            setIsStreaming(false)
            setStatus('idle')
            options.onComplete?.(data)
            ws.close()
            break

          case 'error':
            appendToMessage(msgId, `\n\n❌ Error: ${data.message}`)
            setIsStreaming(false)
            setStatus('idle')
            options.onError?.(data.message)
            ws.close()
            break
        }
      }

      ws.onerror = () => {
        appendToMessage(msgId, '\n\n❌ Connection error')
        setIsStreaming(false)
        setStatus('idle')
        options.onError?.('WebSocket connection failed')
      }

      ws.onclose = () => {
        setIsStreaming(false)
        setStatus('idle')
      }
    },
    [isStreaming, addMessage, appendToMessage, setThinking, options]
  )

  const stopGeneration = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsStreaming(false)
    setStatus('idle')
  }, [])

  const approveToolCall = useCallback(
    (callId: string, approved: boolean) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'approve',
            call_id: callId,
            approved,
          })
        )
        setStatus('streaming')
      }
    },
    []
  )

  return { sendMessage, stopGeneration, approveToolCall, isStreaming, status }
}
