import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import type { Message } from '../types'

interface Props {
  messages: Message[]
  isLoading: boolean
}

function MessageList({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.length === 0 && !isLoading && (
        <p className="text-center text-gray-400 text-sm mt-8">
          Send a message to get started.
        </p>
      )}
      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {isLoading && messages[messages.length - 1]?.role === 'user' && (
        <div className="flex justify-start">
          <div className="bg-gray-100 rounded-lg px-4 py-2 text-sm text-gray-500 animate-pulse">
            Thinking…
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

export default MessageList
