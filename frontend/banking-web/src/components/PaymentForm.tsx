import { useEffect, useState, type FormEvent, type ChangeEvent } from 'react'
import { getBeneficiaries, submitPayment } from '../api'
import type { Beneficiary, PaymentResponse } from '../types'

interface Props {
  accountId: string
}

function PaymentForm({ accountId }: Props) {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [beneficiaryId, setBeneficiaryId] = useState('')
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [reference, setReference] = useState('')
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<PaymentResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingBeneficiaries, setLoadingBeneficiaries] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoadingBeneficiaries(true)

    getBeneficiaries(accountId)
      .then(data => {
        if (!cancelled) setBeneficiaries(data)
      })
      .catch(() => {
        if (!cancelled) setBeneficiaries([])
      })
      .finally(() => {
        if (!cancelled) setLoadingBeneficiaries(false)
      })

    return () => { cancelled = true }
  }, [accountId])

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setInvoiceFile(e.target.files?.[0] ?? null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setResult(null)

    try {
      const response = await submitPayment({
        account_id: accountId,
        beneficiary_id: beneficiaryId,
        amount: parseFloat(amount),
        currency,
        reference,
      })
      setResult(response)
      // Reset form on success
      setBeneficiaryId('')
      setAmount('')
      setReference('')
      setInvoiceFile(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Payment failed')
    } finally {
      setSubmitting(false)
    }
  }

  const isValid = beneficiaryId && parseFloat(amount) > 0 && reference.trim()

  return (
    <div className="bg-white rounded-xl shadow-md border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-700 mb-4">Make a Payment</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="beneficiary" className="block text-sm font-medium text-gray-600 mb-1">
            Beneficiary
          </label>
          <select
            id="beneficiary"
            value={beneficiaryId}
            onChange={e => setBeneficiaryId(e.target.value)}
            disabled={loadingBeneficiaries || submitting}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
          >
            <option value="">Select a beneficiary…</option>
            {beneficiaries.map(b => (
              <option key={b.beneficiary_id} value={b.beneficiary_id}>
                {b.name} – {b.bank} (•••{b.account_number.slice(-4)})
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="amount" className="block text-sm font-medium text-gray-600 mb-1">
              Amount
            </label>
            <input
              id="amount"
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              disabled={submitting}
              placeholder="0.00"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
            />
          </div>
          <div>
            <label htmlFor="currency" className="block text-sm font-medium text-gray-600 mb-1">
              Currency
            </label>
            <select
              id="currency"
              value={currency}
              onChange={e => setCurrency(e.target.value)}
              disabled={submitting}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="reference" className="block text-sm font-medium text-gray-600 mb-1">
            Reference
          </label>
          <input
            id="reference"
            type="text"
            value={reference}
            onChange={e => setReference(e.target.value)}
            disabled={submitting}
            placeholder="Invoice #, description, etc."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
          />
        </div>

        <div>
          <label htmlFor="invoice" className="block text-sm font-medium text-gray-600 mb-1">
            Invoice Upload <span className="text-gray-400">(optional)</span>
          </label>
          <input
            id="invoice"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={handleFileChange}
            disabled={submitting}
            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {invoiceFile && (
            <p className="mt-1 text-xs text-gray-500">Selected: {invoiceFile.name}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={!isValid || submitting}
          className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? 'Processing…' : 'Submit Payment'}
        </button>
      </form>

      {result && (
        <div className="mt-4 p-4 bg-green-50 rounded-lg border border-green-200" role="status">
          <p className="text-sm font-medium text-green-700">Payment Confirmed</p>
          <p className="text-xs text-green-600 mt-1">
            Confirmation: {result.confirmation_id}
          </p>
          <p className="text-xs text-green-600">
            Amount: {new Intl.NumberFormat('en-US', { style: 'currency', currency: result.currency }).format(result.amount)}
          </p>
        </div>
      )}

      {error && (
        <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200" role="alert">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  )
}

export default PaymentForm
