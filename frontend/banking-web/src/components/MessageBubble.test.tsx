import { render, screen } from '@testing-library/react'
import MessageBubble from './MessageBubble'
import type { Message } from '../types'

describe('MessageBubble', () => {
  it('renders user message on the right', () => {
    const msg: Message = { id: '1', role: 'user', content: 'Hello' }
    const { container } = render(<MessageBubble message={msg} />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('justify-end')
  })

  it('renders assistant message on the left', () => {
    const msg: Message = { id: '2', role: 'assistant', content: 'Hi there' }
    const { container } = render(<MessageBubble message={msg} />)
    expect(screen.getByText('Hi there')).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('justify-start')
  })

  it('shows a typing cursor for empty assistant message', () => {
    const msg: Message = { id: '3', role: 'assistant', content: '' }
    render(<MessageBubble message={msg} />)
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })
})
