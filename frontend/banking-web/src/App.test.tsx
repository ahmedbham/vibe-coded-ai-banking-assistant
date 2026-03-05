import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import * as api from './api'

vi.mock('./api')

describe('App', () => {
  beforeEach(() => {
    vi.mocked(api.getAccountDetails).mockResolvedValue({
      account_id: 'ACC001',
      account_type: 'checking',
      balance: 2500,
      currency: 'USD',
      status: 'active',
    })
    vi.mocked(api.getPaymentMethods).mockResolvedValue([])
    vi.mocked(api.getBeneficiaries).mockResolvedValue([])
    vi.mocked(api.searchTransactions).mockResolvedValue([])
  })

  it('renders the dashboard heading', () => {
    render(<App />)
    expect(screen.getByText('Banking Dashboard')).toBeInTheDocument()
  })

  it('shows dashboard tab by default', () => {
    render(<App />)
    expect(screen.getByText('Account Summary')).toBeInTheDocument()
    expect(screen.getByText('Transaction History')).toBeInTheDocument()
    expect(screen.getByText('Make a Payment')).toBeInTheDocument()
  })

  it('switches to chat tab', async () => {
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: /chat/i }))
    expect(screen.getByText('Chat Assistant')).toBeInTheDocument()
  })

  it('switches back to dashboard tab', async () => {
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: /chat/i }))
    await userEvent.click(screen.getByRole('button', { name: /dashboard/i }))

    expect(screen.getByText('Account Summary')).toBeInTheDocument()
  })
})
