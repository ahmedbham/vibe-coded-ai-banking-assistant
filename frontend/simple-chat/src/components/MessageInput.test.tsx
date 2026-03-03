import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageInput from './MessageInput'

describe('MessageInput', () => {
  it('calls onSend when Send button is clicked', async () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Hello')
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(onSend).toHaveBeenCalledWith('Hello')
  })

  it('calls onSend on Enter key press', async () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Test{Enter}')
    expect(onSend).toHaveBeenCalledWith('Test')
  })

  it('does not call onSend with empty input', () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables button and textarea when disabled prop is true', () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={true} />)
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})
