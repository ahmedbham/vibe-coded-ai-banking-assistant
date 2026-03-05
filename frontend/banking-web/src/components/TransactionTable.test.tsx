import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TransactionTable from './TransactionTable'
import * as api from '../api'
import type { Transaction } from '../types'

vi.mock('../api')

const mockTransactions: Transaction[] = [
  {
    transaction_id: 'TXN001',
    account_id: 'ACC001',
    recipient_id: 'RCP001',
    amount: 4.5,
    currency: 'USD',
    description: 'coffee shop',
    category: 'food_and_drink',
    status: 'completed',
    timestamp: '2024-01-15T08:30:00Z',
  },
  {
    transaction_id: 'TXN002',
    account_id: 'ACC001',
    recipient_id: 'RCP002',
    amount: 120.0,
    currency: 'USD',
    description: 'electricity bill payment',
    category: 'utilities',
    status: 'completed',
    timestamp: '2024-01-14T17:00:00Z',
  },
  {
    transaction_id: 'TXN003',
    account_id: 'ACC002',
    recipient_id: 'RCP001',
    amount: 8.75,
    currency: 'USD',
    description: 'coffee and pastry',
    category: 'food_and_drink',
    status: 'completed',
    timestamp: '2024-01-15T09:00:00Z',
  },
]

describe('TransactionTable', () => {
  beforeEach(() => {
    vi.mocked(api.searchTransactions).mockResolvedValue(mockTransactions)
  })

  it('renders transaction rows after loading', async () => {
    render(<TransactionTable />)

    await waitFor(() => {
      expect(screen.getByText('coffee shop')).toBeInTheDocument()
      expect(screen.getByText('electricity bill payment')).toBeInTheDocument()
    })
  })

  it('renders the heading', async () => {
    render(<TransactionTable />)

    await waitFor(() => {
      expect(screen.getByText('Transaction History')).toBeInTheDocument()
    })
  })

  it('has a search input', async () => {
    render(<TransactionTable />)
    expect(screen.getByLabelText('Search transactions')).toBeInTheDocument()
  })

  it('calls searchTransactions with search text', async () => {
    render(<TransactionTable />)

    const input = screen.getByLabelText('Search transactions')
    await userEvent.clear(input)
    await userEvent.type(input, 'coffee')

    await waitFor(() => {
      expect(api.searchTransactions).toHaveBeenCalledWith('coffee')
    })
  })

  it('shows error on failure', async () => {
    vi.mocked(api.searchTransactions).mockRejectedValue(new Error('Network issue'))
    render(<TransactionTable />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network issue')
    })
  })
})
