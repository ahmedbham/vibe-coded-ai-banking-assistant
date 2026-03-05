import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MessageInput from './MessageInput'

describe('MessageInput', () => {
  it('calls onSend when button is clicked', async () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Hello')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(onSend).toHaveBeenCalledWith('Hello')
  })

  it('calls onSend on Enter key', async () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'Hello{enter}')

    expect(onSend).toHaveBeenCalledWith('Hello')
  })

  it('does not send empty messages', async () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={false} />)

    await userEvent.click(screen.getByRole('button', { name: /send/i }))

    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables input when disabled prop is true', () => {
    const onSend = vi.fn()
    render(<MessageInput onSend={onSend} disabled={true} />)

    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })
})
