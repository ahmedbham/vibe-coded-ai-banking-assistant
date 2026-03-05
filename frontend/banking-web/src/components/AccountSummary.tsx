import { useEffect, useState } from 'react'
import { getAccountDetails, getPaymentMethods } from '../api'
import type { AccountDetails, PaymentMethod } from '../types'

interface Props {
  accountId: string
}

function AccountSummary({ accountId }: Props) {
  const [account, setAccount] = useState<AccountDetails | null>(null)
  const [methods, setMethods] = useState<PaymentMethod[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      getAccountDetails(accountId),
      getPaymentMethods(accountId),
    ])
      .then(([acct, pm]) => {
        if (!cancelled) {
          setAccount(acct)
          setMethods(pm)
        }
      })
      .catch(err => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [accountId])

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="h-10 bg-gray-200 rounded w-1/2 mb-4" />
        <div className="h-4 bg-gray-200 rounded w-2/3" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-md p-6 border border-red-200">
        <p className="text-red-600 text-sm" role="alert">{error}</p>
      </div>
    )
  }

  if (!account) return null

  return (
    <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
      <h2 className="text-lg font-semibold text-gray-700 mb-4">Account Summary</h2>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <p className="text-sm text-gray-500">Account Type</p>
          <p className="text-base font-medium text-gray-800 capitalize">{account.account_type}</p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Status</p>
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
            account.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}>
            {account.status}
          </span>
        </div>
        <div className="col-span-2">
          <p className="text-sm text-gray-500">Balance</p>
          <p className="text-3xl font-bold text-blue-700">
            {new Intl.NumberFormat('en-US', { style: 'currency', currency: account.currency }).format(account.balance)}
          </p>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-600 mb-2">Payment Methods</h3>
        {methods.length === 0 ? (
          <p className="text-sm text-gray-400">No payment methods on file.</p>
        ) : (
          <ul className="space-y-2">
            {methods.map(m => (
              <li key={m.payment_method_id} className="flex items-center gap-3 text-sm text-gray-700">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-50 text-blue-600 text-xs font-bold">
                  {m.brand.slice(0, 2).toUpperCase()}
                </span>
                <span className="capitalize">{m.type.replace('_', ' ')}</span>
                <span className="text-gray-400">•••• {m.last4}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default AccountSummary
