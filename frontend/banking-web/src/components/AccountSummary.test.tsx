import { render, screen, waitFor } from '@testing-library/react'
import AccountSummary from './AccountSummary'
import * as api from '../api'
import type { AccountDetails, PaymentMethod } from '../types'

vi.mock('../api')

const mockAccount: AccountDetails = {
  account_id: 'ACC001',
  account_type: 'checking',
  balance: 2500.0,
  currency: 'USD',
  status: 'active',
}

const mockMethods: PaymentMethod[] = [
  { payment_method_id: 'PM001', type: 'debit_card', last4: '1234', brand: 'Visa' },
  { payment_method_id: 'PM002', type: 'credit_card', last4: '5678', brand: 'Mastercard' },
]

describe('AccountSummary', () => {
  beforeEach(() => {
    vi.mocked(api.getAccountDetails).mockResolvedValue(mockAccount)
    vi.mocked(api.getPaymentMethods).mockResolvedValue(mockMethods)
  })

  it('displays account balance after loading', async () => {
    render(<AccountSummary accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText('$2,500.00')).toBeInTheDocument()
    })
  })

  it('displays account type and status', async () => {
    render(<AccountSummary accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText('checking')).toBeInTheDocument()
      expect(screen.getByText('active')).toBeInTheDocument()
    })
  })

  it('displays payment methods', async () => {
    render(<AccountSummary accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText(/1234/)).toBeInTheDocument()
      expect(screen.getByText(/5678/)).toBeInTheDocument()
    })
  })

  it('shows error on failure', async () => {
    vi.mocked(api.getAccountDetails).mockRejectedValue(new Error('Failed'))
    render(<AccountSummary accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Failed')
    })
  })
})
