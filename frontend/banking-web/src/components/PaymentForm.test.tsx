import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PaymentForm from './PaymentForm'
import * as api from '../api'
import type { Beneficiary, PaymentResponse } from '../types'

vi.mock('../api')

const mockBeneficiaries: Beneficiary[] = [
  { beneficiary_id: 'BEN001', name: 'Alice Johnson', account_number: '987654321', bank: 'Chase' },
  { beneficiary_id: 'BEN002', name: 'Bob Williams', account_number: '123456789', bank: 'Wells Fargo' },
]

const mockPaymentResponse: PaymentResponse = {
  confirmation_id: 'CONF-123',
  account_id: 'ACC001',
  beneficiary_id: 'BEN001',
  amount: 100,
  currency: 'USD',
  reference: 'INV-001',
  status: 'confirmed',
  timestamp: '2024-01-15T10:00:00Z',
}

describe('PaymentForm', () => {
  beforeEach(() => {
    vi.mocked(api.getBeneficiaries).mockResolvedValue(mockBeneficiaries)
    vi.mocked(api.submitPayment).mockResolvedValue(mockPaymentResponse)
  })

  it('renders form fields', async () => {
    render(<PaymentForm accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByLabelText(/beneficiary/i)).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/amount/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/reference/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/invoice/i)).toBeInTheDocument()
  })

  it('loads and displays beneficiaries', async () => {
    render(<PaymentForm accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText(/Alice Johnson/)).toBeInTheDocument()
      expect(screen.getByText(/Bob Williams/)).toBeInTheDocument()
    })
  })

  it('submits payment and shows confirmation', async () => {
    render(<PaymentForm accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText(/Alice Johnson/)).toBeInTheDocument()
    })

    await userEvent.selectOptions(screen.getByLabelText(/beneficiary/i), 'BEN001')
    await userEvent.type(screen.getByLabelText(/amount/i), '100')
    await userEvent.type(screen.getByLabelText(/reference/i), 'INV-001')
    await userEvent.click(screen.getByRole('button', { name: /submit payment/i }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Payment Confirmed')
      expect(screen.getByText(/CONF-123/)).toBeInTheDocument()
    })
  })

  it('shows error on payment failure', async () => {
    vi.mocked(api.submitPayment).mockRejectedValue(new Error('Insufficient funds'))

    render(<PaymentForm accountId="ACC001" />)

    await waitFor(() => {
      expect(screen.getByText(/Alice Johnson/)).toBeInTheDocument()
    })

    await userEvent.selectOptions(screen.getByLabelText(/beneficiary/i), 'BEN001')
    await userEvent.type(screen.getByLabelText(/amount/i), '100')
    await userEvent.type(screen.getByLabelText(/reference/i), 'INV-001')
    await userEvent.click(screen.getByRole('button', { name: /submit payment/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Insufficient funds')
    })
  })
})
