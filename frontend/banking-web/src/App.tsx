import { useState } from 'react'
import AccountSummary from './components/AccountSummary'
import TransactionTable from './components/TransactionTable'
import PaymentForm from './components/PaymentForm'
import ChatPanel from './components/ChatPanel'

type TabId = 'dashboard' | 'chat'

const ACCOUNT_ID = 'ACC001'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-blue-700">Banking Dashboard</h1>
          <nav className="flex gap-1">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'chat'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Chat
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'dashboard' ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column: account + payment */}
            <div className="space-y-6">
              <AccountSummary accountId={ACCOUNT_ID} />
              <PaymentForm accountId={ACCOUNT_ID} />
            </div>

            {/* Right column: transactions */}
            <div className="lg:col-span-2">
              <TransactionTable />
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto h-[calc(100vh-8rem)]">
            <ChatPanel />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
