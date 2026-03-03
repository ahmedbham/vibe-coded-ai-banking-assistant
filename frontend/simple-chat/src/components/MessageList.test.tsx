import { render, screen } from '@testing-library/react'
import MessageList from './MessageList'
import type { Message } from '../types'

describe('MessageList', () => {
  it('shows empty state when no messages', () => {
    render(<MessageList messages={[]} isLoading={false} />)
    expect(screen.getByText(/send a message/i)).toBeInTheDocument()
  })

  it('renders all messages', () => {
    const messages: Message[] = [
      { id: '1', role: 'user', content: 'Hello' },
      { id: '2', role: 'assistant', content: 'Hi' },
    ]
    render(<MessageList messages={messages} isLoading={false} />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('Hi')).toBeInTheDocument()
  })
})
