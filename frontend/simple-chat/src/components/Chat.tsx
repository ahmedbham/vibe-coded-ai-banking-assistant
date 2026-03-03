import { useState, useRef, useCallback } from 'react'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import { sendMessage } from '../api'
import type { Message } from '../types'

function generateId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2)
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sessionId = useRef<string>(generateId())

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)
    setError(null)

    const assistantId = generateId()
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '' },
    ])

    try {
      await sendMessage(
        text.trim(),
        sessionId.current,
        (chunk) => {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: m.content + chunk }
                : m,
            ),
          )
        },
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setError(msg)
      setMessages(prev => prev.filter(m => m.id !== assistantId))
    } finally {
      setIsLoading(false)
    }
  }, [isLoading])

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-md overflow-hidden border border-gray-200">
      <MessageList messages={messages} isLoading={isLoading} />
      {error && (
        <div
          role="alert"
          className="px-4 py-2 text-sm text-red-700 bg-red-50 border-t border-red-200"
        >
          {error}
        </div>
      )}
      <MessageInput onSend={handleSend} disabled={isLoading} />
    </div>
  )
}

export default Chat
