import { useState } from 'react'
import { api, CATEGORIES, inr } from '../api.js'

export default function SwipeAdvisor() {
  const [category, setCategory] = useState('groceries')
  const [amount, setAmount] = useState('2000')
  const [merchant, setMerchant] = useState('')
  const [ranked, setRanked] = useState(null)
  const [error, setError] = useState(null)

  const ask = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setRanked(await api.swipe({ category, amount: Number(amount), merchant: merchant || null }))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-semibold">Which card should I swipe?</h2>
      <form onSubmit={ask} className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Category</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}
                  className="rounded-md border border-slate-300 bg-white px-3 py-2">
            {CATEGORIES.map((c) => <option key={c} value={c}>{c.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Amount (₹)</span>
          <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)}
                 className="w-32 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-600">Merchant (optional)</span>
          <input value={merchant} onChange={(e) => setMerchant(e.target.value)}
                 placeholder="e.g. HPCL, Amazon"
                 className="w-44 rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">
          Rank my cards
        </button>
      </form>
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      {ranked && !ranked.length && (
        <p className="mt-4 text-sm text-slate-500">Add cards in the My Cards tab first.</p>
      )}
      {ranked?.map((r, i) => (
        <div key={r.card_id}
             className={`mt-4 rounded-xl border bg-white p-4 shadow-sm ${
               i === 0 ? 'border-emerald-400 ring-1 ring-emerald-200' : 'border-slate-200'}`}>
          <div className="flex items-baseline justify-between">
            <h3 className="font-semibold">
              {i === 0 && <span className="mr-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">BEST</span>}
              {r.display_name}
            </h3>
            <span className="text-lg font-bold">{inr(r.net_value_inr)}</span>
          </div>
          <ul className="mt-2 list-inside list-disc text-xs text-slate-600">
            {r.explanation.map((line, j) => <li key={j}>{line}</li>)}
          </ul>
        </div>
      ))}
    </div>
  )
}
