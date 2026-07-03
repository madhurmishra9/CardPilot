import { useState } from 'react'
import Dashboard from './pages/Dashboard.jsx'
import SwipeAdvisor from './pages/SwipeAdvisor.jsx'
import Redemption from './pages/Redemption.jsx'
import Transactions from './pages/Transactions.jsx'
import Cards from './pages/Cards.jsx'

const TABS = [
  { key: 'dashboard', label: 'Dashboard', el: Dashboard },
  { key: 'swipe', label: 'Swipe Advisor', el: SwipeAdvisor },
  { key: 'redeem', label: 'Redemption', el: Redemption },
  { key: 'txns', label: 'Transactions', el: Transactions },
  { key: 'cards', label: 'My Cards', el: Cards },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const Active = TABS.find((t) => t.key === tab).el

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-5xl items-center gap-8 px-4 py-3">
          <h1 className="text-lg font-bold tracking-tight">
            Card<span className="text-amber-400">Pilot</span>
          </h1>
          <nav className="flex gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`rounded-md px-3 py-1.5 text-sm whitespace-nowrap ${
                  tab === t.key
                    ? 'bg-amber-400 font-semibold text-slate-900'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Active />
      </main>
      <footer className="mx-auto max-w-5xl px-4 pb-6 text-xs text-slate-400">
        Local-first — your financial data never leaves this machine. Card rules are
        seed data; verify against the issuer's MITC.
      </footer>
    </div>
  )
}
