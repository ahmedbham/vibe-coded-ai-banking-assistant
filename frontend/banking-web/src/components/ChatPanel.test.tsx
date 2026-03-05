import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPanel from './ChatPanel'
import * as api from '../api'

vi.mock('../api')

describe('ChatPanel', () => {
  it('renders initial empty state', () => {
    render(<ChatPanel />)
    expect(screen.getByText(/send a message/i)).toBeInTheDocument()
  })

  it('renders chat assistant heading', () => {
    render(<ChatPanel />)
    expect(screen.getByText('Chat Assistant')).toBeInTheDocument()
  })

  it('sends a message and displays the response', async () => {
    vi.mocked(api.sendMessage).mockImplementation(async (_msg, _sid, onChunk) => {
      onChunk('Hello from assistant')
    })

    render(<ChatPanel />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'What is my balance?')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByText('What is my balance?')).toBeInTheDocument()
      expect(screen.getByText('Hello from assistant')).toBeInTheDocument()
    })
  })

  it('shows error message when sendMessage throws', async () => {
    vi.mocked(api.sendMessage).mockRejectedValue(new Error('Network error'))

    render(<ChatPanel />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Test message')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network error')
    })
  })
})
