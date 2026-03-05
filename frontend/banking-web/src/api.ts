import type {
  AccountDetails,
  Beneficiary,
  PaymentMethod,
  PaymentRequest,
  PaymentResponse,
  Transaction,
} from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const ACCOUNT_SERVICE_URL = import.meta.env.VITE_ACCOUNT_SERVICE_URL ?? 'http://localhost:8001'
const PAYMENTS_SERVICE_URL = import.meta.env.VITE_PAYMENTS_SERVICE_URL ?? 'http://localhost:8002'
const TRANSACTIONS_SERVICE_URL = import.meta.env.VITE_TRANSACTIONS_SERVICE_URL ?? 'http://localhost:8003'

// Chat API (streaming)
export async function sendMessage(
  message: string,
  sessionId: string,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Server error: ${response.status} ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    onChunk(decoder.decode(value, { stream: true }))
  }
}

// Account Service
export async function getAccountDetails(accountId: string): Promise<AccountDetails> {
  const res = await fetch(`${ACCOUNT_SERVICE_URL}/accounts/${accountId}/details`)
  if (!res.ok) throw new Error(`Failed to fetch account details: ${res.status}`)
  return res.json()
}

export async function getPaymentMethods(accountId: string): Promise<PaymentMethod[]> {
  const res = await fetch(`${ACCOUNT_SERVICE_URL}/accounts/${accountId}/payment-methods`)
  if (!res.ok) throw new Error(`Failed to fetch payment methods: ${res.status}`)
  return res.json()
}

export async function getBeneficiaries(accountId: string): Promise<Beneficiary[]> {
  const res = await fetch(`${ACCOUNT_SERVICE_URL}/accounts/${accountId}/beneficiaries`)
  if (!res.ok) throw new Error(`Failed to fetch beneficiaries: ${res.status}`)
  return res.json()
}

// Transactions Service
export async function searchTransactions(query: string = ''): Promise<Transaction[]> {
  const params = query ? `?query=${encodeURIComponent(query)}` : ''
  const res = await fetch(`${TRANSACTIONS_SERVICE_URL}/transactions/search${params}`)
  if (!res.ok) throw new Error(`Failed to fetch transactions: ${res.status}`)
  return res.json()
}

// Payments Service
export async function submitPayment(payment: PaymentRequest): Promise<PaymentResponse> {
  const res = await fetch(`${PAYMENTS_SERVICE_URL}/payments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payment),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Payment failed: ${res.status}`)
  }
  return res.json()
}
